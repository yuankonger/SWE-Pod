"""One episode: a team of owner agents (or one solo agent) works a task in a private copy of the company.

Turns go round-robin. A turn is one model call plus the tool calls it makes. Every call draws on one token budget
shared by the whole team. The episode ends when every agent has submitted, the budget runs out, or the hard stop on
model calls is reached. Everything that happens is appended to an event log (JSON lines).
"""
import json
import os
import shutil
import time

from .model import total_tokens
from .tools import Sandbox, tool_definitions

SERVICES = ("storefront", "orders", "billing", "notifications")
CONDITIONS = ("team", "team_no_messaging", "solo")
MAX_IDLE_TURNS = 3

COMPANY = """SeedCo is a subscription retailer run as four services, each with one owner:
- storefront (TypeScript on Node.js): the customer-facing API; calls orders and billing.
- orders (Java): carts, orders and the order state machine; calls billing and publishes order events.
- billing (C#): prices, tax, payments and invoices; reads order events and publishes invoice events.
- notifications (Python): reads order and billing events and sends emails.
Each service publishes its contracts under `contracts/` and keeps copies of the contracts it reads under `pinned/`.
A copy is only a copy: the publishing owner's file and code are the truth, and an owner's `NOTES.md` holds what
only that owner knows."""

OWNER_RULES = """You are the owner of the `{service}` service. You can read and change only the files of your own
service. You cannot see any other service's code or notes.{channel}

How you work:
- You act in turns, alternating with the other owners. In a turn you may call several tools.
- All owners draw on one shared token budget. Each turn update tells you what is left. Spend it on what matters.
- `run_tests` runs your own service's tests only. A hidden end-to-end suite, which you cannot run, decides whether
  the change works across all four services.
- When your part is finished, call `submit`. If a message reaches you later you get another turn."""

SOLO_RULES = """You own all four services and can read and change every file under the services directory.

How you work:
- You act in turns. In a turn you may call several tools.
- You have one token budget. Each turn update tells you what is left.
- `run_tests` runs one service's own tests. A hidden end-to-end suite, which you cannot run, decides whether the
  change works across all four services.
- When the change is finished, call `submit`."""

WITH_MESSAGING = """
You can reach the other owners with `send_message`. They cannot see your files either, so anything they need from
you has to be said, and anything you need from them has to be asked for."""
NO_MESSAGING = """
There is no way to contact the other owners in this change. Work from what your own service's files tell you."""


class Agent:
    def __init__(self, name, services, sandbox, system, tools, brief):
        self.name, self.services, self.sandbox = name, services, sandbox
        self.system, self.tools, self.brief = system, tools, brief
        self.messages = []       # the conversation sent to the model
        self.pending = []        # tool results owed to the model at this agent's next turn
        self.inbox = []
        self.submitted = False
        self.summary = None
        self.calls = 0
        self.idle = 0
        self.tokens = 0


def prepare_workspace(repo_root: str, task_dir: str, dest: str) -> str:
    """A private copy of the company with the task's starting state applied. Returns its path."""
    if os.path.exists(dest):
        shutil.rmtree(dest)
    for part in ("services", "platform"):
        shutil.copytree(os.path.join(repo_root, part), os.path.join(dest, part),
                        ignore=shutil.ignore_patterns("bin", "obj", "__pycache__"))
    overlay = os.path.join(task_dir, "overlay")
    if os.path.isdir(overlay):
        shutil.copytree(overlay, dest, dirs_exist_ok=True)
    return dest


def build_agents(task: dict, condition: str, workspace: str, build_base: str) -> list:
    services_dir = os.path.join(workspace, "services")
    if condition == "solo":
        names = list(SERVICES)
        system = COMPANY + "\n\n" + SOLO_RULES
        return [Agent("solo", names, Sandbox(services_dir, names, build_base), system,
                      tool_definitions(names, [], False), task["solo_brief"])]
    messaging = condition == "team"
    agents = []
    for s in SERVICES:
        system = COMPANY + "\n\n" + OWNER_RULES.format(service=s, channel=WITH_MESSAGING if messaging else NO_MESSAGING)
        agents.append(Agent(s, [s], Sandbox(os.path.join(services_dir, s), [s], build_base), system,
                            tool_definitions([s], [x for x in SERVICES if x != s], messaging), task["briefs"][s]))
    return agents


def run_episode(task: dict, condition: str, model, workspace: str, log_path: str, budget_tokens: int,
                max_model_calls: int = 400, build_base: str = None) -> dict:
    """Runs to the end and returns a summary. The workspace is left as the agents made it, ready for scoring."""
    if condition not in CONDITIONS:
        raise ValueError("condition must be one of {}".format(CONDITIONS))
    build_base = build_base or os.path.join(os.path.dirname(workspace), "build")
    agents = build_agents(task, condition, workspace, build_base)
    by_name = {a.name: a for a in agents}
    used = {"tokens": 0, "calls": 0, "messages": 0}
    usage_total = {}
    started = time.time()
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    log_file = open(log_path, "w")

    def log(kind, **fields):
        log_file.write(json.dumps(dict(kind=kind, t=round(time.time() - started, 2), **fields), default=str) + "\n")
        log_file.flush()

    log("episode_start", task=task["id"], condition=condition, budget_tokens=budget_tokens,
        max_model_calls=max_model_calls, agents=[a.name for a in agents], model=getattr(model, "model", "scripted"))

    def update_text(agent) -> str:
        left = max(0, budget_tokens - used["tokens"])
        parts = []
        if agent.calls == 0:
            parts.append(agent.brief)
        for m in agent.inbox:
            parts.append("Message from {}:\n{}".format(m["from"], m["text"]))
        agent.inbox = []
        parts.append("[turn update] Shared budget left: {:,} of {:,} tokens.".format(left, budget_tokens))
        if agent.idle:
            parts.append("You made no tool call last turn. Keep working, or call `submit` if your part is done.")
        return "\n\n".join(parts)

    def take_turn(agent):
        agent.messages.append({"role": "user",
                               "content": agent.pending + [{"type": "text", "text": update_text(agent)}]})
        agent.pending = []
        reply = model.call(agent.name, agent.system, agent.tools, agent.messages)
        agent.messages.append({"role": "assistant", "content": reply.content})
        agent.calls += 1
        spent = total_tokens(reply.usage)
        agent.tokens += spent
        used["tokens"] += spent
        used["calls"] += 1
        for k, v in reply.usage.items():
            usage_total[k] = usage_total.get(k, 0) + v
        log("model_call", agent=agent.name, stop_reason=reply.stop_reason, usage=reply.usage,
            budget_left=budget_tokens - used["tokens"], content=reply.logged)
        agent.idle = 0 if reply.tool_uses else agent.idle + 1
        for use in reply.tool_uses:
            name, args = use["name"], use["input"] if isinstance(use["input"], dict) else {}
            if name == "send_message" and any(t["name"] == "send_message" for t in agent.tools):
                to = by_name.get(args.get("to"))
                if to is None or to is agent or not args.get("text"):
                    result = "ERROR: `to` must be another owner and `text` must not be empty"
                else:
                    to.inbox.append({"from": agent.name, "text": args["text"]})
                    to.submitted = False
                    result = "delivered to {}".format(to.name)
                    used["messages"] += 1
                    log("message", sender=agent.name, to=to.name, text=args["text"])
            elif name == "submit":
                agent.submitted, agent.summary = True, args.get("summary", "")
                result = "submitted"
                log("submit", agent=agent.name, summary=agent.summary)
            else:
                result = agent.sandbox.call(name, args)
                log("tool", agent=agent.name, name=name, input=args, result=result[:4000])
            agent.pending.append({"type": "tool_result", "tool_use_id": use["id"], "content": result,
                                  **({"is_error": True} if result.startswith("ERROR:") else {})})
        if agent.idle >= MAX_IDLE_TURNS and not agent.submitted:
            agent.submitted, agent.summary = True, "(stopped: no tool call in {} turns)".format(MAX_IDLE_TURNS)
            log("idle_stop", agent=agent.name)

    end = None
    error = None
    try:
        while end is None:
            active = [a for a in agents if not a.submitted or a.inbox]
            if not active:
                end = "all_submitted"
                break
            for agent in active:
                if used["tokens"] >= budget_tokens:
                    end = "budget_exhausted"
                    break
                if used["calls"] >= max_model_calls:
                    end = "hard_stop"
                    break
                take_turn(agent)
    except Exception as exc:  # a model or harness failure: the episode is invalid, never a score
        end, error = "error", "{}: {}".format(type(exc).__name__, exc)
    summary = {
        "task": task["id"], "condition": condition, "end": end, "error": error, "valid": error is None,
        "budget_tokens": budget_tokens, "tokens_used": used["tokens"], "model_calls": used["calls"],
        "usage": usage_total, "wall_seconds": round(time.time() - started, 1),
        "agents": {a.name: {"calls": a.calls, "tokens": a.tokens, "submitted": a.submitted, "summary": a.summary}
                   for a in agents},
        "messages_sent": used["messages"],
    }
    log("episode_end", **summary)
    log_file.close()
    return summary

"""Trajectories in ATIF, the Agent Trajectory Interchange Format Harbor uses (schema: harbor.models.trajectories).

A run's event log (`events.jsonl`) holds everything every agent was told, said and did. This turns it into one
ATIF document per agent, `runs/<run-id>/trajectories/<agent>.json`:

    system step   the agent's system prompt
    user step     what it was told at the start of a turn: the brief, messages from other agents, the budget left
    agent step    one model call: its text, its reasoning, its tool calls, what each tool returned, tokens and cost

An agent the lead started is a trajectory of its own; the lead's `spawn_agent` observation points at it.

    python3 -m kernel.atif runs/<run-id>          # (re)writes the trajectories of a finished run

Logs written before the kernel recorded system prompts and turn texts convert too, without those steps.
"""
import datetime
import json
import os
import sys

SCHEMA_VERSION = "ATIF-v1.8"
KERNEL_VERSION = "0.3"


def _stamp(started_at, seconds):
    if not started_at:
        return None
    start = datetime.datetime.strptime(started_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    return (start + datetime.timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def convert(events: list, run_id: str) -> dict:
    """{agent name: ATIF trajectory} for one run's events."""
    start = next((e for e in events if e["kind"] == "episode_start"), {})
    model = start.get("model")
    agents, order = {}, []

    def of(name):
        if name not in agents:
            order.append(name)
            agents[name] = {"steps": [], "tools": None, "directories": None, "open": None,
                            "totals": {"prompt": 0, "completion": 0, "cached": 0, "cost": 0.0}}
        return agents[name]

    def add(agent, step):
        step["step_id"] = len(agent["steps"]) + 1
        agent["steps"].append(step)
        return step

    for e in events:
        kind, when = e["kind"], _stamp(start.get("started_at"), e.get("t", 0))
        if kind == "agent_start":
            a = of(e["agent"])
            a["tools"], a["directories"] = e.get("tools"), e.get("directories")
            add(a, {"timestamp": when, "source": "system", "message": e["system"]})
        elif kind == "turn":
            add(of(e["agent"]), {"timestamp": when, "source": "user", "message": e["text"]})
        elif kind == "model_call":
            a = of(e["agent"])
            blocks = e.get("content") or []
            usage = e.get("usage") or {}
            prompt = sum(usage.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
            step = add(a, {
                "timestamp": when, "source": "agent", "model_name": model, "reasoning_effort": start.get("effort"),
                "message": "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text"),
                "reasoning_content": "\n".join(b.get("thinking", "") for b in blocks if b.get("type") == "thinking") or None,
                "tool_calls": [{"tool_call_id": b["id"], "function_name": b["name"], "arguments": b.get("input") or {}}
                               for b in blocks if b.get("type") == "tool_use"] or None,
                "metrics": {"prompt_tokens": prompt, "completion_tokens": usage.get("output_tokens", 0),
                            "cached_tokens": usage.get("cache_read_input_tokens", 0), "cost_usd": e.get("cost"),
                            "extra": {"usage": usage, "stop_reason": e.get("stop_reason"), "budget_left": e.get("budget_left")}},
                "llm_call_count": 1})
            a["open"] = step
            a["waiting"] = [c["tool_call_id"] for c in step["tool_calls"] or []]
            t = a["totals"]
            t["prompt"] += prompt
            t["completion"] += usage.get("output_tokens", 0)
            t["cached"] += usage.get("cache_read_input_tokens", 0)
            t["cost"] += e.get("cost") or 0.0
        elif kind == "tool":
            a = of(e["agent"])
            step = a["open"]
            if step is None:
                continue
            # older logs carry no call id: results arrive in the order the calls were made, `submit` unlogged
            call_id = e.get("id") or next((c["tool_call_id"] for c in step["tool_calls"] or []
                                           if c["tool_call_id"] in a["waiting"] and c["function_name"] == e["name"]), None)
            if call_id in a.get("waiting", []):
                a["waiting"].remove(call_id)
            result = {"source_call_id": call_id, "content": e.get("result", "")}
            if e["name"] == "spawn_agent" and not str(e.get("result", "")).startswith("ERROR"):
                child = (e.get("input") or {}).get("name")
                result["subagent_trajectory_ref"] = [{"session_id": "{}:{}".format(run_id, child), "trajectory_path": "{}.json".format(child)}]
            step.setdefault("observation", {"results": []})["results"].append(result)

    out = {}
    for name in order:
        a = agents[name]
        t = a["totals"]
        out[name] = {
            "schema_version": SCHEMA_VERSION, "session_id": "{}:{}".format(run_id, name),
            "agent": {"name": "swe-pod-kernel", "version": KERNEL_VERSION, "model_name": model,
                      "tool_definitions": a["tools"],
                      "extra": {"agent": name, "directories": a["directories"], "task": start.get("task"),
                                "condition": start.get("condition"), "budget_dollars": start.get("budget_dollars")}},
            "steps": [{k: v for k, v in s.items() if v is not None} for s in a["steps"]],
            "final_metrics": {"total_prompt_tokens": t["prompt"], "total_completion_tokens": t["completion"],
                              "total_cached_tokens": t["cached"], "total_cost_usd": round(t["cost"], 6),
                              "total_steps": len(a["steps"])},
        }
    return out


def write(run_dir: str) -> list:
    """Writes `<run_dir>/trajectories/<agent>.json` from `<run_dir>/events.jsonl`. Returns the paths."""
    with open(os.path.join(run_dir, "events.jsonl")) as f:
        events = [json.loads(line) for line in f if line.strip()]
    out_dir = os.path.join(run_dir, "trajectories")
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for name, trajectory in convert(events, os.path.basename(os.path.normpath(run_dir))).items():
        paths.append(os.path.join(out_dir, name + ".json"))
        with open(paths[-1], "w") as f:
            json.dump(trajectory, f, indent=2)
    return paths


if __name__ == "__main__":
    for path in write(sys.argv[1]):
        print(path)

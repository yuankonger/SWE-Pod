"""One episode: agents work a task in a private copy of the company, paid for from one budget in dollars.

Four ways to staff it (the condition):
- team: the owners the task has a brief for, one agent each, with messaging.
- team_no_messaging: the same team with no channel.
- solo: one agent that holds every owner's directory.
- lead: one agent that holds every directory and decides how to staff the work. It may do everything itself, or
  start other agents, give each some directories and instructions, and work with them by message.

A turn is one model call plus the tool calls it makes. Agents work at the same time: each has a clock of its
own and the one furthest behind takes the next turn (see run_episode). Every call is paid from the shared budget. The episode ends when every agent has submitted, the budget is spent, or the hard stop on model calls is
reached. Everything that happens is appended to an event log (JSON lines).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

from .model import total_tokens
from .tools import REGRESSION_TIMEOUT_S, SHELL_TIMEOUT_S, Sandbox, tool_definitions

CONDITIONS = ("team", "team_no_messaging", "solo", "lead")
MAX_IDLE_TURNS = 3
CLOCKS = ("measured", "turns")
MAX_SHARING_AGENTS = 8      # how many agents a lead may start when they may hold the same directories

COMPANY = """SeedCo sells monthly boxes online. Its systems are modelled on Saleor, an open-source commerce platform,
and each has one owner:
- core (Python): the commerce API, in GraphQL. Catalogue, checkouts, orders and transactions. It calculates no
  tax and takes no payments itself: it calls apps for those, and it tells apps what happens to orders.
- storefront (TypeScript): the web shop customers buy from. Calls core and subscriptions.
- dashboard (TypeScript): what staff use to fulfil, cancel and refund orders. Calls core.
- mobile (TypeScript): the phone app. Calls core. Released builds stay on customers' phones and cannot be changed.
- payments (C#): an app core calls to charge and refund cards through the payment provider.
- taxes (Java): an app core calls to calculate tax; it also keeps tax documents.
- notifications (Python): an app that turns core's order events into customer emails.
- subscriptions (C#): an app that adds monthly subscriptions on top of core: renewals, plan changes, dunning.
- support (Ruby): the support desk agents use to talk to customers.
- ops (Prometheus rules): monitoring, alert rules and runbooks, owned by whoever is on call.
An app is installed in core from its manifest and receives webhooks whose payload is the result of the app's own
GraphQL subscription query (under `graphql/`). A service publishes its contracts under `contracts/` and keeps copies
of the contracts it reads under `pinned/`. A copy is only a copy: the publishing owner's file and code are the
truth, and an owner's `NOTES.md` holds what only that owner knows."""

# One set of rules for every agent, whatever the condition. An agent's rules differ from another's only where what
# is true of it differs: its name, what it may read and change, who else is on the work, and the tools it holds.
RULES = """{overview}You are `{name}`. {access}
{company}

How you work:
- You act in turns. In a turn you may call several tools. Anyone else on this work acts at the same time as you,
  at their own pace.
- One budget in dollars pays for every model call made on this work, yours and anyone else's. Each turn update
  tells you what is left. A model call costs more the longer your conversation has become.
- The work is judged first on whether it is right, then on how little of the budget and how little time it took.
  Time runs from the start until everyone on the work has submitted.
{parts}
- When your work is finished, call `submit`.{after} The work ends when everyone on it has submitted or the budget
  is spent."""

ACCESS_FILES = "You can read and change the files of {}, and nothing else."
ACCESS_GIT = ("The company sets what each person may do with its repositories. Yours: {}. Each is checked out for you "
              "at `/work/services/<repository>`.")

ALONE = "Nobody else is working on this."
ALONE_LEAD = "Nobody else is working on this unless you start them."
WITH_OWNERS = "Working on this at the same time as you: {}."
NO_MESSAGING = " There is no way to contact them: work from what you can read yourself."
STARTED = "`lead`, who leads this work, started you. Others on it so far: {}."

GIT = """
- Your checkouts come from the company's git server (`origin`), and you commit under your own name. Only what is
  on `main` there counts: it is what gets deployed and judged, and its state is recorded as the budget is spent.
  Push work to `main` as soon as it is whole enough to keep, not only at the end. The server refuses a push to a
  repository you may only read, and refuses a push that is behind `main` until you have merged."""

COMPACTION = """
- When your conversation grows long you are asked to write a summary of it, and the conversation is then replaced
  by that summary. Your files and commits are not affected."""

MESSAGING = """
- `send_message` reaches anyone else on this work. {sight} A message reaches its reader at the start of their next
  turn after it was sent. `wait_for_message` stops you until one arrives; time passes while you wait. Keep
  messages short."""
SIGHT_NONE = "They cannot see your files, so anything they need from you has to be said, and anything you need from them asked for."
SIGHT_SAME_FILES = ("Agents that hold the same directories work on the same files as you, at the same time, each in a container "
                    "of its own. A file may change while you work: say what you are changing, and read a file again before "
                    "you rely on what it said earlier.")
SIGHT_GIT = "They see what you push, not your checkout or your conversation, so anything else they need from you has to be said."

SPAWNING = """
- How to staff this work is yours to decide. You may do all of it yourself, or start other agents with
  `spawn_agent`. An agent you start gets the access you choose, {overview}the instructions you write and nothing
  else, and begins with an empty conversation. {limit} Agents work at the same time, so work given to several takes
  as long as the slowest of them, not the sum; briefing an agent, reading its reports and clearing up
  misunderstandings also cost."""
LIMIT_GIT = "You cannot give more than you hold yourself."
LIMIT_FILES = {
    False: "No two agents you start may hold the same directory; you keep access to all of them.",
    True: "Agents you start may hold the same directory as each other and as you: they then work on the same files "
          "at the same time, each in a container of its own, and a file one agent changes is changed for all of them.",
}

DATA_OWN = """
- If you have a `query_data` tool, each directory of yours that has a `data/` directory holds a copy of that
  service's database as it is in production today. The company will be started from that history, not from
  empty databases."""
DATA_ALL = """
- `query_data` reads a service's database as it is in production today (a copy is under that service's `data/`).
  The company will be started from that history, not from empty databases."""

COMPACT_ASK = """[conversation limit] Your conversation has grown long and is about to be replaced by a summary. Write that
summary now, as plain text with no tool call. After this message you will have only the task as first given, this
summary, your files and your commits. Say what is done and where it is, what is pushed and what is not, what is
left to do and in what order, what you have agreed with others or are waiting for, and anything you learned that
would be costly to find again (commands that work, traps, names that must match)."""
COMPACT_AGAIN = "Nothing was run. Write the summary now, as plain text with no tool call."
COMPACTED = "Your conversation up to here was replaced by the summary you wrote of it:\n\n{}"


def _judging(own_tests: bool, regression: bool) -> str:
    """What an agent's rules say about tests and how the work is judged, for the tools that agent has."""
    lines = []
    if own_tests:
        lines.append("- `run_tests` runs one owner's own tests only.")
    if regression:
        lines.append("- `run_regression` starts the whole company and runs its end-to-end regression suite: what the "
                     "company does today\n  and must still do. What the work adds is judged by a hidden suite, which you "
                     "cannot see or run; it also runs\n  the regression suite, from its own copy.")
    else:
        lines.append("- The work is judged by a hidden suite, which you cannot see or run. It checks what the work adds, "
                     "and that\n  what works today still works.")
    return "\n".join(lines)


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
        self.dollars = 0.0
        self.clock = 0.0         # this agent's own time since the episode began (see run_episode)
        self.waited = 0.0        # how much of it passed waiting for a message
        self.waiting = False     # stopped by `wait_for_message` until a message reaches it
        self.nobody = False      # its wait ended because nobody was left who could write to it
        self.fresh = True        # its next turn opens a conversation: it is given the brief (again)
        self.carried = None      # the summary that replaced its conversation, if one has
        self.context = 0         # tokens its conversation held at its last model call
        self.compactions = 0
        self.writes = list(services)     # what it may change (with a git server: push to)
        self.warned = False      # told once that it holds work that is not on `main`


def seed_dir(task_dir: str):
    """Where the task's history is: its own `seed/`, or another task's when task.json says `seed_from`. None if neither."""
    with open(os.path.join(task_dir, "task.json")) as f:
        other = json.load(f).get("seed_from")
    path = os.path.join(os.path.dirname(os.path.abspath(task_dir)), other, "seed") if other else os.path.join(task_dir, "seed")
    return path if os.path.isdir(path) else None


def check_dirs(task_dir: str) -> list:
    """The directories that hold a task's rubric and check code: the regression suite agents can see, then the
    hidden checks. A task that says `checks_from` uses that task's as well, before its own; one that says
    `regression_from` uses only that task's regression suite."""
    with open(os.path.join(task_dir, "task.json")) as f:
        info = json.load(f)
    tasks = os.path.dirname(os.path.abspath(task_dir))
    found = []
    if info.get("regression_from"):
        found.append(os.path.join(tasks, info["regression_from"], "regression"))
    if info.get("checks_from"):
        found += [os.path.join(tasks, info["checks_from"], part) for part in ("regression", "hidden")]
    found += [os.path.join(os.path.abspath(task_dir), part) for part in ("regression", "hidden")]
    return [d for d in found if os.path.isdir(d)]


def regression_dir(task_dir: str):
    """The regression suite the task's agents can see and run, or None."""
    found = [d for d in check_dirs(task_dir) if os.path.basename(d) == "regression"]
    return found[-1] if found else None


def prepare_workspace(repo_root: str, task_dir: str, dest: str) -> str:
    """A private copy of the company with the task's starting state applied. Returns its path."""
    if os.path.exists(dest):
        shutil.rmtree(dest)
    for part in ("services", "platform"):
        shutil.copytree(os.path.join(repo_root, part), os.path.join(dest, part),
                        ignore=shutil.ignore_patterns("bin", "obj", "__pycache__"))
    if regression_dir(task_dir):     # what must keep working: agents can read and run it; the verifier runs its own copy
        shutil.copytree(regression_dir(task_dir), os.path.join(dest, "regression"), ignore=shutil.ignore_patterns("__pycache__"))
    overlay = os.path.join(task_dir, "overlay")
    if os.path.isdir(overlay):
        shutil.copytree(overlay, dest, dirs_exist_ok=True)
    # The task's history: each owner gets a copy of its own database under its `data/` directory, to look into.
    # Scoring starts the company from the task's seed, not from these copies.
    seed = seed_dir(task_dir)
    if seed:
        for owner in sorted(os.listdir(seed)):
            if os.path.isdir(os.path.join(dest, "services", owner)):
                shutil.copytree(os.path.join(seed, owner), os.path.join(dest, "services", owner, "data"))
        # ... and its own log of that history, if the history kept logs
        logs = os.path.join(os.path.dirname(seed), "logs")
        for name in sorted(os.listdir(logs)) if os.path.isdir(logs) else ():
            owner = name[:-len(".log")]
            if name.endswith(".log") and os.path.isdir(os.path.join(dest, "services", owner)):
                os.makedirs(os.path.join(dest, "services", owner, "logs"), exist_ok=True)
                shutil.copy(os.path.join(logs, name), os.path.join(dest, "services", owner, "logs", "production.log"))
    return dest


def owners(workspace: str) -> list:
    """Every owner's directory in the company, in name order."""
    services_dir = os.path.join(workspace, "services")
    return sorted(d for d in os.listdir(services_dir) if os.path.isfile(os.path.join(services_dir, d, "NOTES.md")))


def _has_run(services_dir: str, services: list) -> bool:
    """Whether these directories are the company's kind, each with a `run` script for its own tests."""
    return all(os.path.isfile(os.path.join(services_dir, s, "run")) for s in services)


def _with_data(services_dir: str, services: list) -> list:
    return [s for s in services if os.path.isdir(os.path.join(services_dir, s, "data"))]


def _runner(containers, services_dir: str, agent: str, services: list):
    """Starts the agent's container, if agents have containers, and returns how to run a command in it."""
    if containers is None:
        return None
    containers.start(agent, os.path.realpath(services_dir), services)
    return lambda service, args: containers.run(agent, service, args)


def _regression(workspace: str, containers):
    """(the workspace's regression suite, how to run it against the company as it is now), or None if it has none.

    The suite starts the whole company from the copies of the history the owners hold. Every agent may run it,
    as everyone in a company sees the result of its end-to-end tests whichever part they own."""
    suite = os.path.join(workspace, "regression")
    if not os.path.isfile(os.path.join(suite, "test_regression.py")):
        return None

    kept = os.path.join(workspace, ".regression-logs")

    def hand_out_logs():
        """Each service's log of the run goes to its owner: `logs/regression.log` in the owner's directory."""
        for name in sorted(os.listdir(kept)) if os.path.isdir(kept) else ():
            owner = os.path.join(workspace, "services", name[:-len(".log")])
            if name.endswith(".log") and os.path.isdir(owner):
                os.makedirs(os.path.join(owner, "logs"), exist_ok=True)
                shutil.copy(os.path.join(kept, name), os.path.join(owner, "logs", "regression.log"))
        shutil.rmtree(kept, ignore_errors=True)

    def run():
        try:
            if containers:
                return containers.regression(os.path.realpath(workspace), REGRESSION_TIMEOUT_S)
            env = dict(os.environ, SEEDCO_ROOT=workspace, SEEDCO_BASE_PORT="7200", PYTHONDONTWRITEBYTECODE="1", SEEDCO_LOG_DIR=kept)
            env.pop("SEEDCO_SEED_DIR", None)
            try:
                p = subprocess.run([sys.executable, "-m", "unittest", "-v", "test_regression"], cwd=suite, capture_output=True,
                                   text=True, timeout=REGRESSION_TIMEOUT_S, env=env)
            except subprocess.TimeoutExpired:
                return None, ""
            return p.returncode, p.stdout + p.stderr
        finally:
            hand_out_logs()
    return suite, run


def _shell(containers, agent: str, services: list):
    """How to run a shell command in the agent's container, or None when agents have no containers. Without a
    container a shell would see the whole machine, the verifier's files included, so there is none."""
    if containers is None:
        return None
    if containers.images:        # a container per directory: the command runs in the one for `service`
        return lambda command, service=None: containers.execute(agent, ["bash", "-lc", command], "/work/services/" + service, SHELL_TIMEOUT_S, service)
    home = "/work/services" if len(services) > 1 else "/work/services/" + services[0]
    return lambda command, service=None: containers.execute(agent, ["bash", "-lc", command], home, SHELL_TIMEOUT_S)


def _shell_options(containers, everyone: list, agent: str, services: list) -> dict:
    """What an agent's tools must say about its shell: whether each directory has a container of its own, and the
    names containers answer to on the run's network."""
    if containers is None:
        return {}
    networked = bool(containers.network and containers.images)
    return {"shell_by_service": bool(containers.images), "hosts": everyone if networked else (),
            "own_hosts": ["{}-{}".format(agent, s) for s in services] if networked else ()}


def _system(task: dict, name: str, access: str, company: str, judging: str, data: str, git: bool, compaction: bool,
            messaging: bool, sight: str, spawning: bool, shared_tree: bool) -> str:
    """An agent's rules: the same for every agent but for what is true of this one."""
    overview = task.get("overview", COMPANY)
    parts = judging + (GIT if git else "") + data + (COMPACTION if compaction else "")
    if messaging:
        parts += MESSAGING.format(sight=sight)
    if spawning:
        parts += SPAWNING.format(overview="a short overview of the systems, " if overview else "",
                                 limit=LIMIT_GIT if git else LIMIT_FILES[shared_tree])
    return RULES.format(overview=overview + "\n\n" if overview else "", name=name, access=access, company=company, parts=parts,
                        after=" If a message reaches you later you get another turn." if messaging else "")


def _checkout(containers, git, agent: str, repository: str):
    """Clones a repository from the company's git server into the agent's container for it, as that agent."""
    script = ("git config --global --add safe.directory '*' && git config --global user.name {a} "
              "&& git config --global user.email {a}@example.com && git clone -q {url} .").format(a=agent, url=git.url(agent, repository))
    code, out = containers.execute(agent, ["bash", "-lc", script], "/work/services/" + repository, 900, repository)
    if code != 0:
        raise RuntimeError("could not check out {} for {}: {}".format(repository, agent, (out or "timed out")[-400:]))


def _not_on_main(containers, agent: str, repositories: list) -> list:
    """What the agent holds that is not on `main` of the git server: one line per repository that has any."""
    found = []
    for r in repositories:
        code, out = containers.execute(agent, ["bash", "-lc", "git status --porcelain | wc -l; git fetch -q origin; git rev-list --count origin/main..HEAD"],
                                       "/work/services/" + r, 120, r)
        numbers = [int(x) for x in (out or "").split() if x.isdigit()]
        if code == 0 and len(numbers) == 2 and (numbers[0] or numbers[1]):
            found.append("`{}`: {} changed or new files not committed, {} commits not pushed".format(r, numbers[0], numbers[1]))
    return found


def make_agent(task: dict, workspace: str, build_base: str, containers, git, name: str, kind: str, services: list, brief: str,
               company: str, peers, messaging: bool, compaction: bool) -> "Agent":
    """One agent with its container(s), sandbox, rules and tools. `kind`: solo, owner, lead or worker; it decides
    only whether the agent can start others. `git` (kernel.gitserver.GitServer): the agent works in checkouts of
    its own, of every repository the server lets it read, and `services` is ignored."""
    shared_tree = bool(task.get("shared_tree")) and not git
    if git:
        held = git.rules["access"][name]
        services = sorted(held)
        services_dir = os.path.join(workspace, "agents", name, "services")
        for s in services:
            os.makedirs(os.path.join(services_dir, s), exist_ok=True)
        everyone = list(git.repositories)
        access = ACCESS_GIT.format("; ".join("`{}`: {}".format(s, "read and push" if held[s] == "write" else "read only") for s in services))
        sight = SIGHT_GIT
    else:
        services_dir = os.path.join(workspace, "services")
        everyone = owners(workspace)
        access = ACCESS_FILES.format("your directory, `{}`".format(services[0]) if len(services) == 1 else
                                     "these directories: " + ", ".join("`{}`".format(s) for s in services))
        sight = SIGHT_SAME_FILES if shared_tree and kind in ("lead", "worker") else SIGHT_NONE
    runner = None
    if containers is not None:
        if git:
            containers.start(name, os.path.realpath(services_dir), services, named=[s for s in services if held[s] == "write"])
            for s in services:
                _checkout(containers, git, name, s)
        else:
            runner = _runner(containers, services_dir, name, services)
    regression = _regression(workspace, containers)
    with_data = _with_data(services_dir, services)
    spawning = kind == "lead"
    system = _system(task, name, access, company, _judging(_has_run(services_dir, services), bool(regression)),
                     (DATA_ALL if kind in ("solo", "lead") else DATA_OWN) if with_data else "", bool(git), compaction,
                     messaging, sight, spawning, shared_tree)
    tools = tool_definitions(services, peers, messaging, with_data, everyone if spawning else (), bool(regression), containers is not None,
                             _has_run(services_dir, services), shared_tree=shared_tree, spawn_access=dict(held) if git and spawning else None,
                             **_shell_options(containers, everyone, name, services))
    sandbox = Sandbox(services_dir, services, build_base, runner, regression, _shell(containers, name, services), bool(containers and containers.images))
    agent = Agent(name, services, sandbox, system, tools, brief)
    agent.writes = [s for s in services if held[s] == "write"] if git else list(services)
    return agent


def build_agents(task: dict, condition: str, workspace: str, build_base: str, containers=None, git=None, compaction: bool = False) -> list:
    """The agents an episode starts with. `containers` (kernel.containers.Containers) gives each its own container.

    A task may say `overview` (what every agent is told about the systems, in place of the company's) and
    `shared_tree` (without a git server, agents a lead starts may hold the same directories). With `git`, who may
    read and push what comes from the server's table of grants, which is the environment's and not the condition's."""
    if condition in ("solo", "lead"):
        lead = condition == "lead"
        name = "lead" if lead else "solo"
        return [make_agent(task, workspace, build_base, containers, git, name, name, None if git else owners(workspace),
                           task.get("lead_brief", task["solo_brief"]) if lead else task["solo_brief"],
                           ALONE_LEAD if lead else ALONE, None if lead else [], lead, compaction)]
    messaging = condition == "team"
    team = list(task["briefs"])
    does = lambda s: "pushes to " + ", ".join(r for r, level in sorted(git.rules["access"][s].items()) if level == "write") if git else "owns " + s
    agents = []
    for s in team:
        company = WITH_OWNERS.format(", ".join("`{}` ({})".format(x, does(x)) for x in team if x != s)) + ("" if messaging else NO_MESSAGING)
        agents.append(make_agent(task, workspace, build_base, containers, git, s, "owner", [s], task["briefs"][s], company,
                                 [x for x in team if x != s], messaging, compaction))
    return agents


def _minutes(seconds: float) -> str:
    return "{}m {:02d}s".format(int(seconds) // 60, int(seconds) % 60)


def run_episode(task: dict, condition: str, model, workspace: str, log_path: str, budget_dollars: float,
                max_model_calls: int = 400, build_base: str = None, containers=None, clock: str = "measured",
                git=None, compact_at_tokens: int = None, checkpoint_dollars: float = None) -> dict:
    """Runs to the end and returns a summary. The workspace is left as the agents made it, ready for scoring.

    Agents work at the same time. The kernel runs one turn at a time, but each agent has a clock of its own, which a
    turn moves on by what the turn took: the model call and the tools it ran. The agent whose clock is furthest
    behind takes the next turn, so turns happen in the order they would if the agents ran side by side. A message
    carries the sender's clock and reaches its reader at the first turn the reader starts at or after that time. An
    agent that is waiting or has submitted is moved on to the time its next message arrives. The time the work took
    is the furthest clock, not the sum.

    `clock`: "measured" takes each turn's real seconds. "turns" counts every turn as one unit, which gives plain
    round-robin and the same order on every run (for tests and scripted agents).

    `git` (kernel.gitserver.GitServer, started): agents work in checkouts of their own and the work is what is on
    `main` of the server. `compact_at_tokens`: an agent whose conversation has reached this many tokens writes a
    summary, which replaces the conversation. `checkpoint_dollars` (with `git`): every time this much more of the
    budget is spent, the commits `main` is at are recorded, so the work can be scored against what it had cost.

    One thing is not as it would be side by side: a command runs whole at the moment its turn starts, so nothing
    another agent does can land in the middle of it."""
    if condition not in CONDITIONS:
        raise ValueError("condition must be one of {}".format(CONDITIONS))
    if clock not in CLOCKS:
        raise ValueError("clock must be one of {}".format(CLOCKS))
    if git and not (containers and containers.images):
        raise ValueError("a git server needs a container per repository for each agent")
    measured = clock == "measured"
    shared_tree = bool(task.get("shared_tree")) and not git
    build_base = build_base or os.path.join(os.path.dirname(workspace), "build")
    agents = build_agents(task, condition, workspace, build_base, containers, git, bool(compact_at_tokens))
    by_name = {a.name: a for a in agents}
    used = {"dollars": 0.0, "tokens": 0, "calls": 0, "messages": 0, "compactions": 0}
    usage_total = {}
    checkpoints = []
    started = time.time()
    turn = {"started": 0.0}
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    log_file = open(log_path, "w")

    def log(kind, **fields):
        log_file.write(json.dumps(dict(kind=kind, t=round(time.time() - started, 2), **fields), default=str) + "\n")
        log_file.flush()

    def now(agent) -> float:
        """The agent's own time at this point of its turn."""
        return agent.clock + (time.monotonic() - turn["started"] if measured else 0.0)

    log("episode_start", task=task["id"], condition=condition, budget_dollars=budget_dollars, clock=clock,
        max_model_calls=max_model_calls, agents=[a.name for a in agents], model=getattr(model, "model", "scripted"),
        effort=getattr(model, "effort", None), started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        git=bool(git), access=git.rules["access"] if git else None, compact_at_tokens=compact_at_tokens, checkpoint_dollars=checkpoint_dollars)

    def introduce(agent):
        """What the agent starts with, logged once, so that a trajectory can be rebuilt from the log alone."""
        log("agent_start", agent=agent.name, directories=agent.services, system=agent.system, tools=agent.tools, clock=round(agent.clock, 2))

    for a in agents:
        introduce(a)

    def checkpoint(at):
        """Where `main` is now that `at` dollars are spent (None: at the end)."""
        entry = {"dollars": at if at is not None else round(used["dollars"], 4), "spent": round(used["dollars"], 4), "end": at is None,
                 "team_seconds": round(max(a.clock for a in agents), 1), "heads": {r: git.head(r) for r in git.repositories}}
        checkpoints.append(entry)
        log("checkpoint", **entry)

    def update_text(agent) -> str:
        left = max(0.0, budget_dollars - used["dollars"])
        parts = []
        if agent.fresh:
            parts.append(agent.brief)
            if agent.carried is not None:
                parts.append(COMPACTED.format(agent.carried))
            agent.fresh = False
        arrived = [m for m in agent.inbox if m["at"] <= agent.clock]
        agent.inbox = [m for m in agent.inbox if m["at"] > agent.clock]
        for m in arrived:
            parts.append("Message from {}:\n{}".format(m["from"], m["text"]))
        if agent.nobody and not arrived:
            parts.append("No message came: every other agent has submitted or is waiting as well.")
        update = "[turn update] Shared budget left: ${:,.2f} of ${:,.2f}.".format(left, budget_dollars)
        if measured:
            update += " Time since the work began: {}.".format(_minutes(agent.clock))
        parts.append(update)
        if agent.idle:
            parts.append("You made no tool call last turn. Keep working, or call `submit` if your part is done.")
        return "\n\n".join(parts)

    def spawn(lead, args) -> str:
        """The lead starts another agent and hands it some of what it holds."""
        name, instructions = args.get("name") or "", args.get("instructions") or ""
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,23}", name) or name in by_name:
            return "ERROR: `name` must be new, at most 24 characters, lower-case letters, digits and hyphens"
        if not instructions.strip():
            return "ERROR: `instructions` must say what the agent is to do"
        if git:
            access = args.get("access") if isinstance(args.get("access"), dict) else {}
            if not access:
                return "ERROR: `access` must name one or more of {}, each with `read` or `write`".format(git.repositories)
            if len(agents) - 1 >= MAX_SHARING_AGENTS:
                return "ERROR: you cannot start more than {} agents".format(MAX_SHARING_AGENTS)
            try:
                git.grant(lead.name, name, access)
            except PermissionError as e:
                return "ERROR: {}".format(e)
            directories = sorted(access)
        else:
            directories = args.get("directories") or []
            everyone = owners(workspace)
            taken = {d for a in agents if a.name != "lead" for d in a.services}
            if not directories or len(set(directories)) != len(directories) or any(d not in everyone for d in directories):
                return "ERROR: `directories` must be one or more of {}, each once".format(everyone)
            if taken & set(directories) and not shared_tree:
                return "ERROR: already held by another agent you started: {}".format(sorted(taken & set(directories)))
            most = MAX_SHARING_AGENTS if shared_tree else len(everyone)
            if len(agents) - 1 >= most:
                return "ERROR: you cannot start more than {} agents".format(most)
            directories = sorted(directories)
        others = ", ".join("`{}` ({})".format(a.name, ", ".join(a.writes or a.services)) for a in agents if a.name != "lead") or "none yet"
        worker = make_agent(task, workspace, build_base, containers, git, name, "worker", directories, instructions,
                            STARTED.format(others), None, True, bool(compact_at_tokens))
        worker.clock = now(lead)         # it begins at the moment it is started, not at the start of the episode
        agents.append(worker)
        by_name[name] = worker
        introduce(worker)
        log("spawn", agent=name, directories=directories, access=git.rules["access"][name] if git else None, instructions=instructions)
        return "started `{}` with {}. It is working now, at the same time as you.".format(
            name, ", ".join("{} ({})".format(r, level) for r, level in sorted(git.rules["access"][name].items())) if git else ", ".join(directories))

    def call_model(agent, **noted):
        reply = model.call(agent.name, agent.system, agent.tools, agent.messages)
        agent.calls += 1
        agent.tokens += total_tokens(reply.usage)
        agent.dollars += reply.cost
        agent.context = total_tokens(reply.usage)        # what the conversation holds now: everything read plus what was just written
        used["tokens"] += total_tokens(reply.usage)
        used["dollars"] += reply.cost
        used["calls"] += 1
        for k, v in reply.usage.items():
            usage_total[k] = usage_total.get(k, 0) + v
        log("model_call", agent=agent.name, stop_reason=reply.stop_reason, usage=reply.usage, cost=round(reply.cost, 6),
            budget_left=round(budget_dollars - used["dollars"], 4), content=reply.logged, clock=round(now(agent), 2), **noted)
        return reply

    def compact(agent):
        """The agent writes a summary of its conversation, which then replaces it. Paid for and timed like any turn."""
        tokens = agent.context
        said = COMPACT_ASK
        for attempt in range(2):
            log("turn", agent=agent.name, text=said, clock=round(now(agent), 2))
            agent.messages.append({"role": "user", "content": agent.pending + [{"type": "text", "text": said}]})
            agent.pending = []
            reply = call_model(agent, compaction=True)
            if reply.text.strip() and not reply.tool_uses:
                break
            agent.messages.append({"role": "assistant", "content": reply.content})
            for use in reply.tool_uses:
                log("tool", agent=agent.name, id=use["id"], name=use["name"], input=use["input"], result="ERROR: not run")
                agent.pending.append({"type": "tool_result", "tool_use_id": use["id"], "content": "ERROR: not run", "is_error": True})
            said = COMPACT_AGAIN
        agent.pending = []
        agent.carried = reply.text.strip() or "(no summary was written)"
        agent.messages, agent.context, agent.fresh = [], 0, True
        agent.compactions += 1
        used["compactions"] += 1
        log("compaction", agent=agent.name, tokens_before=tokens, summary=agent.carried, clock=round(now(agent), 2))

    def take_turn(agent):
        turn["started"] = time.monotonic()
        if compact_at_tokens and agent.context >= compact_at_tokens:
            compact(agent)
        said = update_text(agent)
        woke_to_nobody, agent.nobody = agent.nobody, False
        log("turn", agent=agent.name, text=said, clock=round(agent.clock, 2))    # what the agent is told this turn, beside its tool results
        agent.messages.append({"role": "user", "content": agent.pending + [{"type": "text", "text": said}]})
        agent.pending = []
        reply = call_model(agent)
        agent.messages.append({"role": "assistant", "content": reply.content})
        offered = {t["name"] for t in agent.tools}
        only_waited = bool(reply.tool_uses) and all(u["name"] == "wait_for_message" for u in reply.tool_uses)
        # a turn that does nothing, or only waits again when nobody is left to write, is an idle one
        agent.idle = 0 if reply.tool_uses and not (only_waited and woke_to_nobody) else agent.idle + 1
        for use in reply.tool_uses:
            name, args = use["name"], use["input"] if isinstance(use["input"], dict) else {}
            if name == "send_message" and name in offered:
                to = by_name.get(args.get("to"))
                if to is None or to is agent or not args.get("text"):
                    result = "ERROR: `to` must be another agent ({}) and `text` must not be empty".format(
                        ", ".join(n for n in by_name if n != agent.name) or "there is none yet")
                else:
                    at = round(now(agent), 2)
                    to.inbox.append({"from": agent.name, "text": args["text"], "at": at})
                    result = "sent to {}".format(to.name)
                    used["messages"] += 1
                    log("message", sender=agent.name, to=to.name, text=args["text"], at=at)
            elif name == "wait_for_message" and name in offered:
                agent.waiting = True
                result = "waiting: your next turn begins when a message reaches you"
            elif name == "spawn_agent" and name in offered:
                result = spawn(agent, args)
            elif name == "submit":
                behind = _not_on_main(containers, agent.name, agent.writes) if git and not agent.warned else []
                if behind:           # said once: work that is not on `main` does not count
                    agent.warned = True
                    result = ("ERROR: not submitted. You hold work that is not on `main` and so will not count: {}. Commit and "
                              "push what should count, then call `submit` again; a second `submit` is accepted as it is.".format("; ".join(behind)))
                else:
                    agent.submitted, agent.summary = True, args.get("summary", "")
                    result = "submitted"
                    log("submit", agent=agent.name, summary=agent.summary, clock=round(now(agent), 2))
            else:
                result = agent.sandbox.call(name, args)
            # every tool call and the whole of what it returned: exactly what the model reads next turn
            log("tool", agent=agent.name, id=use["id"], name=name, input=args, result=result)
            agent.pending.append({"type": "tool_result", "tool_use_id": use["id"], "content": result,
                                  **({"is_error": True} if result.startswith("ERROR:") else {})})
        if agent.idle >= MAX_IDLE_TURNS and not agent.submitted:
            agent.submitted, agent.summary = True, "(stopped: no tool call in {} turns)".format(MAX_IDLE_TURNS)
            log("idle_stop", agent=agent.name)
        agent.clock = now(agent) if measured else agent.clock + 1.0

    def ready_at(agent):
        """When the agent can take its next turn, on its own clock; None while it has stopped and nothing is on its way."""
        if not agent.submitted and not agent.waiting:
            return agent.clock
        return max(agent.clock, min(m["at"] for m in agent.inbox)) if agent.inbox else None

    def move_on(agent, to: float):
        agent.waited += max(0.0, to - agent.clock)
        agent.clock = max(agent.clock, to)
        agent.submitted = agent.waiting = False

    end = None
    error = None
    next_checkpoint = checkpoint_dollars if git and checkpoint_dollars else None
    try:
        while end is None:
            while next_checkpoint and used["dollars"] >= next_checkpoint:
                checkpoint(next_checkpoint)
                next_checkpoint += checkpoint_dollars
            if used["dollars"] >= budget_dollars:
                end = "budget_exhausted"
            elif used["calls"] >= max_model_calls:
                end = "hard_stop"
            else:
                ready = [(ready_at(a), i) for i, a in enumerate(agents) if ready_at(a) is not None]
                waiting = [a for a in agents if a.waiting and not a.submitted]
                if ready:
                    at, i = min(ready)           # furthest behind first; the earlier-started agent on a tie
                    move_on(agents[i], at)
                    take_turn(agents[i])
                elif waiting:                    # everyone left is waiting for someone else: tell them so
                    latest = max(a.clock for a in agents)
                    for a in waiting:
                        move_on(a, latest)
                        a.nobody = True
                else:
                    end = "all_submitted"
        if git:
            checkpoint(None)
    except Exception as exc:  # a model or harness failure: the episode is invalid, never a score
        end, error = "error", "{}: {}".format(type(exc).__name__, exc)
    summary = {
        "task": task["id"], "condition": condition, "end": end, "error": error, "valid": error is None,
        "budget_dollars": budget_dollars, "dollars_used": round(used["dollars"], 4), "tokens_used": used["tokens"],
        "model_calls": used["calls"], "usage": usage_total, "wall_seconds": round(time.time() - started, 1),
        # how long the work took with the agents side by side, and what the same turns took one after another
        "clock": clock, "team_seconds": round(max(a.clock for a in agents), 1), "agent_seconds": round(sum(a.clock - a.waited for a in agents), 1),
        "agents": {a.name: {"directories": a.services, "calls": a.calls, "tokens": a.tokens, "dollars": round(a.dollars, 4),
                            "submitted": a.submitted, "summary": a.summary, "seconds": round(a.clock, 1),
                            "waited_seconds": round(a.waited, 1), "compactions": a.compactions} for a in agents},
        "messages_sent": used["messages"], "compactions": used["compactions"],
    }
    if git:
        summary["checkpoints"] = checkpoints
        summary["access"] = git.rules["access"]
    log("episode_end", **summary)
    log_file.close()
    return summary

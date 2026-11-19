"""The tools an agent has, and the sandbox that confines them to what that agent may see.

An agent holds one or more owners' directories. With one directory, paths are relative to it. With several, paths
are relative to the services directory and start with the owner's name. Nothing outside the agent's directories
can be read or written. Tool results are plain strings; failures are strings that start with "ERROR:".
"""
import os
import subprocess

MAX_READ_CHARS = 60_000
MAX_OUTPUT_CHARS = 12_000
TEST_TIMEOUT_S = 300
REGRESSION_TIMEOUT_S = 900
SHELL_TIMEOUT_S = 180


def _schema(properties: dict, required: list) -> dict:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


def tool_definitions(services: list, peers, messaging: bool, with_data: list = (), can_spawn: list = (), regression: bool = False, shell: bool = False, own_tests: bool = True, shared_tree: bool = False,
                     shell_by_service: bool = False, hosts: list = (), own_hosts: list = (), spawn_access: dict = None) -> list:
    """Tool definitions for one agent.

    `services`: the directories it holds. `peers`: the other agents' names, or None when agents can appear during
    the episode and the recipient is checked when the message is sent. `with_data`: the directories of its own
    that have a database to look into. `can_spawn`: for a lead, the directories it may hand to a new agent.
    `regression`: the company has a regression suite the agent may read and run. `shell`: the agent has a
    container of its own to run commands in. `shared_tree`: agents a lead starts may hold the same directories.
    `shell_by_service`: each directory has a container of its own, so a shell command names the directory it runs
    in. `hosts`: the names the run's containers answer to on its network, if it has one. `spawn_access`: with a git
    server, what the lead itself holds ({repository: "read" | "write"}); it can hand on any part of it."""
    many = len(services) > 1
    where = ("Paths are relative to the services directory, e.g. `core/src/core.py`."
             if many else "Paths are relative to your directory, e.g. `src/...`.")
    service = {"service": {"type": "string", "enum": list(services)}} if many else {}
    tools = [
        {"name": "list_files", "description": "List every file you can see, with sizes. " + where,
         "input_schema": _schema({"path": {"type": "string", "description": "Directory to list; omit for everything."}}, [])},
        {"name": "read_file", "description": "Read a text file. " + where,
         "input_schema": _schema({"path": {"type": "string"}}, ["path"])},
        {"name": "write_file", "description": "Create or overwrite a file with the given content. " + where,
         "input_schema": _schema({"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"])},
        {"name": "edit_file",
         "description": "Replace one exact occurrence of `old` with `new` in a file. Fails if `old` is missing or "
                        "occurs more than once. " + where,
         "input_schema": _schema({"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}},
                                 ["path", "old", "new"])},
    ]
    if own_tests:        # a directory with a `run` script of the company's kind; a mined repository has none
        tools.append({"name": "run_tests",
                      "description": "Run one owner's own test suite (`./run test`) and return its output. These tests cover that "
                                     "owner's code alone; they do not start the rest of the company.",
                      "input_schema": _schema(service, ["service"] if many else [])})
    if regression:
        tools.append({"name": "run_regression",
                      "description": "Start the whole company as it is now, with every owner's current files and its "
                                     "history, and run the end-to-end regression suite: the checks of what the company "
                                     "does today and must still do after the work. Returns the suite's output. It takes "
                                     "a few minutes. It does not check what the work is meant to add. Afterwards "
                                     "each service's log of the run is in its `logs/regression.log`.",
                      "input_schema": _schema({}, [])})
        tools.append({"name": "read_regression",
                      "description": "Read a file of the regression suite, e.g. `regression_checks.py`. Omit `path` to "
                                     "list its files. The suite can be read but not changed.",
                      "input_schema": _schema({"path": {"type": "string"}}, [])})
    if shell:
        reach = ("it has no network beyond itself" if not hosts else
                 "the only network it has is this work's own. On it {} to {}, and a directory's name alone ({}) reaches the "
                 "container of the agent who held that directory first. A service started in one container, listening on "
                 "0.0.0.0, can be called from the others".format(
                     "your containers answer" if len(own_hosts) > 1 else "your container answers",
                     ", ".join("`{}`".format(h) for h in own_hosts), ", ".join("`{}`".format(h) for h in hosts)))
        if shell_by_service:
            place = ("Each of your directories has a container of its own, with that system's toolchain and only that "
                     "directory in it, at `/work/services/<directory>`, where the command starts" if many else
                     "The container holds your directory, at `/work/services/{}`, where the command starts, and its toolchain".format(services[0]))
        else:
            place = ("The container holds the directories you can see, under `/work/services`, and the toolchains{}".format(
                ", the stack runner (`/work/platform`) and the regression suite (`/work/regression`)" if regression else ""))
        tools.append({"name": "shell",
                      "description": "Run a bash command in {} and return what it printed (stdout and stderr) and its exit "
                                     "code. {}; {}. Use it to search files and logs (`grep`, `tail`), to build and run code, "
                                     "and to start services and send them requests. A command is stopped after {} seconds: "
                                     "start anything long-lived in the background (`nohup ... &`).".format(
                                         "the container of one of your directories" if shell_by_service and many else "your own container",
                                         place, reach, SHELL_TIMEOUT_S),
                      "input_schema": _schema(dict({"command": {"type": "string"}}, **(service if shell_by_service else {})),
                                              ["command", "service"] if shell_by_service and many else ["command"])})
    if with_data:
        tools.append({"name": "query_data",
                      "description": "Run one read-only SQL query on a service's database as it is in production today "
                                     "(SQLite, or H2 for taxes). Returns up to 200 rows. Start with the table list: "
                                     "`SELECT name FROM sqlite_master` (SQLite) or `SHOW TABLES` (H2).",
                      "input_schema": _schema(dict({"sql": {"type": "string"}},
                                                   **({"service": {"type": "string", "enum": list(with_data)}} if many else {})),
                                              ["sql", "service"] if many else ["sql"])})
    if can_spawn:
        if spawn_access:
            levels = lambda held: ["read", "write"] if held == "write" else ["read"]
            given = {"access": {"type": "object", "minProperties": 1, "additionalProperties": False,
                                "description": "What the agent may do with each repository it gets: `read`, or `write` (read and push). "
                                               "Never more than you hold yourself. A repository left out cannot be seen by it at all.",
                                "properties": {r: {"type": "string", "enum": levels(spawn_access[r])} for r in sorted(spawn_access)}}}
            what = ("It gets a checkout of its own of each repository you give it, and the git server holds it to the "
                    "access you chose. Several agents may push to the same repository: each push must then be merged with what is already on `main`.")
        else:
            given = {"directories": {"type": "array", "items": {"type": "string", "enum": list(can_spawn)}, "minItems": 1}}
            what = ("It can read and change only the directories you give it. " + ("Agents may be given the same directory: they then work on the same files."
                                                                                  if shared_tree else "No two agents you start may share a directory."))
        tools.append({"name": "spawn_agent",
                      "description": "Start a new agent to work alongside you. It starts knowing nothing but a short overview of the "
                                     "company's systems and your `instructions`, so put everything it needs there. It starts at once and works "
                                     "at the same time as you, can message you and the other agents, and its model calls are paid from "
                                     "the same budget as yours. " + what,
                      "input_schema": _schema(dict({"name": {"type": "string", "description": "A short name, lower-case letters, digits and hyphens."}},
                                                   **given, instructions={"type": "string"}), ["name", list(given)[0], "instructions"])})
    if messaging and (peers is None or peers):
        to = {"type": "string", "description": "The name of another agent."} if peers is None else {"type": "string", "enum": list(peers)}
        tools.append({"name": "send_message",
                      "description": "Send a message to another agent. They work at the same time as you and read it at "
                                     "the start of their next turn after you sent it. "
                                     "Use it to ask for what you need and to tell others what they need.",
                      "input_schema": _schema({"to": to, "text": {"type": "string"}}, ["to", "text"])})
        tools.append({"name": "wait_for_message",
                      "description": "Stop until a message reaches you: your next turn begins when one does. Use it when "
                                     "you cannot go on without an answer or without another agent's work. Time passes "
                                     "while you wait, so do what you can do first.",
                      "input_schema": _schema({}, [])})
    tools.append({"name": "submit",
                  "description": "Declare your part of the work finished. You stop taking turns unless a new "
                                 "message arrives for you.",
                  "input_schema": _schema({"summary": {"type": "string",
                                                       "description": "What you changed and what others must know."}},
                                          ["summary"])})
    return tools


def _capped(out: str) -> str:
    """Output short enough to read: the start and the end, and between them how much was left out."""
    if len(out) <= MAX_OUTPUT_CHARS:
        return out
    dropped = len(out) - MAX_OUTPUT_CHARS
    return (out[:3000] + "\n[... {:,} characters left out here: the output was {:,} characters and at most {:,} are shown. "
            "Narrow the command or read the rest in parts ...]\n".format(dropped, len(out), MAX_OUTPUT_CHARS) + out[-(MAX_OUTPUT_CHARS - 3000):])


class Sandbox:
    """File, test and data access for one agent, confined to the directories of the owners it holds."""

    def __init__(self, services_dir: str, services: list, build_base: str, runner=None, regression=None, shell=None, shell_by_service: bool = False):
        """`runner(service, args)` runs `./run <args>` for that owner somewhere else (the agent's container) and
        returns (exit code, output), or (None, "") on a timeout. Without it, commands run here as child processes.
        `regression`: (the regression suite's directory, a function that runs it and returns (exit code, output))."""
        self.regression_dir, self.regression_run = regression or (None, None)
        self.shell_run = shell      # shell(command, service) -> (exit code, output) in the agent's container; None: no shell
        self.shell_by_service = shell_by_service      # a container per directory: a command names its directory
        self.services_dir = os.path.realpath(services_dir)
        self.services = list(services)
        self.many = len(self.services) > 1
        self.root = self.services_dir if self.many else os.path.join(self.services_dir, self.services[0])
        self.build_base = build_base  # compiled output goes here, never into a service directory
        self.runner = runner

    def _resolve(self, path: str, allow_root: bool = False) -> str:
        full = os.path.realpath(os.path.join(self.root, path or "."))
        homes = [os.path.join(self.services_dir, s) for s in self.services]
        inside = any(full == h or full.startswith(h + os.sep) for h in homes)
        if not inside and not (allow_root and self.many and full == self.services_dir):
            raise PermissionError("that path is outside what you can access")
        return full

    def list_files(self, path: str = "") -> str:
        base = self._resolve(path, allow_root=True)
        if not os.path.isdir(base):
            return "ERROR: not a directory: {}".format(path)
        starts = [os.path.join(base, s) for s in self.services] if base == self.services_dir and self.many else [base]
        rows = []
        for start in starts:
            for d, dirs, files in os.walk(start):
                dirs[:] = sorted(x for x in dirs if x not in ("bin", "obj", "__pycache__", ".git"))
                for f in sorted(files):
                    full = os.path.join(d, f)
                    rows.append("{}  ({} bytes)".format(os.path.relpath(full, self.root), os.path.getsize(full)))
        return "\n".join(rows) or "(no files)"

    def read_file(self, path: str) -> str:
        full = self._resolve(path)
        if not os.path.isfile(full):
            return "ERROR: no such file: {}".format(path)
        with open(full, errors="replace") as f:
            text = f.read()
        if len(text) > MAX_READ_CHARS:
            return text[:MAX_READ_CHARS] + "\n[file continues: {} characters in total]".format(len(text))
        return text

    def write_file(self, path: str, content: str) -> str:
        full = self._resolve(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)
        return "wrote {} ({} bytes)".format(path, len(content.encode()))

    def edit_file(self, path: str, old: str, new: str) -> str:
        full = self._resolve(path)
        if not os.path.isfile(full):
            return "ERROR: no such file: {}".format(path)
        with open(full) as f:
            text = f.read()
        count = text.count(old)
        if count != 1:
            return "ERROR: `old` occurs {} times in {}; it must occur exactly once".format(count, path)
        with open(full, "w") as f:
            f.write(text.replace(old, new, 1))
        return "edited {}".format(path)

    def _run(self, service: str, args: list) -> str:
        """Runs `./run <args>` for one owner, in the agent's container if it has one, and returns what it printed."""
        if self.many:
            if service not in self.services:
                return "ERROR: service must be one of {}".format(self.services)
        else:
            service = self.services[0]
        cwd = os.path.join(self.services_dir, service)
        if self.runner:
            code, out = self.runner(service, args)
            if code is None:
                return "ERROR: `{}` did not finish within {} seconds".format(args[0], TEST_TIMEOUT_S)
        else:
            env = dict(os.environ, SEEDCO_BUILD_DIR=os.path.join(self.build_base, service))
            try:
                p = subprocess.run(["./run"] + args, cwd=cwd, capture_output=True, text=True, timeout=TEST_TIMEOUT_S, env=env)
            except subprocess.TimeoutExpired:
                return "ERROR: `{}` did not finish within {} seconds".format(args[0], TEST_TIMEOUT_S)
            code, out = p.returncode, p.stdout + p.stderr
        out = out.strip()
        out = _capped(out)
        return "exit code {}\n{}".format(code, out)

    def run_tests(self, service: str = None) -> str:
        return self._run(service, ["test"])

    def query_data(self, sql: str, service: str = None) -> str:
        return self._run(service, ["query", sql])

    def shell(self, command: str, service: str = None) -> str:
        if not self.shell_run:
            return "ERROR: you have no shell"
        if self.shell_by_service:
            service = service if self.many else self.services[0]
            if service not in self.services:
                return "ERROR: service must be one of {}".format(self.services)
        code, out = self.shell_run(command, service)
        if code is None:
            return "ERROR: the command did not finish within {} seconds".format(SHELL_TIMEOUT_S)
        out = out.strip()
        out = _capped(out)
        return "exit code {}\n{}".format(code, out)

    def run_regression(self) -> str:
        if not self.regression_run:
            return "ERROR: this company has no regression suite"
        code, out = self.regression_run()
        if code is None:
            return "ERROR: the regression suite did not finish within {} seconds".format(REGRESSION_TIMEOUT_S)
        out = out.strip()
        out = _capped(out)
        return "exit code {}\n{}".format(code, out)

    def read_regression(self, path: str = "") -> str:
        if not self.regression_dir:
            return "ERROR: this company has no regression suite"
        base = os.path.realpath(self.regression_dir)
        full = os.path.realpath(os.path.join(base, path or "."))
        if full != base and not full.startswith(base + os.sep):
            raise PermissionError("that path is outside the regression suite")
        if os.path.isdir(full):
            rows = []
            for d, dirs, files in os.walk(full):
                dirs[:] = sorted(x for x in dirs if x != "__pycache__")
                rows += ["{}  ({} bytes)".format(os.path.relpath(os.path.join(d, f), base), os.path.getsize(os.path.join(d, f))) for f in sorted(files)]
            return "\n".join(rows) or "(no files)"
        if not os.path.isfile(full):
            return "ERROR: no such file in the regression suite: {}".format(path)
        with open(full, errors="replace") as f:
            return f.read()[:MAX_READ_CHARS]

    def call(self, name: str, args: dict) -> str:
        """Run a file, test or data tool. Messaging, spawning and submit are handled by the episode, not here."""
        try:
            if name == "list_files":
                return self.list_files(args.get("path", ""))
            if name == "read_file":
                return self.read_file(args["path"])
            if name == "write_file":
                return self.write_file(args["path"], args["content"])
            if name == "edit_file":
                return self.edit_file(args["path"], args["old"], args["new"])
            if name == "run_tests":
                return self.run_tests(args.get("service"))
            if name == "query_data":
                return self.query_data(args["sql"], args.get("service"))
            if name == "shell":
                return self.shell(args["command"], args.get("service"))
            if name == "run_regression":
                return self.run_regression()
            if name == "read_regression":
                return self.read_regression(args.get("path", ""))
        except PermissionError as e:
            return "ERROR: {}".format(e)
        except (KeyError, TypeError) as e:
            return "ERROR: bad arguments for {}: {}".format(name, e)
        except OSError as e:
            return "ERROR: {}".format(e)
        return "ERROR: unknown tool {}".format(name)

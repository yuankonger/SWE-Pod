"""The tools an owner agent has, and the sandbox that confines them to what that owner may see.

An owner sees one service directory (the solo agent sees all of them). Paths are relative to that root; nothing
outside it can be read or written. Tool results are plain strings; failures are strings that start with "ERROR:".
"""
import os
import subprocess

MAX_READ_CHARS = 60_000
MAX_OUTPUT_CHARS = 12_000
TEST_TIMEOUT_S = 300


def _schema(properties: dict, required: list) -> dict:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


def tool_definitions(services: list, peers: list, messaging: bool) -> list:
    """Tool definitions for one agent. `services`: the services it owns; `peers`: the other agents' names."""
    many = len(services) > 1
    where = ("Paths are relative to the services directory, e.g. `billing/src/Billing.cs`."
             if many else "Paths are relative to your service directory, e.g. `src/...`.")
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
        {"name": "run_tests",
         "description": "Run a service's own test suite (`./run test`) and return its output. These tests cover that "
                        "service alone; they do not start the other services.",
         "input_schema": _schema({"service": {"type": "string", "enum": services}} if many else {},
                                 ["service"] if many else [])},
    ]
    if messaging and peers:
        tools.append({"name": "send_message",
                      "description": "Send a message to another service owner. They read it at the start of their "
                                     "next turn. Use it to ask for what you need and to tell others what they need.",
                      "input_schema": _schema({"to": {"type": "string", "enum": peers}, "text": {"type": "string"}},
                                              ["to", "text"])})
    tools.append({"name": "submit",
                  "description": "Declare your part of the change finished. You stop taking turns unless a new "
                                 "message arrives for you.",
                  "input_schema": _schema({"summary": {"type": "string",
                                                       "description": "What you changed and what others must know."}},
                                          ["summary"])})
    return tools


class Sandbox:
    """File and test access for one agent, rooted at `root` (a service directory, or `services/` for solo)."""

    def __init__(self, root: str, services: list, build_base: str):
        self.root = os.path.realpath(root)
        self.services = services
        self.many = len(services) > 1
        self.build_base = build_base  # compiled output goes here, never into the service directory

    def _resolve(self, path: str) -> str:
        full = os.path.realpath(os.path.join(self.root, path or "."))
        if full != self.root and not full.startswith(self.root + os.sep):
            raise PermissionError("that path is outside what you can access")
        return full

    def list_files(self, path: str = "") -> str:
        base = self._resolve(path)
        if not os.path.isdir(base):
            return "ERROR: not a directory: {}".format(path)
        rows = []
        for d, dirs, files in os.walk(base):
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

    def run_tests(self, service: str = None) -> str:
        if self.many:
            if service not in self.services:
                return "ERROR: service must be one of {}".format(self.services)
            cwd = os.path.join(self.root, service)
        else:
            cwd, service = self.root, self.services[0]
        env = dict(os.environ, SEEDCO_BUILD_DIR=os.path.join(self.build_base, service))
        try:
            p = subprocess.run(["./run", "test"], cwd=cwd, capture_output=True, text=True, timeout=TEST_TIMEOUT_S,
                               env=env)
        except subprocess.TimeoutExpired:
            return "ERROR: the tests did not finish within {} seconds".format(TEST_TIMEOUT_S)
        out = (p.stdout + p.stderr).strip()
        if len(out) > MAX_OUTPUT_CHARS:
            out = out[:3000] + "\n[... output cut ...]\n" + out[-(MAX_OUTPUT_CHARS - 3000):]
        return "exit code {}\n{}".format(p.returncode, out)

    def call(self, name: str, args: dict) -> str:
        """Run a file or test tool. Messaging and submit are handled by the episode, not here."""
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
        except PermissionError as e:
            return "ERROR: {}".format(e)
        except (KeyError, TypeError) as e:
            return "ERROR: bad arguments for {}: {}".format(name, e)
        except OSError as e:
            return "ERROR: {}".format(e)
        return "ERROR: unknown tool {}".format(name)

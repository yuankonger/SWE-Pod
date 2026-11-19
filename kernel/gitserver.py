"""The company's git server: one shared container that holds every repository and decides who may push where.

Permissions belong to the environment, not to the condition. The same server and the same rule serve a solo
agent, a fixed team and a lead that starts its own agents; only the table of grants differs:

    solo         one agent, write on every repository
    fixed team   each owner writes its own repository, and reads the others or not (`others`)
    lead         the lead holds what a solo agent holds, and can pass any agent a part of what it holds itself

An agent works in a checkout, in a container of its own, and its work counts once it is pushed to `main` here.
Scoring and deployment take `main` from this server, never from an agent's workspace.

Needs the `docker` command. The image must have git and python3 (every toolchain image here does).
"""
import json
import os
import secrets
import subprocess

IMAGE = "seedco-toolchain:0.4"
HOST = "git"
PORT = 8080
READ, WRITE = "read", "write"
ORDER = {None: 0, READ: 1, WRITE: 2}
OTHERS = ("read", "none")      # what a fixed-team owner may do with repositories that are not its own

# Records each branch a push moved, with who pushed it. Runs inside the server after a push is accepted.
POST_RECEIVE = """#!/bin/sh
while read old new ref; do
  printf '{"at": %s, "agent": "%s", "repository": "%s", "action": "moved", "ref": "%s", "old": "%s", "new": "%s"}\\n' \\
    "$(date +%s)" "$REMOTE_USER" "$(basename "$PWD" .git)" "$ref" "$old" "$new" >> "$SEEDCO_PUSH_LOG"
done
"""


def grants(condition: str, owners: dict, others: str = "read") -> dict:
    """The table of grants a condition starts with. `owners` is {agent: [repositories it owns]}; for solo and
    lead give the one agent every repository. `others` is the environment's rule for repositories an agent does
    not own, and is the same whatever the condition."""
    if others not in OTHERS:
        raise ValueError("others must be one of {}".format(OTHERS))
    every = sorted({r for held in owners.values() for r in held})
    table = {}
    for agent, held in owners.items():
        table[agent] = {r: WRITE for r in held}
        if others == "read":
            for r in every:
                table[agent].setdefault(r, READ)
    return table


class GitServer:
    def __init__(self, run_id: str, network: str = None, image: str = IMAGE):
        """`network`: the run's Docker network; the server answers there as `git`. Without one it has no network
        and can only be used from inside its own container."""
        self.name = "seedco-{}-git".format("".join(c if c.isalnum() else "-" for c in run_id.lower()))[:60]
        self.network, self.image = network, image
        self.rules = {"tokens": {}, "access": {}}
        self.repositories = []

    def _exec(self, command: list, stdin: str = None, timeout: float = 600):
        p = subprocess.run(["docker", "exec", "-i", self.name] + command, input=stdin, capture_output=True, text=True, timeout=timeout)
        if p.returncode != 0:
            raise RuntimeError("git server: {} failed: {}".format(" ".join(command[:3]), (p.stderr or p.stdout).strip()[-500:]))
        return p.stdout

    def _write_rules(self):
        self._exec(["sh", "-c", "cat > /srv/access.tmp && mv /srv/access.tmp /srv/access.json"], json.dumps(self.rules))

    def start(self, repositories: dict, access: dict):
        """`repositories`: {name: directory on this machine holding the starting tree}. A directory that is already
        a git checkout keeps its history; a plain tree becomes one commit that holds every file of it, ignored or not. `access`: see `grants`."""
        net = ["--network", self.network, "--network-alias", HOST] if self.network else ["--network", "none"]
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)
        started = subprocess.run(["docker", "run", "-d", "--rm", "--name", self.name] + net + [self.image, "sleep", "infinity"],
                                 capture_output=True, text=True)
        if started.returncode != 0:
            raise RuntimeError("could not start the git server: {}".format(started.stderr.strip()[-500:]))
        self._exec(["sh", "-c", "mkdir -p /srv/git /srv/in && : > /srv/log.jsonl && git config --global init.defaultBranch main "
                                "&& git config --global user.name SeedCo && git config --global user.email seedco@example.com "
                                "&& git config --global --add safe.directory '*'"])
        app = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gitserver_app.py")
        subprocess.run(["docker", "cp", app, self.name + ":/srv/app.py"], check=True, capture_output=True)
        for name, tree in repositories.items():
            subprocess.run(["docker", "cp", os.path.abspath(tree) + "/.", "{}:/srv/in/{}".format(self.name, name)], check=True, capture_output=True)
            self._exec(["sh", "-c", "cd /srv/in/{0} && if [ ! -e .git ]; then git init -q && git add -A -f && git commit -qm 'Where the work starts'; fi "
                                    "&& git branch -M main && git clone -q --bare . /srv/git/{0}.git && rm -rf /srv/in/{0} "
                                    "&& cat > /srv/git/{0}.git/hooks/post-receive && chmod +x /srv/git/{0}.git/hooks/post-receive".format(name)],
                       POST_RECEIVE)
            self.repositories.append(name)
        self.rules = {"tokens": {a: secrets.token_hex(12) for a in access}, "access": {a: dict(v) for a, v in access.items()}}
        self._write_rules()
        subprocess.run(["docker", "exec", "-d", self.name, "python3", "/srv/app.py", "/srv/git", "/srv/access.json", "/srv/log.jsonl", str(PORT)],
                       check=True, capture_output=True)
        self._exec(["sh", "-c", "for i in $(seq 50); do python3 -c \"import socket; socket.create_connection(('127.0.0.1', {}), 1)\" 2>/dev/null && exit 0; sleep 0.2; done; exit 1".format(PORT)])

    def grant(self, giver: str, agent: str, access: dict):
        """`giver` passes `agent` a part of what it holds itself: {repository: "read" | "write"}. Refused, with
        nothing changed, if any of it is more than the giver has."""
        held = self.rules["access"].get(giver, {})
        for repository, level in access.items():
            if level not in (READ, WRITE) or ORDER[level] > ORDER[held.get(repository)]:
                raise PermissionError("{} cannot give {} on `{}`: it holds {}".format(giver, level, repository, held.get(repository) or "nothing"))
        self.rules["tokens"].setdefault(agent, secrets.token_hex(12))
        self.rules["access"].setdefault(agent, {}).update(access)
        self._write_rules()

    def url(self, agent: str, repository: str, host: str = HOST) -> str:
        """What the agent clones and pushes to. It carries the agent's token, so it goes to that agent only."""
        return "http://{}:{}@{}:{}/{}.git".format(agent, self.rules["tokens"][agent], host, PORT, repository)

    def export(self, repository: str, destination: str, ref: str = "main"):
        """Writes the tree at `ref` into `destination` on this machine: what gets deployed and scored."""
        os.makedirs(destination, exist_ok=True)
        archive = subprocess.run(["docker", "exec", self.name, "git", "-C", "/srv/git/{}.git".format(repository), "archive", ref],
                                 capture_output=True, timeout=600)
        if archive.returncode != 0:
            raise RuntimeError("could not export {}: {}".format(repository, archive.stderr.decode()[-300:]))
        subprocess.run(["tar", "-x", "-C", destination], input=archive.stdout, check=True)

    def head(self, repository: str, ref: str = "main") -> str:
        return self._exec(["git", "-C", "/srv/git/{}.git".format(repository), "rev-parse", ref]).strip()

    def log(self) -> list:
        """Every fetch and push, allowed or refused, and every branch a push moved."""
        return [json.loads(line) for line in self._exec(["cat", "/srv/log.jsonl"]).splitlines() if line.strip()]

    def stop(self):
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)

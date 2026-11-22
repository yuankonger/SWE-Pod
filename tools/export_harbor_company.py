"""Exports a company task (mined/<company>) as a Harbor task with several containers, for stock harnesses.

    python3 tools/export_harbor_company.py <company> --clone owner=path ... [--out harbor/<company>]

What a stock harness (Claude Code, Codex, ...) gets is one seat and a company running beside it:

    main        the agent's seat: a checkout of every repository under /work, with every repository's toolchain,
                so the harness's own shell can build and test all of it. Harbor installs and runs the harness here.
    git         the company's git server (sidecars/gitserver_app.py). The checkouts are clones of it. It decides
                who may push where; the seat of a solo agent may push to every repository.
    ci          CI and deploy (sidecars/ci.py). When `main` of a repository moves it deploys that repository, then
                tests the systems together as they run, and serves the result at http://ci:8080/.
    <owner>     one sidecar per repository: that system as last deployed from `main` (sidecars/service.py).

The work that counts is what is on `main` of the git server: the verifier clones it from there, with a token of
its own, and never looks at the seat's checkouts.

The seat has the internet, because a stock harness is installed from it and reaches its model over it. The hosts
the real feature could be fetched from (code hosts, package registries, the project's own site) are made
unreachable from the seat by name. That is a list of names, not a wall: a run's trajectory should still be
checked for fetches from elsewhere, and the harness's own web tools should be turned off.

The verifier is the scorer of tools/mined_company.py, run inside the seat on a fresh clone of `main`:
every repository's own tests with the feature's hidden tests laid over, and whether the two sides agree.
reward = mean progress x product of regression x agreement. A company that names a `business` check also gets a
business verdict beside the reward (tools/harbor_business_check.py): pass, fail or infrastructure. The hidden tests exist only under tests/, which
Harbor copies in after the agent has finished.

    harbor/<company>/instruction.md
    harbor/<company>/task.toml
    harbor/<company>/environment/Dockerfile            every toolchain, the checkouts as git repositories
    harbor/<company>/environment/docker-compose.yaml   the sidecars
    harbor/<company>/environment/work/<owner>/         each repository as the work starts from it
    harbor/<company>/environment/sidecars/             what the sidecars run (copied from sidecars/)
    harbor/<company>/tests/test.sh, score.py, config.json, hidden/   the scorer and what it needs
    harbor/<company>/solution/solve.sh, <owner>.patch  the real feature, as the oracle

The directory is generated: change mined/ and export again.
"""
import argparse
import json
import re
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "tools"))
import mined_company as mc                       # noqa: E402
from mined_pilot import export, put              # noqa: E402

# What a repository's notes say that is true of the kernel's containers and not of a Harbor seat.
NOT_HERE = ("A shell command is stopped after", "There is no git history", "To serve the API to the other containers",
            "The containers of this work can reach each other", "The other containers of this work")
REWORDED = {"- There is no network and no git history.\n": "",
            " There is no internet: nothing can be installed.": " Nothing needs to be installed.",
            "is about 830 files and takes three minutes.": "is about 830 files. On this machine run it with `--maxWorkers=2` and a directory at a time: "
            "with four workers, or the whole suite in one run, Jest needs more memory than there is here and stops without finishing."}

# Where the repositories' real history, or packages built from it, can be had.
UNREACHABLE = ("github.com", "www.github.com", "api.github.com", "raw.githubusercontent.com", "codeload.github.com", "objects.githubusercontent.com",
               "gist.github.com", "github.githubassets.com", "ghcr.io", "gitlab.com", "bitbucket.org", "sourcegraph.com", "grep.app",
               "pypi.org", "files.pythonhosted.org", "registry.npmjs.org", "registry.yarnpkg.com", "cdn.jsdelivr.net", "unpkg.com", "esm.sh",
               "web.archive.org", "archive.org",
               # The model is reached through the gateway alone. A harness that falls back to its vendor's own
               # servers would send them the gateway's key, so those are unreachable too.
               "api.openai.com", "chatgpt.com", "auth.openai.com")

# Names on the company's git server. A token only tells the server who is asking; what each may do is in its table.
TOKENS = {"solo": "seat-7f3a91c2d4", "ci": "ci-2b8e6d10aa", "verifier": "verifier-c41f09be73", "oracle": "oracle-9a17c3e55b"}
OWNER_TOKEN = "seat-{}-4e81b7"          # an owner's, in a team
CHAT_ADMIN = "chat-admin-5d02e7"        # as in tools/harbor_team.py
JUDGE_TOKEN = "judge-3b9e51c07a2d"      # the seat's verifier and the judge share it; the agent sees neither
SEAT_MEMORY = "6144m"                   # every seat has the same limit, in every condition: the task's memory_mb

CODEX_VERSION = "0.169.0"

SOLO_SEAT = """
## Your seat

You may push to every repository. Nobody else is working on this.
"""

MCP_TEAM = """
[[environment.mcp_servers]]
name = "team"
transport = "stdio"
command = "python3"
args = ["/opt/seedco/team_mcp.py"]
"""

DOCKERFILE = """# The agent's seat: every repository's toolchain, and a checkout of every repository under /work.
# Generated by tools/export_harbor_company.py. The same image runs the sidecars.
{stages}FROM {first}
{copies}ENV {env}
# Codex is put in here because its own installer fetches from hosts the seat cannot reach (see UNREACHABLE).
RUN apt-get update && apt-get install -y --no-install-recommends ripgrep && rm -rf /var/lib/apt/lists/* \
    && npm install -g @openai/codex@{codex} && codex --version
{browser}# the judge runs the work's code as this user, never as root (sidecars/judge.py)
RUN useradd -m -s /bin/bash scorer
COPY sidecars /opt/seedco
COPY work /work
RUN git config --global user.name SeedCo && git config --global user.email seedco@example.com \\
    && git config --global init.defaultBranch main && git config --global --add safe.directory '*' \\
    && for r in {owners}; do (cd /work/$r && git init -q && git add -A -f && git commit -qm "Where the work starts") || exit 1; done
WORKDIR /work
ENTRYPOINT ["/opt/seedco/seat.sh"]
CMD ["bash"]
"""

# The verifier's business outcome check drives the staff application in a browser. It must be in the image: the
# verifier runs in the seat, after the agent, and installs nothing.
BROWSER = "RUN cd /deps && npx playwright install --with-deps chromium && rm -rf /var/lib/apt/lists/*\n"

# The public images the toolchains start from, pinned, so that the task builds the same wherever it is built.
PINNED = {"python:3.12-bookworm": "python:3.12-bookworm@sha256:4209fae09a3e20afd863e528bfddc235da5fd5977983e1996cd54cc9a72e6267",
          "node:24-bookworm": "node:24-bookworm@sha256:9d266751ca3d7fdbe651c878ffd5ad0a42fed49a18c283509267c97f025b7496"}


def base_stage(owner, repo):
    """A repository's toolchain as a stage of the task's own Dockerfile: the recipe of mined/<task>/Dockerfile, with
    its lock files taken from the repository's tree as the work starts (they are the ones the toolchain was made for).
    So the task builds from its own directory, with nothing built beforehand."""
    with open(os.path.join(REPO, "mined", repo["id"], "Dockerfile")) as f:
        recipe = f.read()
    out = ["# The `{}` toolchain (from mined/{}/Dockerfile)".format(owner, repo["id"])]
    for line in recipe.splitlines():
        if line.startswith("FROM "):
            base = line.split()[1]
            line = "FROM {} AS base-{}".format(PINNED.get(base, base), owner)
        elif line.startswith("COPY ") and not line.startswith("COPY --"):
            parts = line.split()
            line = " ".join(["COPY"] + ["work/{}/{}".format(owner, p) for p in parts[1:-1]] + [parts[-1]])
        elif line.startswith(("ENTRYPOINT", "CMD")):
            continue
        out.append(line)
    return "\n".join(out) + "\n"


# Node from the dashboard's image into the Python image: the binary, its global packages and their launchers.
NODE_COPIES = """COPY --from={stage} /usr/local/bin/node /usr/local/bin/node
COPY --from={stage} /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN cd /usr/local/bin && ln -sf node nodejs && ln -sf ../lib/node_modules/npm/bin/npm-cli.js npm \\
    && ln -sf ../lib/node_modules/npm/bin/npx-cli.js npx \\
    && if [ -d ../lib/node_modules/pnpm ]; then ln -sf ../lib/node_modules/pnpm/bin/pnpm.mjs pnpm; elif command -v corepack > /dev/null; then corepack enable pnpm; fi
"""
# What of a toolchain's image is merged into the seat's, beside Node: `/deps` (installed dependencies) by default, or
# the paths its task names in `toolchain_paths` (a pnpm store, corepack's prepared versions).
# Merged from a mount of the other stage, not copied in and then merged: a copy would stay in the image as a layer of
# its own (2 GB of node_modules, twice).
TOOLCHAIN_COPY = """RUN --mount=type=bind,from={stage},source={path},target=/mnt/toolchain mkdir -p {path} && cp -an /mnt/toolchain/. {path}/
"""

TEST_SH = """#!/bin/bash
# The verifier. It does not score here: this is the agent's seat, and nothing in it can be trusted to judge. It hands
# the task's tests to the company's judge (sidecars/judge.py), a container the agent never had, which runs the rubric
# (/tests/rubric.toml, with /tests/score.py) on `main` of the company's git server, and takes back what it wrote: the
# reward, score.json and rubric.txt (one line per criterion). It also keeps what the company recorded of the work.
mkdir -p /logs/verifier/records
TOKEN=$(python3 -I -c "import json; print(json.load(open('/tests/config.json'))['judge_token'])")
GIT=$(python3 -I -c "import json; print(json.load(open('/tests/config.json'))['git'])")
JUDGE=http://judge:8095
curl -s -m 30 "$GIT/_log" > /logs/verifier/records/git.jsonl || true
curl -s -m 30 http://ci:8080/status.json > /logs/verifier/records/ci.json || true
curl -s -m 30 http://meter:8318/_records > /logs/verifier/records/model.jsonl || true
curl -s -m 30 "http://chat:8080/log?token={chat_admin}" > /logs/verifier/records/chat.json 2>/dev/null || rm -f /logs/verifier/records/chat.json
tar -C /tests -czf /tmp/judge-tests.tgz .
code=$(curl -s -o /logs/verifier/judge-start.json -w '%{http_code}' -X POST --data-binary @/tmp/judge-tests.tgz -H 'Content-Type: application/gzip' "$JUDGE/judge?token=$TOKEN")
if [ "$code" != 202 ]; then echo "the judge did not take the work ($code)" > /logs/verifier/output.txt; echo 0 > /logs/verifier/reward.txt; cat /logs/verifier/reward.txt; exit 0; fi
until curl -s -m 20 "$JUDGE/status?token=$TOKEN" | grep -q '"state": "\\(done\\|failed\\)"'; do sleep 20; done
curl -s -m 20 "$JUDGE/status?token=$TOKEN" > /logs/verifier/judge-status.json
curl -s -m 120 -o /tmp/judge-result.tgz "$JUDGE/result?token=$TOKEN" && tar -C /logs/verifier -xzf /tmp/judge-result.tgz
[ -f /logs/verifier/reward.txt ] || echo 0 > /logs/verifier/reward.txt
cat /logs/verifier/reward.txt
"""

SOLVE_SH = """#!/bin/bash
# The oracle: the feature as the real project wrote it, laid over each checkout, committed and pushed to `main`.
set -e
for r in {owners}; do
  cd /work/$r && git apply --binary --whitespace=nowarn /solution/$r.patch
  git add -A -f && git commit -qm "The feature, as the project wrote it" && git push -q {oracle}/$r.git HEAD:main
done
"""

TASK_TOML = """schema_version = "1.4"

[task]
name = "seedco/{slug}"
description = {title}
keywords = ["swe-pod", "multi-repository", "mined", "interface agreement"]

[metadata]
category = "software-engineering"
repositories = {repositories}
source = {source}

[verifier]
# Runs both repositories' test suites, one after the other, then starts the provider from nothing.
timeout_sec = 10800.0
environment_mode = "shared"

[agent]
timeout_sec = 14400.0

[environment]
build_timeout_sec = 2400.0
cpus = 6
memory_mb = {memory}
storage_mb = 30720
workdir = "/work"
"""

# The brief is what a colleague would be told: the feature, and what done means. Where the repositories are, how a
# change reaches the running company and what runs where are for the agent to find (each repository's NOTES.md says);
# what belongs to the seat and not to the work is in the seat's note.
INSTRUCTION = """{feature}
{parts}
{done}
"""
# What each repository's NOTES.md says of the running company.
RUNNING = """
## The running company

- This repository is a clone of the company's git server (`origin`), which decides who may push where. `main` there is what is deployed and what is judged.
- It runs as {where}
- CI and deploy are at `http://ci:8080/`. Whenever `main` of a repository moves it deploys that repository, then tests the systems together as they run: {checks} `curl http://ci:8080/` shows the latest run and `curl http://ci:8080/runs` every run.
{others}"""
# What CI checks of the running systems, by the contract's type (sidecars/ci.py).
CI_CHECKS = {
    "graphql": "that each started, that the API answers, that every GraphQL operation the dashboard sends is valid against the schema the running API really has, and that the API, asked as staff for the fields it gained since the work started, answers them without an error in a resolver.",
    "lexicon": "that each started, that the AppView answers `getGroupedNotifications` for a seeded account through the PDS, that every AppView method the app calls is one the AppView serves, and that the app's vendored copies of the lexicons the AppView gained state what the AppView has.",
    "websocket": "that each started, that Home Assistant answers over its WebSocket API as its owner, that every command the frontend sends is one core registers, and that the devices core lists have every field the frontend's own types for that answer require.",
}
# What each type of contract needs beside the scorer: in the task's tests/, and in the sidecars for CI.
CONTRACT_TOOLS = {
    "graphql": [("tools", "mined_graphql_agreement.cjs"), ("sidecars", "fetch_schema.cjs")],
    "websocket": [("tools", "ha_seed.py"), ("tools", "mined_ws_contract.py"), ("tools", "mined_ws_agreement.cjs")],
    "lexicon": [("tools", "mined_lexicon_contract.py"), ("tools", "bsky_seed.mjs"), ("tools", "bsky_serve_web.py")],
}
ENDING = ("Ending: when you stop, the work stops. Anything you left running is ended with you, and only what is on `main` "
          "by then counts.")

# What a seat's holder is told about the seat: role, permissions, tools, budget. It is no part of the brief. The
# harness gets it as an addition to its system prompt (tools/harbor_team.py, `seat_notes`), filled in with the run's
# own figures: {cap} this seat's spending cap, {total} the whole work's, {hours} the time limit.
SEAT_NOTES = {
    "solo": """# Your seat

Role: you are the one engineer on this work. Nobody else is working on it.
Permissions: you may read and push to every repository.
Tools: your shell and file tools at this seat. You cannot start other agents. There is no web search or web fetch.
Budget: the work has ${total} of model spending in all, and all of it is yours. You are stopped when it is spent.
Time: the work ends {hours} hours after it starts at the latest.""",
    "lead": """# Your seat

Role: you lead this work. Nobody else is working on it unless you start them: you may start other agents to work
for you, and how many, when, and on what is yours to decide.
Permissions: you, and any agent you start, may read and push to every repository.
Tools: your shell and file tools at this seat, and the tools that start other agents. There is no web search or web fetch.
Budget: the work has ${total} of model spending in all. It is one pool: what the agents you start spend comes out of
it, and you are all stopped when it is spent.
Time: the work ends {hours} hours after it starts at the latest. Agents you started are ended when you stop.""",
    "team": """# Your seat

Role: you are `{owner}`, the owner of the `{owner}` repository, one of a team of {n}. {others} at the same time
as you, each at a seat of their own.
Permissions: you may push to `{owner}`. You can read {others_repos} but not push to {them}.
Tools: your shell and file tools at this seat. You cannot start other agents. There is no web search or web fetch.
{messaging}
Budget: the work has ${total} of model spending in all, split evenly between the seats: ${cap} is this seat's. What a
seat does not spend does not pass to another. You are stopped when yours is spent.
Time: the work ends {hours} hours after it starts at the latest.""",
}
MESSAGING = {
    True: ("You can reach the others with the `send_message` tool; `read_messages` shows what has reached you and `wait_for_message` waits for it. "
           "They see what you push, not your checkout or your conversation, so anything else they need from you has to be said. "
           "Someone who has finished reads no more messages."),
    False: "There is no way to contact the others: work from what you can read yourself.",
}


ISOLATED_PERMISSIONS = ("Permissions: `{owner}` is the one repository you have, and you may push to it. You cannot read or push to {others_repos}. "
                        "Of {them_long} you can see what is deployed from `main` (your repository's `NOTES.md` says where each system runs) and what CI reports.")


def coworker_seats(out, owners, coworker, people):
    """<task>/seats/coworker/: the seat's note for each arm (docs/COWORKER_SPEC.md, section 8). `full-<value>` states the
    requirement as that variant has it; the others leave it to be asked for, or not."""
    owner, names = coworker["seat"], [p["name"].capitalize() for p in people["people"]]
    others = ", ".join("`{}`".format(o) for o in owners if o != owner)
    requirement = next(t for p in people["people"] for t in p["topics"] if t["kind"] == "requirement")
    os.makedirs(os.path.join(out, "seats", "coworker"), exist_ok=True)
    def note(arm):
        return COWORKER_SEAT.format(owner=owner, requester=names[0], others_repos=others,
                                    reach=COWORKER_REACH[arm].format(names=" and ".join("{} (`{}`)".format(n, n.lower()) for n in names), first=names[0]))
    notes = {arm: note(arm) for arm in COWORKER_REACH}
    for value, says in requirement["says"].items():
        notes["full-" + value] = note("partial") + COWORKER_FULL.format(first=names[0], says=says)
    for name, text in notes.items():
        with open(os.path.join(out, "seats", "coworker", name + ".md"), "w") as f:
            f.write(text + "\n" + ENDING + "\n")


def seat_notes(out, owners, isolated=False):
    """Writes <task>/seats/: one note per condition and seat. The same files are in the solo and the team task.
    `isolated`: a team's seats hold their own repository only."""
    def put(path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text + "\n" + ENDING + "\n")
    for condition in ("solo", "lead"):
        put(os.path.join(out, "seats", condition + ".md"), SEAT_NOTES[condition])
    for messaging in (True, False):
        for owner in owners:
            others = [o for o in owners if o != owner]
            names = ", ".join("`{}`".format(o) for o in others)
            note = SEAT_NOTES["team"].format(
                owner=owner, n=len(owners), others_repos=names, them="them" if len(others) > 1 else "it",
                others=("The owners of {} are" if len(others) > 1 else "The owner of {} is").format(names) + " working on this",
                messaging=MESSAGING[messaging], total="{total}", cap="{cap}", hours="{hours}")
            if isolated:
                note = "\n".join(ISOLATED_PERMISSIONS.format(owner=owner, others_repos=names, them_long="the others' work" if len(others) > 1 else "the other's work")
                                 if line.startswith("Permissions:") else line for line in note.splitlines())
                note = note.replace("They see what you push, not your checkout", "They see what is deployed from what you push, not your repository")
            put(os.path.join(out, "seats", "team" if messaging else "team_no_messaging", owner + ".md"), note)



def notes_for_harbor(text: str) -> str:
    for old, new in REWORDED.items():
        text = text.replace(old, new)
    return "".join(line for line in text.splitlines(keepends=True) if not any(x in line for x in NOT_HERE))


# A coworker task (docs/COWORKER_SPEC.md): one agent at one owner's seat, and people it reaches through the chat.
# What the seat's holder is told, per arm of the evidence gate. {says} is the requirement as the variant has it.
COWORKER_SEAT = """# Your seat

Role: you are `{owner}`, the owner of the `{owner}` repository. {requester} asked for this work.
Permissions: `{owner}` is the one repository you have, and you may push to it. You cannot read or push to {others_repos}.
Tools: your shell and file tools at this seat. You cannot start other agents. There is no web search or web fetch.
{reach}
Budget: the work has ${{total}} of model spending in all. You are stopped when it is spent.
Time: the work ends {{hours}} hours after it starts at the latest."""
COWORKER_REACH = {
    "partial": "You can reach {names} with the `send_message` tool; `read_messages` shows what has reached you and `wait_for_message` waits for it.",
    "no_interaction": "There is no way to contact anyone: work from what you have.",
    "told": ("You can reach {names} with the `send_message` tool; `read_messages` shows what has reached you and `wait_for_message` waits for it.\n"
             "Before you build, ask {first} for any requirements the brief leaves out."),
}
COWORKER_FULL = "\n\n## What {first} has also told you\n\n{says}"
COWORKER_SOLVE = """#!/bin/bash
# The oracle for the requirement as `{value}` has it: the feature as the real project wrote it{more}, pushed to `main`.
set -e
cd /work/{owner} && git apply --binary --whitespace=nowarn /solution/{owner}.patch{apply}
git add -A -f && git commit -qm "The feature" && git push -q {oracle}/{owner}.git HEAD:main
"""


def coworker_people(company, tokens):
    """mined/<company>/people.toml as the people sidecar reads it."""
    import tomllib
    with open(mc.company_file(company, "people.toml"), "rb") as f:
        raw = tomllib.load(f)
    return {"default": raw["default"], "people": [
        {"name": p["name"], "role": p["role"], "about": p.get("about", ""), "token": tokens[p["name"]],
         "reply_delay_min": p.get("reply_delay_min", 0),
         "topics": [{k: t[k] for k in ("id", "kind", "topic", "says")} for t in p["topic"]]} for p in raw["person"]]}


def git_line_endings(tree: str) -> list:
    """Rewrites the files of a tree that git would store with other line endings than they have (the tree's own
    .gitattributes says `text=auto` and upstream committed some with CRLF), so that the task is the same bytes on
    disk, in this repository and in a clone of it: a freeze made here must verify there."""
    holder = tempfile.mkdtemp(prefix="harbor-eol-")
    env = dict(os.environ, GIT_DIR=os.path.join(holder, "git"), GIT_WORK_TREE=tree)
    run = lambda *args: subprocess.run(["git"] + list(args), check=True, capture_output=True, text=True, env=env, cwd=tree)
    run("init", "-q")
    run("add", "-A", "-f")
    changed = []
    for line in run("ls-files", "--eol").stdout.splitlines():
        state, name = line.split("\t", 1)
        if "i/lf" in state.split() and "w/crlf" in state.split():
            path = os.path.join(tree, name)
            with open(path, "rb") as f:
                data = f.read()
            with open(path, "wb") as f:
                f.write(data.replace(b"\r\n", b"\n"))
            changed.append(name)
    shutil.rmtree(holder, ignore_errors=True)
    return changed


def patch(start: str, clone: str, commit: str, keep: tuple) -> bytes:
    """The change from a repository's starting tree to the feature's commit, as one binary git patch."""
    holder = tempfile.mkdtemp(prefix="harbor-patch-")
    tree = os.path.join(holder, "tree")
    shutil.copytree(start, tree, symlinks=True)
    run = lambda *args: subprocess.run(["git", "-C", tree, "-c", "user.name=x", "-c", "user.email=x@example.com"] + list(args), check=True, capture_output=True)
    run("init", "-q")
    run("add", "-A", "-f")
    run("commit", "-qm", "start")
    for name in os.listdir(tree):
        if name not in keep + (".git",):
            path = os.path.join(tree, name)
            shutil.rmtree(path) if os.path.isdir(path) and not os.path.islink(path) else os.remove(path)
    export(clone, commit, tree)
    git_line_endings(tree)          # as the start was made: the patch must not carry line endings alone
    run("add", "-A", "-f")
    out = run("diff", "--cached", "--binary").stdout
    shutil.rmtree(holder, ignore_errors=True)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("company")
    ap.add_argument("--clone", action="append", default=[])
    ap.add_argument("--out")
    ap.add_argument("--team", action="store_true", help="a fixed team: one seat per owner, each pushing to its own repository only, and a chat sidecar")
    a = ap.parse_args()
    clones = dict(c.split("=", 1) for c in a.clone)
    info, repos = mc.load_company(a.company)
    out = os.path.abspath(a.out or os.path.join(REPO, "harbor", a.company + ("_team" if a.team else "")))
    # The task is made again from nothing, but its trajectories/ (the runs on it, outside the freeze) are kept.
    kept_runs = None
    if os.path.isdir(os.path.join(out, "trajectories")):
        kept_runs = tempfile.mkdtemp(prefix="harbor-trajectories-")
        shutil.move(os.path.join(out, "trajectories"), os.path.join(kept_runs, "trajectories"))
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    if kept_runs:
        shutil.move(os.path.join(kept_runs, "trajectories"), os.path.join(out, "trajectories"))
        shutil.rmtree(kept_runs, ignore_errors=True)
    env_dir, tests, solution = (os.path.join(out, d) for d in ("environment", "tests", "solution"))
    for d in (env_dir, os.path.join(tests, "hidden"), solution):
        os.makedirs(d)

    # ---- the checkouts, at the state the work starts from
    workspace = os.path.join(tempfile.mkdtemp(prefix="harbor-company-"), "ws")
    mc.prepare(a.company, clones, workspace)
    keep = {}
    for owner, repo in repos.items():
        tree = os.path.join(workspace, "services", owner)
        with open(os.path.join(tree, "NOTES.md")) as f:
            notes = notes_for_harbor(f.read())
        where = info.get("deployed", {})
        if owner in where:
            notes = notes.rstrip("\n") + "\n" + RUNNING.format(where=where[owner]["where"], checks=CI_CHECKS[mc.contract_type(info["contracts"][0])], others="".join(
                "- The other system, `{}`: {}\n".format(o, w["where"]) for o, w in where.items() if o != owner))
        with open(os.path.join(tree, "NOTES.md"), "w") as f:
            f.write(notes)
        for name in git_line_endings(tree):
            print("  line endings as git stores them: {}: {}".format(owner, name))
        shutil.copytree(tree, os.path.join(env_dir, "work", owner), symlinks=True)
        keep[owner] = ("NOTES.md", "INTERFACE.md") + tuple(repo.get("links", {}))

    # ---- the seat's image: the first repository's image, the others' toolchains copied in
    owners = list(repos)
    stages, copies = "".join(base_stage(owner, repos[owner]) for owner in owners), ""
    for owner in owners[1:]:
        if repos[owner].get("language") != "typescript":
            raise SystemExit("only a Node toolchain can be added to the seat's image so far ({})".format(owner))
        copies += NODE_COPIES.format(stage="base-" + owner) + "".join(
            TOOLCHAIN_COPY.format(stage="base-" + owner, path=path) for path in repos[owner].get("toolchain_paths", ["/deps"]))
    variables = {"CI": "true", "pnpm_config_verify_deps_before_run": "false", "NODE_PATH": "/deps/node_modules"}
    for owner in owners:
        variables.update(info.get("env", {}).get(owner, {}))
    with open(os.path.join(env_dir, "Dockerfile"), "w") as f:
        f.write(DOCKERFILE.format(stages=stages, first="base-" + owners[0], copies=copies, owners=" ".join(owners),
                                  env=" ".join("{}={}".format(k, v) for k, v in variables.items()), codex=CODEX_VERSION,
                                  browser=(info["business"].get("browser_install", BROWSER) if info.get("business") else "")))

    # ---- the sidecars: the git server, CI and deploy, and each system as last deployed from `main`
    shutil.copytree(os.path.join(REPO, "sidecars"), os.path.join(env_dir, "sidecars"), ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(os.path.join(REPO, "tools", "model_meter.py"), os.path.join(env_dir, "sidecars"))
    # the Harbor agents that run a seat and a fixed team with a stock harness, for whoever runs the task (see RUNNING.md)
    os.makedirs(os.path.join(out, "agents"), exist_ok=True)
    shutil.copy(os.path.join(REPO, "tools", "harbor_team.py"), os.path.join(out, "agents", "harbor_team.py"))
    for doc in ("RUNNING.md", "DATASHEET.md"):      # how to run it, and what it is (mined/<company>/)
        if os.path.isfile(mc.company_file(a.company, doc)):
            shutil.copy(mc.company_file(a.company, doc), os.path.join(out, doc))
    contract = info["contracts"][0]
    kind = mc.contract_type(contract)
    for where, name in CONTRACT_TOOLS[kind]:
        shutil.copy(os.path.join(REPO, where, name), os.path.join(env_dir, "sidecars"))
    deploy = info.get("deployed", {})
    everything = lambda level: {o: level for o in owners}
    # An isolated owner must not be able to work out another's token from its own, so each is a hash and not a pattern.
    import hashlib
    owner_token = lambda o: ("seat-{}-{}".format(o, hashlib.sha256("{}/{}/owner".format(a.company, o).encode()).hexdigest()[:12])
                             if info.get("isolated") else OWNER_TOKEN.format(o))
    tokens = dict(TOKENS, **({o: owner_token(o) for o in owners} if a.team else {}))
    coworker = info.get("coworker")
    if coworker:      # one seat, its owner's; the people are names on the chat, not on the git server
        if a.team:
            raise SystemExit("a coworker task has one seat: export it without --team")
        hashed = lambda who: hashlib.sha256("{}/{}/coworker".format(a.company, who).encode()).hexdigest()[:12]
        tokens[coworker["seat"]] = "seat-{}-{}".format(coworker["seat"], hashed(coworker["seat"]))
        people = coworker_people(a.company, {p: "person-{}-{}".format(p, hashed(p)) for p in coworker["people"]})
    access = {"tokens": tokens, "access": {"ci": everything("read"), "verifier": everything("read"), "oracle": everything("write")}}
    isolated = bool(a.team and info.get("isolated"))      # each owner has its own repository and cannot read the others'
    if isolated:
        access["access"].update({o: {o: "write"} for o in owners})
    elif a.team:    # each owner pushes to its own repository and reads the others: the same rule a solo agent's reading has
        access["access"].update({o: dict(everything("read"), **{o: "write"}) for o in owners})
    elif coworker:
        access["access"][coworker["seat"]] = {coworker["seat"]: "write"}
    else:
        access["access"]["solo"] = everything("write")
    git_url = lambda who: "http://{}:{}@git:8080".format(who, tokens[who])
    build = {"context": "."}
    services = {
        "git": {"build": build, "command": ["python3", "/opt/seedco/gitserver_start.py"], "environment": {"GIT_ACCESS": json.dumps(access)},
                "healthcheck": {"test": ["CMD-SHELL", "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/ | grep -q 401"],
                                "interval": "3s", "timeout": "5s", "retries": 40}},
        "ci": {"build": build, "command": ["python3", "/opt/seedco/ci.py"], "volumes": ["deployed:/deployed"],
               "environment": {"CI": json.dumps({"git": git_url("ci"), "repositories": owners, "start_timeout": info.get("ci_start_timeout", 600), "contract": dict(
                   {"type": kind, "provider": contract["provider"], "consumer": contract["consumer"], "url": contract["live_url"]},
                   **({"staff": ["admin@example.com", "admin"]} if kind == "graphql" else
                      {"ask": contract["ask"], "network": "/deployed/status/{}-network.json".format(contract["provider"])} if kind == "lexicon" else
                      {"ask": contract["ask"], "token": "/deployed/status/{}-token".format(contract["provider"])}))})},
               "depends_on": {"git": {"condition": "service_healthy"}},
               "healthcheck": {"test": ["CMD-SHELL", "curl -sf http://127.0.0.1:8080/ready > /dev/null"], "interval": "10s", "timeout": "8s", "retries": 90, "start_period": "600s"}},
    }
    # The model meter (tools/model_meter.py): a harness given http://meter:8318/seat/<seat> as its model service is
    # measured there, whichever harness it is. METER_UPSTREAM is where the meter passes requests on to.
    services["judge"] = {"build": build, "command": ["python3", "/opt/seedco/judge.py"], "volumes": ["${HOST_VERIFIER_LOGS_PATH:?Harbor 0.26: run with --ek auto_mounting=true, see RUNNING.md}/../judge:/judge-out"],
                         "environment": {"JUDGE": json.dumps({"token": JUDGE_TOKEN, "git": git_url("verifier"), "repositories": owners, "user": "scorer"})},
                         "depends_on": {"git": {"condition": "service_healthy"}},
                         "healthcheck": {"test": ["CMD-SHELL", "curl -sf http://127.0.0.1:8095/ready > /dev/null"], "interval": "5s", "timeout": "5s", "retries": 120}}
    services["meter"] = {"build": build, "command": ["python3", "/opt/seedco/model_meter.py", "${METER_UPSTREAM:-https://api.anthropic.com}", "/srv/meter", "8318"]}
    deployed = []
    for owner in owners:
        d = deploy[owner]
        services[owner] = {"build": build, "command": ["python3", "/opt/seedco/service.py", owner], "volumes": ["deployed:/deployed"],
                           "environment": dict(variables, SERVICE=json.dumps({k: d[k] for k in ("start", "prepare", "first") if k in d}), **d.get("env", {}))}
        deployed.append("- `{}`: {}".format(owner, d["where"]))
    # A stock harness needs the internet to be installed and to reach its model, so the seat cannot be cut off as
    # the kernel's containers are. The places the real feature could be fetched from are made unreachable by name.
    def seat(who):
        return {"depends_on": {"ci": {"condition": "service_healthy"}}, "extra_hosts": ["{}:0.0.0.0".format(h) for h in UNREACHABLE + tuple(info.get("unreachable", []))],
                "environment": dict({"SEAT": who, "SEAT_TOKEN": tokens[who], "TEAM": ",".join(owners) if a.team else ""},
                                    **({"SEAT_ONLY": who} if isolated else {}))}

    services["main"] = seat(owners[0] if a.team else coworker["seat"] if coworker else "solo")
    if coworker:
        variant = "${{VARIANT:-{}}}".format(coworker["variants"]["default"])      # set by whoever starts the run; the seat never has it
        services["main"]["environment"].update(SEAT_ONLY=coworker["seat"], TEAM=",".join([coworker["seat"]] + list(coworker["people"])))
        services["judge"]["environment"]["SEEDCO_VARIANT"] = variant
        services["chat"] = {"build": build, "command": ["python3", "/opt/seedco/chat.py"],
                            "environment": {"CHAT": json.dumps({"tokens": dict({coworker["seat"]: tokens[coworker["seat"]]}, **{p["name"]: p["token"] for p in people["people"]}),
                                                                "admin": CHAT_ADMIN, "clock": {"seat": coworker["seat"]}})}}
        # The people's sidecar asks a model what a message is about (sidecars/people.py). Where that model is and its key
        # come from whoever starts the run, and are in this container's environment only.
        services["people"] = {"build": build, "command": ["python3", "/opt/seedco/people.py"], "volumes": ["${HOST_VERIFIER_LOGS_PATH:?Harbor 0.26: run with --ek auto_mounting=true, see RUNNING.md}/../people:/people-out"],
                              "depends_on": {"chat": {"condition": "service_started"}}, "extra_hosts": ["host.docker.internal:host-gateway"],
                              "environment": {"SEEDCO_VARIANT": variant, "SEEDCO_REPLY_DELAY": "${REPLY_DELAY:-}",      # minutes; set by whoever starts the run
                                              "PEOPLE": json.dumps({"chat": "http://chat:8080", "file": "/opt/seedco/people.json", "out": "/people-out",
                                                                    "model": {"url": "${PEOPLE_MODEL_URL}", "key": "${PEOPLE_MODEL_KEY}", "id": coworker["model"]}})}}
        with open(os.path.join(env_dir, "sidecars", "people.json"), "w") as f:
            json.dump(people, f, indent=1)
    if a.team:      # the first owner sits at Harbor's own seat; every other owner gets one like it
        for owner in owners[1:]:
            services["seat-" + owner] = dict(seat(owner), build=build, command=["sleep", "infinity"], volumes=["${HOST_AGENT_LOGS_PATH:?Harbor 0.26: run with --ek auto_mounting=true, see RUNNING.md}/" + owner + ":/logs/agent"],
                                             deploy={"resources": {"limits": {"memory": SEAT_MEMORY}}})
        services["chat"] = {"build": build, "command": ["python3", "/opt/seedco/chat.py"],
                            "environment": {"CHAT": json.dumps({"tokens": {o: tokens[o] for o in owners}, "admin": CHAT_ADMIN})}}
    # One image for every container of the company: the git server's build names it, the others run it. Each service
    # building its own would keep as many copies of several gigabytes. (The seat's is Harbor's to build, from the same file.)
    image = "seedco-task-{}:1".format(a.company.replace("_", "-"))
    for name, service in services.items():
        if service.get("build") and name != "git":
            del service["build"]
            service.update(image=image, pull_policy="never")
            service.setdefault("depends_on", {}).setdefault("git", {"condition": "service_started"})
    services["git"]["image"] = image
    with open(os.path.join(env_dir, "docker-compose.yaml"), "w") as f:      # JSON is YAML
        f.write("# The company beside the agent's seat. Generated by tools/export_harbor_company.py.\n"
                + json.dumps({"services": services, "volumes": {"deployed": {}}}, indent=2) + "\n")

    # ---- what the agent is told
    with open(os.path.join(out, "instruction.md"), "w") as f:
        f.write(INSTRUCTION.format(feature=info["feature"], parts=mc.statement(info, repos), done=info["done"]))
    if coworker:
        coworker_seats(out, owners, coworker, people)
    seat_notes(out, owners, isolated=bool(info.get("isolated")))        # role, permissions, tools and budget: apart from the brief, which is the same for every condition
    with open(os.path.join(out, "task.toml"), "w") as f:
        f.write(TASK_TOML.format(slug=a.company.replace("_", "-") + ("-team" if a.team else ""), title=json.dumps(info["title"]), repositories=len(owners),
                                 source=json.dumps(info["source"]), memory=6144) + (MCP_TEAM if a.team or coworker else ""))

    # ---- the verifier: the scorer, the hidden tests, the test lists, the contract check
    config = {"owners": {}, "git": git_url("verifier"), "judge_token": JUDGE_TOKEN,
              "contract": dict(contract, usage="hidden/usage.json", **({"base_schema": "hidden/base_schema.graphql"} if kind == "graphql" else {}))}
    for owner, repo in repos.items():
        target = mc.target_commit(clones[owner], repo)
        laid = tempfile.mkdtemp(prefix="harbor-tests-")
        put(clones[owner], target, mc.changed_tests(clones[owner], repo), laid)
        fixes = mc.company_file(a.company, "test_fixes.py")      # reviewed fixes to how upstream's tests check
        if os.path.isfile(fixes):
            import importlib.util
            spec = importlib.util.spec_from_file_location("test_fixes_" + a.company, fixes)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            for fixed in module.apply(owner, laid):
                print("  hidden test fixed: {}: {}".format(owner, fixed))
        subprocess.run(["tar", "-czf", os.path.join(tests, "hidden", owner + "-tests.tar.gz"), "-C", laid, "."], check=True,
                       env=dict(os.environ, COPYFILE_DISABLE="1"))        # macOS tar would add a `._name` file beside every file
        shutil.rmtree(laid, ignore_errors=True)
        shutil.copy(os.path.join(REPO, "mined", info["owners"][owner]["task"], "reference.json"), os.path.join(tests, "hidden", owner + "-reference.json"))
        config["owners"][owner] = dict({"test_command": repo["test_command"], "report": repo.get("report", "junit"), "links": repo.get("links", {})},
                                       **{k: repo[k] for k in ("setup", "list_tests") if k in repo})
        change = patch(os.path.join(workspace, "services", owner), clones[owner], target, keep[owner])
        with open(os.path.join(solution, owner + ".patch"), "wb") as f:
            f.write(change)
        # files the feature itself removes: their going is no change to the tests by the work
        config["owners"][owner]["removed_by_feature"] = sorted(
            m.group(1).decode() for m in re.finditer(rb"^diff --git a/(\S+) b/\S+\ndeleted file mode", change, re.M))
    if kind == "graphql":
        mc._schema_at(clones[contract["provider"]], repos[contract["provider"]]["base"], contract, os.path.join(tests, "hidden", "base_schema.graphql"))
    shutil.copy(mc._usage_file(a.company, contract), os.path.join(tests, "hidden", "usage.json"))
    for where, name in CONTRACT_TOOLS[kind]:      # e.g. the schema the API serves is read by fetch_schema.cjs
        shutil.copy(os.path.join(REPO, where, name), tests)
    shutil.copy(os.path.join(REPO, "tools", "harbor_company_score.py"), os.path.join(tests, "score.py"))
    shutil.copy(os.path.join(REPO, "tools", "harbor_rubric.py"), os.path.join(tests, "rubric.py"))
    with open(mc.company_file(a.company, "rubric.toml")) as f, open(os.path.join(tests, "rubric.toml"), "w") as g:
        g.write("# GENERATED by tools/export_harbor_company.py from {}. Do not edit: change the source and export again.\n".format(
            os.path.relpath(mc.company_file(a.company, "rubric.toml"), REPO)) + f.read())
    if info.get("business"):      # the business outcome check, beside the reward: the two sides run together, in a browser
        shutil.copy(os.path.join(REPO, "tools", info["business"].get("driver", "harbor_business_check.py")), os.path.join(tests, "business.py"))
        shutil.copy(os.path.join(REPO, "tools", info["business"]["script"]), tests)
        config["business"] = {"roles": info["business"]["roles"], "script": info["business"]["script"]}
    with open(os.path.join(tests, "config.json"), "w") as f:
        json.dump(config, f, indent=2)
    scripts = [(os.path.join(tests, "test.sh"), TEST_SH.replace("{chat_admin}", CHAT_ADMIN)),
               (os.path.join(solution, "solve.sh"), SOLVE_SH.format(owners=" ".join(owners), oracle=git_url("oracle")))]
    if coworker:
        # Each value of the requirement: the tests that judge it (laid over the feature's), which of the feature's tests
        # they replace, and an oracle of its own. Upstream's patch is the oracle only for the value upstream built.
        variants, seat_owner = coworker["variants"], coworker["seat"]
        config["variants"] = {"requirement": variants["requirement"], "default": variants["default"], "values": {}}
        scripts = scripts[:1]
        for value, spec in variants["values"].items():
            config["variants"]["values"][value] = {o: {k: c[k] for k in ("remove", "add") if k in c} for o, c in spec.get("tests", {}).items()}
            source = os.path.join(REPO, "mined", a.company, "variants", value)
            for o in spec.get("tests", {}):
                laid = os.path.join(source, "tests", o)
                if os.path.isdir(laid):
                    os.makedirs(os.path.join(tests, "hidden", "variants", value), exist_ok=True)
                    subprocess.run(["tar", "-czf", os.path.join(tests, "hidden", "variants", value, o + "-tests.tar.gz"), "-C", laid, "."], check=True,
                                   env=dict(os.environ, COPYFILE_DISABLE="1"))
            apply = ""
            if os.path.isfile(os.path.join(source, seat_owner + ".patch")):
                os.makedirs(os.path.join(solution, "variants", value), exist_ok=True)
                shutil.copy(os.path.join(source, seat_owner + ".patch"), os.path.join(solution, "variants", value, seat_owner + ".patch"))
                apply = " && git apply --whitespace=nowarn /solution/variants/{}/{}.patch".format(value, seat_owner)
            scripts.append((os.path.join(solution, "solve.sh" if value == variants["default"] else "solve-{}.sh".format(value)),
                            COWORKER_SOLVE.format(value=value, owner=seat_owner, oracle=git_url("oracle"), apply=apply,
                                                  more=", with this value's change on top" if apply else "")))
        with open(os.path.join(tests, "config.json"), "w") as f:
            json.dump(config, f, indent=2)
    for path, text in scripts:
        with open(path, "w") as f:
            f.write(text)
        os.chmod(path, 0o755)
    shutil.rmtree(os.path.dirname(workspace), ignore_errors=True)
    size = sum(os.path.getsize(os.path.join(d, f)) for d, _, files in os.walk(out) for f in files if not os.path.islink(os.path.join(d, f)))
    print("{}: {} repositories, {:,.0f} MB".format(os.path.relpath(out, REPO), len(owners), size / 1e6))


if __name__ == "__main__":
    main()

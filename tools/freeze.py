"""Freezes a Harbor task: what agents are told and what judges them, so that runs can be compared.

    python3 tools/freeze.py freeze <task dir> [...]     writes <task dir>/FROZEN.json
    python3 tools/freeze.py verify <task dir> [...]     exits 1, naming what changed, if anything is not as frozen

Frozen is every file of the task (the brief, the seat notes, the environment, the verifier and what it reads,
the oracle), the two files that run it (tools/harbor_team.py, tools/harbor_harness.sh), and the images the
environment is built from. Task-root trajectories/ holds past run outputs and is excluded.
The id of a freeze is the hash of all of that; tools/harbor_harness.sh writes it into
each run it starts and refuses to start a run on a task that is not as frozen.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNERS = ("tools/harbor_team.py", "tools/harbor_harness.sh")


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def state(task):
    files = {}
    for d, dirs, names in os.walk(task):
        dirs[:] = sorted(x for x in dirs if x != "__pycache__")
        if d == task and "trajectories" in dirs:
            dirs.remove("trajectories")
        for name in sorted(names):
            path = os.path.join(d, name)
            if name != "FROZEN.json" and not os.path.islink(path):
                files[os.path.relpath(path, task)] = digest(path)
    runners = {r: digest(os.path.join(REPO, r)) for r in RUNNERS}
    images = {}
    dockerfile = os.path.join(task, "environment", "Dockerfile")
    if os.path.isfile(dockerfile):
        with open(dockerfile) as f:
            for image in re.findall(r"^FROM (\S+)", f.read(), re.M):
                found = subprocess.run(["docker", "image", "inspect", "-f", "{{.Id}}", image], capture_output=True, text=True)
                images[image] = found.stdout.strip() or "not here"
    whole = json.dumps([files, runners, images], sort_keys=True).encode()
    return {"id": hashlib.sha256(whole).hexdigest()[:16], "files": files, "runners": runners, "images": images}


def main():
    what, tasks = sys.argv[1], sys.argv[2:]
    bad = 0
    for task in tasks:
        now, path = state(task), os.path.join(task, "FROZEN.json")
        if what == "freeze":
            with open(path, "w") as f:
                json.dump(dict(now, frozen_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())), f, indent=1)
            print("{}: frozen as {} ({} files)".format(task, now["id"], len(now["files"])))
            continue
        if not os.path.isfile(path):
            print("{}: not frozen".format(task))
            bad = 1
            continue
        with open(path) as f:
            was = json.load(f)
        changed = [k + " " + name for k in ("files", "runners", "images") for name in sorted(set(was[k]) | set(now[k])) if was[k].get(name) != now[k].get(name)]
        if changed:
            bad = 1
            print("{}: not as frozen ({}):\n  {}".format(task, was["id"], "\n  ".join(changed[:20])))
        else:
            print("{}: as frozen {}".format(task, was["id"]))
    sys.exit(bad)


if __name__ == "__main__":
    main()

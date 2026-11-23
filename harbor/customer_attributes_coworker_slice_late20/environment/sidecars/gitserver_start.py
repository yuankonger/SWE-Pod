"""Starts the company's git server in its sidecar: one bare repository per checkout under /work, then the server.

Who may read and push what comes from GIT_ACCESS: {"tokens": {name: token}, "access": {name: {repository: "read" | "write"}}}.
"""
import json
import os
import subprocess

ROOT = "/srv/git"
os.makedirs(ROOT, exist_ok=True)
for name in sorted(os.listdir("/work")):
    if os.path.isdir(os.path.join("/work", name, ".git")) and not os.path.isdir(os.path.join(ROOT, name + ".git")):
        subprocess.run(["git", "clone", "-q", "--bare", os.path.join("/work", name), os.path.join(ROOT, name + ".git")], check=True)
        # what is pushed adds to the history: it cannot rewrite it, nor delete a branch
        for key in ("receive.denyNonFastForwards", "receive.denyDeletes"):
            subprocess.run(["git", "-C", os.path.join(ROOT, name + ".git"), "config", key, "true"], check=True)
with open("/srv/access.json", "w") as f:
    json.dump(json.loads(os.environ["GIT_ACCESS"]), f)
open("/srv/log.jsonl", "a").close()
os.execvp("python3", ["python3", os.path.join(os.path.dirname(os.path.abspath(__file__)), "gitserver_app.py"), ROOT, "/srv/access.json", "/srv/log.jsonl", "8080"])

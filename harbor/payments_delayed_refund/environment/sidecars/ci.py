"""The company's CI and deploy, in its sidecar.

Watches `main` of every repository on the git server. When one moves it deploys that repository (writes the tree
to /deployed/<name>, which the system's own sidecar restarts from), waits for the system to come up, then tests
the systems together as they now run, and keeps the result. Anyone on the company's network can read it:

    http://ci:8080/              the latest run, as text
    http://ci:8080/runs          every run, newest first, as text
    http://ci:8080/status.json   the same as JSON
    http://ci:8080/ready         200 once the first run is done

What a run checks is what the company can see of itself, not what a feature is supposed to add:
    deploy <name>      the system started from the new commit (for the API that includes its database migration)
    <provider> serves  the API answers a query
    <consumer> calls   every GraphQL operation in the consumer's source is valid against the schema the running
                       API really has (not against the consumer's own copy of it)

CI = {"git": "http://name:token@git:8080", "repositories": [...], "contract": {"provider", "consumer", "url"},
      "serves": {name: url}}
`contract` and `serves` are each optional. `serves`: a system that must answer 200 at its URL after a deploy.
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CONFIG = json.loads(os.environ["CI"])
HERE = os.path.dirname(os.path.abspath(__file__))
CLONES, DEPLOYED, SCRATCH = "/srv/ci/clones", "/deployed", "/srv/ci/scratch"
START_TIMEOUT_S = 600
runs, lock = [], threading.Lock()


def sh(args, cwd=None, timeout=600, env=None):
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
        return p.returncode, (p.stdout + p.stderr)
    except subprocess.TimeoutExpired:
        return 124, "timed out"


def head(repository):
    code, out = sh(["git", "ls-remote", "{}/{}.git".format(CONFIG["git"], repository), "refs/heads/main"], timeout=60)
    return out.split()[0] if code == 0 and out.strip() else None


def deploy(repository, commit):
    """Puts the commit's tree where the system's sidecar runs it from. Returns (ok, what went wrong)."""
    clone = os.path.join(CLONES, repository)
    if not os.path.isdir(clone):
        code, out = sh(["git", "clone", "-q", "--bare", "{}/{}.git".format(CONFIG["git"], repository), clone])
    else:
        code, out = sh(["git", "-C", clone, "fetch", "-q", "origin", "+refs/heads/main:refs/heads/main"])
    if code != 0:
        return False, out[-1500:]
    new, live, old = (os.path.join(DEPLOYED, repository + suffix) for suffix in (".new", "", ".old"))
    shutil.rmtree(new, ignore_errors=True)
    os.makedirs(new)
    archive = subprocess.Popen(["git", "-C", clone, "archive", commit], stdout=subprocess.PIPE)
    done = subprocess.run(["tar", "-x", "-C", new], stdin=archive.stdout)
    if archive.wait() != 0 or done.returncode != 0:
        return False, "could not read the commit's tree"
    shutil.rmtree(old, ignore_errors=True)
    if os.path.isdir(live):
        os.rename(live, old)
    os.rename(new, live)
    shutil.rmtree(old, ignore_errors=True)
    with open(os.path.join(DEPLOYED, repository + ".version.tmp"), "w") as f:
        f.write(commit)
    os.replace(os.path.join(DEPLOYED, repository + ".version.tmp"), os.path.join(DEPLOYED, repository + ".version"))
    return True, ""


def started(repository, commit):
    """Waits for the system's sidecar to say what became of the commit. Returns (ok, its log if not)."""
    path = os.path.join(DEPLOYED, "status", repository + ".json")
    deadline = time.time() + START_TIMEOUT_S
    while time.time() < deadline:
        try:
            with open(path) as f:
                status = json.load(f)
        except (OSError, ValueError):
            status = {}
        if status.get("version") == commit and status.get("state") == "running":
            return True, ""
        if status.get("version") == commit and status.get("state") == "failed":
            return False, "{} failed:\n{}".format(status.get("step"), status.get("log", ""))
        time.sleep(2)
    return False, "did not start within {} seconds".format(START_TIMEOUT_S)


def answers(url, tries=40):
    body = json.dumps({"query": "{ __typename }"}).encode()
    for _ in range(tries):
        try:
            request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=8) as r:
                if r.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(3)
    return False


def reachable(url, tries=40):
    for _ in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=8) as r:
                if r.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(3)
    return False


def together(contract):
    """The systems tested against each other as they run now. Returns the checks: [{name, ok, detail}]."""
    provider, consumer, url = contract["provider"], contract["consumer"], contract["url"]
    checks = []
    up = answers(url)
    checks.append({"name": provider + " serves", "ok": up, "detail": "" if up else "no answer at {}".format(url)})
    if not up:
        checks.append({"name": consumer + " calls", "ok": False, "detail": "not checked: the API does not answer"})
        return checks
    os.makedirs(SCRATCH, exist_ok=True)
    schema, found = os.path.join(SCRATCH, "live.graphql"), os.path.join(SCRATCH, "calls.json")
    env = dict(os.environ, NODE_PATH="/deps/node_modules")
    code, out = sh(["node", os.path.join(HERE, "fetch_schema.cjs"), url, schema], env=env, timeout=120)
    if code != 0:
        checks.append({"name": consumer + " calls", "ok": False, "detail": "could not read the API's schema: " + out[-500:]})
        return checks
    if os.path.isfile(found):
        os.remove(found)
    code, out = sh(["node", os.path.join(HERE, "mined_graphql_agreement.cjs"), schema, os.path.join(DEPLOYED, consumer), found], env=env, timeout=300)
    if not os.path.isfile(found):
        checks.append({"name": consumer + " calls", "ok": False, "detail": "could not read the operations: " + out[-800:]})
        return checks
    with open(found) as f:
        result = json.load(f)
    bad = result["invalid"]
    detail = "{} of {} operations valid against the running API".format(result["valid"], result["operations"])
    if bad:
        detail += "\n" + "\n".join("  {}: {}".format(name, "; ".join(errors)) for name, errors in sorted(bad.items())[:40])
    if result.get("unreadable"):
        detail += "\n  files that could not be read: " + ", ".join(sorted(result["unreadable"]))
    checks.append({"name": consumer + " calls", "ok": not bad and not result.get("unreadable") and result["operations"] > 0, "detail": detail})
    return checks


def run(heads, moved):
    record = {"id": len(runs) + 1, "started": time.strftime("%H:%M:%S"), "commits": dict(heads), "moved": moved, "state": "running", "checks": [], "started_at": round(time.time(), 1)}
    with lock:
        runs.append(record)
    for repository in moved:
        ok, why = deploy(repository, heads[repository])
        if ok:
            ok, why = started(repository, heads[repository])
        record["checks"].append({"name": "deploy " + repository, "ok": ok, "detail": why})
    if CONFIG.get("contract"):
        record["checks"] += together(CONFIG["contract"])
    for name, url in (CONFIG.get("serves") or {}).items():
        up = reachable(url)
        record["checks"].append({"name": name + " serves", "ok": up, "detail": "" if up else "no answer at {}".format(url)})
    record["state"] = "passed" if all(c["ok"] for c in record["checks"]) else "failed"
    record["finished"] = time.strftime("%H:%M:%S")
    record["finished_at"] = round(time.time(), 1)


def text(record):
    lines = ["run {} {} (started {}{}): {}".format(
        record["id"], record["state"].upper(), record["started"], ", finished " + record["finished"] if record.get("finished") else "",
        ", ".join("{} at {}{}".format(r, c[:10], " (new)" if r in record["moved"] else "") for r, c in sorted(record["commits"].items())))]
    for check in record["checks"]:
        lines.append("  [{}] {}".format("ok" if check["ok"] else "FAILED", check["name"]))
        lines += ["      " + line for line in (check["detail"] or "").splitlines()]
    return "\n".join(lines)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        with lock:
            kept = list(runs)
        finished = [r for r in kept if r["state"] != "running"]
        if self.path.startswith("/ready"):
            code, body, kind = (200, "ready\n", "text/plain") if finished else (503, "the first run is not done\n", "text/plain")
        elif self.path.startswith("/status.json"):
            code, body, kind = 200, json.dumps({"runs": kept[::-1]}), "application/json"
        elif self.path.startswith("/runs"):
            code, body, kind = 200, "\n\n".join(text(r) for r in kept[::-1]) + "\n", "text/plain"
        else:
            code, body, kind = 200, (text(kept[-1]) if kept else "no run yet") + "\n\nEvery run: /runs    As JSON: /status.json\n", "text/plain"
        self.send_response(code)
        self.send_header("Content-Type", kind + "; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())


def main():
    for d in (CLONES, os.path.join(DEPLOYED, "status")):
        os.makedirs(d, exist_ok=True)
    threading.Thread(target=ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever, daemon=True).start()
    seen = {}
    while True:
        heads = {r: head(r) for r in CONFIG["repositories"]}
        if all(heads.values()):
            moved = [r for r in CONFIG["repositories"] if heads[r] != seen.get(r)]
            if moved:
                try:
                    run(heads, moved)
                except Exception as e:      # a run that breaks is a failed run, and the loop goes on
                    runs[-1].update(state="failed", finished=time.strftime("%H:%M:%S"))
                    runs[-1]["checks"].append({"name": "ci", "ok": False, "detail": "{}: {}".format(type(e).__name__, e)})
                seen = heads
        time.sleep(5)


if __name__ == "__main__":
    sys.exit(main())

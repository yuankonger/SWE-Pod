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
    <provider> answers what it gained   the API asked, as staff, for the fields it gained since CI first saw it
                       (sidecars/smoke_new_fields.cjs): an error in a resolver fails it
A `lexicon` contract (Bluesky) is checked instead by
    <provider> answers   the AppView, asked through the PDS as a seeded account (the network's status file, written
                       by bsky_seed.mjs: the PDS's URL, the AppView's DID, the accounts), answers the contract's `ask`
                       methods with 200
    <consumer> calls     every AppView method the consumer's code calls is one the deployed AppView serves, read from
                       both deployed sources (mined_lexicon_contract.py). Methods the consumer called at CI's first run
                       that the AppView did not serve then are taken as another service's (the PDS's, chat's)
    <consumer> copies    every lexicon the consumer vendors that the AppView has states what the AppView has; those
                       that differed at CI's first run are left out
A `websocket` contract (Home Assistant) is checked instead by
    <provider> answers   Home Assistant, asked as its owner over its WebSocket API (the token the provider's sidecar
                       wrote, `token`), answers the contract's `ask` commands
    <consumer> calls     every command the consumer sends is one the provider registers, read from the provider's
                       deployed source (mined_ws_contract.py, mined_ws_agreement.cjs). Commands the consumer sent at
                       CI's first run that could not be found then are taken as registered in a way that cannot be read
    <consumer> reads what <provider> answers   every entry the provider returned has every field the consumer's own
                       types for that answer require

CI = {"git": "http://name:token@git:8080", "repositories": [...], "contract": {"provider", "consumer", "url", "staff": [email, password]}
      (or {"type": "websocket", "provider", "consumer", "url", "ask": [commands], "token": file},
       or {"type": "lexicon", "provider", "consumer", "url", "network": status file, "ask": [methods]}),
      "serves": {name: url}}
"systems": {repository: [the systems it holds]} where a repository holds more than the one of its own name.
`contract` and `serves` are each optional. `serves`: a system that must answer 200 at its URL after a deploy.
"start_timeout": seconds a deployed system has to start (600 by default).
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CONFIG = json.loads(os.environ["CI"])
HERE = os.path.dirname(os.path.abspath(__file__))
CLONES, DEPLOYED, SCRATCH = "/srv/ci/clones", "/deployed", "/srv/ci/scratch"
START_TIMEOUT_S = CONFIG.get("start_timeout", 600)      # a system that builds another's output first takes longer
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


def together_websocket(contract):
    """Home Assistant and its frontend tested against each other as they run now. Returns the checks."""
    provider, consumer, url = contract["provider"], contract["consumer"], contract["url"]
    os.makedirs(SCRATCH, exist_ok=True)
    answers_file, commands, found = (os.path.join(SCRATCH, n) for n in ("answers.json", "commands.json", "calls.json"))
    for path in (answers_file, found):
        if os.path.isfile(path):
            os.remove(path)
    for _ in range(60):      # the provider's sidecar writes the owner's token once it has onboarded Home Assistant
        if os.path.isfile(contract["token"]):
            break
        time.sleep(3)
    code, out = sh(["python3", os.path.join(HERE, "ha_seed.py"), "ask", url, contract["token"], answers_file] + [json.dumps(a) for a in contract["ask"]], timeout=300)
    asked = json.load(open(answers_file)) if os.path.isfile(answers_file) else {}
    failed = {t: a["error"] for t, a in asked.items() if not a["success"]}
    up = code == 0 and asked and not failed
    checks = [{"name": provider + " answers", "ok": bool(up), "detail": out.strip()[-800:] if not up else "answers " + ", ".join(asked)}]
    if not up:
        checks.append({"name": consumer + " calls", "ok": False, "detail": "not checked: {} does not answer".format(provider)})
        return checks
    code, out = sh(["python3", "-I", os.path.join(HERE, "mined_ws_contract.py"), os.path.join(DEPLOYED, provider), commands], timeout=300)
    if code != 0:
        checks.append({"name": consumer + " calls", "ok": False, "detail": "could not read the commands {} registers: {}".format(provider, out[-500:])})
        return checks
    baseline = os.path.join(CLONES, "..", "ws-baseline.json")
    args = ["node", os.path.join(HERE, "mined_ws_agreement.cjs"), os.path.join(DEPLOYED, consumer), commands, answers_file, found]
    code, out = sh(args + (["--ignore", baseline] if os.path.isfile(baseline) else []), env=dict(os.environ, NODE_PATH="/deps/node_modules"), timeout=600)
    if not os.path.isfile(found):
        checks.append({"name": consumer + " calls", "ok": False, "detail": "could not read the frontend's commands: " + out[-800:]})
        return checks
    with open(found) as f:
        result = json.load(f)
    if not os.path.isfile(baseline):      # the first run: what could not be found then is what this check cannot read
        with open(baseline, "w") as f:
            json.dump(sorted(result["invalid"]), f)
        result.update(invalid={}, valid=result["operations"] - sum(len(v) for v in result["invalid"].values()))
    bad = result["invalid"]
    detail = "{} of {} places that send a command name one {} registers".format(result["operations"] - sum(len(v) for v in bad.values()), result["operations"], provider)
    if bad:
        detail += "\n" + "\n".join("  {}: {}".format(t, ", ".join(places[:5])) for t, places in sorted(bad.items())[:40])
    checks.append({"name": consumer + " calls", "ok": not bad and result["operations"] > 0, "detail": detail})
    misfits = {t: p for t, p in result["payloads"].items() if p.get("share", 1) < 1}
    detail = "; ".join("{}: {} of {} entries have every field the {} types require".format(t, p.get("matched"), p.get("entries"), consumer) for t, p in result["payloads"].items())
    for t, p in misfits.items():
        detail += "\n" + "\n".join("  {} ({}): missing {}".format(u.get("name"), u.get("id"), ", ".join(u["missing"])) for u in p.get("unmatched", []))
    checks.append({"name": "{} reads what {} answers".format(consumer, provider), "ok": not misfits, "detail": detail})
    return checks


def together_lexicon(contract):
    """The AppView and the app tested against each other as they run now. Returns the checks."""
    provider, consumer = contract["provider"], contract["consumer"]
    os.makedirs(SCRATCH, exist_ok=True)
    status = {}
    for _ in range(100):      # the provider's sidecar writes the network's status once it has started and seeded it
        try:
            with open(contract["network"]) as f:
                status = json.load(f)
            break
        except (OSError, ValueError):
            time.sleep(3)
    pds = contract["url"]      # the PDS, by the provider's name on the company's network
    asked, detail = {}, "the network's status ({}) was not written".format(contract["network"])
    if status:
        try:
            account = status["accounts"]["alice"]
            body = json.dumps({"identifier": account["handle"], "password": account["password"]}).encode()
            request = urllib.request.Request(pds + "/xrpc/com.atproto.server.createSession", data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=20) as r:
                session = json.load(r)
            for method in contract["ask"]:
                request = urllib.request.Request("{}/xrpc/{}".format(pds, method), headers={
                    "Authorization": "Bearer " + session["accessJwt"], "atproto-proxy": status["appviewDid"] + "#bsky_appview"})
                try:
                    with urllib.request.urlopen(request, timeout=30) as r:
                        asked[method] = r.status
                except urllib.error.HTTPError as e:
                    asked[method] = "{} {}".format(e.code, e.read()[:300].decode(errors="replace"))
            detail = ", ".join("{}: {}".format(m, a) for m, a in asked.items())
        except (OSError, ValueError, KeyError) as e:
            detail = "could not sign in to the PDS as a seeded account: {}".format(e)
    up = bool(asked) and all(a == 200 for a in asked.values())
    checks = [{"name": provider + " answers", "ok": up, "detail": detail}]
    tool = os.path.join(HERE, "mined_lexicon_contract.py")
    read = {}
    for side, owner in (("provider", provider), ("consumer", consumer)):
        out_file = os.path.join(SCRATCH, side + "-lexicons.json")
        code, out = sh(["python3", "-I", tool, side, os.path.join(DEPLOYED, owner), out_file], timeout=300)
        if code != 0:
            checks.append({"name": consumer + " calls", "ok": False, "detail": "could not read {}'s source: {}".format(owner, out[-500:])})
            return checks
        with open(out_file) as f:
            read[side] = json.load(f)
    served, calls = set(read["provider"]["served"]), read["consumer"]["calls"]
    theirs, mine = read["provider"]["schemas"], read["consumer"]["schemas"]
    differ = sorted(n for n in mine if n in theirs and mine[n] != theirs[n])
    baseline = os.path.join(CLONES, "..", "lexicon-baseline.json")
    if not os.path.isfile(baseline):      # the first run: what was not served, or differed, then is no part of this work
        with open(baseline, "w") as f:
            json.dump({"elsewhere": sorted(n for n in calls if n not in served), "differ": differ}, f)
    with open(baseline) as f:
        known = json.load(f)
    unserved = {n: calls[n] for n in calls if n not in served and n not in known["elsewhere"]}
    detail = "{} of {} AppView methods the app calls are ones {} serves".format(
        sum(1 for n in calls if n in served), sum(1 for n in calls if n not in known["elsewhere"]), provider)
    if unserved:
        detail += "\n" + "\n".join("  {}: {}".format(n, ", ".join(f[:5])) for n, f in sorted(unserved.items())[:40])
    checks.append({"name": consumer + " calls", "ok": not unserved, "detail": detail})
    stale = [n for n in differ if n not in known["differ"]]
    missing = [n for n in contract["ask"] if n in theirs and n not in mine]
    checks.append({"name": consumer + " copies", "ok": not stale and not missing,
                   "detail": "vendored copies that differ from {}'s: {}; asked-for lexicons not vendored: {}".format(provider, ", ".join(stale) or "none", ", ".join(missing) or "none")})
    return checks


def together(contract):
    """The systems tested against each other as they run now. Returns the checks: [{name, ok, detail}]."""
    if contract.get("type") == "websocket":
        return together_websocket(contract)
    if contract.get("type") == "lexicon":
        return together_lexicon(contract)
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
    if result.get("collisions"):
        detail += "\n  fragments defined twice, differently: " + ", ".join(sorted(result["collisions"]))
    checks.append({"name": consumer + " calls", "ok": not bad and not result.get("unreadable") and not result.get("collisions") and result["operations"] > 0, "detail": detail})
    checks.append(answers_what_it_gained(provider, url, schema, contract.get("staff")))
    return checks


def answers_what_it_gained(provider, url, schema, staff):
    """The API asked, as staff, for what it gained since CI first saw it (sidecars/smoke_new_fields.cjs): an error in a
    resolver fails the check. The schema CI first saw is kept as the baseline."""
    name, baseline = provider + " answers what it gained", os.path.join(CLONES, "..", "baseline.graphql")
    if not os.path.isfile(baseline):
        shutil.copy(schema, baseline)
    token = None
    if staff:
        body = json.dumps({"query": "mutation($e: String!, $p: String!) { tokenCreate(email: $e, password: $p) { token } }",
                           "variables": {"e": staff[0], "p": staff[1]}}).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}), timeout=20) as r:
                token = ((json.loads(r.read()).get("data") or {}).get("tokenCreate") or {}).get("token")
        except OSError:
            pass
    found = os.path.join(SCRATCH, "gained.json")
    if os.path.isfile(found):
        os.remove(found)
    code, out = sh(["node", os.path.join(HERE, "smoke_new_fields.cjs"), url, baseline, found] + (["--token", token] if token else []),
                   env=dict(os.environ, NODE_PATH="/deps/node_modules"), timeout=300)
    if not os.path.isfile(found):
        return {"name": name, "ok": False, "detail": "could not ask: " + out[-500:]}
    with open(found) as f:
        result = json.load(f)
    detail = "{} gained fields; asked through {} queries{}".format(result["gained"], len(result["asked"]), "" if token else " (not signed in as staff)")
    if result["failures"]:
        detail += "\n" + "\n".join("  {}: {}".format(e["field"], e["message"]) for e in result["failures"][:20])
    return {"name": name, "ok": not result["failures"], "detail": detail}


def run(heads, moved):
    record = {"id": len(runs) + 1, "started": time.strftime("%H:%M:%S"), "commits": dict(heads), "moved": moved, "state": "running", "checks": [], "started_at": round(time.time(), 1)}
    with lock:
        runs.append(record)
    for repository in moved:
        ok, why = deploy(repository, heads[repository])
        if ok:
            ok, why = True, ""
            for system in (CONFIG.get("systems") or {}).get(repository, [repository]):      # every system the repository holds
                ok, why = started(system, heads[repository])
                if not ok:
                    why = "{}: {}".format(system, why)
                    break
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

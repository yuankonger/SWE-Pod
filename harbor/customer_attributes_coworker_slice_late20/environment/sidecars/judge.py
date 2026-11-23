"""The company's judge, in a container of its own: it scores the work where the work never ran.

    python3 judge.py

The verifier Harbor runs is in the agent's seat, a container the agent had to itself for hours. Nothing that runs
there can be trusted to judge: its interpreter, its packages, its shell start-up files, its processes are all the
agent's to change. So the seat's tests/test.sh only hands the task's tests to this judge and takes back the result.

The judge is started with the company, from the same image as every other container, and nobody works in it. It
keeps the commit every repository is at as the company starts (the start the work is judged from, whatever the
history of `main` says later). When it is asked, it runs the task's scorer (tests/score.py) as root, against `main`
of the git server, with SEEDCO_SCORER set: the scorer runs everything of the work's own code as an unprivileged user.

    POST /judge?token=<t>      body: the task's tests/ as a gzipped tar. Starts scoring; 409 if it already is.
    GET  /status?token=<t>     {"state": "idle" | "scoring" | "done" | "failed", "started", "finished", "detail"}
    GET  /result?token=<t>     what the scorer wrote (reward.txt, score.json, rubric.txt, ...) as a gzipped tar

JUDGE = {"token": t, "git": "http://verifier:<token>@git:8080", "repositories": [...], "user": "scorer"}
The token is in the task's tests/config.json and in this container's environment, neither of which the seat has.

The seat's test.sh copies the result into the verifier's folder, which is what Harbor reads. But test.sh runs in the
seat, whose programs the agent could have replaced. So the judge also writes its result itself into /judge-out, the
trial's judge/ folder on the host, which is mounted here and in no seat. That copy is the one to trust; a verifier
folder that says otherwise was written by something in the seat.
Standard library only.
"""
import io
import json
import os
import shutil
import subprocess
import tarfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

CONFIG = json.loads(os.environ["JUDGE"])
ROOT = "/srv/judge"
TESTS, OUT, START = ROOT + "/tests", ROOT + "/out", ROOT + "/start.json"
KEPT = "/judge-out"      # mounted from the trial's judge/ folder on the host, where Harbor runs the task
state = {"state": "idle"}
lock = threading.Lock()


def heads():
    found = {}
    for r in CONFIG["repositories"]:
        out = subprocess.run(["git", "ls-remote", "{}/{}.git".format(CONFIG["git"], r), "refs/heads/main"], capture_output=True, text=True).stdout.split()
        if out:
            found[r] = out[0]
    return found


def keep_start():
    """The commit each repository is at as the company starts: the git server is asked until it says, once."""
    while not os.path.isfile(START):
        found = heads()
        if len(found) == len(CONFIG["repositories"]):
            with open(START + ".tmp", "w") as f:
                json.dump(found, f)
            os.replace(START + ".tmp", START)
            print("start:", found, flush=True)
            return
        time.sleep(3)


def score():
    started = time.time()
    try:
        env = dict(os.environ, SEEDCO_SCORER=CONFIG.get("user", "scorer"), SEEDCO_START=START, PATH="/venv/bin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
        env.pop("JUDGE", None)
        with open(os.path.join(OUT, "judge.log"), "w") as log:
            done = subprocess.run(["/venv/bin/python", "-I", os.path.join(TESTS, "score.py"), TESTS, "/work", OUT], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        user = CONFIG.get("user", "scorer")
        subprocess.run(["pkill", "-9", "-u", user], capture_output=True)
        if os.path.isdir(KEPT):      # the trial's own folder for the judge, which no seat has: the result to trust
            for name in os.listdir(KEPT):
                path = os.path.join(KEPT, name)
                shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
            shutil.copytree(OUT, KEPT, dirs_exist_ok=True)
        with lock:
            state.update(state="done" if os.path.isfile(os.path.join(OUT, "reward.txt")) else "failed", finished=round(time.time(), 1),
                         seconds=round(time.time() - started), detail="" if done.returncode == 0 else "the scorer ended with {}".format(done.returncode))
    except Exception as e:
        with lock:
            state.update(state="failed", finished=round(time.time(), 1), detail="{}: {}".format(type(e).__name__, e)[:500])


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, code, body, kind="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def allowed(self):
        return (parse_qs(urlparse(self.path).query).get("token") or [""])[0] == CONFIG["token"]

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/ready":
            return self.reply(200 if os.path.isfile(START) else 503, {"start": os.path.isfile(START)})
        if not self.allowed():
            return self.reply(403, {"error": "not for you"})
        if path == "/status":
            with lock:
                return self.reply(200, state)
        if path == "/result":
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w:gz") as t:
                t.add(OUT, arcname=".")
            return self.reply(200, buf.getvalue(), "application/gzip")
        self.reply(404, {"error": "no such thing"})

    def do_POST(self):
        if urlparse(self.path).path != "/judge" or not self.allowed():
            return self.reply(403, {"error": "not for you"})
        if not os.path.isfile(START):
            return self.reply(503, {"error": "the start of the work is not known yet"})
        with lock:
            if state["state"] == "scoring":
                return self.reply(409, state)
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            for d in (TESTS, OUT):
                shutil.rmtree(d, ignore_errors=True)
                os.makedirs(d)
            with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as t:
                t.extractall(TESTS, filter="data")
            os.chmod(TESTS, 0o700)      # the hidden tests and the reference are root's: the work's code, run as the scorer user, cannot read them
            state.clear()
            state.update(state="scoring", started=round(time.time(), 1))
        threading.Thread(target=score, daemon=True).start()
        self.reply(202, state)


if __name__ == "__main__":
    os.makedirs(ROOT, exist_ok=True)
    os.chmod(ROOT, 0o755)
    threading.Thread(target=keep_start, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", 8095), Handler).serve_forever()

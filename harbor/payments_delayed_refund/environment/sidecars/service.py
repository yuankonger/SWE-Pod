"""Runs one of the company's systems in its sidecar, as CI and deploy last put it there.

    python3 service.py <name>

The deploy sidecar writes the system's tree to /deployed/<name> and then the commit it is at to
/deployed/<name>.version. This loop notices a new version, stops the system, runs its `prepare` command (a
database migration, say), once ever its `first` command (sample data), and starts it again. What happened is
written to /deployed/status/<name>.json, where the CI sidecar reads it. A system that stops by itself is started
again. SERVICE = {"start": command, "prepare": command, "first": command}, all optional but `start`.

With LOGS = {"port": N, "tokens": [...]} the system's own output can be read by whoever holds one of the tokens:
    GET /log?token=<token>&lines=N     the last N lines (default 200)
    GET /version                       for anyone: {"version": the commit it runs, "state": ...}, as the system last said
"""
import json
import os
import signal
import subprocess
import sys
import time

NAME = sys.argv[1]
SPEC = json.loads(os.environ["SERVICE"])
TREE, VERSION, STATUS = "/deployed/" + NAME, "/deployed/{}.version".format(NAME), "/deployed/status/{}.json".format(NAME)
LOG = "/tmp/{}.log".format(NAME)


def serve_log():
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import parse_qs, urlparse
    spec = json.loads(os.environ["LOGS"])

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            q = parse_qs(urlparse(self.path).query)
            if urlparse(self.path).path == "/version":      # for anyone: the commit this system runs, and how it fares
                try:
                    with open(STATUS) as f:
                        code, body = 200, f.read()
                except OSError:
                    code, body = 200, "{}"
            elif (q.get("token") or [""])[0] not in spec["tokens"]:
                code, body = 403, "this log is not yours to read\n"
            else:
                try:
                    with open(LOG, errors="replace") as f:
                        code, body = 200, "".join(f.readlines()[-int((q.get("lines") or ["200"])[0]):])
                except (OSError, ValueError):
                    code, body = 200, ""
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode())

    threading.Thread(target=ThreadingHTTPServer(("0.0.0.0", int(spec["port"])), Handler).serve_forever, daemon=True).start()


def say(**status):
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    with open(STATUS + ".tmp", "w") as f:
        json.dump(dict(status, at=round(time.time(), 1)), f)
    os.replace(STATUS + ".tmp", STATUS)


def run(command):
    p = subprocess.run(["bash", "-lc", command], cwd=TREE, capture_output=True, text=True)
    return p.returncode == 0, (p.stdout + p.stderr)[-3000:]


def stop(proc):
    if proc and proc.poll() is None:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(20)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)


def start():
    return subprocess.Popen(["bash", "-lc", "exec {} >> {} 2>&1".format(SPEC["start"], LOG)], cwd=TREE, start_new_session=True)


if os.environ.get("LOGS"):
    serve_log()
version, proc, first_done, failed = None, None, False, False
while True:
    try:
        wanted = open(VERSION).read().strip()
    except OSError:
        wanted = None
    if wanted and wanted != version:
        stop(proc)
        proc, version, failed = None, wanted, False
        say(version=version, state="deploying")
        ok, out = run(SPEC["prepare"]) if SPEC.get("prepare") else (True, "")
        if ok and SPEC.get("first") and not first_done:
            run(SPEC["first"])
            first_done = True
        if ok:
            proc = start()
            say(version=version, state="running")
        else:
            failed = True
            say(version=version, state="failed", step="prepare", log=out)
    elif version and not failed and (proc is None or proc.poll() is not None):       # it stopped by itself
        log = open(LOG, errors="replace").read()[-3000:] if os.path.isfile(LOG) else ""
        say(version=version, state="restarting", log=log)
        time.sleep(5)
        proc = start()
        say(version=version, state="running", restarted=True, log=log)
    time.sleep(2)

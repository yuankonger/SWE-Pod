"""Runs one of the company's systems in its sidecar, as CI and deploy last put it there.

    python3 service.py <name>

The deploy sidecar writes the system's tree to /deployed/<name> and then the commit it is at to
/deployed/<name>.version. This loop notices a new version, stops the system, runs its `prepare` command (a
database migration, say), once ever its `first` command (sample data), and starts it again. What happened is
written to /deployed/status/<name>.json, where the CI sidecar reads it. A system that stops by itself is started
again. SERVICE = {"start": command, "prepare": command, "first": command}, all optional but `start`. With
SERVICE["repository"] the system is one of several in that repository: it runs /deployed/<repository>, and says what
became of it under its own name.

With SERVICE["edge"] = {"port": N, "to": M, "limit": seconds} the system is reached through what stands in front of
it where it is hosted: requests to port N are passed to the system at port M, and one the system has not answered
within `limit` seconds is answered 504, as a hosting platform ends a function that runs too long. The system is not
stopped: it goes on with what it was doing. Each 504 is a line of the system's log.

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
REPOSITORY = SPEC.get("repository", NAME)      # a repository that holds several systems is deployed once and run by each of them
TREE, VERSION, STATUS = "/deployed/" + REPOSITORY, "/deployed/{}.version".format(REPOSITORY), "/deployed/status/{}.json".format(NAME)
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


def serve_edge(spec):
    import http.client
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    hop = {"connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade", "proxy-authorization", "proxy-authenticate", "content-length", "host"}

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def handle_any(self):
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            headers = {k: v for k, v in self.headers.items() if k.lower() not in hop}
            headers["Host"] = self.headers.get("Host") or "localhost"
            started = time.time()
            try:
                upstream = http.client.HTTPConnection("127.0.0.1", int(spec["to"]), timeout=float(spec["limit"]))
                upstream.request(self.command, self.path, body=body or None, headers=headers)
                answer = upstream.getresponse()
                status, sent, data = answer.status, [(k, v) for k, v in answer.getheaders() if k.lower() not in hop], answer.read()
            except TimeoutError:
                status, sent, data = 504, [("Content-Type", "text/plain; charset=utf-8")], b"FUNCTION_INVOCATION_TIMEOUT\n"
                with open(LOG, "a") as f:
                    f.write("edge: 504 {} {} was not answered within {:.0f} s (FUNCTION_INVOCATION_TIMEOUT)\n".format(self.command, self.path.split("?")[0], time.time() - started))
            except OSError as e:
                status, sent, data = 502, [("Content-Type", "text/plain; charset=utf-8")], "the system is not answering: {}\n".format(e).encode()
            try:
                self.send_response(status)
                for k, v in sent:
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(data)
            except OSError:
                pass

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = handle_any

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
if SPEC.get("edge"):
    serve_edge(SPEC["edge"])
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

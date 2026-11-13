"""Start the whole company on localhost: the broker and the four services, each as its own process.

    with Stack(root) as s:
        s.post("storefront", "/checkout", {...})

Run directly to serve until interrupted:  python3 platform/stack.py
"""
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

SERVICES = ("storefront", "orders", "billing", "notifications")
OFFSETS = {"broker": 0, "storefront": 1, "orders": 2, "billing": 3, "notifications": 4}


class Stack:
    def __init__(self, root=None, base_port=7000, log_dir=None, start_timeout=120.0):
        self.root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.ports = {name: base_port + off for name, off in OFFSETS.items()}
        self.log_dir = log_dir or os.path.join("/tmp", "seedco-logs-{}".format(base_port))
        self.start_timeout = start_timeout
        self.procs = {}
        self._logs = []

    def url(self, name, path=""):
        return "http://127.0.0.1:{}{}".format(self.ports[name], path)

    def _spawn(self, name, cmd, cwd):
        os.makedirs(self.log_dir, exist_ok=True)
        env = dict(os.environ, PORT=str(self.ports[name]), BROKER_URL=self.url("broker"),
                   ORDERS_URL=self.url("orders"), BILLING_URL=self.url("billing"),
                   SEEDCO_BUILD_DIR="/tmp/seedco-build-{}/{}".format(self.ports["broker"], name))
        log = open(os.path.join(self.log_dir, name + ".log"), "w")
        self._logs.append(log)
        self.procs[name] = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                                            start_new_session=True)

    def start(self):
        self._spawn("broker", [sys.executable, os.path.join(self.root, "platform", "broker.py")], self.root)
        for name in SERVICES:
            self._spawn(name, ["./run", "serve"], os.path.join(self.root, "services", name))
        deadline = time.time() + self.start_timeout
        waiting = set(self.procs)
        while waiting:
            for name in sorted(waiting):
                if self.procs[name].poll() is not None:
                    raise RuntimeError("{} exited during start-up:\n{}".format(name, self.log(name)[-2000:]))
                try:
                    urllib.request.urlopen(self.url(name, "/health"), timeout=1).read()
                    waiting.discard(name)
                except (urllib.error.URLError, OSError):
                    pass
            if waiting and time.time() > deadline:
                raise RuntimeError("not healthy after {}s: {}".format(self.start_timeout, sorted(waiting)))
            if waiting:
                time.sleep(0.2)
        return self

    def stop(self):
        for p in self.procs.values():
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for p in self.procs.values():
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()
        for f in self._logs:
            f.close()
        self.procs, self._logs = {}, []

    def log(self, name):
        try:
            with open(os.path.join(self.log_dir, name + ".log")) as f:
                return f.read()
        except OSError:
            return ""

    def request(self, name, method, path, body=None):
        """Returns (status, parsed JSON body or None)."""
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.url(name, path), data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw or b"null")
            except ValueError:
                return e.code, None

    def get(self, name, path):
        return self.request(name, "GET", path)

    def post(self, name, path, body=None):
        return self.request(name, "POST", path, body)

    def wait_for(self, check, timeout=10.0, interval=0.1):
        """Poll `check()` until it returns something truthy; returns it, or None at the timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            value = check()
            if value:
                return value
            time.sleep(interval)
        return check() or None

    __enter__ = start

    def __exit__(self, *exc):
        self.stop()


if __name__ == "__main__":
    stack = Stack().start()
    print("up: " + ", ".join("{}={}".format(n, p) for n, p in stack.ports.items()), flush=True)
    try:
        signal.pause()
    except KeyboardInterrupt:
        pass
    finally:
        stack.stop()

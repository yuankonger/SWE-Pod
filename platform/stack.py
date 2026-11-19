"""Start the whole company on localhost: Core, the apps around it, the shops and Prometheus, each as its own process.

    with Stack(root) as s:
        s.gql("{ products(first: 5) { totalCount } }")

Run directly to serve until interrupted:  python3 platform/stack.py
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

# Every service the company can have, with its port offset. A service that has no directory is left out.
OFFSETS = {"core": 0, "storefront": 1, "dashboard": 2, "payments": 3, "taxes": 4, "notifications": 5, "subscriptions": 6,
           "support": 7, "prometheus": 9}
SERVICES = tuple(s for s in OFFSETS if s != "prometheus")
# The services Core installs as apps: each serves a manifest and receives webhooks.
APPS = ("payments", "taxes", "notifications", "subscriptions", "support")


def _listeners(ports):
    """{pid: port} for the processes listening on any of `ports`, read from /proc (Linux)."""
    inodes = {}
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(table) as f:
                rows = f.read().splitlines()[1:]
        except OSError:
            continue
        for row in rows:
            cols = row.split()
            port = int(cols[1].rsplit(":", 1)[1], 16)
            if cols[3] == "0A" and port in ports:          # 0A: a listening socket
                inodes["socket:[{}]".format(cols[9])] = port
    found = {}
    for pid in (d for d in os.listdir("/proc") if d.isdigit()) if inodes else ():
        try:
            for fd in os.listdir("/proc/{}/fd".format(pid)):
                port = inodes.get(os.readlink("/proc/{}/fd/{}".format(pid, fd)))
                if port:
                    found[int(pid)] = port
        except OSError:
            continue          # the process ended, or is not ours to look at
    return found


def free_ports(ports, wait=5.0):
    """Kills (SIGKILL) whatever is listening on `ports`, so that a company can be started on them.

    Whoever worked in this machine before may have left services running, and a start on an occupied port fails
    or, worse, talks to the service that was left behind. Returns {port: [pids killed]}. Where there is no
    /proc (not Linux) nothing can be found and nothing is killed."""
    ports, killed, deadline = set(ports), {}, time.time() + wait
    while True:
        found = {pid: port for pid, port in _listeners(ports).items() if pid != os.getpid()}
        if not found or time.time() > deadline:
            return killed
        for pid, port in found.items():
            try:
                os.kill(pid, signal.SIGKILL)
                killed.setdefault(port, []).append(pid)
            except (ProcessLookupError, PermissionError):
                pass
        time.sleep(0.2)


class Stack:
    def __init__(self, root=None, base_port=7000, log_dir=None, start_timeout=180.0, data_dir=None, seed_dir=None, extra_manifests=(), app_urls=None):
        """`data_dir`: where the services keep their databases. Left out, each start gets a fresh directory that
        is removed on stop; given, the data is kept, so a second start finds what the first one stored.
        `seed_dir` (or SEEDCO_SEED_DIR): a directory of databases, one subdirectory per service, that a fresh data
        directory starts as a copy of. It gives the company a history instead of empty databases.
        `extra_manifests`: manifest URLs of apps that are not the company's own, for Core to install as well. They
        must be served before the company is started."""
        self.extra_manifests = list(extra_manifests)
        # `app_urls`: {service: URL} for a service that Core should reach at another address than its own, for
        # example through a proxy. The service advertises that address in its manifest.
        self.app_urls = dict(app_urls or {})
        self.seed_dir = seed_dir or os.environ.get("SEEDCO_SEED_DIR")
        self.root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.ports = {name: base_port + off for name, off in OFFSETS.items()}
        self.log_dir = log_dir or os.environ.get("SEEDCO_LOG_DIR") or os.path.join("/tmp", "seedco-logs-{}".format(base_port))
        self.start_timeout = start_timeout
        self.data_dir = data_dir
        self._own_data_dir = None
        self.services = [s for s in SERVICES if os.path.isfile(os.path.join(self.root, "services", s, "run"))]
        self.procs = {}
        self._logs = []
        self._tokens = {}

    def url(self, name, path=""):
        return "http://127.0.0.1:{}{}".format(self.ports[name], path)

    def _spawn(self, name, cmd, cwd):
        os.makedirs(self.log_dir, exist_ok=True)
        apps = [a for a in APPS if a in self.services]
        env = dict(os.environ, PORT=str(self.ports[name]), APP_URL=self.app_urls.get(name, self.url(name)), CORE_URL=self.url("core", "/graphql/"),
                   SEEDCO_APP_MANIFESTS=",".join([self.url(a, "/api/manifest") for a in apps] + self.extra_manifests),
                   SEEDCO_DATA_DIR=os.path.join(self.data_dir, name),
                   SEEDCO_BUILD_DIR="/tmp/seedco-build-{}/{}".format(self.ports["core"], name),
                   **{"{}_URL".format(s.upper()): self.url(s) for s in SERVICES if s != "core"})
        log = open(os.path.join(self.log_dir, name + ".log"), "w")
        self._logs.append(log)
        self.procs[name] = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                                            start_new_session=True)

    def _start_prometheus(self):
        """Runs the real Prometheus with the on-call owner's configuration (services/ops/prometheus) and our scrape targets."""
        config = os.path.join(self.root, "services", "ops", "prometheus")
        if not os.path.isfile(os.path.join(config, "prometheus.yml")) or not shutil.which("prometheus"):
            return
        run = os.path.join(self.data_dir, "prometheus")
        shutil.copytree(config, run, dirs_exist_ok=True)
        with open(os.path.join(run, "targets.json"), "w") as f:
            json.dump([{"targets": ["127.0.0.1:{}".format(self.ports[s])], "labels": {"service": s}} for s in self.services], f)
        self._spawn("prometheus", ["prometheus", "--config.file=prometheus.yml", "--storage.tsdb.path=tsdb", "--log.level=warn",
                                   "--web.listen-address=127.0.0.1:{}".format(self.ports["prometheus"])], run)

    def start(self, clear_ports=False):
        """`clear_ports`: first kill whatever is listening on this company's ports (see free_ports)."""
        if clear_ports:
            self.cleared = free_ports(self.ports.values())
        if self.data_dir is None:
            self.data_dir = self._own_data_dir = tempfile.mkdtemp(prefix="seedco-data-")
            if self.seed_dir and os.path.isdir(self.seed_dir):
                shutil.copytree(self.seed_dir, self.data_dir, dirs_exist_ok=True)
        for name in self.services:
            os.makedirs(os.path.join(self.data_dir, name), exist_ok=True)
            self._spawn(name, ["./run", "serve"], os.path.join(self.root, "services", name))
        self._start_prometheus()
        deadline = time.time() + self.start_timeout
        waiting = set(self.procs)
        while waiting:
            for name in sorted(waiting):
                if self.procs[name].poll() is not None:
                    raise RuntimeError("{} exited during start-up:\n{}".format(name, self.log(name)[-2000:]))
                try:
                    path = "/-/ready" if name == "prometheus" else "/health"   # Core is healthy once its apps are installed
                    urllib.request.urlopen(self.url(name, path), timeout=1).read()
                    waiting.discard(name)
                except (urllib.error.URLError, OSError):
                    pass
            if waiting and time.time() > deadline:
                raise RuntimeError("not healthy after {}s: {}\n{}".format(
                    self.start_timeout, sorted(waiting), "\n".join(self.log(n)[-600:] for n in sorted(waiting))))
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
        self.procs, self._logs, self._tokens = {}, [], {}
        if self._own_data_dir:
            shutil.rmtree(self._own_data_dir, ignore_errors=True)
            self.data_dir = self._own_data_dir = None

    def log(self, name):
        try:
            with open(os.path.join(self.log_dir, name + ".log")) as f:
                return f.read()
        except OSError:
            return ""

    def request(self, name, method, path, body=None, headers=None):
        """Returns (status, parsed JSON body, or the text if the body is not JSON)."""
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.url(name, path), data=data, method=method,
                                     headers=dict({"Content-Type": "application/json"}, **(headers or {})))
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                status, raw = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
        try:
            return status, json.loads(raw or b"null")
        except ValueError:
            return status, raw.decode("utf-8", "replace")

    def get(self, name, path):
        return self.request(name, "GET", path)

    def post(self, name, path, body=None):
        return self.request(name, "POST", path, body)

    def staff_token(self, email="admin@seedco.example", password="admin"):
        if email not in self._tokens:
            data = self.gql("mutation($e: String!, $p: String!) { tokenCreate(email: $e, password: $p) { token } }", e=email, p=password)
            self._tokens[email] = data["tokenCreate"]["token"]
        return self._tokens[email]

    def gql(self, query, token=None, **variables):
        """Runs a GraphQL operation on Core and returns `data`. Top-level errors are raised."""
        headers = {"Authorization": "Bearer " + token} if token else None
        status, body = self.request("core", "POST", "/graphql/", {"query": query, "variables": variables}, headers)
        if status != 200 or not isinstance(body, dict) or body.get("errors"):
            raise AssertionError("core answered {}: {}".format(status, body))
        return body["data"]

    def wait_for(self, check, timeout=10.0, interval=0.1):
        """Poll `check()` until it returns something truthy; returns it, or None at the timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            value = check()
            if value:
                return value
            time.sleep(interval)
        return check() or None

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()


if __name__ == "__main__":
    stack = Stack().start()
    print("up: " + ", ".join("{}={}".format(n, stack.ports[n]) for n in stack.procs), flush=True)
    try:
        signal.pause()
    except KeyboardInterrupt:
        pass
    finally:
        stack.stop()

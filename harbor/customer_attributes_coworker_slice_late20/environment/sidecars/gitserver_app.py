"""The company's git server, as it runs inside its container. Started by kernel/gitserver.py.

    python3 gitserver_app.py <directory of bare repositories> <access file> <log file> [port]

Serves the repositories over HTTP by handing each request to `git http-backend`. Who may do what is decided here
and nowhere else: every request carries an agent's name and token, and the access file says, per agent and per
repository, "read" or "write". The file is read again on every request, so a grant made during a run takes effect
at once. Every request that fetches or pushes is written to the log, allowed or not.

Access file: {"tokens": {agent: token}, "access": {agent: {repository: "read" | "write"}}}
"""
import base64
import json
import os
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT, ACCESS, LOG = sys.argv[1:4]
PORT = int(sys.argv[4]) if len(sys.argv) > 4 else 8080
BACKEND = "/usr/lib/git-core/git-http-backend"


def record(**entry):
    entry["at"] = round(time.time(), 3)
    with open(LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"           # the reply ends when the connection closes; no length needed

    def log_message(self, *args):
        pass

    def _refuse(self, code, why, challenge=False):
        self.send_response(code)
        if challenge:
            self.send_header("WWW-Authenticate", 'Basic realm="git"')
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write((why + "\n").encode())

    def _agent(self, rules):
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return None
        try:
            name, _, token = base64.b64decode(header[6:]).decode().partition(":")
        except ValueError:
            return None
        return name if token and rules.get("tokens", {}).get(name) == token else None

    def _body(self):
        if self.headers.get("Transfer-Encoding", "").lower() == "chunked":      # git sends large pushes this way
            parts = []
            while True:
                size = int(self.rfile.readline().split(b";")[0].strip() or b"0", 16)
                if size == 0:
                    while self.rfile.readline().strip():
                        pass
                    break
                parts.append(self.rfile.read(size))
                self.rfile.readline()
            return b"".join(parts)
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))

    def _serve(self):
        path, _, query = self.path.partition("?")
        repository = path.strip("/").split("/")[0]
        if repository.endswith(".git"):
            repository = repository[:-4]
        pushing = "git-receive-pack" in path or "service=git-receive-pack" in query
        try:
            rules = json.load(open(ACCESS))
        except (OSError, ValueError):
            rules = {}
        agent = self._agent(rules)
        if path == "/_log" and agent == "verifier":      # the record of who fetched and pushed what, for whoever judges the work
            try:
                with open(LOG, "rb") as f:
                    data = f.read()
            except OSError:
                data = b""
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            self.wfile.write(data)
            return
        if agent is None:
            return self._refuse(401, "Say who you are: this server needs your agent name and token.", challenge=True)
        held = rules.get("access", {}).get(agent, {}).get(repository)
        allowed = held == "write" or (held == "read" and not pushing)
        # git asks first (info/refs) and sends second: an allowed exchange is logged when it sends, a refused one when it asks
        if (path.endswith(("git-receive-pack", "git-upload-pack")) and self.command == "POST") or (not allowed and held is not None):
            record(agent=agent, repository=repository, action="push" if pushing else "fetch", allowed=allowed)
        if not allowed:
            if held is None:
                return self._refuse(404, "There is no repository `{}` that you can read.".format(repository))
            return self._refuse(403, "You can read `{}` but not push to it. Its owner can.".format(repository))
        if not os.path.isdir(os.path.join(ROOT, repository + ".git")):
            return self._refuse(404, "There is no repository `{}`.".format(repository))

        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "GIT_PROJECT_ROOT": ROOT, "GIT_HTTP_EXPORT_ALL": "1",
               "REQUEST_METHOD": self.command, "PATH_INFO": "/" + repository + ".git" + path.strip("/")[len(path.strip("/").split("/")[0]):],
               "QUERY_STRING": query, "REMOTE_USER": agent, "REMOTE_ADDR": self.client_address[0],
               "CONTENT_TYPE": self.headers.get("Content-Type", ""), "SEEDCO_PUSH_LOG": LOG}
        for header, name in (("Content-Encoding", "HTTP_CONTENT_ENCODING"), ("Git-Protocol", "GIT_PROTOCOL")):
            if self.headers.get(header):
                env[name] = self.headers[header]
        body = self._body() if self.command == "POST" else b""
        env["CONTENT_LENGTH"] = str(len(body))
        done = subprocess.run([BACKEND], input=body, env=env, capture_output=True)
        head, _, rest = done.stdout.partition(b"\r\n\r\n")
        status, headers = 200, []
        for line in head.decode("latin-1").split("\r\n"):
            name, _, value = line.partition(":")
            if name.lower() == "status":
                status = int(value.split()[0])
            elif value:
                headers.append((name, value.strip()))
        self.send_response(status)
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(rest)

    do_GET = do_POST = _serve


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

"""The event broker: an append-only log per topic, over HTTP. Platform-owned; no service owner edits it.

POST /topics/<topic>            body: one event (JSON object)  -> {"offset": n}
GET  /topics/<topic>?offset=n   -> {"events": [...], "next_offset": m, "end_offset": m}
GET  /health

Delivery is at-least-once from the consumer's side: a consumer polls from an offset it keeps itself.
"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

LOGS = {}
LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/health":
            return self._send(200, {"ok": True})
        if u.path.startswith("/topics/"):
            topic = u.path[len("/topics/"):]
            offset = int(parse_qs(u.query).get("offset", ["0"])[0])
            with LOCK:
                log = LOGS.get(topic, [])
                events = log[offset:]
                end = len(log)
            return self._send(200, {"events": events, "next_offset": end, "end_offset": end})
        self._send(404, {"error": "not_found"})

    def do_POST(self):
        u = urlparse(self.path)
        if not u.path.startswith("/topics/"):
            return self._send(404, {"error": "not_found"})
        topic = u.path[len("/topics/"):]
        try:
            event = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        except ValueError:
            return self._send(400, {"error": "invalid_json"})
        with LOCK:
            log = LOGS.setdefault(topic, [])
            log.append(event)
            offset = len(log) - 1
        self._send(201, {"offset": offset})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "7000"))
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()

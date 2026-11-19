"""HTTP wiring for Notifications: the manifest Core installs it from, its webhook, the notify endpoint and the outbox."""
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from notifications import Outbox
from payload import PayloadError
from store import Store, default_path

HERE = os.path.dirname(os.path.abspath(__file__))
OUTBOX = Outbox(Store(default_path()))
COUNTERS = {}
LOCK = threading.Lock()


def count(name, **labels):
    series = "{}{{{}}}".format(name, ",".join('{}="{}"'.format(k, v) for k, v in sorted(labels.items())))
    with LOCK:
        COUNTERS[series] = COUNTERS.get(series, 0) + 1


def metrics() -> str:
    with LOCK:
        items = sorted(COUNTERS.items())
    names = sorted({s.split("{")[0] for s, _ in items})
    return "".join("# TYPE {} counter\n".format(n) for n in names) + "".join("{} {}\n".format(s, v) for s, v in items)


def log(level, message, **attributes):
    record = dict({"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "level": level,
                   "service": "notifications", "message": message}, **attributes)
    print(json.dumps(record), file=sys.stdout, flush=True)


def manifest(app_url: str) -> dict:
    with open(os.path.join(HERE, "..", "graphql", "order-events.graphql")) as f:
        query = f.read()
    return {"id": "seedco.notifications", "name": "Customer emails", "version": "1.0.0", "permissions": ["MANAGE_ORDERS"],
            "tokenTargetUrl": app_url + "/api/register",
            "webhooks": [{"name": "order-events", "query": query, "targetUrl": app_url + "/api/webhooks/order-events",
                          "asyncEvents": ["ORDER_CONFIRMED", "ORDER_FULLY_PAID", "ORDER_FULFILLED", "ORDER_CANCELLED", "ORDER_REFUNDED"]}]}


class Handler(BaseHTTPRequestHandler):
    app_url = ""

    def log_message(self, *a):
        pass

    def reply(self, status, body, content_type="application/json"):
        data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        count("http_server_request_count_total", http_route=urlparse(self.path).path, http_response_status_code=status)

    def do_GET(self):
        u = urlparse(self.path)
        query = parse_qs(u.query)
        if u.path == "/health":
            return self.reply(200, {"ok": True})
        if u.path == "/metrics":
            return self.reply(200, metrics(), "text/plain; version=0.0.4")
        if u.path == "/api/manifest":
            return self.reply(200, manifest(self.app_url))
        if u.path == "/outbox":
            return self.reply(200, {"emails": OUTBOX.emails(query.get("email", [None])[0])})
        if u.path == "/dropped":
            return self.reply(200, {"dropped": OUTBOX.store.dropped()})
        self.reply(404, {"error": "not_found"})

    def do_POST(self):
        u = urlparse(self.path)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"null")
        except ValueError:
            return self.reply(400, {"error": "invalid_json"})
        if u.path == "/api/register":
            OUTBOX.store.set_setting("auth_token", (body or {}).get("auth_token", ""))
            return self.reply(200, {"success": True})
        if u.path == "/api/webhooks/order-events":
            # Always 200: an event we cannot use is recorded as dropped, and Core sending it again would not help.
            before = len(OUTBOX.store.dropped())
            email = OUTBOX.consume(body if isinstance(body, dict) else {})
            if email:
                count("seedco_emails_sent_total", kind=email["kind"])
            if len(OUTBOX.store.dropped()) > before:
                dropped = OUTBOX.store.dropped()[-1]
                count("seedco_events_dropped_total", event_type=dropped["event_type"])
                log("error", "dropped an event it could not read", event_type=dropped["event_type"], reason=dropped["reason"])
            return self.reply(200, {"success": True})
        if u.path == "/api/notify":
            try:
                email = OUTBOX.notify(body if isinstance(body, dict) else {})
            except PayloadError as exc:
                log("error", "refused a notify request", reason=str(exc))
                return self.reply(400, {"error": "bad_request", "message": str(exc)})
            if email:
                count("seedco_emails_sent_total", kind=email["kind"])
            return self.reply(200, {"sent": email is not None})
        self.reply(404, {"error": "not_found"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "7005"))
    Handler.app_url = os.environ.get("APP_URL", "http://127.0.0.1:{}".format(port))
    log("info", "notifications listening", port=port)
    # BIND is the address to listen on: this machine only by default, 0.0.0.0 when each service has its own container
    ThreadingHTTPServer((os.environ.get("BIND", "127.0.0.1"), port), Handler).serve_forever()

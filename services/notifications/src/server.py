"""HTTP wiring for Notifications: the outbox endpoint and one polling consumer per topic."""
import json
import os
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from notifications import TOPICS, Outbox

OUTBOX = Outbox()


def consume(broker_url: str, topic: str):
    offset = 0
    while True:
        try:
            with urllib.request.urlopen("{}/topics/{}?offset={}".format(broker_url, topic, offset), timeout=5) as r:
                page = json.loads(r.read())
            for event in page["events"]:
                try:
                    OUTBOX.handle(event)
                except Exception as exc:  # one unreadable event must not stop the consumer
                    print("notifications: dropped an event it could not read: {!r}".format(exc), file=sys.stderr)
            offset = page["next_offset"]
        except OSError:
            pass
        time.sleep(0.1)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/health":
            body = {"ok": True}
        elif u.path == "/outbox":
            body = {"emails": OUTBOX.for_customer(parse_qs(u.query).get("customer_id", [None])[0])}
        else:
            self.send_response(404)
            self.end_headers()
            return
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "7004"))
    broker = os.environ.get("BROKER_URL", "http://127.0.0.1:7000")
    for t in TOPICS:
        threading.Thread(target=consume, args=(broker, t), daemon=True).start()
    print("notifications listening on {}".format(port), flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()

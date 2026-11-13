"""HTTP wiring for Notifications: the outbox endpoints and one polling consumer per topic."""
import json
import os
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from notifications import TOPICS, Outbox
from store import Store, default_path

OUTBOX = Outbox(Store(default_path()))


def consume(broker_url: str, topic: str):
    """Polls one topic from the offset we last stored. The offset is saved after each page is handled."""
    store = OUTBOX.store
    while True:
        try:
            offset = store.offset(topic)
            with urllib.request.urlopen("{}/topics/{}?offset={}".format(broker_url, topic, offset), timeout=5) as r:
                page = json.loads(r.read())
            for event in page["events"]:
                before = len(store.dropped())
                OUTBOX.consume(event)
                if len(store.dropped()) > before:
                    print("notifications: dropped an event it could not read: {}".format(store.dropped()[-1]["reason"]),
                          file=sys.stderr, flush=True)
            if page["next_offset"] != offset:
                store.set_offset(topic, page["next_offset"])
        except OSError:
            pass
        time.sleep(0.1)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        query = parse_qs(u.query)
        if u.path == "/health":
            body = {"ok": True}
        elif u.path == "/outbox":
            body = {"emails": OUTBOX.for_customer(query.get("customer_id", [None])[0])}
        elif u.path == "/dropped":
            body = {"dropped": OUTBOX.store.dropped()}
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

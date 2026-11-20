"""The company's chat, in its sidecar: messages between the people working on a change.

    POST /send   {"from", "token", "to", "text"}     -> {"delivered": bool, "note": str}
    GET  /inbox?name=&token=&wait=<seconds>           -> {"messages": [{"from", "text", "at"}], "others_working": [names], "others_paused": {name: until}}
    POST /done   {"name", "token"}                    that person has finished and reads nothing more
    POST /paused {"name", "token", "until"}           that person is stopped by a limit on the model service until about `until`
                                                      (seconds since 1970); messages to them are kept and read when they are back
    POST /resumed {"name", "token"}                   that person is back
    GET  /log?token=<admin token>                     everything sent, for whoever runs the company

CHAT = {"tokens": {name: token}, "admin": token}. A message to someone who has finished is kept in the log but
not delivered, and the sender is told so. /inbox waits up to `wait` seconds for a message, and stops waiting at
once when nobody else is still working.
"""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

CONFIG = json.loads(os.environ["CHAT"])
TOKENS = CONFIG["tokens"]
inbox = {name: [] for name in TOKENS}
done, log = set(), []
paused, pauses = {}, []     # who is paused and until when; every pause, for whoever runs the company
changed = threading.Condition()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError:
            return self.reply(400, {"error": "not JSON"})
        name = body.get("from") or body.get("name")
        if TOKENS.get(name) is None or TOKENS[name] != body.get("token"):
            return self.reply(401, {"error": "who are you?"})
        with changed:
            if self.path.startswith("/done"):
                done.add(name)
                changed.notify_all()
                return self.reply(200, {"ok": True})
            if self.path.startswith("/paused"):
                paused[name] = float(body.get("until") or 0)
                pauses.append({"name": name, "at": round(time.time(), 1), "until": paused[name]})
                changed.notify_all()
                return self.reply(200, {"ok": True})
            if self.path.startswith("/resumed"):
                if paused.pop(name, None) is not None:
                    pauses.append({"name": name, "at": round(time.time(), 1), "resumed": True})
                changed.notify_all()
                return self.reply(200, {"ok": True})
            to, text = body.get("to"), (body.get("text") or "").strip()
            if to not in TOKENS or to == name or not text:
                return self.reply(400, {"error": "`to` must be one of {} and `text` must not be empty".format(sorted(n for n in TOKENS if n != name))})
            delivered = to not in done
            entry = {"from": name, "to": to, "text": text, "at": round(time.time(), 1), "delivered": delivered}
            log.append(entry)
            if delivered:
                inbox[to].append({"from": name, "text": text, "at": entry["at"]})
                changed.notify_all()
            until = paused.get(to)
        note = "sent to {}".format(to) if delivered else "{} has finished and will not read this".format(to)
        if delivered and until is not None:
            note = "kept for {}, who is paused by a limit on the model service and is expected back around {} UTC; they will read it then".format(
                to, time.strftime("%H:%M", time.gmtime(until)))
        self.reply(200, {"delivered": delivered, "note": note})

    def do_GET(self):
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        if url.path == "/log":
            if q.get("token") != CONFIG["admin"]:
                return self.reply(401, {"error": "not for you"})
            return self.reply(200, {"messages": log, "done": sorted(done), "pauses": pauses})
        name = q.get("name")
        if TOKENS.get(name) is None or TOKENS[name] != q.get("token"):
            return self.reply(401, {"error": "who are you?"})
        deadline = time.time() + min(float(q.get("wait") or 0), 900)
        with changed:
            while not inbox[name] and time.time() < deadline and any(n not in done for n in TOKENS if n != name):
                changed.wait(min(5, max(0.1, deadline - time.time())))
            messages, inbox[name] = inbox[name], []
            others = sorted(n for n in TOKENS if n != name and n not in done and n not in paused)
            waiting = {n: until for n, until in paused.items() if n != name and n not in done}
        self.reply(200, {"messages": messages, "others_working": others, "others_paused": waiting})


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("CHAT_PORT") or 8080)), Handler).serve_forever()

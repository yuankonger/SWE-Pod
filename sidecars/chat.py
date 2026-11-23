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

With CHAT["clock"] = {"seat": name} the chat keeps a clock for that seat (docs/COWORKER_SPEC.md, 3.3): one agent at
`name`, and everyone else on the chat a scripted person (sidecars/people.py). Then:

    the clock       is the seat's working time: wall time, less the time the seat is paused by a limit on the model
                    service. Messages carry it as `at_v`, in seconds.
    /send           from a scripted person may carry "due_at_v": the message reaches the seat when the clock is there.
    /inbox?wait=    from the seat waits in real time, as for anyone, and ends when a held message falls due. The answer
                    says how long it took (`waited_s`).
    /log            also gives the clock: where it stands, every wait, and when each held message was delivered.

A wait is real because the rest of the company is: a test suite the agent started, a deploy CI is running. With
"jump": true in the clock a wait returns at once and moves the clock forward instead (to the next message due, or by
the whole wait), holding only while a person's reply is still being decided so that a jump never passes it. That is
for agents that have nothing running while they wait (scripted ones, in probes): with an agent that has, the clock
would run ahead of its own work, and a reply's delay could be passed in a few calls. No exported task sets it.
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


class Clock:
    """A seat's virtual time, in seconds: its working time, plus what it has jumped over by waiting. `now` gives wall
    time, so a recorded run can be replayed. Not safe on its own: used under `changed`."""

    def __init__(self, now=time.time):
        self.wall, self.started, self.jumped, self.paused_for, self.paused_since = now, now(), 0.0, 0.0, None
        self.held, self.waits, self.unanswered = [], [], 0

    def now(self):
        away = self.paused_for + (self.wall() - self.paused_since if self.paused_since is not None else 0.0)
        return round(self.wall() - self.started - away + self.jumped, 1)

    def pause(self):
        if self.paused_since is None:
            self.paused_since = self.wall()

    def resume(self):
        if self.paused_since is not None:
            self.paused_for, self.paused_since = self.paused_for + self.wall() - self.paused_since, None

    def hold(self, entry, due):
        self.held.append((due, len(self.held), entry))

    def due(self):
        """The held messages whose time has come, in the order they fall due (then the order they were sent)."""
        at = self.now()
        ready = sorted(h for h in self.held if h[0] <= at)
        self.held = [h for h in self.held if h[0] > at]
        return [entry for _, _, entry in ready]

    def wait(self, seconds):
        """Jump for a wait of `seconds`: to the next held message if one is due within it, else by all of it.
        Returns how far the clock moved."""
        at = self.now()
        ahead = [due - at for due, _, _ in self.held if due - at <= seconds]
        by = round(max(0.0, min(ahead)) if ahead else seconds, 1)
        self.jumped += by
        self.waits.append({"at_v": at, "by_s": by, "asked_s": seconds, "to_a_message": bool(ahead), "jumped": True})
        return by


CLOCK = Clock() if CONFIG.get("clock") else None
SEAT = (CONFIG.get("clock") or {}).get("seat")


def deliver_due():
    """Puts the held messages that are due into the seat's inbox. Under `changed`."""
    for entry in CLOCK.due():
        entry.update(delivered_at=round(time.time(), 1), delivered_at_v=CLOCK.now())
        inbox[entry["to"]].append({"from": entry["from"], "text": entry["text"], "at": entry["delivered_at"]})


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
                if CLOCK and name == SEAT:
                    CLOCK.pause()
                paused[name] = float(body.get("until") or 0)
                pauses.append({"name": name, "at": round(time.time(), 1), "until": paused[name]})
                changed.notify_all()
                return self.reply(200, {"ok": True})
            if self.path.startswith("/resumed"):
                if CLOCK and name == SEAT:
                    CLOCK.resume()
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
            if CLOCK:
                entry["at_v"] = CLOCK.now()
                if delivered and name == SEAT:
                    CLOCK.unanswered += 1
                elif name != SEAT:      # a person's one reply to a message: scheduled from here on, or delivered now
                    CLOCK.unanswered = max(0, CLOCK.unanswered - 1)
            if delivered and CLOCK and to == SEAT and body.get("due_at_v") is not None and float(body["due_at_v"]) > CLOCK.now():
                entry["due_at_v"] = round(float(body["due_at_v"]), 1)
                CLOCK.hold(entry, entry["due_at_v"])
                changed.notify_all()
            elif delivered:
                message = {"from": name, "text": text, "at": entry["at"]}
                if CLOCK:
                    message["at_v"] = entry["at_v"]
                    if to == SEAT:
                        entry.update(delivered_at=entry["at"], delivered_at_v=entry["at_v"])
                inbox[to].append(message)
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
            with changed:
                clock = CLOCK and {"seat": SEAT, "now_v": CLOCK.now(), "waited_s": round(sum(w["by_s"] for w in CLOCK.waits), 1),
                                   "jumped_s": round(CLOCK.jumped, 1), "waits": CLOCK.waits, "not_delivered": len(CLOCK.held)}
            return self.reply(200, dict({"messages": log, "done": sorted(done), "pauses": pauses}, **({"clock": clock} if clock else {})))
        name = q.get("name")
        if TOKENS.get(name) is None or TOKENS[name] != q.get("token"):
            return self.reply(401, {"error": "who are you?"})
        asked = min(float(q.get("wait") or 0), 900)
        deadline = time.time() + asked
        if CLOCK and name == SEAT:      # the seat's wait ends when a held message falls due
            with changed:
                deliver_due()
                began, jumps, waited = CLOCK.now(), CONFIG["clock"].get("jump"), 0.0
                while asked and not inbox[name] and time.time() < deadline and (CLOCK.unanswered or not jumps):
                    changed.wait(0.5)
                    deliver_due()
                if asked and not inbox[name] and jumps:
                    waited = CLOCK.wait(asked)
                    deliver_due()
                elif asked and not jumps:
                    waited = round(CLOCK.now() - began, 1)
                    CLOCK.waits.append({"at_v": began, "by_s": waited, "asked_s": asked, "to_a_message": bool(inbox[name]), "jumped": False})
                messages, inbox[name] = inbox[name], []
                others = sorted(n for n in TOKENS if n != name and n not in done and n not in paused)
            return self.reply(200, {"messages": messages, "others_working": others, "others_paused": {}, "waited_s": waited})
        with changed:
            while not inbox[name] and time.time() < deadline and any(n not in done for n in TOKENS if n != name):
                changed.wait(min(5, max(0.1, deadline - time.time())))
            messages, inbox[name] = inbox[name], []
            others = sorted(n for n in TOKENS if n != name and n not in done and n not in paused)
            waiting = {n: until for n, until in paused.items() if n != name and n not in done}
        self.reply(200, {"messages": messages, "others_working": others, "others_paused": waiting})


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("CHAT_PORT") or 8080)), Handler).serve_forever()

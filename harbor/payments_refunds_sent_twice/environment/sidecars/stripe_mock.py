"""The payment provider, in its sidecar: a stand-in for Stripe's API, for a company whose payment app talks to Stripe.

It answers the part of Stripe's HTTP API the Saleor Stripe app uses, in Stripe's shapes, and it calls the app back
the way Stripe does: signed events, sent after the fact, retried when refused. It is also the record of what money
really moved, which is what the company is judged on.

    POST   /v1/payment_intents                      create       (Idempotency-Key replays the first answer)
    GET    /v1/payment_intents?limit=N              list
    GET    /v1/payment_intents/<id>                 retrieve     (expand[]=payment_method)
    POST   /v1/payment_intents/<id>                 update       (metadata, description)
    POST   /v1/payment_intents/<id>/confirm         what the customer's browser does: payment_method=pm_card_visa ...
    POST   /v1/payment_intents/<id>/capture         amount_to_capture optional
    POST   /v1/payment_intents/<id>/cancel
    POST   /v1/refunds                              payment_intent, amount optional
    GET    /v1/refunds?payment_intent=<id>&limit=N  list;  GET /v1/refunds/<id>  retrieve
A publishable key (pk_...) may only confirm a payment intent and retrieve one; everything else needs the other key.
    POST   /v1/webhook_endpoints, GET|POST|DELETE /v1/webhook_endpoints/<id>

    GET    /_ledger?token=<admin>                   everything: intents, refunds, events and each delivery of them
    POST   /_endpoints?token=<admin>                {"id", "url", "secret", "enabled_events"}: an endpoint that exists
                                                    from the start, as one made in Stripe's dashboard would
    POST   /_arm?token=<admin>                      {"intent", "slow_refunds": n, "refuse_refunds": n, "late_events": seconds, "lock": seconds, "calm": true}: what the
                                                    faults below do by chance, done to this payment for certain, and
                                                    with "calm" nothing done to it by chance (for a verifier)

STRIPE = {"keys": [secret or restricted keys accepted], "admin": token, "viewers": [tokens that may read the ledger only],
          "deliver_after": seconds before an event is sent (default 0.5), "retry_after": [seconds, ...],
          "endpoints": [{"id", "url", "secret", "enabled_events"}], "faults": {...}}
Faults are for whoever writes a task, and each is something Stripe does:
    {"duplicate": ["charge.refund.updated"]}          those events are sent twice
    {"slow_refunds": {"share": 0.3, "seconds": 13}}    that share of refunds is made at once and answered late
    {"lock": {"share": 0.2, "seconds": 4}}             for that share of payments, the intent cannot be read or changed
                                                       for a few seconds after the card is confirmed: 429 `lock_timeout`
A request whose Idempotency-Key is that of a request still being answered is refused, 409 `idempotency_key_in_use`.
With TLS_CERT and TLS_KEY set it serves HTTPS (the app only speaks HTTPS to api.stripe.com); otherwise HTTP.
Standard library only.
"""
import hashlib
import hmac
import json
import os
import random
import re
import secrets
import ssl
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlparse

CONFIG = json.loads(os.environ.get("STRIPE") or "{}")
KEYS, ADMIN = set(CONFIG.get("keys") or []), CONFIG.get("admin")
API_VERSION = "2025-04-30.basil"
CARDS = {      # the payment methods a test can pay with: what becomes of a confirmation
    "pm_card_visa": ("visa", "4242", None), "pm_card_mastercard": ("mastercard", "4444", None),
    "pm_card_chargeDeclined": ("visa", "0002", "card_declined"), "pm_card_chargeDeclinedInsufficientFunds": ("visa", "9995", "insufficient_funds"),
}
lock = threading.RLock()
intents, refunds, endpoints, events, replies = {}, {}, {}, [], {}
answering, armed, locked = set(), {}, {}      # keys of requests still being answered; faults armed per intent; intent -> locked until
FAULTS = CONFIG.get("faults") or {}
for e in CONFIG.get("endpoints") or []:
    endpoints[e["id"]] = dict(e, object="webhook_endpoint", status="enabled")


class Refused(Exception):
    def __init__(self, status, kind, message, code=None):
        self.status, self.body = status, {"error": {"type": kind, "message": message, **({"code": code} if code else {})}}


class Late(Exception):
    """What was asked is done, and the answer is held back for a while."""
    def __init__(self, seconds, answer, status=200):
        self.seconds, self.answer, self.status = float(seconds), answer, status


def new(prefix):
    return prefix + "_" + secrets.token_hex(12)


def nested(pairs):
    """Stripe's form encoding (`a[b][c]=1`, `expand[]=x`) as a dict."""
    out = {}
    for key, value in pairs:
        parts = re.findall(r"[^\[\]]+|\[\]", key)
        at = out
        for i, part in enumerate(parts[:-1]):
            at = at.setdefault(part, {})
        last = parts[-1]
        if last == "[]":
            at.setdefault("_list", []).append(value)
        else:
            at[last] = value
    def lists(d):
        if isinstance(d, dict):
            if set(d) == {"_list"}:
                return d["_list"]
            if d and all(k.isdigit() for k in d):      # `expand[0]=x`, as Stripe's own libraries write a list
                return [lists(d[k]) for k in sorted(d, key=int)]
            return {k: lists(v) for k, v in d.items()}
        return d
    return lists(out)


def seen(intent, expand=()):
    """A payment intent as the API shows it."""
    out = {k: v for k, v in intent.items() if not k.startswith("_")}
    if "payment_method" in expand and intent.get("payment_method"):
        brand, last4, _ = CARDS[intent["payment_method"]]
        out["payment_method"] = {"id": intent["payment_method"], "object": "payment_method", "type": "card",
                                 "card": {"brand": brand, "display_brand": brand, "last4": last4, "exp_month": 12, "exp_year": 2034}}
    return out


def emit(kind, obj, after=None):
    """Records an event and sends it to every endpoint that asked for its kind, a little later, as Stripe does."""
    event = {"id": new("evt"), "object": "event", "api_version": API_VERSION, "created": int(time.time()), "type": kind, "livemode": False,
             "pending_webhooks": 1, "request": {"id": None, "idempotency_key": None}, "data": {"object": json.loads(json.dumps(obj))}}
    with lock:
        events.append({"event": event, "deliveries": []})
        record = events[-1]
        targets = [e for e in endpoints.values() if e["status"] == "enabled" and (kind in e["enabled_events"] or "*" in e["enabled_events"])]
    times = 2 if kind in (CONFIG.get("faults") or {}).get("duplicate", []) else 1
    for endpoint in targets:
        for _ in range(times):
            threading.Thread(target=deliver, args=(record, endpoint, after), daemon=True).start()


def deliver(record, endpoint, after=None):
    body = json.dumps(record["event"])
    for wait in [float(CONFIG.get("deliver_after", 0.5) if after is None else after)] + list(CONFIG.get("retry_after") or [2, 5, 15, 30, 60]):
        time.sleep(wait)
        stamp = int(time.time())
        signature = hmac.new(endpoint["secret"].encode(), "{}.{}".format(stamp, body).encode(), hashlib.sha256).hexdigest()
        request = urllib.request.Request(endpoint["url"], data=body.encode(), method="POST", headers={
            "Content-Type": "application/json", "Stripe-Signature": "t={},v1={}".format(stamp, signature), "User-Agent": "Stripe/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=30) as r:
                status, said = r.status, r.read()[:300].decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            status, said = e.code, e.read()[:300].decode("utf-8", "replace")
        except OSError as e:
            status, said = 0, str(e)[:300]
        with lock:
            record["deliveries"].append({"endpoint": endpoint["id"], "at": round(time.time(), 2), "status": status, "said": said})
        if 200 <= status < 300:
            return


def intent_of(ident):
    if ident not in intents:
        raise Refused(404, "invalid_request_error", "No such payment_intent: '{}'".format(ident), "resource_missing")
    return intents[ident]


def create_intent(p):
    try:
        amount = int(p["amount"])
    except (KeyError, ValueError):
        raise Refused(400, "invalid_request_error", "Invalid integer: amount")
    if amount < 50 or not p.get("currency"):
        raise Refused(400, "invalid_request_error", "Amount must be at least 50 in a currency's smallest unit, and a currency is required.", "amount_too_small")
    manual = (p.get("capture_method") == "manual"
              or ((p.get("payment_method_options") or {}).get("card") or {}).get("capture_method") == "manual")
    ident = new("pi")
    intents[ident] = {"id": ident, "object": "payment_intent", "amount": amount, "amount_received": 0, "amount_capturable": 0,
                      "currency": p["currency"].lower(), "status": "requires_payment_method", "client_secret": ident + "_secret_" + secrets.token_hex(12),
                      "capture_method": "manual" if manual else "automatic", "metadata": p.get("metadata") or {}, "description": p.get("description"),
                      "payment_method": None, "canceled_at": None, "created": int(time.time()), "livemode": False, "last_payment_error": None}
    return intents[ident]


def confirm(intent, p):
    if intent["status"] not in ("requires_payment_method", "requires_confirmation", "requires_action"):
        raise Refused(400, "invalid_request_error", "This PaymentIntent's status is {}; it cannot be confirmed.".format(intent["status"]), "payment_intent_unexpected_state")
    method = p.get("payment_method") or "pm_card_visa"
    if method not in CARDS:
        raise Refused(400, "invalid_request_error", "No such PaymentMethod: '{}'".format(method), "resource_missing")
    declined = CARDS[method][2]
    intent["payment_method"] = method
    lock_for = (armed.get(intent["id"]) or {}).pop("lock", None)
    if lock_for is None and not (armed.get(intent["id"]) or {}).get("calm") and random.random() < (FAULTS.get("lock") or {}).get("share", 0):
        lock_for = FAULTS["lock"].get("seconds", 4)
    if lock_for:
        locked[intent["id"]] = time.time() + float(lock_for)
    if declined:
        intent["last_payment_error"] = {"type": "card_error", "code": declined, "message": "Your card was declined."}
        emit("payment_intent.payment_failed", seen(intent))
        raise Refused(402, "card_error", "Your card was declined.", declined)
    if intent["capture_method"] == "manual":
        intent.update(status="requires_capture", amount_capturable=intent["amount"])
        emit("payment_intent.amount_capturable_updated", seen(intent))
    else:
        intent.update(status="succeeded", amount_received=intent["amount"])
        emit("payment_intent.succeeded", seen(intent))
    return intent


def capture(intent, p):
    if intent["status"] != "requires_capture":
        raise Refused(400, "invalid_request_error", "This PaymentIntent could not be captured because it has a status of {}.".format(intent["status"]), "payment_intent_unexpected_state")
    amount = int(p.get("amount_to_capture") or intent["amount_capturable"])
    if amount > intent["amount_capturable"] or amount <= 0:
        raise Refused(400, "invalid_request_error", "amount_to_capture must be between 1 and the capturable amount.", "amount_too_large")
    intent.update(status="succeeded", amount_received=amount, amount_capturable=0)      # what is not captured is released
    if p.get("metadata"):
        intent["metadata"].update(p["metadata"])
    emit("payment_intent.succeeded", seen(intent))
    return intent


def cancel(intent):
    if intent["status"] in ("succeeded", "canceled"):
        raise Refused(400, "invalid_request_error", "You cannot cancel this PaymentIntent because it has a status of {}.".format(intent["status"]), "payment_intent_unexpected_state")
    intent.update(status="canceled", amount_capturable=0, canceled_at=int(time.time()))
    emit("payment_intent.canceled", seen(intent))
    return intent


def refund(p):
    intent = intent_of(p.get("payment_intent") or "")
    already = sum(r["amount"] for r in refunds.values() if r["payment_intent"] == intent["id"] and r["status"] != "failed")
    amount = int(p.get("amount") or intent["amount_received"] - already)
    if intent["status"] != "succeeded" or amount <= 0 or amount > intent["amount_received"] - already:
        raise Refused(400, "invalid_request_error", "Refund amount is greater than what is left of the charge.", "charge_already_refunded")
    if (armed.get(intent["id"]) or {}).get("refuse_refunds", 0):      # as when the account's balance does not cover it
        armed[intent["id"]]["refuse_refunds"] -= 1
        refusal = Refused(400, "invalid_request_error", "Insufficient funds in your Stripe account to refund this amount.", "balance_insufficient")
        if (armed[intent["id"]].get("slow_refunds") or 0) > 0:      # and the refusal itself comes late
            armed[intent["id"]]["slow_refunds"] -= 1
            raise Late((FAULTS.get("slow_refunds") or {}).get("seconds", 13), refusal.body, refusal.status)
        raise refusal
    ident = new("re")
    refunds[ident] = {"id": ident, "object": "refund", "amount": amount, "currency": intent["currency"], "payment_intent": intent["id"],
                      "status": "succeeded", "metadata": p.get("metadata") or {}, "created": int(time.time()), "reason": p.get("reason")}
    emit("charge.refund.updated", refunds[ident], (armed.get(intent["id"]) or {}).get("late_events"))
    slow = (armed.get(intent["id"]) or {}).get("slow_refunds", 0)
    if slow:
        armed[intent["id"]]["slow_refunds"] = slow - 1
    elif not (armed.get(intent["id"]) or {}).get("calm") and random.random() < (FAULTS.get("slow_refunds") or {}).get("share", 0):
        slow = 1
    if slow:
        raise Late((FAULTS.get("slow_refunds") or {}).get("seconds", 13), refunds[ident])
    return refunds[ident]


def route(method, path, p, q):
    parts = [x for x in path.split("/") if x]
    if parts[:2] == ["v1", "payment_intents"]:
        if len(parts) == 2:
            if method == "POST":
                return create_intent(p)
            found = sorted(intents.values(), key=lambda i: -i["created"])[:int(q.get("limit") or 10)]
            return {"object": "list", "data": [seen(i) for i in found], "has_more": False, "url": "/v1/payment_intents"}
        intent = intent_of(parts[2])
        if locked.get(intent["id"], 0) > time.time():
            raise Refused(429, "invalid_request_error", "This object cannot be accessed right now because another API request or Stripe process "
                          "is currently accessing it. If you see this error intermittently, retry the request.", "lock_timeout")
        if len(parts) == 3:
            if method == "POST":
                intent["metadata"].update(p.get("metadata") or {})
                if "description" in p:
                    intent["description"] = p["description"]
            return seen(intent, q.get("expand") or p.get("expand") or ())
        return seen({"confirm": lambda: confirm(intent, p), "capture": lambda: capture(intent, p), "cancel": lambda: cancel(intent)}[parts[3]]())
    if parts[:2] == ["v1", "refunds"]:
        if len(parts) == 2 and method == "POST":
            return refund(p)
        if len(parts) == 2:      # list: newest first, of one payment if asked
            of = q.get("payment_intent")
            found = sorted((r for r in refunds.values() if not of or r["payment_intent"] == of), key=lambda r: -r["created"])
            return {"object": "list", "data": found[:int(q.get("limit") or 10)], "has_more": False, "url": "/v1/refunds"}
        if parts[2] not in refunds:
            raise Refused(404, "invalid_request_error", "No such refund: '{}'".format(parts[2]), "resource_missing")
        return refunds[parts[2]]
    if parts[:2] == ["v1", "webhook_endpoints"]:
        if len(parts) == 2 and method == "POST":
            ident = new("we")
            endpoints[ident] = {"id": ident, "object": "webhook_endpoint", "url": p["url"], "enabled_events": p.get("enabled_events") or ["*"], "status": "enabled",
                                "secret": "whsec_" + secrets.token_hex(16), "description": p.get("description"), "metadata": p.get("metadata") or {}}
            return endpoints[ident]
        if len(parts) == 3:
            if parts[2] not in endpoints:
                raise Refused(404, "invalid_request_error", "No such webhook endpoint: '{}'".format(parts[2]), "resource_missing")
            if method == "DELETE":
                return {"id": endpoints.pop(parts[2])["id"], "object": "webhook_endpoint", "deleted": True}
            if method == "POST":
                endpoints[parts[2]].update({k: p[k] for k in ("description", "url", "enabled_events") if k in p})
            return {k: v for k, v in endpoints[parts[2]].items() if k != "secret"}
    raise Refused(404, "invalid_request_error", "Unrecognized request URL ({}: {}).".format(method, path))


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def reply(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Request-Id", new("req"))
        self.end_headers()
        self.wfile.write(data)

    def handle_any(self):
        url = urlparse(self.path)
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
        q = nested(parse_qsl(url.query))
        if url.path.startswith("/_"):
            viewing = url.path == "/_ledger" and self.command == "GET" and q.get("token") in (CONFIG.get("viewers") or [])
            if not viewing and (not ADMIN or q.get("token") != ADMIN):
                return self.reply(401, {"error": "not for you"})
            with lock:
                if url.path == "/_endpoints" and self.command == "POST":
                    e = json.loads(raw)
                    endpoints[e["id"]] = dict(e, object="webhook_endpoint", status="enabled")
                    return self.reply(200, {"ok": True})
                if url.path == "/_arm" and self.command == "POST":
                    a = json.loads(raw)
                    armed.setdefault(a["intent"], {}).update({k: a[k] for k in ("slow_refunds", "refuse_refunds", "late_events", "lock", "calm") if k in a})
                    return self.reply(200, {"ok": True})
                return self.reply(200, {"payment_intents": [seen(i) for i in intents.values()], "refunds": list(refunds.values()),
                                        "events": events, "endpoints": [{k: v for k, v in e.items() if k != "secret"} for e in endpoints.values()]})
        key = (self.headers.get("Authorization") or "").replace("Bearer ", "", 1)
        if KEYS and key not in KEYS:
            return self.reply(401, {"error": {"type": "invalid_request_error", "message": "Invalid API Key provided"}})
        if key.startswith("pk_"):      # a publishable key is the customer's browser: it may confirm a payment and look at it, nothing else
            parts = [x for x in url.path.split("/") if x]
            mine = parts[:2] == ["v1", "payment_intents"] and ((len(parts) == 4 and parts[3] == "confirm" and self.command == "POST")
                                                                or (len(parts) == 3 and self.command == "GET"))
            if not mine:
                return self.reply(401, {"error": {"type": "invalid_request_error", "message":
                                                  "This API call cannot be made with a publishable API key. Please use a secret API key."}})
        again, wait = self.headers.get("Idempotency-Key"), 0
        with lock:
            if again and (key, again) in answering:      # the same request again while the first is still being answered
                return self.reply(409, {"error": {"type": "idempotency_error", "code": "idempotency_key_in_use", "message":
                                                  "There is currently another in-progress request using this Stripe Idempotent Key."}})
            if again and (key, again) in replies:      # the same request again: the first answer again, and nothing done twice
                return self.reply(*replies[(key, again)])
            try:
                answer = 200, route(self.command, url.path, nested(parse_qsl(raw)), q)
            except Refused as e:
                answer = e.status, e.body
            except Late as e:
                answer, wait = (e.status, e.answer), e.seconds
                if again:
                    answering.add((key, again))
            if again and self.command == "POST" and answer[0] != 429:      # a request refused for a lock was not carried out, and may be made again
                replies[(key, again)] = answer
        if wait:
            time.sleep(wait)
            with lock:
                answering.discard((key, again))
        try:
            self.reply(*answer)
        except OSError:      # whoever asked has stopped listening
            pass

    do_GET = do_POST = do_DELETE = handle_any


if __name__ == "__main__":
    tls = os.environ.get("TLS_CERT")
    server = ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT") or (443 if tls else 8080))), Handler)
    if tls:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(tls, os.environ["TLS_KEY"])
        server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()

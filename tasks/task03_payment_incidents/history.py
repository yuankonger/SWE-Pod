"""The company's history before task 3: task 1's history, then the week after release 2026.11.

The week is replayed against the company as the task finds it, with the release's faults in it, so the databases
hold what really happened: refunds the provider paid more than once, a subscriber billed a new order on three
days running, and renewals that did not happen until support stepped in. tools/build_task_seed.py runs this.

One of the refunds went wrong because the payment app's answer never reached Core. To make that happen, Core
reaches the payment app through `Wire` during the history: it passes everything on and can drop one answer. Core
learns an app's address afresh from its manifest at every start, so nothing of the wire is left in the seed.
"""
import datetime
import importlib.util
import os
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("base_history", os.path.join(HERE, "..", "task01_order_confirmation", "history.py"))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

# What customers wrote to support during the week. The first two are about the incident; the rest are not.
MESSAGES = [
    ("{switcher}", "I asked to switch to the small box from next month. Three small boxes have arrived this week and I can see three orders in my account. I only want one!", None, False),
    ("{late}", "My monthly box usually comes on the same day each month and nothing has shipped yet. Is something wrong with my subscription?", "shipping", True),
    ("k.yilmaz@example.com", "My card was declined at checkout but my bank says there is no problem on their side.", None, False),
    ("h.jensen@example.com", "Can I change the delivery address for my next box?", None, False),
]


class Wire:
    """The network between Core and the payment app. `lose` answers to refund requests are dropped on the way back."""
    lose = 0

    def __init__(self, port, target):
        wire = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def relay(self, body=None):
                request = urllib.request.Request(target + self.path, data=body, method=self.command, headers={
                    k: v for k, v in self.headers.items() if k.lower() in ("content-type",) or k.lower().startswith("saleor-")})
                try:
                    with urllib.request.urlopen(request, timeout=30) as r:
                        status, raw, kind = r.status, r.read(), r.headers.get("Content-Type", "application/json")
                except urllib.error.HTTPError as e:
                    status, raw, kind = e.code, e.read(), e.headers.get("Content-Type", "application/json")
                except OSError:
                    status, raw, kind = 503, b"{}", "application/json"
                if self.path.endswith("refund-requested") and wire.lose > 0:
                    wire.lose -= 1
                    self.close_connection = True
                    return self.connection.close()
                self.send_response(status)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):
                self.relay()

            def do_POST(self):
                self.relay(self.rfile.read(int(self.headers.get("Content-Length") or 0)))

        threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever, daemon=True).start()


WIRE = None


def before_start(base_port):
    """Puts the wire in place. Returns what the stack must be started with for Core to use it."""
    global WIRE
    WIRE = Wire(base_port + 8, "http://127.0.0.1:{}".format(base_port + 3))
    return {"app_urls": {"payments": "http://127.0.0.1:{}".format(base_port + 8)}}


def replay(s, Browser, log=print):
    base.replay(s, Browser, log)
    admin = s.staff_token()
    names = {c[0]: "{} {}".format(c[1], c[2]) for c in base.CUSTOMERS}

    # Refunds. Staff give two goodwill refunds of $5 on each of three shipped orders, a day apart.
    orders = [e["node"] for e in s.gql("""{ orders(first: 100) { edges { node { id number status origin userEmail
        transactions { id chargedAmount { amount } refundedAmount { amount } } } } } }""", admin)["orders"]["edges"]]
    shipped = [o for o in orders if o["status"] == "FULFILLED" and o["origin"] == "CHECKOUT" and o["transactions"]
               and o["transactions"][0]["refundedAmount"]["amount"] == 0 and o["transactions"][0]["chargedAmount"]["amount"] > 40]
    shipped = sorted(shipped, key=lambda o: int(o["number"]))
    goodwill, damaged = shipped[:3], shipped[3]
    refund = "mutation($id: ID!, $a: PositiveDecimal) { transactionRequestAction(id: $id, actionType: REFUND, amount: $a) { errors { code } } }"
    for order in goodwill:
        for _ in range(2):
            s.gql(refund, admin, id=order["transactions"][0]["id"], a=5)
    # One more refund, asked for once, of an amount never refunded on that order: $12.40 for a damaged item. The
    # payment app's answer is lost on the way to Core.
    WIRE.lose = 1
    s.gql(refund, admin, id=damaged["transactions"][0]["id"], a=12.4)

    # Renewals. The nightly run on the day the month ends, and on the two days after it. Then support cancels the
    # subscription that keeps getting orders, and the fourth night's run goes through.
    subs = s.get("subscriptions", "/api/subscriptions")[1]["subscriptions"]
    switcher = next(x for x in subs if x.get("pending_sku"))
    end = datetime.date.fromisoformat(switcher["current_period_end"])
    answers = []
    for night in range(3):
        answers.append(s.post("subscriptions", "/api/renewals/run", {"as_of": str(end + datetime.timedelta(days=night))})[0])
    s.post("subscriptions", "/api/subscriptions/{}/cancel".format(switcher["subscription_id"]))
    answers.append(s.post("subscriptions", "/api/renewals/run", {"as_of": str(end + datetime.timedelta(days=3))})[0])
    after = s.get("subscriptions", "/api/subscriptions")[1]["subscriptions"]
    late = next((x["email"] for x in after if x["status"] == "active" and x["current_period_start"] == str(end + datetime.timedelta(days=0))
                 and subs.index(next(y for y in subs if y["subscription_id"] == x["subscription_id"])) > subs.index(switcher)), None)

    agent = {"api_access_token": "support-agent-token"}
    canned = {c["short_code"]: c["content"] for c in s.request("support", "GET", "/api/v1/accounts/1/canned_responses", headers=agent)[1]}
    for who, text, reply, resolved in MESSAGES:
        email = who.format(switcher=switcher["email"], late=late or "r.singh@example.com")
        contact = s.post("support", "/public/api/v1/inboxes/web/contacts", {"name": names.get(email, email), "email": email})[1]
        conversation = s.post("support", "/public/api/v1/inboxes/web/contacts/{}/conversations".format(contact["id"]), {"message": text})[1]
        path = "/api/v1/accounts/1/conversations/{}".format(conversation["id"])
        if reply:
            s.request("support", "POST", path + "/messages", {"content": canned[reply]}, agent)
        if resolved:
            s.request("support", "POST", path + "/toggle_status", {"status": "resolved"}, agent)
    log("the week after the release: goodwill refunds on orders {}; lost answer on order {}; renewal runs answered {}; switcher {}; late {}".format(
        [o["number"] for o in goodwill], damaged["number"], answers, switcher["email"], late))

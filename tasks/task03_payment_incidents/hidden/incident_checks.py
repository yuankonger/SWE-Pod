"""The incidents after release 2026.11: what must be true once they are fixed. One check per method.

Each fails on the company as the task finds it. Nothing here is told to the agents: they get symptoms.
`rubric.toml` lists the checks with a note on what each is for.
"""
import csv
import json
import os
import sqlite3
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REFUND = """mutation($id: ID!, $a: PositiveDecimal) { transactionRequestAction(id: $id, actionType: REFUND, amount: $a) {
  transaction { refundedAmount { amount } chargedAmount { amount } events { type amount { amount } } } errors { code message } } }"""
INITIALIZE_QUERY = """subscription TransactionInitializeSession { event { ... on TransactionInitializeSession {
  action { amount currency actionType } idempotencyKey } } }"""
REFUND_QUERY = """subscription TransactionRefundRequested { event { ... on TransactionRefundRequested {
  action { amount currency actionType } transaction { id pspReference } idempotencyKey } } }"""


def over_refunds(seed_dir: str) -> dict:
    """{order number: dollars the provider paid back beyond what staff asked for}, worked out from the history.

    What staff asked for is Core's REFUND_REQUEST events on the order's payment; what the provider paid is in
    the payment app's database, in cents. Only orders where it paid more are returned."""
    def rows(service, file, sql):
        db = sqlite3.connect("file:{}?mode=ro".format(os.path.join(seed_dir, service, file)), uri=True)
        try:
            return [json.loads(body) for (body,) in db.execute(sql)]
        finally:
            db.close()

    numbers = {o["id"]: str(o["number"]) for o in rows("core", "core.db", "SELECT body FROM docs WHERE kind = 'order'")}
    paid = {}
    for refund in rows("payments", "payments.db", "SELECT body FROM refunds"):
        paid[refund["payment_intent"]] = paid.get(refund["payment_intent"], 0) + refund["amount"]
    over = {}
    for t in rows("core", "core.db", "SELECT body FROM docs WHERE kind = 'transaction'"):
        asked = round(sum(float(e["amount"]) for e in t["events"] if e["type"] == "REFUND_REQUEST") * 100)
        extra = paid.get(t["psp_reference"], 0) - asked
        if extra > 0 and t["source_kind"] == "order":
            over[numbers[t["source_id"]]] = extra / 100
    return over


REPORT = os.path.join("services", "payments", "docs", "over-refunds.csv")


class VerifierApps:
    """Two payment apps the verifier runs and Core installs beside the company's own.

    `verifier.gateway` stands alone: it charges whatever it is asked to, so Core's side of the refund contract can
    be watched without the company's payment app in the way.
    `verifier.proxy` sits in front of the company's payment app: it registers that app's own webhook queries, so
    Core builds exactly the payload the app asked for, and passes each request on. It can lose an answer on the
    way back, or deliver a request twice, which is what a network does to a webhook now and then.
    Not answering means closing the connection without a response, as an app that is restarting does."""

    def __init__(self, port, payments_url):
        self.url, self.payments = "http://127.0.0.1:{}".format(port), payments_url
        self.refund_requests = []            # what Core sent the gateway
        self.unanswered = 0                  # gateway: how many of the next refund requests get no answer
        self.lose_answers = 0                # proxy: how many of the next refund answers are lost on the way back
        self.deliver_twice = False           # proxy: pass the next refund request to the app twice
        self.app_answers = []                # proxy: what the company's app answered, in order
        self.count = 0
        apps = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def answer(self, status, body):
                raw = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def hang_up(self):
                self.close_connection = True
                self.connection.close()

            def do_GET(self):
                if self.path == "/gateway/manifest":
                    hook = lambda name, event, query: {"name": name, "syncEvents": [event], "query": query, "targetUrl": apps.url + "/gateway/" + name}  # noqa: E731
                    return self.answer(200, {"id": "verifier.gateway", "name": "Verifier gateway", "version": "1.0.0", "permissions": ["HANDLE_PAYMENTS"],
                                             "tokenTargetUrl": apps.url + "/register",
                                             "webhooks": [hook("initialize", "TRANSACTION_INITIALIZE_SESSION", INITIALIZE_QUERY),
                                                          hook("refund", "TRANSACTION_REFUND_REQUESTED", REFUND_QUERY)]})
                try:                                 # the proxy's manifest is the company's app's, with our address in it
                    with urllib.request.urlopen(apps.payments + "/api/manifest", timeout=3) as r:
                        theirs = json.loads(r.read())
                except OSError:
                    return self.answer(503, {"error": "the payment app is not up yet"})
                webhooks = [dict(w, targetUrl=apps.url + "/proxy/" + w["targetUrl"].rsplit("/", 1)[-1]) for w in theirs["webhooks"]]
                self.answer(200, {"id": "verifier.proxy", "name": "Verifier proxy", "version": "1.0.0", "permissions": ["HANDLE_PAYMENTS"],
                                  "tokenTargetUrl": apps.url + "/register", "webhooks": webhooks})

            def forward(self, name, body):
                request = urllib.request.Request(apps.payments + "/api/webhooks/saleor/" + name, data=body, method="POST",
                                                 headers={"Content-Type": "application/json"})
                try:
                    with urllib.request.urlopen(request, timeout=30) as r:
                        return r.status, r.read()
                except urllib.error.HTTPError as e:
                    return e.code, e.read()

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                apps.count += 1
                if self.path == "/register":
                    return self.answer(200, {"success": True})
                kind, name = self.path.strip("/").split("/", 1)
                if kind == "gateway":
                    payload = json.loads(body)
                    if name == "initialize":
                        return self.answer(200, {"pspReference": "vg_{}".format(apps.count), "result": "CHARGE_SUCCESS", "amount": payload["action"]["amount"]})
                    apps.refund_requests.append(payload)
                    if apps.unanswered > 0:
                        apps.unanswered -= 1
                        return self.hang_up()
                    return self.answer(200, {"pspReference": "vgr_{}".format(apps.count), "result": "REFUND_SUCCESS", "amount": payload["action"]["amount"]})
                refund = name.endswith("refund-requested")
                status, raw = self.forward(name, body)
                if refund:
                    apps.app_answers.append((status, raw))
                    if apps.deliver_twice:               # the same bytes again, as a redelivery is
                        apps.deliver_twice = False
                        status, raw = self.forward(name, body)
                        apps.app_answers.append((status, raw))
                    if apps.lose_answers > 0:
                        apps.lose_answers -= 1
                        return self.hang_up()
                self.answer(status, raw)

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


class IncidentChecks:
    apps = None

    @classmethod
    def other_apps(cls, base_port):
        # port +8 is the one of the company's ten that no service uses; the payment app is at +3
        cls.apps = VerifierApps(base_port + 8, "http://127.0.0.1:{}".format(base_port + 3))
        return [cls.apps.url + "/gateway/manifest", cls.apps.url + "/proxy/manifest"]

    def _all(self, path, name):
        """Every record of one of the payment app's lists, paged or not."""
        found, last, more = [], None, True
        while more:
            status, page = self.s.get("payments", path + ("?starting_after=" + last if last else ""))
            self.assertEqual(status, 200, page)
            found += page[name]
            more = bool(page.get("has_more")) and bool(page[name])
            last = page[name][-1].get("id") if page[name] else None
        return found

    def provider_refunds(self, order):
        """What the payment provider paid back on the order's payment, in the provider's units, oldest first."""
        intent = order["transactions"][0]["pspReference"]
        return [r["amount"] for r in self._all("/api/refunds", "refunds") if r["payment_intent"] == intent]

    def refund(self, order, amount):
        answer = self.s.gql(REFUND, self.admin, id=order["transactions"][0]["id"], a=amount)["transactionRequestAction"]
        self.assertEqual(answer["errors"], [])
        return answer["transaction"]

    @staticmethod
    def outcomes(transaction):
        return [e["type"] for e in transaction["events"] if e["type"] in ("REFUND_SUCCESS", "REFUND_FAILURE")]

    # ---- refunds ----
    def test_core_payments__the_same_amount_refunded_twice_is_paid_twice(self):
        order = self.buy("goodwill@example.com", {"ADD-TEA": 4})
        for expected in (5.0, 10.0):
            transaction = self.refund(order, 5)
            self.assertEqual(self.outcomes(transaction)[-1], "REFUND_SUCCESS", "Core recorded the refund as failed")
            self.assertEqual(transaction["refundedAmount"]["amount"], expected)
        self.assertEqual(self.provider_refunds(order), [500, 500], "the provider did not pay back exactly what staff asked for")

    def test_payments_api__the_refund_ledger_holds_what_the_provider_paid(self):
        order = self.buy("ledger@example.com", {"ADD-TEA": 4})
        for _ in range(2):
            self.refund(order, 5)
        intent = order["transactions"][0]["pspReference"]
        status, body = self.s.get("payments", "/api/refund-requests")
        self.assertEqual(status, 200, "the ledger of refund requests that release 2026.11 added is gone")
        ledger = sorted(r["refund"] for r in self._all("/api/refund-requests", "refund_requests") if r["payment_intent"] == intent)
        paid = sorted(r["id"] for r in self._all("/api/refunds", "refunds") if r["payment_intent"] == intent)
        self.assertEqual(len(paid), 2, "the provider did not pay back exactly what staff asked for")
        self.assertEqual(ledger, paid, "the ledger and the provider do not hold the same refunds")

    def test_core_payments__a_refund_request_delivered_twice_is_paid_once(self):
        order = self.buy("redelivered@example.com", {"ADD-TEA": 4}, gateway="verifier.proxy")
        del self.apps.app_answers[:]
        self.apps.deliver_twice = True
        transaction = self.refund(order, 4)
        answers = []
        for status, raw in self.apps.app_answers[:2]:
            try:
                body = json.loads(raw)
            except ValueError:
                body = {}
            answers.append((status, body.get("result"), body.get("pspReference")))
        self.assertEqual(len(answers), 2)
        self.assertEqual([a[0] for a in answers], [200, 200], "the payment app failed on a refund request: {}".format(answers))
        self.assertEqual(self.provider_refunds(order), [400], "one refund request, delivered to the payment app twice, was paid twice")
        self.assertEqual(answers[0][:2], (200, "REFUND_SUCCESS"), answers)
        self.assertEqual(answers[1], answers[0], "the repeat was not answered as the first delivery was")
        self.assertEqual((self.outcomes(transaction), transaction["refundedAmount"]["amount"]), (["REFUND_SUCCESS"], 4.0))
        self.refund(order, 4)                         # a new request for the same amount is another refund
        self.assertEqual(self.provider_refunds(order), [400, 400])

    def test_core_api__a_refund_request_is_repeated_under_one_key(self):
        order = self.buy("gateway@example.com", {"ADD-TEA": 2}, gateway="verifier.gateway")
        sent = self.apps.refund_requests
        del sent[:]
        self.apps.unanswered = 1
        transaction = self.refund(order, 3)
        self.apps.unanswered = 0
        self.assertGreaterEqual(len(sent), 2, "Core did not ask a payment app that gave no answer again (release 2026.11 made it ask again)")
        self.assertEqual(len({r["idempotencyKey"] for r in sent}), 1, "Core sent one refund request under different idempotency keys")
        self.assertEqual((self.outcomes(transaction), transaction["refundedAmount"]["amount"]), (["REFUND_SUCCESS"], 3.0))
        first = sent[0]["idempotencyKey"]
        del sent[:]
        self.refund(order, 3)                         # a new request is not a repeat of the last one
        self.assertNotEqual(sent[0]["idempotencyKey"], first, "two different refund requests were sent under one key")

    def test_core_payments__a_lost_answer_does_not_pay_twice(self):
        order = self.buy("lost-answer@example.com", {"ADD-TEA": 4}, gateway="verifier.proxy")
        self.apps.lose_answers = 1
        transaction = self.refund(order, 6)
        self.apps.lose_answers = 0
        self.assertEqual(self.provider_refunds(order), [600], "the payment app's answer was lost once and the provider paid more than once")
        self.assertEqual((self.outcomes(transaction), transaction["refundedAmount"]["amount"]), (["REFUND_SUCCESS"], 6.0),
                         "the provider paid and Core does not show the refund")

    def test_payments_data__finance_gets_the_orders_that_were_refunded_too_much(self):
        expected = over_refunds(os.environ["SEEDCO_SEED_DIR"])
        self.assertTrue(expected, "the history holds no over-refunded order: the task's seed is not the one this check was written for")
        path = os.path.join(os.environ["SEEDCO_ROOT"], REPORT)
        self.assertTrue(os.path.isfile(path), "there is no {}".format(REPORT))
        with open(path, newline="") as f:
            rows = [r for r in csv.reader(f) if r and any(cell.strip() for cell in r)]
        self.assertEqual([c.strip().lower() for c in rows[0]], ["order_number", "overpaid"], "the first line must be the header order_number,overpaid")
        listed = {}
        for row in rows[1:]:
            self.assertEqual(len(row), 2, "a line is not `order number, amount`: {}".format(row))
            listed[row[0].strip().lstrip("#")] = round(float(row[1].strip().lstrip("$")), 2)      # "#6" and "$24.80" are accepted
        self.assertEqual(listed, expected, "the report does not list exactly the orders the provider overpaid, with the amount overpaid")

    # ---- renewals ----
    def switcher_and_neighbour(self, tag):
        """A subscriber who has asked to move to the small box at the end of the month, and one who subscribed after them."""
        switcher, neighbour = "switcher-{}@example.com".format(tag), "neighbour-{}@example.com".format(tag)
        self.buy(switcher, {"BOX-L": 1})
        sub = (self.s.wait_for(lambda: self.subscriptions(switcher), timeout=20) or [None])[0]
        self.assertIsNotNone(sub, "no subscription was started for the paid order")
        self.buy(neighbour, {"BOX-S": 1})
        self.assertTrue(self.s.wait_for(lambda: self.subscriptions(neighbour), timeout=20), "no subscription was started for the paid order")
        status, changed = self.s.post("subscriptions", "/api/subscriptions/{}/plan".format(sub["subscription_id"]), {"sku": "BOX-S"})
        self.assertEqual((status, changed.get("pending_sku")), (200, "BOX-S"), changed)
        return switcher, neighbour, sub["current_period_end"]

    def test_subscriptions_core__a_scheduled_plan_change_renews_once_on_the_new_plan(self):
        switcher, _, end = self.switcher_and_neighbour("a")
        runs = [self.s.post("subscriptions", "/api/renewals/run", {"as_of": end}) for _ in range(2)]     # two nights
        self.assertEqual(runs[0][0], 200, "the renewal run failed: {}".format(runs[0][1]))
        renewals = self.renewals(switcher)
        self.assertEqual(len(renewals), 1, "the subscriber has {} renewal orders for one month".format(len(renewals)))
        order = self.order(renewals[0]["id"])
        self.assertEqual(([l["productSku"] for l in order["lines"]], order["chargeStatus"], order["status"]), (["BOX-S"], "FULL", "UNFULFILLED"))
        sub = self.subscriptions(switcher)[0]
        self.assertEqual((sub["sku"], sub["status"], sub["current_period_start"], sub.get("pending_sku")), ("BOX-S", "active", end, None))

    def test_subscriptions_core__the_renewal_order_of_a_plan_change_names_the_new_box(self):
        switcher, _, end = self.switcher_and_neighbour("c")
        self.s.post("subscriptions", "/api/renewals/run", {"as_of": end})
        renewals = self.renewals(switcher)
        self.assertTrue(renewals, "the subscription did not renew")
        notes = [m["value"] for m in renewals[0]["metadata"] if m["key"] == "subscription_plan_change"]
        self.assertEqual(notes, ["Small monthly box"], "the note for the warehouse that release 2026.11 added is missing or wrong")

    def test_subscriptions_core__a_subscriber_after_one_with_a_plan_change_is_renewed(self):
        _, neighbour, end = self.switcher_and_neighbour("b")
        self.s.post("subscriptions", "/api/renewals/run", {"as_of": end})
        renewals = self.renewals(neighbour)
        self.assertEqual(len(renewals), 1, "a subscriber who signed up after one with a plan change has {} renewal orders".format(len(renewals)))
        self.assertEqual(self.subscriptions(neighbour)[0]["current_period_start"], end)

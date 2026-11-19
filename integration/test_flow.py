"""End-to-end checks on the base company: purchases followed through every service."""
import os
import sys
import tempfile
import unittest
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "platform"))
sys.path.insert(0, HERE)

from shop import Browser  # noqa: E402
from stack import Stack  # noqa: E402

BASE_PORT = int(os.environ.get("SEEDCO_BASE_PORT", "7000"))
ITEMS = {"BOX-S": 2, "ADD-TEA": 1}
# 2 x 24.99 = 49.98 and 6.25, taxed line by line at 8.75%: 54.35 and 6.80. Net 56.23, tax 4.92, shipping 5.00, total 66.15.
ORDER = """query($id: ID!) { order(id: $id) { id number status chargeStatus userEmail total { gross { amount } tax { amount } }
  totalRefunded { amount } lines { id productSku quantity } transactions { id pspReference chargedAmount { amount } } } }"""


class FlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = Stack(base_port=BASE_PORT).start()

    @classmethod
    def tearDownClass(cls):
        cls.stack.stop()

    def emails(self, address, kind=None):
        emails = self.stack.get("notifications", "/outbox?email=" + urllib.parse.quote(address))[1]["emails"]
        return [e for e in emails if kind is None or e["kind"] == kind]

    def buy(self, email, items=ITEMS, **details):
        """Buys through the shop. Returns (browser, the order as Core holds it)."""
        browser = Browser(self.stack.url("storefront"))
        status, location, text = browser.buy(items, email=email, **details)
        self.assertEqual(status, 303, text[-600:] + self.stack.log("storefront")[-800:])
        order_id = urllib.parse.unquote(location.rsplit("/", 1)[-1])
        return browser, self.stack.gql(ORDER, id=order_id)["order"]

    def test_a_purchase_reaches_every_service(self):
        s = self.stack
        browser, order = self.buy("pat@example.com")
        self.assertEqual((order["status"], order["chargeStatus"], order["userEmail"]), ("UNFULFILLED", "FULL", "pat@example.com"))
        self.assertEqual(order["total"], {"gross": {"amount": 66.15}, "tax": {"amount": 4.92}})

        _, _, page = browser.open("/orders/" + urllib.parse.quote(order["id"], safe=""))
        for text in ("Order #" + order["number"], "Being prepared", "Paid", "$49.98", "$56.23", "$5.00", "$4.92", "$66.15"):
            self.assertIn(text, page)

        intents = s.get("payments", "/api/payment-intents")[1]["payment_intents"]
        mine = [i for i in intents if i["id"] == order["transactions"][0]["pspReference"]]
        self.assertEqual([(i["amount"], i["currency"], i["status"]) for i in mine], [(6615, "usd", "succeeded")])

        documents = s.wait_for(lambda: [d for d in s.get("taxes", "/api/tax-documents")[1]["documents"] if d["order_id"] == order["id"]])
        self.assertTrue(documents, s.log("taxes")[-1500:])
        self.assertEqual((float(documents[0]["tax"]), documents[0]["status"]), (4.92, "committed"))

        emails = s.wait_for(lambda: len(self.emails("pat@example.com")) >= 2 and self.emails("pat@example.com"))
        self.assertTrue(emails, "notifications sent fewer than two emails\n" + s.log("notifications")[-1500:])
        kinds = {e["kind"]: e for e in emails}
        self.assertIn("Total: $66.15", kinds["order_confirmation"]["body"])
        for text in ("2 x Small monthly box  $49.98", "Subtotal: $56.23", "Shipping: $5.00", "Tax: $4.92", "Total: $66.15"):
            self.assertIn(text, kinds["receipt"]["body"])
        self.assertEqual(s.get("notifications", "/dropped")[1]["dropped"], [])

    def test_a_declined_card_places_no_order(self):
        browser = Browser(self.stack.url("storefront"))
        status, _, text = browser.buy(ITEMS, email="decl@example.com", paymentMethod="pm_card_declined")
        self.assertEqual(status, 400)
        self.assertIn("did not go through (card_declined)", text)
        found = self.stack.gql('{ orders(filter: {customer: "decl@example.com"}) { totalCount } }', self.stack.staff_token())
        self.assertEqual(found["orders"]["totalCount"], 0)
        self.assertEqual(self.emails("decl@example.com"), [])

    def test_staff_fulfil_cancel_and_refund(self):
        s, admin = self.stack, self.stack.staff_token()
        _, shipped = self.buy("ship@example.com", postalCode="10001")
        self.assertEqual(shipped["total"]["tax"]["amount"], 3.38)      # 6%: 49.98 -> 52.98, 6.25 -> 6.63
        lines = [{"orderLineId": l["id"], "quantity": l["quantity"]} for l in shipped["lines"]]
        done = s.gql("mutation($o: ID!, $l: [OrderFulfillLineInput!]!) { orderFulfill(order: $o, input: {lines: $l}) { order { status } errors { code } } }",
                     admin, o=shipped["id"], l=lines)["orderFulfill"]
        self.assertEqual(done, {"order": {"status": "FULFILLED"}, "errors": []})
        self.assertTrue(s.wait_for(lambda: self.emails("ship@example.com", "shipping")))

        _, cancelled = self.buy("cancel@example.com")
        s.gql("mutation($id: ID!) { orderCancel(id: $id) { errors { code } } }", admin, id=cancelled["id"])
        refund = s.gql("mutation($id: ID!) { transactionRequestAction(id: $id, actionType: REFUND) { transaction { refundedAmount { amount } } errors { code message } } }",
                       admin, id=cancelled["transactions"][0]["id"])["transactionRequestAction"]
        self.assertEqual(refund, {"transaction": {"refundedAmount": {"amount": 66.15}}, "errors": []})
        after = s.gql(ORDER, id=cancelled["id"])["order"]
        self.assertEqual((after["status"], after["chargeStatus"], after["totalRefunded"]["amount"]), ("CANCELED", "NONE", 66.15))
        self.assertEqual([r["amount"] for r in s.get("payments", "/api/refunds")[1]["refunds"]
                          if r["payment_intent"] == cancelled["transactions"][0]["pspReference"]], [6615])
        emails = s.wait_for(lambda: len(self.emails("cancel@example.com")) >= 4 and self.emails("cancel@example.com"))
        self.assertTrue(emails, s.log("notifications")[-1500:])
        self.assertEqual(sorted(e["kind"] for e in emails), ["cancellation", "order_confirmation", "receipt", "refund"])
        self.assertIn("We have refunded $66.15", [e for e in emails if e["kind"] == "refund"][0]["body"])
        voided = s.wait_for(lambda: [d for d in s.get("taxes", "/api/tax-documents")[1]["documents"]
                                     if d["order_id"] == cancelled["id"] and d["status"] == "voided"])
        self.assertTrue(voided)


    def test_a_subscription_is_upgraded_downgraded_and_renewed(self):
        s = self.stack
        email = "sub@example.com"
        browser, first = self.buy(email)
        subs = s.wait_for(lambda: s.get("subscriptions", "/api/subscriptions?email=" + urllib.parse.quote(email))[1]["subscriptions"])
        self.assertTrue(subs, "no subscription was started\n" + s.log("subscriptions")[-1500:])
        sub = subs[0]
        self.assertEqual((sub["sku"], sub["qty"], sub["status"], sub["payment_method"]), ("BOX-S", 2, "active", "pm_card_ok"))
        end = sub["current_period_end"]

        # The account page offers the upgrade. On the first day of the period the whole month's difference is due:
        # 2 x (39.50 - 24.99) = 29.02, plus 8.75% tax = 31.56. The subscriptions app bills it as a new order in Core.
        _, _, account = browser.open("/account")
        self.assertIn("Upgrade to Large monthly box now", account)
        status, location, _ = browser.open("/account/subscriptions/{}/plan".format(sub["subscription_id"]), {"sku": "BOX-L"})
        self.assertEqual((status, location), (303, "/account"))
        admin = s.staff_token()
        orders = s.gql("""query($e: String) { orders(filter: {customer: $e}) { edges { node { number origin chargeStatus total { gross { amount } }
            metadata { key value } } } } }""", admin, e=email)["orders"]["edges"]
        change = orders[0]["node"]                                   # newest first
        self.assertEqual((change["origin"], change["chargeStatus"], change["total"]["gross"]["amount"]), ("DRAFT", "FULL", 31.56))
        self.assertIn({"key": "subscription_reason", "value": "plan_change"}, change["metadata"])
        self.assertTrue(s.wait_for(lambda: [e for e in self.emails(email, "subscription_plan_changed")
                                            if e["body"] == "Your plan is now Large monthly box."]), s.log("notifications")[-1500:])

        # A downgrade waits for the period to end, then the renewal is charged at the small plan's price.
        browser.open("/account/subscriptions/{}/plan".format(sub["subscription_id"]), {"sku": "BOX-S"})
        self.assertIn("Changes to Small monthly box on " + end, browser.open("/account")[2])
        status, run = s.post("subscriptions", "/api/renewals/run", {"as_of": end})
        self.assertEqual(status, 200, run)                            # the run renews every subscription that is due
        renewed = s.get("subscriptions", "/api/subscriptions?email=" + urllib.parse.quote(email))[1]["subscriptions"][0]
        self.assertEqual((renewed["sku"], renewed["current_period_start"]), ("BOX-S", end))
        receipts = s.wait_for(lambda: len(self.emails(email, "receipt")) >= 3 and self.emails(email, "receipt"))
        self.assertTrue(receipts, s.log("notifications")[-1500:])
        self.assertIn("Total: $54.35", receipts[-1]["body"])          # 2 x 24.99 = 49.98, tax 4.37, renewals ship free
        self.assertEqual(len(s.get("subscriptions", "/api/subscriptions?email=" + urllib.parse.quote(email))[1]["subscriptions"]), 1)

        # A card that starts declining: the renewal fails, the unpaid order is cancelled, the customer is told.
        s.request("subscriptions", "PUT", "/api/customers/payment-method", {"email": email, "payment_method": "pm_card_declined"})
        status, run = s.post("subscriptions", "/api/renewals/run", {"as_of": renewed["current_period_end"]})
        self.assertEqual(run["failed"], 1, run)
        failed = s.wait_for(lambda: self.emails(email, "subscription_payment_failed"))
        self.assertIn("A payment of $54.35 for Small monthly box did not go through (card_declined)", failed[0]["body"])
        newest = s.gql("query($e: String) { orders(first: 1, filter: {customer: $e}) { edges { node { status chargeStatus } } } }", admin, e=email)
        self.assertEqual(newest["orders"]["edges"][0]["node"], {"status": "CANCELED", "chargeStatus": "NONE"})

    def test_staff_work_through_the_dashboard_and_permissions_hold(self):
        s = self.stack
        _, order = self.buy("dash@example.com")
        path = "/orders/" + urllib.parse.quote(order["id"], safe="")
        support = Browser(s.url("dashboard"))
        self.assertEqual(support.open("/")[1], "/login")
        self.assertEqual(support.open("/login", {"email": "support@seedco.example", "password": "support"})[0], 303)
        self.assertIn("dash@example.com", support.open("/?q=dash")[2])
        status, _, text = support.open(path + "/refund", {"transaction": order["transactions"][0]["id"], "amount": ""})
        self.assertEqual(status, 403)                                 # support staff may manage orders, not payments
        self.assertIn("HANDLE_PAYMENTS", text)
        admin = Browser(s.url("dashboard"))
        admin.open("/login", {"email": "admin@seedco.example", "password": "admin"})
        self.assertEqual(admin.open(path + "/refund", {"transaction": order["transactions"][0]["id"], "amount": "6.15"})[0], 303)
        page = admin.open(path)[2]
        for text in ("Refunded $6.15", "REFUND_SUCCESS $6.15", "Storefront checkout", "Fulfill remaining items"):
            self.assertIn(text, page)
        apps = admin.open("/apps")[2]
        for text in ("seedco.taxes", "CHECKOUT_CALCULATE_TAXES (sync)", "pricesEnteredWithTax", "seedco.subscriptions"):
            self.assertIn(text, apps)

    def test_support_sees_the_customers_orders_and_hears_about_refunds(self):
        s = self.stack
        _, order = self.buy("help@example.com")
        _, contact = s.post("support", "/public/api/v1/inboxes/web/contacts", {"name": "Hel P", "email": "help@example.com"})
        base = "/public/api/v1/inboxes/web/contacts/{}/conversations".format(contact["id"])
        _, conversation = s.post("support", base, {"message": "Please refund my order"})
        agent = {"api_access_token": "support-agent-token"}
        self.assertEqual(s.get("support", "/api/v1/accounts/1/conversations")[0], 401)
        status, listed = s.request("support", "GET", "/api/v1/accounts/1/conversations?status=open", headers=agent)
        self.assertIn(conversation["id"], [c["id"] for c in listed["data"]["payload"]])
        status, panel = s.request("support", "GET", "/api/v1/accounts/1/integrations/saleor/orders?contact_id={}".format(contact["id"]), headers=agent)
        self.assertEqual(status, 200, panel)
        self.assertEqual([(o["number"], o["total"], o["charge_status"], o["items"]) for o in panel["orders"]],
                         [(order["number"], "66.15", "FULL", "2 x Small monthly box, 1 x Tea add-on")])
        s.gql("mutation($id: ID!) { transactionRequestAction(id: $id, actionType: REFUND) { errors { code } } }",
              s.staff_token(), id=order["transactions"][0]["id"])
        path = "/api/v1/accounts/1/conversations/{}".format(conversation["id"])
        notes = s.wait_for(lambda: [m["content"] for m in s.request("support", "GET", path, headers=agent)[1]["messages"] if m["private"]])
        self.assertEqual(notes, ["Order #{} was refunded: $66.15 so far.".format(order["number"])], s.log("support")[-1500:])
        customer_view = s.get("support", base + "/{}".format(conversation["id"]))[1]
        self.assertEqual([m["content"] for m in customer_view["messages"]], ["Please refund my order"])   # no private notes

    def test_every_supported_mobile_release_can_still_buy(self):
        import json
        import subprocess
        mobile = os.path.join(self.stack.root, "services", "mobile")
        with open(os.path.join(mobile, "releases", "supported.json")) as f:
            supported = json.load(f)["supported"]
        self.assertTrue(supported)
        for version in supported + ["source"]:
            run = subprocess.run(["./run", "replay", version, self.stack.url("core", "/graphql/"), json.dumps({"email": "mobile@example.com"})],
                                 cwd=mobile, capture_output=True, text=True, timeout=120)
            screens = json.loads(run.stdout.strip().splitlines()[-1])
            self.assertTrue(screens["ok"], "release {} cannot buy: {}".format(version, screens))
            self.assertEqual((screens["order"]["status"], screens["order"]["paid"]), ("Being prepared", True))
            self.assertEqual([screens["order"][k] for k in ("subtotal", "shipping", "tax", "total")], ["$56.23", "$5.00", "$4.92", "$66.15"])
            self.assertEqual(screens["shop"]["products"][0], {"variantId": screens["shop"]["products"][0]["variantId"], "sku": "BOX-S",
                                                              "name": "Small monthly box", "price": "$24.99"})


class MonitoringTest(unittest.TestCase):
    def test_prometheus_scrapes_every_service_and_pages_when_one_goes_down(self):
        import signal
        with Stack(base_port=BASE_PORT + 40) as s:
            if "prometheus" not in s.procs:
                self.skipTest("prometheus is not installed")
            Browser(s.url("storefront")).buy(ITEMS)

            def query(expr):
                return s.get("prometheus", "/api/v1/query?query=" + urllib.parse.quote(expr))[1]["data"]["result"]

            up = s.wait_for(lambda: len(query("up == 1")) == len(s.services) and query("up == 1"), timeout=20)
            self.assertTrue(up, query("up"))
            self.assertEqual(sorted(r["metric"]["service"] for r in up), sorted(s.services))
            paid = s.wait_for(lambda: query('seedco_payment_results_total{result="CHARGE_SUCCESS"}'), timeout=20)
            self.assertEqual(paid[0]["value"][1], "1")
            self.assertTrue(s.wait_for(lambda: query('saleor_webhook_request_count_total{saleor_app_identifier="seedco.taxes",outcome="success"}'), timeout=20))
            self.assertEqual(s.get("prometheus", "/api/v1/alerts")[1]["data"]["alerts"], [])

            os.killpg(s.procs["taxes"].pid, signal.SIGKILL)

            def firing():
                return [a for a in s.get("prometheus", "/api/v1/alerts")[1]["data"]["alerts"] if a["state"] == "firing"]

            alerts = s.wait_for(firing, timeout=30)
            self.assertEqual([(a["labels"]["alertname"], a["labels"]["service"]) for a in alerts], [("ServiceDown", "taxes")])
            # with the tax app gone a checkout cannot be taxed, and the checkout alerts follow
            status, _, text = Browser(s.url("storefront")).buy(ITEMS)
            self.assertEqual(status, 400, text[-300:])
            names = s.wait_for(lambda: {"TaxCalculationFailing", "SyncWebhookFailing"} <= {a["labels"]["alertname"] for a in firing()}
                               and sorted({a["labels"]["alertname"] for a in firing()}), timeout=30)
            self.assertEqual(names, ["ServiceDown", "SyncWebhookFailing", "TaxCalculationFailing"])


class RestartTest(unittest.TestCase):
    def test_orders_payments_and_emails_survive_a_restart(self):
        data = tempfile.mkdtemp(prefix="seedco-restart-")
        with Stack(base_port=BASE_PORT + 20, data_dir=data) as s:
            status, location, text = Browser(s.url("storefront")).buy(ITEMS)
            self.assertEqual(status, 303, text[-600:])
            order_id = urllib.parse.unquote(location.rsplit("/", 1)[-1])
            self.assertTrue(s.wait_for(lambda: len(s.get("notifications", "/outbox?email=pat%40example.com")[1]["emails"]) >= 2))
        with Stack(base_port=BASE_PORT + 20, data_dir=data) as s:
            order = s.gql(ORDER, id=order_id)["order"]
            self.assertEqual((order["number"], order["chargeStatus"], order["total"]["gross"]["amount"]), ("1", "FULL", 66.15))
            self.assertEqual(len(s.get("notifications", "/outbox?email=pat%40example.com")[1]["emails"]), 2)
            self.assertEqual(len(s.get("payments", "/api/payment-intents")[1]["payment_intents"]), 1)
            self.assertEqual(len(s.get("taxes", "/api/tax-documents")[1]["documents"]), 1)
            # The first run may have stopped before Core delivered the order event to the subscriptions app.
            # Core keeps undelivered events in its database and sends them after the restart.
            subs = s.wait_for(lambda: s.get("subscriptions", "/api/subscriptions?email=pat%40example.com")[1]["subscriptions"])
            self.assertEqual([(x["sku"], x["status"]) for x in subs or []], [("BOX-S", "active")])


if __name__ == "__main__":
    unittest.main()

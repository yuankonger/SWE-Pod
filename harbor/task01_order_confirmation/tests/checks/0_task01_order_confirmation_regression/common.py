"""What the end-to-end checks share: the running company, buying something, and looking at what each system holds.

Purchases go through Core's API, which is the contract every shop is built on. The pages of the web shop and
the dashboard are only touched by the checks that are about those pages, so a page that is laid out differently
cannot fail a check that is about something else.

The company under test is the one in SEEDCO_ROOT (default: the directory this one sits in). It is started from
the history in SEEDCO_SEED_DIR, or, without that, from the copies each owner holds under `services/<owner>/data`.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.environ.get("SEEDCO_ROOT") or os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.append(os.path.join(ROOT, "platform"))     # the stack runner, unless whoever runs this put its own first

from shop import Browser  # noqa: E402,F401
from stack import Stack  # noqa: E402

ITEMS = {"BOX-S": 2, "ADD-TEA": 1}     # net 56.23, tax 4.92 at 8.75%, shipping 5.00, total 66.15
ADDRESS = {"firstName": "Pat", "lastName": "Lee", "streetAddress1": "1 Main St", "city": "San Francisco",
           "postalCode": "94105", "country": "US", "countryArea": "CA"}
ORDER = """query($id: ID!) { order(id: $id) { id number status chargeStatus origin userEmail metadata { key value }
  total { gross { amount } } lines { id productSku quantity } transactions { id pspReference } } }"""
FULFIL = "mutation($o: ID!, $l: [OrderFulfillLineInput!]!) { orderFulfill(order: $o, input: {lines: $l}) { order { status } errors { code } } }"
PRISTINE_MOBILE = os.path.join(HERE, "pristine", "mobile-1.0.0")     # release 1.0.0 exactly as it was shipped


class Company:
    """Starts the company once for all checks. Mixed into the TestCase that holds the checks."""

    @classmethod
    def history(cls):
        """The directory of databases the company starts from, or None to start empty."""
        if os.environ.get("SEEDCO_SEED_DIR"):
            return os.environ["SEEDCO_SEED_DIR"]
        cls._seed = tempfile.mkdtemp(prefix="seedco-seed-")
        for owner in sorted(os.listdir(os.path.join(ROOT, "services"))):
            data = os.path.join(ROOT, "services", owner, "data")
            if os.path.isdir(data):
                shutil.copytree(data, os.path.join(cls._seed, owner))
        return cls._seed if os.listdir(cls._seed) else None

    @classmethod
    def other_apps(cls, base_port):
        """Manifest URLs of apps Core should install besides the company's own. They must already be served."""
        return []

    @classmethod
    def setUpClass(cls):
        cls._seed = None
        base_port = int(os.environ.get("SEEDCO_BASE_PORT", "7100"))
        cls.s = Stack(root=ROOT, base_port=base_port, start_timeout=240, seed_dir=cls.history(), extra_manifests=cls.other_apps(base_port))
        try:
            # Anything left listening on these ports is killed first: a company started beside a stale one would
            # be checked against the stale one's answers.
            cls.s.start(clear_ports=True)
            cls.admin = cls.s.staff_token()
            nodes = cls.s.gql("{ products(first: 100) { edges { node { variants { id sku } } } } }")["products"]["edges"]
            cls.variants = {v["sku"]: v["id"] for e in nodes for v in e["node"]["variants"] if v["sku"]}
            cls.first = cls.buy("pat@example.com")       # the order most checks look at; nobody confirms it
        except Exception:
            cls.s.stop()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.s.stop()
        if cls._seed:
            shutil.rmtree(cls._seed, ignore_errors=True)

    @classmethod
    def buy(cls, email, items=None, payment_method="pm_card_ok", gateway="seedco.payments"):
        """Buys through Core's API, as every shop does underneath, and returns the order straight afterwards."""
        def done(name, payload):
            if payload.get("errors"):
                raise AssertionError("Core refused {}: {}".format(name, payload["errors"]))
            return payload

        lines = [{"variantId": cls.variants[sku], "quantity": qty} for sku, qty in (items or ITEMS).items()]
        checkout = done("checkoutCreate", cls.s.gql(
            """mutation($email: String, $lines: [CheckoutLineInput!]) { checkoutCreate(input: {channel: "default-channel", email: $email, lines: $lines}) {
               checkout { id } errors { code message } } }""", email=email, lines=lines)["checkoutCreate"])["checkout"]["id"]
        methods = done("checkoutShippingAddressUpdate", cls.s.gql(
            """mutation($id: ID!, $a: AddressInput!) { checkoutShippingAddressUpdate(id: $id, shippingAddress: $a) {
               checkout { shippingMethods { id } } errors { code message } } }""", id=checkout, a=ADDRESS)["checkoutShippingAddressUpdate"])
        done("checkoutDeliveryMethodUpdate", cls.s.gql(
            "mutation($id: ID!, $m: ID) { checkoutDeliveryMethodUpdate(id: $id, deliveryMethodId: $m) { errors { code message } } }",
            id=checkout, m=methods["checkout"]["shippingMethods"][0]["id"])["checkoutDeliveryMethodUpdate"])
        paid = done("transactionInitialize", cls.s.gql(
            """mutation($id: ID!, $gateway: String!, $data: JSON) { transactionInitialize(id: $id, paymentGateway: {id: $gateway, data: $data}) {
               transactionEvent { type message } errors { code message } } }""", id=checkout, gateway=gateway,
            data={"paymentMethod": payment_method})["transactionInitialize"])
        if paid["transactionEvent"]["type"] != "CHARGE_SUCCESS":
            raise AssertionError("the payment was not taken: {}".format(paid["transactionEvent"]))
        order = done("checkoutComplete", cls.s.gql(
            "mutation($id: ID!) { checkoutComplete(id: $id) { order { id } errors { code message } } }", id=checkout)["checkoutComplete"])["order"]
        return cls.s.gql(ORDER, id=order["id"])["order"]

    def order(self, order_id):
        return self.s.gql(ORDER, id=order_id)["order"]

    def orders_of(self, email):
        """A customer's orders as staff see them, newest first."""
        found = self.s.gql("""query($e: String) { orders(first: 100, filter: {customer: $e}) { edges { node { id number status chargeStatus origin
            userEmail total { gross { amount } } metadata { key value } lines { id quantity } } } } }""", self.admin, e=email)
        # Core's customer filter is a search: it also finds addresses that contain this one
        return [e["node"] for e in found["orders"]["edges"] if e["node"]["userEmail"] == email]

    def emails(self, address, kind=None):
        emails = self.s.get("notifications", "/outbox?email=" + urllib.parse.quote(address))[1]["emails"]
        return [e for e in emails if kind is None or e["kind"] == kind]

    def documents(self, order_id, status=None):
        """The order's tax documents, optionally only those in one status."""
        found = [d for d in self.s.get("taxes", "/api/tax-documents")[1]["documents"] if d["order_id"] == order_id]
        return [d for d in found if status is None or d["status"] == status]

    def subscriptions(self, email):
        return self.s.get("subscriptions", "/api/subscriptions?email=" + urllib.parse.quote(email))[1]["subscriptions"]

    def never(self, check, seconds=3.0):
        """Watches for `seconds` for something that must not happen. Returns what `check` found if it did, else None.

        Core delivers an event to an app within a fraction of a second, so a few seconds is long enough to see an
        email or a document that is going to appear, without depending on any other system to signal the moment."""
        deadline = time.time() + seconds
        while time.time() < deadline:
            found = check()
            if found:
                return found
            time.sleep(0.2)
        return None

    def renewals(self, email):
        """The customer's renewal orders. Every check that runs renewals renews everyone who is due, so there may be several."""
        return [o for o in self.orders_of(email) if {"key": "subscription_reason", "value": "renewal"} in o["metadata"]]

    def replay(self, bundle, **purchase):
        """Buys something the way one build of the mobile app does. Returns the screens the customer saw."""
        run = subprocess.run(["node", os.path.join(HERE, "replay.ts"), bundle, self.s.url("core", "/graphql/"), json.dumps(purchase)],
                             capture_output=True, text=True, timeout=120, env=dict(os.environ, NODE_NO_WARNINGS="1"))
        lines = [l for l in run.stdout.splitlines() if l.startswith("{")]
        return json.loads(lines[-1]) if lines else {"ok": False, "kind": "crash", "error": (run.stderr or run.stdout)[-400:]}

    def supported_mobile_builds(self):
        """{version: directory} for the builds customers still run. 1.0.0 is taken from the checks' own copy: it is
        on customers' phones as it was shipped, whatever the repository now holds."""
        mobile = os.path.join(ROOT, "services", "mobile", "releases")
        with open(os.path.join(mobile, "supported.json")) as f:
            supported = json.load(f)["supported"]
        self.assertIn("1.0.0", supported, "release 1.0.0 is on customers' phones and must stay supported")
        return {v: PRISTINE_MOBILE if v == "1.0.0" else os.path.join(mobile, v) for v in supported}

"""Core against stand-in apps: a tax app, a payment app and an app that listens to order events."""
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import telemetry  # noqa: E402
from server import Api  # noqa: E402
from store import Store  # noqa: E402

telemetry.log = lambda *a, **k: None   # keep test output readable

ADDRESS = {"firstName": "Pat", "lastName": "Lee", "streetAddress1": "1 Main St", "city": "San Francisco",
           "postalCode": "94105", "country": "US", "countryArea": "CA"}
TAX_QUERY = """subscription { event { ... on CalculateTaxes { taxBase { pricesEnteredWithTax currency
  shippingPrice { amount } address { postalCode } lines { quantity productSku totalPrice { amount } }
  sourceObject { __typename ... on Checkout { id } ... on Order { id } } } } } }"""
PAY_QUERY = """subscription { event { ... on TransactionInitializeSession { action { amount currency actionType } data
  merchantReference idempotencyKey transaction { id } sourceObject { __typename ... on Checkout { id } ... on Order { id number } } } } }"""
REFUND_QUERY = "subscription { event { ... on TransactionRefundRequested { action { amount currency } transaction { id pspReference } } } }"
ORDER_QUERY = """subscription { event { __typename ... on OrderCreated { order { id number userEmail total { gross { amount } } } }
  ... on OrderFullyPaid { order { number chargeStatus } } ... on OrderConfirmed { order { number status } } ... on OrderCancelled { order { number status } }
  ... on OrderFulfilled { order { number status } } ... on OrderRefunded { order { number totalRefunded { amount } } }
  ... on OrderFullyRefunded { order { number chargeStatus } } } }"""


class FakeApp:
    """An app on a local port: serves its manifest, takes its token, and answers webhooks with `answer(name, payload)`."""

    def __init__(self, identifier, permissions, webhooks, answer=lambda name, payload: {}):
        self.identifier, self.calls, self.token, self.answer, self.fail = identifier, [], None, answer, 0
        app = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def reply(self, status, body):
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self.reply(200, {"id": identifier, "name": identifier, "version": "1.0.0", "permissions": permissions,
                                 "tokenTargetUrl": app.url + "/register",
                                 "webhooks": [dict(w, targetUrl=app.url + "/webhooks/" + w["name"]) for w in webhooks]})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"null")
                if self.path == "/register":
                    app.token = body["auth_token"]
                    return self.reply(200, {})
                if app.fail:
                    app.fail -= 1
                    return self.reply(500, {})
                name = self.path.rsplit("/", 1)[-1]
                app.calls.append((self.headers.get("Saleor-Event"), body))
                self.reply(200, app.answer(name, body))

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:{}".format(self.server.server_address[1])
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def events(self, name):
        return [body for event, body in self.calls if event == name]


def taxes(name, payload):
    """8.75% on lines, nothing on shipping. Rates are percentages; amounts are decimals."""
    base = payload["taxBase"]
    return {"shipping_tax_rate": 0, "shipping_price_net_amount": base["shippingPrice"]["amount"],
            "shipping_price_gross_amount": base["shippingPrice"]["amount"],
            "lines": [{"tax_rate": 8.75, "total_net_amount": l["totalPrice"]["amount"],
                       "total_gross_amount": round(l["totalPrice"]["amount"] * 1.0875 + 1e-9, 2)} for l in base["lines"]]}


def payments(name, payload):
    if name == "refund":
        return {"pspReference": "re_1", "result": "REFUND_SUCCESS", "amount": payload["action"]["amount"]}
    declined = (payload.get("data") or {}).get("paymentMethod") == "pm_card_declined"
    return {"pspReference": "" if declined else "pi_1", "result": "CHARGE_FAILURE" if declined else "CHARGE_SUCCESS",
            "amount": payload["action"]["amount"], "message": "card_declined" if declined else ""}


class CoreTest(unittest.TestCase):
    def setUp(self):
        self.tax = FakeApp("seedco.taxes", ["HANDLE_TAXES"], [
            {"name": "taxes", "syncEvents": ["CHECKOUT_CALCULATE_TAXES", "ORDER_CALCULATE_TAXES"], "query": TAX_QUERY}], taxes)
        self.pay = FakeApp("seedco.payments", ["HANDLE_PAYMENTS"], [
            {"name": "initialize", "syncEvents": ["TRANSACTION_INITIALIZE_SESSION"], "query": PAY_QUERY},
            {"name": "refund", "syncEvents": ["TRANSACTION_REFUND_REQUESTED"], "query": REFUND_QUERY}], payments)
        self.listener = FakeApp("seedco.listener", ["MANAGE_ORDERS", "NOT_A_PERMISSION"], [
            {"name": "orders", "query": ORDER_QUERY, "asyncEvents": ["ORDER_CREATED", "ORDER_CONFIRMED", "ORDER_FULLY_PAID", "ORDER_CANCELLED",
                                                                     "ORDER_FULFILLED", "ORDER_REFUNDED", "ORDER_FULLY_REFUNDED"]},
            {"name": "broken", "query": "subscription { event { ... on OrderCreated { order { nope } } } }", "asyncEvents": ["ORDER_CREATED"]}])
        self.api = self.start(Store())

    def start(self, store):
        api = Api(store, "http://core.test/graphql/")
        for app in (self.tax, self.pay, self.listener):
            api.apps.install(app.url + "/manifest")
        return api

    def gql(self, query, token=None, **variables):
        result = self.api.run({"query": query, "variables": variables}, "Bearer " + token if token else None)
        self.assertNotIn("errors", result, result.get("errors"))
        return result["data"]

    def staff(self, email="admin@seedco.example", password="admin"):
        return self.gql('mutation($e: String!, $p: String!) { tokenCreate(email: $e, password: $p) { token errors { code } } }',
                        e=email, p=password)["tokenCreate"]["token"]

    def variants(self):
        data = self.gql("{ products(first: 3) { edges { node { name variants { id sku pricing { price { gross { amount } } } } } } } }")
        return {e["node"]["variants"][0]["sku"]: e["node"]["variants"][0]["id"] for e in data["products"]["edges"]}

    def checkout(self, method="pm_card_ok", pay=True):
        """A checkout for 2 small boxes and a tea, addressed, with shipping chosen, and paid unless told otherwise."""
        v = self.variants()
        created = self.gql("""mutation($lines: [CheckoutLineInput!]) { checkoutCreate(input: {email: "pat@example.com", lines: $lines}) {
            checkout { id totalPrice { gross { amount } } } errors { code } } }""",
                           lines=[{"variantId": v["BOX-S"], "quantity": 2}, {"variantId": v["ADD-TEA"], "quantity": 1}])["checkoutCreate"]
        cid = created["checkout"]["id"]
        self.assertEqual(created["checkout"]["totalPrice"]["gross"]["amount"], 56.23)   # no address yet: no tax
        ship = self.gql("""mutation($id: ID!, $a: AddressInput!) { checkoutShippingAddressUpdate(id: $id, shippingAddress: $a) {
            checkout { shippingMethods { id name price { amount } } } errors { code } } }""", id=cid, a=ADDRESS)
        method_id = ship["checkoutShippingAddressUpdate"]["checkout"]["shippingMethods"][0]["id"]
        self.gql("mutation($id: ID!, $m: ID) { checkoutDeliveryMethodUpdate(id: $id, deliveryMethodId: $m) { errors { code } } }",
                 id=cid, m=method_id)
        if pay:
            self.pay_for(cid, method)
        return cid

    def pay_for(self, source_id, method="pm_card_ok", key=None):
        return self.gql("""mutation($id: ID!, $data: JSON, $key: String) { transactionInitialize(id: $id, idempotencyKey: $key,
            paymentGateway: {id: "seedco.payments", data: $data}) { transaction { id chargedAmount { amount } }
            transactionEvent { type message amount { amount } } errors { code message } } }""",
                        id=source_id, data={"paymentMethod": method}, key=key)["transactionInitialize"]

    def complete(self, cid):
        return self.gql("""mutation($id: ID!) { checkoutComplete(id: $id) { order { id number status chargeStatus isPaid userEmail
            lines { productName quantity taxRate unitPrice { net { amount } gross { amount } } totalPrice { gross { amount } tax { amount } } }
            subtotal { net { amount } gross { amount } } shippingPrice { gross { amount } }
            total { gross { amount fractionalAmount } tax { amount } } transactions { id pspReference chargedAmount { amount } } }
            errors { code field } } }""", id=cid)["checkoutComplete"]

    def confirm(self, order_id, token=None):
        return self.gql("mutation($id: ID!) { orderConfirm(id: $id) { order { status } errors { code } } }",
                        token or self.staff(), id=order_id)["orderConfirm"]

    def test_a_shop_order_waits_for_staff_to_confirm_it(self):
        order = self.complete(self.checkout())["order"]
        line = self.gql("query($id: ID!) { order(id: $id) { lines { id } } }", id=order["id"])["order"]["lines"][0]["id"]
        fulfil = "mutation($o: ID!, $l: [OrderFulfillLineInput!]!) { orderFulfill(order: $o, input: {lines: $l}) { order { status } errors { code } } }"
        held = self.gql(fulfil, self.staff(), o=order["id"], l=[{"orderLineId": line, "quantity": 1}])["orderFulfill"]
        self.assertEqual(held["errors"], [{"code": "CANNOT_FULFILL"}])
        denied = self.api.run({"query": "mutation($id: ID!) { orderConfirm(id: $id) { errors { code } } }", "variables": {"id": order["id"]}})
        self.assertEqual(denied["errors"][0]["extensions"]["exception"]["code"], "PermissionDenied")
        self.assertEqual(self.confirm(order["id"]), {"order": {"status": "UNFULFILLED"}, "errors": []})
        self.assertEqual(self.confirm(order["id"])["errors"], [{"code": "INVALID"}])
        self.assertEqual(self.gql(fulfil, self.staff(), o=order["id"], l=[{"orderLineId": line, "quantity": 1}])["orderFulfill"]["errors"], [])
        self.deliver()
        self.assertEqual(self.listener.events("order_confirmed"), [{"__typename": "OrderConfirmed", "order": {"number": "1", "status": "UNFULFILLED"}}])

    def deliver(self):
        self.api.apps.deliver_pending()

    def test_the_catalogue_has_products_with_many_variants_categories_and_missing_skus(self):
        data = self.gql("""{ products(first: 100) { totalCount pageInfo { hasNextPage } edges { node { name slug
            category { name parent { name } } productType { name } variants { name sku pricing { price { gross { amount } } } } } } } }""")["products"]
        products = [e["node"] for e in data["edges"]]
        self.assertEqual((data["totalCount"], data["pageInfo"]["hasNextPage"], sum(len(p["variants"]) for p in products)), (29, False, 83))
        self.assertEqual([p["name"] for p in products[:3]], ["Small monthly box", "Large monthly box", "Tea add-on"])
        self.assertEqual(products[0]["variants"], [{"name": "", "sku": "BOX-S", "pricing": {"price": {"gross": {"amount": 24.99}}}}])
        filter_blend = next(p for p in products if p["name"] == "Filter blend")
        self.assertEqual((len(filter_blend["variants"]), filter_blend["category"]), (10, {"name": "Ground", "parent": {"name": "Coffee"}}))
        self.assertEqual(sum(1 for p in products for v in p["variants"] if v["sku"] is None), 2)
        self.assertEqual(max(v["pricing"]["price"]["gross"]["amount"] for p in products for v in p["variants"]), 2300.0)
        page = self.gql("{ products(first: 20) { pageInfo { hasNextPage endCursor } edges { node { name } } } }")["products"]
        self.assertEqual((len(page["edges"]), page["pageInfo"]["hasNextPage"]), (20, True))
        rest = self.gql("query($a: String) { products(first: 20, after: $a) { edges { node { name } } } }", a=page["pageInfo"]["endCursor"])
        self.assertEqual(len(rest["products"]["edges"]), 9)
        found = self.gql('{ products(filter: {search: "crème"}) { edges { node { name } } } }')["products"]["edges"]
        self.assertEqual([e["node"]["name"] for e in found], ["Earl Grey Crème", 'Rooibos "Crème Brûlée"'])

    def test_a_variant_without_a_sku_can_be_bought(self):
        nodes = self.gql("{ products(first: 100) { edges { node { name variants { id name sku } } } } }")["products"]["edges"]
        refill = next(v for e in nodes for v in e["node"]["variants"] if e["node"]["name"] == "Shortbread fingers" and v["sku"] is None)
        cid = self.gql("mutation($l: [CheckoutLineInput!]) { checkoutCreate(input: {email: \"pat@example.com\", lines: $l}) { checkout { id } } }",
                       l=[{"variantId": refill["id"], "quantity": 3}])["checkoutCreate"]["checkout"]["id"]
        self.gql("mutation($id: ID!, $a: AddressInput!) { checkoutShippingAddressUpdate(id: $id, shippingAddress: $a) { errors { code } } }", id=cid, a=ADDRESS)
        line = self.gql("query($id: ID!) { checkout(id: $id) { lines { variant { name sku product { name } } totalPrice { gross { amount } } } } }", id=cid)["checkout"]["lines"][0]
        self.assertEqual(line, {"variant": {"name": "Refill bag", "sku": None, "product": {"name": "Shortbread fingers"}}, "totalPrice": {"gross": {"amount": 16.31}}})
        self.assertEqual(self.tax.events("checkout_calculate_taxes")[-1]["taxBase"]["lines"][0]["productSku"], None)

    def test_a_checkout_is_taxed_paid_and_becomes_an_order(self):
        cid = self.checkout(pay=False)
        view = self.gql("""query($id: ID!) { checkout(id: $id) { chargeStatus subtotalPrice { net { amount } gross { amount } }
            totalPrice { gross { amount } } availablePaymentGateways { id } } }""", id=cid)["checkout"]
        self.assertEqual((view["subtotalPrice"]["net"]["amount"], view["subtotalPrice"]["gross"]["amount"]), (56.23, 61.15))
        self.assertEqual((view["totalPrice"]["gross"]["amount"], view["chargeStatus"]), (66.15, "NONE"))
        self.assertEqual(view["availablePaymentGateways"], [{"id": "seedco.payments"}])
        self.assertEqual(self.complete(cid)["errors"], [{"code": "CHECKOUT_NOT_FULLY_PAID", "field": None}])

        paid = self.pay_for(cid)
        self.assertEqual((paid["transactionEvent"]["type"], paid["transaction"]["chargedAmount"]["amount"]), ("CHARGE_SUCCESS", 66.15))
        order = self.complete(cid)["order"]
        self.assertEqual((order["number"], order["status"], order["chargeStatus"], order["isPaid"]), ("1", "UNCONFIRMED", "FULL", True))
        self.assertEqual(order["lines"][0]["taxRate"], 0.0875)          # the app said 8.75; the API says 0.0875
        self.assertEqual(order["lines"][0]["unitPrice"], {"net": {"amount": 24.99}, "gross": {"amount": 27.18}})
        self.assertEqual([l["totalPrice"]["gross"]["amount"] for l in order["lines"]], [54.35, 6.8])
        self.assertEqual(order["total"], {"gross": {"amount": 66.15, "fractionalAmount": 6615}, "tax": {"amount": 4.92}})
        self.assertEqual(order["transactions"][0]["pspReference"], "pi_1")
        self.assertIsNone(self.gql("query($id: ID!) { checkout(id: $id) { id } }", id=cid)["checkout"])

    def test_each_app_is_sent_exactly_what_its_query_asks_for(self):
        cid = self.checkout()
        tax_payload = self.tax.events("checkout_calculate_taxes")[-1]
        self.assertEqual(tax_payload["taxBase"]["lines"][0], {"quantity": 2, "productSku": "BOX-S", "totalPrice": {"amount": 49.98}})
        self.assertEqual(tax_payload["taxBase"]["pricesEnteredWithTax"], False)
        self.assertEqual(tax_payload["taxBase"]["sourceObject"], {"__typename": "Checkout", "id": cid})
        pay_payload = self.pay.events("transaction_initialize_session")[-1]
        self.assertEqual(pay_payload["action"], {"amount": 66.15, "currency": "USD", "actionType": "CHARGE"})
        self.assertEqual((pay_payload["data"], pay_payload["merchantReference"]), ({"paymentMethod": "pm_card_ok"}, cid))
        order = self.complete(cid)["order"]
        self.deliver()
        created = self.listener.events("order_created")
        self.assertEqual(created, [{"__typename": "OrderCreated", "order": {
            "id": order["id"], "number": "1", "userEmail": "pat@example.com", "total": {"gross": {"amount": 66.15}}}}])
        self.assertEqual(self.listener.events("order_fully_paid"), [{"__typename": "OrderFullyPaid", "order": {"number": "1", "chargeStatus": "FULL"}}])

    def test_a_webhook_with_a_query_the_schema_does_not_allow_is_refused(self):
        apps = self.gql("{ apps { identifier permissions { code } webhooks { name syncEvents { eventType } } } }", self.staff())["apps"]
        listener = next(a for a in apps if a["identifier"] == "seedco.listener")
        self.assertEqual([w["name"] for w in listener["webhooks"]], ["orders"])
        self.assertEqual(listener["permissions"], [{"code": "MANAGE_ORDERS"}])
        self.assertIsNotNone(self.listener.token)

    def test_a_declined_payment_leaves_the_checkout_unpaid(self):
        cid = self.checkout(method="pm_card_declined")
        event = self.gql("query($id: ID!) { checkout(id: $id) { chargeStatus transactions { events { type message } } } }", id=cid)["checkout"]
        self.assertEqual(event["chargeStatus"], "NONE")
        self.assertEqual(event["transactions"][0]["events"][-1], {"type": "CHARGE_FAILURE", "message": "card_declined"})
        self.assertEqual(self.complete(cid)["errors"][0]["code"], "CHECKOUT_NOT_FULLY_PAID")
        self.pay_for(cid)
        self.assertEqual(self.complete(cid)["order"]["chargeStatus"], "FULL")

    def test_a_repeated_idempotency_key_charges_once(self):
        cid = self.checkout(pay=False)
        first = self.pay_for(cid, key="k1")
        self.assertEqual(self.pay_for(cid, key="k1")["transaction"]["id"], first["transaction"]["id"])
        self.assertEqual(len(self.pay.events("transaction_initialize_session")), 1)
        self.assertEqual(self.pay_for(cid)["errors"][0]["code"], "INVALID")       # nothing left to pay

    def test_a_bad_answer_from_an_app_is_an_error_not_a_price(self):
        self.tax.answer = lambda name, payload: dict(taxes(name, payload), lines=[])
        cid = self.checkout(pay=False)
        self.assertEqual(self.complete(cid)["errors"][0]["code"], "TAX_ERROR")
        self.tax.answer = taxes
        self.pay.answer = lambda name, payload: {"result": "PAID", "pspReference": "x"}
        failed = self.pay_for(cid)
        self.assertEqual(failed["transactionEvent"]["type"], "CHARGE_FAILURE")
        self.assertIn("unknown result 'PAID'", failed["transactionEvent"]["message"])

    def test_staff_permissions_guard_orders_and_refunds(self):
        order = self.complete(self.checkout())["order"]
        denied = self.api.run({"query": "{ orders(first: 5) { totalCount } }"})
        self.assertEqual(denied["errors"][0]["extensions"]["exception"]["code"], "PermissionDenied")
        self.assertIsNone(self.staff(password="wrong"))
        support = self.staff("support@seedco.example", "support")
        found = self.gql('{ orders(first: 5, filter: {customer: "PAT@"}) { totalCount edges { node { number } } } }', support)["orders"]
        self.assertEqual((found["totalCount"], found["edges"][0]["node"]["number"]), (1, "1"))
        refund = {"query": "mutation($id: ID!) { transactionRequestAction(id: $id, actionType: REFUND) { errors { code } } }",
                  "variables": {"id": order["transactions"][0]["id"]}}
        self.assertEqual(self.api.run(refund, "Bearer " + support)["errors"][0]["extensions"]["exception"]["code"], "PermissionDenied")
        self.assertEqual(self.api.run(refund, "Bearer " + self.staff())["data"]["transactionRequestAction"]["errors"], [])
        self.assertEqual(self.api.run(refund, "Bearer " + self.pay.token)["data"]["transactionRequestAction"]["errors"][0]["code"], "INVALID")

    def test_fulfil_refund_and_cancel_tell_the_apps(self):
        admin = self.staff()
        first = self.complete(self.checkout())["order"]
        self.assertEqual(self.confirm(first["id"])["order"]["status"], "UNFULFILLED")
        line = self.gql("query($id: ID!) { order(id: $id) { lines { id quantity } } }", id=first["id"])["order"]["lines"]
        fulfil = "mutation($o: ID!, $l: [OrderFulfillLineInput!]!) { orderFulfill(order: $o, input: {lines: $l}) { order { status } errors { code } } }"
        part = self.gql(fulfil, admin, o=first["id"], l=[{"orderLineId": line[0]["id"], "quantity": 1}])["orderFulfill"]
        self.assertEqual(part["order"]["status"], "PARTIALLY_FULFILLED")
        over = self.gql(fulfil, admin, o=first["id"], l=[{"orderLineId": line[0]["id"], "quantity": 5}])["orderFulfill"]
        self.assertEqual(over["errors"][0]["code"], "FULFILL_ORDER_LINE")
        self.gql(fulfil, admin, o=first["id"], l=[{"orderLineId": line[0]["id"], "quantity": 1}, {"orderLineId": line[1]["id"], "quantity": 1}])
        cancel = "mutation($id: ID!) { orderCancel(id: $id) { order { status } errors { code } } }"
        self.assertEqual(self.gql(cancel, admin, id=first["id"])["orderCancel"]["errors"][0]["code"], "CANNOT_CANCEL_ORDER")

        second = self.complete(self.checkout())["order"]
        self.assertEqual(self.gql(cancel, admin, id=second["id"])["orderCancel"]["order"]["status"], "CANCELED")
        self.gql("mutation($id: ID!) { transactionRequestAction(id: $id, actionType: REFUND, amount: 16.15) { errors { code } } }",
                 admin, id=second["transactions"][0]["id"])
        self.gql("mutation($id: ID!) { transactionRequestAction(id: $id, actionType: REFUND) { errors { code } } }",
                 admin, id=second["transactions"][0]["id"])
        self.deliver()
        self.assertEqual(self.listener.events("order_fulfilled"), [{"__typename": "OrderFulfilled", "order": {"number": "1", "status": "FULFILLED"}}])
        self.assertEqual(self.listener.events("order_cancelled")[0]["order"], {"number": "2", "status": "CANCELED"})
        self.assertEqual([e["order"]["totalRefunded"]["amount"] for e in self.listener.events("order_refunded")], [16.15, 66.15])
        self.assertEqual(self.listener.events("order_fully_refunded")[0]["order"], {"number": "2", "chargeStatus": "NONE"})

    def test_an_app_can_create_an_order_and_charge_it(self):
        v = self.variants()
        token = self.listener.token
        draft = self.gql("""mutation($lines: [OrderLineCreateInput!], $a: AddressInput) { draftOrderCreate(input: {
            userEmail: "pat@example.com", lines: $lines, shippingAddress: $a}) { order { id status total { gross { amount } } } errors { code } } }""",
                         token, lines=[{"variantId": v["BOX-L"], "quantity": 1, "price": 10}], a=ADDRESS)["draftOrderCreate"]["order"]
        self.assertEqual((draft["status"], draft["total"]["gross"]["amount"]), ("DRAFT", 10.88))      # 10.00 + 8.75%
        self.gql('mutation($id: ID!) { updateMetadata(id: $id, input: [{key: "subscription_id", value: "sub_1"}]) { errors { code } } }', token, id=draft["id"])
        done = self.gql("mutation($id: ID!) { draftOrderComplete(id: $id) { order { status chargeStatus origin metadata { key value } } errors { code } } }",
                        token, id=draft["id"])["draftOrderComplete"]["order"]
        self.assertEqual((done["status"], done["chargeStatus"], done["origin"]), ("UNFULFILLED", "NONE", "DRAFT"))
        self.assertEqual(done["metadata"], [{"key": "subscription_id", "value": "sub_1"}])
        self.assertEqual(self.pay_for(draft["id"])["transaction"]["chargedAmount"]["amount"], 10.88)
        self.assertEqual(self.pay.events("transaction_initialize_session")[-1]["sourceObject"], {"__typename": "Order", "id": draft["id"], "number": "1"})
        self.deliver()
        self.assertEqual([e["__typename"] for _, e in self.listener.calls], ["OrderCreated", "OrderConfirmed", "OrderFullyPaid"])
        found = self.gql('{ orders(filter: {metadata: [{key: "subscription_id", value: "sub_1"}]}) { totalCount } }', self.staff())
        self.assertEqual(found["orders"]["totalCount"], 1)

    def test_a_delivery_that_fails_is_sent_again(self):
        self.complete(self.checkout())
        self.listener.fail = 1
        self.assertEqual(self.api.apps.deliver_pending(), 1)      # the first failed and waits; the second went through
        self.assertEqual(len(self.listener.calls), 1)
        for d in self.api.core.store.all("delivery", "pending"):
            self.api.core.store.put("delivery", dict(d, next_attempt=0), "pending")
        self.assertEqual(self.api.apps.deliver_pending(), 0)
        self.assertEqual(sorted(e for e, _ in self.listener.calls), ["order_created", "order_fully_paid"])

    def test_orders_and_apps_survive_a_restart(self):
        path = os.path.join(tempfile.mkdtemp(prefix="seedco-core-"), "core.db")
        self.api = self.start(Store(path))
        order = self.complete(self.checkout())["order"]
        token = self.pay.token
        self.api = self.start(Store(path))
        again = self.gql("query($id: ID!) { order(id: $id) { number total { gross { amount } } } }", id=order["id"])["order"]
        self.assertEqual(again, {"number": "1", "total": {"gross": {"amount": 66.15}}})
        self.assertEqual(self.pay.token, token)                   # a reinstalled app keeps its token
        self.assertEqual(self.complete(self.checkout())["order"]["number"], "2")


if __name__ == "__main__":
    unittest.main()

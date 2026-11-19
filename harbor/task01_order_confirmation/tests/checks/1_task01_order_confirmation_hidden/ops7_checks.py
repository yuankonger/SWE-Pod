"""OPS-7: staff confirm orders before they are fulfilled. One check per method, named test_<boundary>__<what>.

These are the checks of what the change adds: each fails on the company as it was. What must keep working is
checked by the regression suite (../regression), which agents can see; these they cannot. `rubric.toml` lists
every check of both kinds with a note on what it is for.

Each check asks for what the decision record states and no more. Where the record leaves the form open (how a
page is written, whether a system keeps a note of an order it has not acted on yet), the check does not decide it.
"""
import urllib.parse

from common import FULFIL
from shop import Browser, submit_labelled, text_of

CONFIRM = "mutation($id: ID!) { orderConfirm(id: $id) { order { status } errors { code } } }"


class Ops7Checks:
    def confirm(self, order_id):
        """Confirms as staff. Fails the check if Core has no such mutation."""
        status, body = self.s.request("core", "POST", "/graphql/", {"query": CONFIRM, "variables": {"id": order_id}},
                                      {"Authorization": "Bearer " + self.admin})
        self.assertFalse(body.get("errors"), "Core refused orderConfirm: {}".format(body.get("errors")))
        return body["data"]["orderConfirm"]

    def held(self, order=None):
        """What most checks here start from: an order placed in the shop waits for staff."""
        order = order or self.first
        self.assertEqual(order["status"], "UNCONFIRMED", "an order placed in the shop is not held for confirmation")

    def test_core_api__a_shop_order_starts_unconfirmed_and_paid(self):
        self.assertEqual((self.first["status"], self.first["chargeStatus"], self.first["origin"]), ("UNCONFIRMED", "FULL", "CHECKOUT"))

    def test_core_api__staff_confirm_an_order_once(self):
        order = self.buy("confirm@example.com")
        status, anonymous = self.s.request("core", "POST", "/graphql/", {"query": CONFIRM, "variables": {"id": order["id"]}})
        codes = [e.get("extensions", {}).get("exception", {}).get("code") for e in anonymous.get("errors") or []]
        self.assertEqual(codes, ["PermissionDenied"], anonymous)
        self.assertEqual(self.order(order["id"])["status"], "UNCONFIRMED")
        self.assertEqual(self.confirm(order["id"]), {"order": {"status": "UNFULFILLED"}, "errors": []})
        self.assertEqual([e["code"] for e in self.confirm(order["id"])["errors"]], ["INVALID"])
        self.assertEqual(self.order(order["id"])["status"], "UNFULFILLED")

    def test_core_api__an_unconfirmed_order_cannot_be_fulfilled_but_can_be_cancelled(self):
        order = self.buy("hold@example.com")
        self.held(order)
        lines = [{"orderLineId": l["id"], "quantity": l["quantity"]} for l in order["lines"]]
        refused = self.s.gql(FULFIL, self.admin, o=order["id"], l=lines)["orderFulfill"]
        self.assertEqual([e["code"] for e in refused["errors"]], ["CANNOT_FULFILL"])
        self.assertEqual(self.order(order["id"])["status"], "UNCONFIRMED")
        self.confirm(order["id"])
        self.assertEqual(self.s.gql(FULFIL, self.admin, o=order["id"], l=lines)["orderFulfill"], {"order": {"status": "FULFILLED"}, "errors": []})
        other = self.buy("hold2@example.com")
        cancelled = self.s.gql("mutation($id: ID!) { orderCancel(id: $id) { order { status } errors { code } } }", self.admin, id=other["id"])
        self.assertEqual(cancelled["orderCancel"], {"order": {"status": "CANCELED"}, "errors": []})

    def test_core_notifications__the_confirmation_email_waits_for_confirmation(self):
        order = self.buy("mail@example.com")
        self.held(order)
        subject = "Order #{} confirmed".format(order["number"])

        def confirmations():
            return [e for e in self.emails("mail@example.com") if e["subject"] == subject]

        self.assertIsNone(self.never(confirmations), "the confirmation email went out before the order was confirmed")
        self.confirm(order["id"])
        sent = self.s.wait_for(confirmations)
        self.assertTrue(sent, "no confirmation email after the order was confirmed")
        self.assertIn("Total: $66.15", sent[0]["body"])
        self.confirm(order["id"])                    # refused, and must not send a second email
        self.assertIsNone(self.never(lambda: len(confirmations()) > 1, 1.5), "confirming twice sent the email twice")

    def test_core_taxes__the_tax_document_is_committed_at_confirmation(self):
        order = self.buy("tax@example.com")
        self.held(order)
        # Whether the tax app keeps anything about an order it has not reported yet is its own business:
        # what must not exist before confirmation is a committed document.
        self.assertIsNone(self.never(lambda: self.documents(order["id"], "committed")), "a tax document was committed before the order was confirmed")
        self.confirm(order["id"])
        documents = self.s.wait_for(lambda: self.documents(order["id"], "committed"))
        self.assertTrue(documents, "no committed tax document after the order was confirmed")
        self.assertEqual([(float(d["tax"]), float(d["gross"])) for d in documents], [(4.92, 66.15)])

    def test_core_taxes__an_order_cancelled_before_confirmation_is_never_reported(self):
        order = self.buy("never@example.com")
        self.held(order)
        self.s.gql("mutation($id: ID!) { orderCancel(id: $id) { errors { code } } }", self.admin, id=order["id"])
        self.assertIsNone(self.never(lambda: self.documents(order["id"], "committed")), "a cancelled, never-confirmed order was reported for tax")

    def test_dashboard_core__staff_confirm_from_the_order_page(self):
        order = self.buy("desk@example.com")
        self.held(order)
        staff = Browser(self.s.url("dashboard"))
        staff.open("/login", {"email": "admin@seedco.example", "password": "admin"})
        path = "/orders/" + urllib.parse.quote(order["id"], safe="")
        status, _, page = staff.open(path)
        self.assertEqual(status, 200)
        self.assertEqual(submit_labelled(page, "Fulfill remaining items"), (None, None), "fulfilment is offered before the order is confirmed")
        form, button = submit_labelled(page, "Confirm order")
        self.assertIsNotNone(form, 'the order page has no "Confirm order" button')
        status, _, _ = staff.follow(staff.submit(form, button))        # with whatever fields the form carries
        self.assertLess(status, 400, "pressing Confirm order failed")
        self.assertEqual(self.order(order["id"])["status"], "UNFULFILLED")
        page = staff.open(path)[2]
        self.assertIsNotNone(submit_labelled(page, "Fulfill remaining items")[0], "fulfilment is not offered after the order is confirmed")
        self.assertEqual(submit_labelled(page, "Confirm order"), (None, None), "a confirmed order still offers Confirm order")

    def test_core_storefront__a_held_order_shows_as_received_in_the_web_shop(self):
        self.held()
        shop = Browser(self.s.url("storefront"))
        placed = shop.buy({self.variants[sku]: qty for sku, qty in {"BOX-S": 2, "ADD-TEA": 1}.items()}, email="shop-held@example.com")
        status, _, page = shop.follow(placed)
        self.assertEqual(status, 200)
        self.assertEqual([o["status"] for o in self.orders_of("shop-held@example.com")], ["UNCONFIRMED"])
        self.assertIn("Order received", text_of(page))

    def test_core_mobile__a_held_order_shows_as_received_in_every_supported_build(self):
        self.held()
        for version, bundle in self.supported_mobile_builds().items():
            email = "mobile-held-{}@example.com".format(version.replace(".", "-"))
            screens = self.replay(bundle, email=email)
            self.assertTrue(screens.get("ok"), "release {} cannot buy: {}".format(version, screens))
            self.assertEqual((screens["order"]["status"], screens["order"]["paid"]), ("Order received", True))
            self.assertEqual([o["status"] for o in self.orders_of(email)], ["UNCONFIRMED"])

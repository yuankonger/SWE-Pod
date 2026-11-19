"""What the company does today and must still do after any change. One check per method, named test_<boundary>__<what>.

These checks pass on the company as it is. They say nothing about what a change is meant to add: they are the
things a change must not break. They run against the company's history (45 orders, 10 subscriptions, and what
was sent for them), so "still works" includes "still works for the customers we already have".
"""
import os

from common import FULFIL, PRISTINE_MOBILE, ROOT
from shop import Browser, text_of


class RegressionChecks:
    def test_core_notifications__a_paid_order_gets_its_receipt(self):
        receipt = self.s.wait_for(lambda: self.emails("pat@example.com", "receipt"))
        self.assertTrue(receipt, "no receipt for a paid order")
        for text in ("2 x Small monthly box  $49.98", "Tax: $4.92", "Total: $66.15"):
            self.assertIn(text, receipt[0]["body"])
        dropped = [d for d in self.s.get("notifications", "/dropped")[1]["dropped"] if d["event_type"] in ("OrderFullyPaid", "OrderConfirmed", "OrderCreated")]
        self.assertEqual(dropped, [], "the email app could not read some order events")

    def test_core_storefront__a_customer_buys_in_the_web_shop(self):
        shop = Browser(self.s.url("storefront"))
        placed = shop.buy({self.variants[sku]: qty for sku, qty in {"BOX-S": 2, "ADD-TEA": 1}.items()}, email="web@example.com")
        self.assertIn(placed[0], (200, 301, 302, 303, 307, 308), "the shop did not place the order: {}".format(text_of(placed[2])[-300:]))
        status, _, page = shop.follow(placed)
        self.assertEqual(status, 200)
        mine = self.orders_of("web@example.com")
        self.assertEqual([(o["chargeStatus"], o["total"]["gross"]["amount"]) for o in mine], [("FULL", 66.15)])
        shown = text_of(page)
        for text in ("Order #" + mine[0]["number"], "Paid", "$66.15"):
            self.assertIn(text, shown)

    def test_core_mobile__every_supported_release_buys(self):
        for version, bundle in self.supported_mobile_builds().items():
            email = "phone-{}@example.com".format(version.replace(".", "-"))
            screens = self.replay(bundle, email=email)
            self.assertTrue(screens.get("ok"), "release {} cannot buy: {}".format(version, screens))
            self.assertEqual((screens["order"]["paid"], screens["order"]["total"]), (True, "$66.15"))
            self.assertTrue(screens["order"]["status"], "release {} shows no status for the order".format(version))
            placed = self.orders_of(email)                 # what Core holds, whatever the app showed
            self.assertEqual([(o["chargeStatus"], o["total"]["gross"]["amount"]) for o in placed], [("FULL", 66.15)])

    def test_mobile_data__release_1_0_0_is_as_it_shipped(self):
        """A released build is on customers' phones. It is never edited, and it stays supported."""
        self.supported_mobile_builds()
        shipped = os.path.join(ROOT, "services", "mobile", "releases", "1.0.0")
        for name in sorted(os.listdir(PRISTINE_MOBILE)):
            with open(os.path.join(PRISTINE_MOBILE, name)) as was, open(os.path.join(shipped, name)) as now:
                self.assertEqual(now.read(), was.read(), "release 1.0.0 was edited after it shipped ({})".format(name))

    def test_core_subscriptions__a_subscription_renews_with_an_order_ready_to_ship(self):
        subs = self.s.wait_for(lambda: self.subscriptions("pat@example.com"))
        self.assertTrue(subs, "no subscription was started for the paid order")
        status, run = self.s.post("subscriptions", "/api/renewals/run", {"as_of": subs[0]["current_period_end"]})
        self.assertEqual(status, 200, run)
        renewals = self.renewals("pat@example.com")
        self.assertTrue(renewals, "the subscription did not renew")
        self.assertEqual({(o["status"], o["chargeStatus"], o["origin"]) for o in renewals}, {("UNFULFILLED", "FULL", "DRAFT")})

    def test_payments_subscriptions__a_new_subscription_records_its_card(self):
        # bought through Core, so that what card a shop's form offers does not come into it
        self.buy("card@example.com", {"BOX-L": 1}, payment_method="pm_card_visa_debit")
        subs = self.s.wait_for(lambda: self.subscriptions("card@example.com"), timeout=20)
        self.assertTrue(subs, "no subscription was started for the paid order")
        self.assertEqual(subs[0]["payment_method"], "pm_card_visa_debit", "the subscription does not hold the card the order was paid with")

    def test_core_data__an_order_from_the_history_can_still_be_shipped(self):
        old = [o for o in self.orders_of("legacy.unfulfilled@example.com") if o["origin"] == "CHECKOUT"]     # not its renewals
        self.assertEqual([(o["status"], o["chargeStatus"]) for o in old], [("UNFULFILLED", "FULL")],
                         "the order that was waiting to be shipped is not as it was")
        order = old[0]
        lines = [{"orderLineId": l["id"], "quantity": l["quantity"]} for l in order["lines"]]
        self.assertEqual(self.s.gql(FULFIL, self.admin, o=order["id"], l=lines)["orderFulfill"], {"order": {"status": "FULFILLED"}, "errors": []})
        again = [e for e in self.emails("legacy.unfulfilled@example.com") if e["subject"] == "Order #{} confirmed".format(order["number"])]
        self.assertEqual(len(again), 1, "the old order's confirmation email was sent again, or is gone")
        self.assertEqual(len(self.documents(order["id"], "committed")), 1, "the old order's tax document is gone or was committed again")

    def test_core_data__a_subscription_from_the_history_renews(self):
        subs = self.subscriptions("legacy.sub@example.com")
        self.assertEqual([(x["sku"], x["status"]) for x in subs], [("BOX-L", "active")], "the subscriber from the history is missing")
        status, run = self.s.post("subscriptions", "/api/renewals/run", {"as_of": subs[0]["current_period_end"]})
        self.assertEqual(status, 200, run)
        renewals = self.renewals("legacy.sub@example.com")
        self.assertTrue(renewals, "the subscription did not renew")
        self.assertEqual({(o["status"], o["chargeStatus"], o["total"]["gross"]["amount"]) for o in renewals}, {("UNFULFILLED", "FULL", 41.87)})   # 39.50 + 6%
        # the customer and the tax records hear about a renewal order at once
        subject = "Order #{} confirmed".format(renewals[0]["number"])
        self.assertTrue(self.s.wait_for(lambda: [e for e in self.emails("legacy.sub@example.com") if e["subject"] == subject]),
                        "no confirmation email for the renewal order")
        self.assertTrue(self.s.wait_for(lambda: self.documents(renewals[0]["id"], "committed")), "no tax document for the renewal order")

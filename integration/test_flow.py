"""End-to-end checks on the base company: checkouts followed through all four services."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "platform"))

from stack import Stack  # noqa: E402

BASE_PORT = int(os.environ.get("SEEDCO_BASE_PORT", "7000"))
CHECKOUT = {"customer_id": "cust_42", "email": "pat@example.com", "postal_code": 94105,
            "items": [{"sku": "BOX-S", "qty": 2}, {"sku": "ADD-TEA", "qty": 1}]}
# 2 x 24.99 + 6.25 = 56.23; tax at 8.75% = 4.920125 -> 4.92; total 61.15


class FlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = Stack(base_port=BASE_PORT).start()

    @classmethod
    def tearDownClass(cls):
        cls.stack.stop()

    def emails(self, customer, kind=None):
        emails = self.stack.get("notifications", "/outbox?customer_id=" + customer)[1]["emails"]
        return [e for e in emails if kind is None or e["kind"] == kind]

    def checkout(self, customer, **changes):
        status, page = self.stack.post("storefront", "/checkout", dict(CHECKOUT, customer_id=customer, **changes))
        self.assertEqual(status, 201, page)
        return page

    def subscription(self, customer):
        s = self.stack
        subs = s.wait_for(lambda: s.get("billing", "/subscriptions?customer_id=" + customer)[1]["subscriptions"])
        self.assertTrue(subs, "billing started no subscription\n" + s.log("billing")[-1500:])
        return subs[0]

    def test_checkout_reaches_every_service(self):
        s = self.stack
        page = self.checkout("cust_42")
        self.assertEqual(page["status_label"], "Paid")
        self.assertEqual(page["subtotal_display"], "$56.23")
        self.assertEqual(page["tax_display"], "$4.92")
        self.assertEqual(page["total_display"], "$61.15")
        self.assertEqual([l["line_total_display"] for l in page["lines"]], ["$49.98", "$6.25"])

        invoices = s.wait_for(lambda: s.get("billing", "/invoices?order_id=" + page["order_id"])[1]["invoices"])
        self.assertTrue(invoices, "billing issued no invoice\n" + s.log("billing")[-1500:])
        self.assertEqual(float(invoices[0]["total"]), 61.15)
        self.assertEqual([l["type"] for l in invoices[0]["lines"]], ["RECURRING", "FIXED"])

        emails = s.wait_for(lambda: len(self.emails("cust_42")) >= 2 and self.emails("cust_42"))
        self.assertTrue(emails, "notifications sent fewer than two emails\n" + s.log("notifications")[-1500:])
        kinds = {e["kind"]: e for e in emails}
        self.assertIn("Total: $61.15", kinds["order_confirmation"]["body"])
        self.assertIn("Total: $61.15", kinds["receipt"]["body"])
        self.assertIn("Tax: $4.92", kinds["receipt"]["body"])

        status, account = s.get("storefront", "/account/cust_42/orders")
        self.assertEqual(status, 200)
        self.assertEqual(account["orders"][0]["invoice"]["total_display"], "$61.15")
        self.assertEqual(s.get("notifications", "/dropped")[1]["dropped"], [])

    def test_cancel_sends_one_cancellation_and_refunds(self):
        s = self.stack
        page = self.checkout("cust_77", postal_code=10001)
        self.assertEqual(page["tax_display"], "$3.37")  # 56.23 * 0.06 = 3.3738
        self.subscription("cust_77")
        status, cancelled = s.post("storefront", "/orders/{}/cancel".format(page["order_id"]))
        self.assertEqual(status, 200)
        self.assertEqual(cancelled["status_label"], "Cancelled")
        s.post("storefront", "/orders/{}/cancel".format(page["order_id"]))
        emails = s.wait_for(lambda: self.emails("cust_77", "cancellation"))
        self.assertEqual(len(emails), 1)
        refunds = s.wait_for(lambda: s.get("billing", "/refunds?order_id=" + page["order_id"])[1]["refunds"])
        self.assertEqual([float(r["amount"]) for r in refunds], [59.6])
        self.assertEqual(self.subscription("cust_77")["status"], "canceled")
        self.assertEqual(s.get("storefront", "/account/cust_77/orders")[1]["orders"][0]["invoice"]["status"], "refunded")

    def test_bad_requests_are_rejected_at_the_edge(self):
        s = self.stack
        self.assertEqual(s.post("storefront", "/checkout", dict(CHECKOUT, items=[]))[0], 400)
        self.assertEqual(s.post("storefront", "/checkout", dict(CHECKOUT, items=[{"sku": "NOPE", "qty": 1}]))[0], 400)

    def test_a_declined_card_fails_the_order_and_tells_the_customer(self):
        s = self.stack
        page = self.checkout("cust_decl", payment_method="pm_card_declined")
        self.assertEqual(page["status_label"], "Payment failed")
        failed = s.wait_for(lambda: self.emails("cust_decl", "payment_failed"))
        self.assertTrue(failed, s.log("notifications")[-1500:])
        self.assertIn("$61.15 did not go through (card_declined)", failed[0]["body"])
        self.assertEqual(s.get("billing", "/invoices?order_id=" + page["order_id"])[1]["invoices"], [])
        self.assertEqual(self.emails("cust_decl", "order_confirmation"), [])

    def test_a_subscription_is_upgraded_downgraded_and_renewed(self):
        s = self.stack
        self.checkout("cust_sub")
        sub = self.subscription("cust_sub")
        self.assertEqual((sub["sku"], sub["qty"], sub["status"]), ("BOX-S", 2, "active"))
        start, end = sub["current_period_start"], sub["current_period_end"]

        # an upgrade starts at once; on the first day of the period the whole month is credited and recharged
        status, page = s.post("storefront", "/subscriptions/{}/plan".format(sub["subscription_id"]), {"sku": "BOX-L"})
        self.assertEqual(status, 200, page)
        self.assertEqual((page["plan"], page["price_display"]), ("Large monthly box", "$79.00 a month"))
        receipt = s.wait_for(lambda: [e for e in self.emails("cust_sub", "receipt") if "plan change" in e["subject"]])
        self.assertTrue(receipt, s.log("notifications")[-1500:])
        self.assertIn("2 x Unused time on Small monthly box  -$49.98", receipt[0]["body"])
        self.assertIn("Subtotal: $29.02", receipt[0]["body"])        # 79.00 - 49.98
        self.assertTrue(s.wait_for(lambda: [e for e in self.emails("cust_sub", "subscription_update")
                                           if e["body"] == "Your plan is now Large monthly box."]))

        # a downgrade waits for the period to end
        status, page = s.post("storefront", "/subscriptions/{}/plan".format(sub["subscription_id"]), {"sku": "BOX-S"})
        self.assertEqual(page["note"], "Changes to Small monthly box on " + end)
        self.assertEqual(page["plan"], "Large monthly box")

        status, run = s.post("billing", "/renewals/run", {"as_of": end})
        self.assertEqual((status, run["renewed"]), (200, 1), run)
        renewed = self.subscription("cust_sub")
        self.assertEqual((renewed["sku"], renewed["current_period_start"]), ("BOX-S", end))
        renewal = s.wait_for(lambda: [e for e in self.emails("cust_sub", "receipt") if e["subject"].startswith("Renewal")])
        self.assertTrue(renewal, s.log("notifications")[-1500:])
        self.assertIn("Total: $54.35", renewal[0]["body"])           # 2 x 24.99 = 49.98, tax 4.37
        self.assertNotEqual(start, end)

    def test_the_shop_serves_pages_and_a_cart_becomes_an_order(self):
        s = self.stack
        status, shop = s.get("storefront", "/")
        self.assertEqual(status, 200)
        self.assertIn("Small monthly box", shop)
        self.assertIn("Renews monthly at $24.99", shop)
        s.request("storefront", "PUT", "/api/cart/cust_cart/items/BOX-L", {"qty": 1})
        status, cart = s.request("storefront", "PUT", "/api/cart/cust_cart/items/ADD-TEA", {"qty": 2})
        self.assertEqual((status, cart["subtotal_display"]), (200, "$52.00"))
        status, order = s.post("orders", "/carts/cust_cart/checkout", {"email": "kim@example.com", "postal_code": 10001})
        self.assertEqual((status, order["status"]), (201, "paid"), order)
        self.assertEqual(s.get("storefront", "/api/cart/cust_cart")[1]["empty"], True)
        status, shipped = s.post("orders", "/orders/{}/ship".format(order["order_id"]))
        self.assertEqual((status, shipped["status"]), (200, "shipped"))
        self.assertEqual(s.post("orders", "/orders/{}/cancel".format(order["order_id"]))[0], 409)
        self.assertTrue(s.wait_for(lambda: self.emails("cust_cart", "shipping")))


class RestartTest(unittest.TestCase):
    def test_orders_invoices_and_emails_survive_a_restart(self):
        data = tempfile.mkdtemp(prefix="seedco-restart-")
        with Stack(base_port=BASE_PORT + 20, data_dir=data) as s:
            status, page = s.post("storefront", "/checkout", CHECKOUT)
            self.assertEqual(status, 201, page)
            self.assertTrue(s.wait_for(lambda: len(s.get("notifications", "/outbox?customer_id=cust_42")[1]["emails"]) >= 2))
        with Stack(base_port=BASE_PORT + 20, data_dir=data) as s:
            account = s.get("storefront", "/account/cust_42/orders")[1]["orders"]
            self.assertEqual([o["order_id"] for o in account], [page["order_id"]])
            self.assertEqual(account[0]["invoice"]["total_display"], "$61.15")
            self.assertEqual(len(s.get("notifications", "/outbox?customer_id=cust_42")[1]["emails"]), 2)
            self.assertEqual(len(s.get("billing", "/subscriptions?customer_id=cust_42")[1]["subscriptions"]), 1)


if __name__ == "__main__":
    unittest.main()

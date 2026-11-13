"""End-to-end checks on the base company: one checkout, followed through all four services."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "platform"))

from stack import Stack  # noqa: E402

CHECKOUT = {"customer_id": "cust_42", "email": "pat@example.com", "postal_code": 94105,
            "items": [{"sku": "BOX-S", "qty": 2}, {"sku": "ADD-TEA", "qty": 1}]}
# 2 x 24.99 + 6.25 = 56.23; tax at 8.75% = 4.920125 -> 4.92; total 61.15


class FlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = Stack(base_port=int(os.environ.get("SEEDCO_BASE_PORT", "7000"))).start()

    @classmethod
    def tearDownClass(cls):
        cls.stack.stop()

    def emails(self, customer):
        return self.stack.get("notifications", "/outbox?customer_id=" + customer)[1]["emails"]

    def test_checkout_reaches_every_service(self):
        s = self.stack
        status, page = s.post("storefront", "/checkout", CHECKOUT)
        self.assertEqual(status, 201, page)
        self.assertEqual(page["status_label"], "Paid")
        self.assertEqual(page["subtotal_display"], "$56.23")
        self.assertEqual(page["tax_display"], "$4.92")
        self.assertEqual(page["total_display"], "$61.15")
        self.assertEqual([l["line_total_display"] for l in page["lines"]], ["$49.98", "$6.25"])

        invoices = s.wait_for(lambda: s.get("billing", "/invoices?order_id=" + page["order_id"])[1]["invoices"])
        self.assertTrue(invoices, "billing issued no invoice\n" + s.log("billing")[-1500:])
        self.assertEqual(float(invoices[0]["total"]), 61.15)

        emails = s.wait_for(lambda: len(self.emails("cust_42")) >= 2 and self.emails("cust_42"))
        self.assertTrue(emails, "notifications sent fewer than two emails\n" + s.log("notifications")[-1500:])
        kinds = {e["kind"]: e for e in emails}
        self.assertIn("Total: $61.15", kinds["order_confirmation"]["body"])
        self.assertIn("Total: $61.15", kinds["receipt"]["body"])
        self.assertIn("Tax: $4.92", kinds["receipt"]["body"])

        status, account = s.get("storefront", "/account/cust_42/orders")
        self.assertEqual(status, 200)
        self.assertEqual(account["orders"][0]["invoice"]["total_display"], "$61.15")

    def test_cancel_sends_one_cancellation(self):
        s = self.stack
        _, page = s.post("storefront", "/checkout", dict(CHECKOUT, customer_id="cust_77", postal_code=10001))
        self.assertEqual(page["tax_display"], "$3.37")  # 56.23 * 0.06 = 3.3738
        status, cancelled = s.post("storefront", "/orders/{}/cancel".format(page["order_id"]))
        self.assertEqual(status, 200)
        self.assertEqual(cancelled["status_label"], "Cancelled")
        s.post("storefront", "/orders/{}/cancel".format(page["order_id"]))
        emails = s.wait_for(lambda: [e for e in self.emails("cust_77") if e["kind"] == "cancellation"])
        self.assertEqual(len(emails), 1)

    def test_bad_requests_are_rejected_at_the_edge(self):
        s = self.stack
        self.assertEqual(s.post("storefront", "/checkout", dict(CHECKOUT, items=[]))[0], 400)
        self.assertEqual(s.post("storefront", "/checkout", dict(CHECKOUT, items=[{"sku": "NOPE", "qty": 1}]))[0], 400)


if __name__ == "__main__":
    unittest.main()

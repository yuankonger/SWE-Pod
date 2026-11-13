"""Hidden checks for task01_money. One check per method, named test_<boundary>__<what>."""
import os
import unittest

from stack import Stack

USD = lambda minor: {"currency": "USD", "minor": minor}  # noqa: E731
CHECKOUT = {"customer_id": "cust_42", "email": "pat@example.com", "postal_code": 94105,
            "items": [{"sku": "BOX-S", "qty": 2}, {"sku": "ADD-TEA", "qty": 1}]}
# 2 x 2499 + 625 = 5623; tax 8.75% = 492.01 -> 492; total 6115
BIG = {"customer_id": "cust_77", "email": "sam@example.com", "postal_code": 10001,
       "items": [{"sku": "BOX-L", "qty": 3}, {"sku": "ADD-TEA", "qty": 7}]}
# 3 x 3950 + 7 x 625 = 16225; tax 6% = 973.5 -> 974 (half up); total 17199


class Task01(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = Stack(root=os.environ["SEEDCO_ROOT"], base_port=int(os.environ.get("SEEDCO_BASE_PORT", "7100")),
                      start_timeout=180).start()
        try:
            cls.status, cls.page = cls.s.post("storefront", "/checkout", CHECKOUT)
            cls.big_status, cls.big = cls.s.post("storefront", "/checkout", BIG)
            oid = (cls.page or {}).get("order_id")
            cls.order = cls.s.get("orders", "/orders/" + oid)[1] if oid else None
            cls.invoices = cls.s.wait_for(
                lambda: (cls.s.get("billing", "/invoices?order_id=" + oid)[1] or {}).get("invoices")) if oid else None
            cls.emails = cls.s.wait_for(lambda: (lambda e: len(e) >= 2 and e)(
                (cls.s.get("notifications", "/outbox?customer_id=cust_42")[1] or {}).get("emails") or [])) or []
        except Exception:
            cls.s.stop()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.s.stop()

    def email(self, kind):
        found = [e for e in self.emails if e.get("kind") == kind]
        self.assertTrue(found, "no {} email was sent".format(kind))
        return found[0]["body"]

    def events(self, topic, event_type):
        events = self.s.get("broker", "/topics/{}?offset=0".format(topic))[1]["events"]
        found = [e for e in events if e.get("event_type") == event_type]
        self.assertTrue(found, "no {} event on the {} topic".format(event_type, topic))
        return found

    # A check that customers still see the same text also requires the new representation on the wire behind it:
    # an untouched company shows the right text and must score nothing.
    def wire_is_money(self):
        self.assertIsNotNone(self.order, "checkout did not return an order")
        self.assertEqual(self.order["total"], USD(6115), "the order behind this page or email is not in Money objects")

    def test_storefront_orders__checkout_page_shows_the_same_dollars(self):
        self.assertEqual(self.status, 201, self.page)
        self.wire_is_money()
        self.assertEqual((self.page["subtotal_display"], self.page["tax_display"], self.page["total_display"]),
                         ("$56.23", "$4.92", "$61.15"))
        self.assertEqual([l["line_total_display"] for l in self.page["lines"]], ["$49.98", "$6.25"])
        self.assertEqual([l["unit_price_display"] for l in self.page["lines"]], ["$24.99", "$6.25"])

    def test_orders_api__order_carries_money_objects(self):
        self.assertIsNotNone(self.order, "checkout did not return an order")
        self.assertEqual((self.order["subtotal"], self.order["tax"], self.order["total"]),
                         (USD(5623), USD(492), USD(6115)))
        self.assertEqual([l["unit_price"] for l in self.order["lines"]], [USD(2499), USD(625)])

    def test_orders_billing__quote_and_charge_take_and_return_money_objects(self):
        status, quote = self.s.post("billing", "/quotes", {"postal_code": 94105, "lines": [
            {"sku": "BOX-S", "qty": 2, "unit_price": USD(2499)}, {"sku": "ADD-TEA", "qty": 1, "unit_price": USD(625)}]})
        self.assertEqual(status, 200, quote)
        self.assertEqual(quote, {"subtotal": USD(5623), "tax": USD(492), "total": USD(6115)})
        status, payment = self.s.post("billing", "/charges", {"order_id": "ord_x", "customer_id": "c", "amount": USD(6115)})
        self.assertEqual(status, 200, payment)
        self.assertEqual(payment["amount"], USD(6115))

    def test_orders_billing__billing_rejects_plain_numbers(self):
        status, _ = self.s.post("billing", "/quotes", {"postal_code": 94105, "lines": [
            {"sku": "BOX-S", "qty": 2, "unit_price": 24.99}]})
        self.assertEqual(status, 400)
        status, _ = self.s.post("billing", "/charges", {"order_id": "ord_x", "customer_id": "c", "amount": 61.15})
        self.assertEqual(status, 400)

    def test_orders_events__order_placed_carries_money_objects(self):
        order = self.events("orders", "order.placed")[0]["data"]["order"]
        self.assertEqual(order["total"], USD(6115))
        self.assertEqual(order["lines"][0]["unit_price"], USD(2499))

    def test_events_billing__invoice_is_issued_in_minor_units(self):
        self.assertTrue(self.invoices, "billing issued no invoice for the order")
        inv = self.invoices[0]
        self.assertEqual((inv["subtotal"], inv["tax"], inv["total"]), (USD(5623), USD(492), USD(6115)))
        self.assertEqual([l["amount"] for l in inv["lines"]], [USD(4998), USD(625)])

    def test_billing_events__invoice_paid_carries_money_objects(self):
        invoice = self.events("billing", "invoice.paid")[0]["data"]["invoice"]
        self.assertEqual(invoice["total"], USD(6115))

    def test_events_notifications__emails_show_the_same_dollars(self):
        self.wire_is_money()
        self.assertEqual(self.events("billing", "invoice.paid")[0]["data"]["invoice"]["total"], USD(6115))
        self.assertIn("Total: $61.15", self.email("order_confirmation"))
        receipt = self.email("receipt")
        for text in ("2 x Small monthly box  $49.98", "Subtotal: $56.23", "Tax: $4.92", "Total: $61.15"):
            self.assertIn(text, receipt)

    def test_storefront_billing__account_page_shows_the_invoice_total(self):
        self.wire_is_money()
        status, account = self.s.get("storefront", "/account/cust_42/orders")
        self.assertEqual(status, 200, account)
        self.assertTrue(self.s.wait_for(lambda: self.s.get("storefront", "/account/cust_42/orders")[1]["orders"][0]["invoice"]),
                        "the account page never showed an invoice")
        page = self.s.get("storefront", "/account/cust_42/orders")[1]["orders"][0]
        self.assertEqual(page["invoice"]["total_display"], "$61.15")

    def test_events_notifications__renewal_receipt_shows_the_same_dollars(self):
        subs = self.s.wait_for(lambda: (self.s.get("billing", "/subscriptions?customer_id=cust_42")[1] or {}).get("subscriptions"))
        self.assertTrue(subs, "billing started no subscription for the order")
        status, run = self.s.post("billing", "/renewals/run", {"as_of": subs[0]["current_period_end"]})
        self.assertEqual(status, 200, run)   # the run renews every subscription that is due, the other customer's too
        renewals = [i for i in self.s.get("billing", "/invoices?customer_id=cust_42")[1]["invoices"] if i.get("reason") == "renewal"]
        self.assertEqual([i["total"] for i in renewals], [USD(5435)])    # 2 x 2499 = 4998; tax 8.75% = 437.3 -> 437
        receipt = self.s.wait_for(lambda: [e for e in self.s.get("notifications", "/outbox?customer_id=cust_42")[1]["emails"]
                                           if e["subject"].startswith("Renewal receipt")])
        self.assertTrue(receipt, "no renewal receipt was sent")
        for text in ("2 x Small monthly box  $49.98", "Tax: $4.37", "Total: $54.35"):
            self.assertIn(text, receipt[0]["body"])

    def test_storefront_billing__subscription_page_shows_the_monthly_price(self):
        subs = self.s.wait_for(lambda: (self.s.get("billing", "/subscriptions?customer_id=cust_77")[1] or {}).get("subscriptions"))
        self.assertTrue(subs, "billing started no subscription for the order")
        self.assertEqual(subs[0]["unit_price"], USD(3950), "the subscription is not priced in Money objects")
        status, page = self.s.get("storefront", "/account/cust_77/subscriptions")
        self.assertEqual(status, 200, page)
        self.assertEqual(page["subscriptions"][0]["price_display"], "$118.50 a month")    # 3 x 39.50

    def test_rounding__tax_rounds_half_up_to_the_cent_end_to_end(self):
        self.assertEqual(self.big_status, 201, self.big)
        big = self.s.get("orders", "/orders/" + self.big["order_id"])[1]
        self.assertEqual((big["subtotal"], big["tax"], big["total"]), (USD(16225), USD(974), USD(17199)))
        self.assertEqual((self.big["subtotal_display"], self.big["tax_display"], self.big["total_display"]),
                         ("$162.25", "$9.74", "$171.99"))

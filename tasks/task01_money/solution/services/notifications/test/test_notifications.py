import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from notifications import Outbox, money  # noqa: E402

ORDER = {"order_id": "ord_1", "customer_id": "c1", "email": "a@example.com", "status": "paid",
         "lines": [{"sku": "BOX-S", "name": "Small monthly box", "qty": 2, "unit_price": {"currency": "USD", "minor": 2499}}],
         "subtotal": {"currency": "USD", "minor": 4998}, "tax": {"currency": "USD", "minor": 437}, "total": {"currency": "USD", "minor": 5435}}
INVOICE = {"invoice_id": "inv_1", "order_id": "ord_1", "customer_id": "c1", "email": "a@example.com",
           "lines": [{"sku": "BOX-S", "name": "Small monthly box", "qty": 2, "unit_price": {"currency": "USD", "minor": 2499}, "amount": {"currency": "USD", "minor": 4998}}],
           "subtotal": {"currency": "USD", "minor": 4998}, "tax": {"currency": "USD", "minor": 437}, "total": {"currency": "USD", "minor": 5435}, "status": "paid"}


def event(event_id, event_type, **data):
    return {"event_id": event_id, "event_type": event_type, "occurred_at": "2026-01-01T00:00:00Z", "data": data}


class OutboxTest(unittest.TestCase):
    def test_money_formats_dollars(self):
        self.assertEqual(money({"currency": "USD", "minor": 5435}), "$54.35")
        self.assertEqual(money({"currency": "USD", "minor": 123450}), "$1,234.50")

    def test_order_confirmation(self):
        email = Outbox().handle(event("evt_1", "order.placed", order=ORDER))
        self.assertEqual(email["to"], "a@example.com")
        self.assertEqual(email["subject"], "Order ord_1 confirmed")
        self.assertIn("2 x Small monthly box", email["body"])
        self.assertIn("Total: $54.35", email["body"])

    def test_receipt_shows_lines_tax_and_total(self):
        email = Outbox().handle(event("evt_2", "invoice.paid", invoice=INVOICE))
        self.assertEqual(email["kind"], "receipt")
        for text in ("2 x Small monthly box  $49.98", "Subtotal: $49.98", "Tax: $4.37", "Total: $54.35"):
            self.assertIn(text, email["body"])

    def test_one_email_per_event(self):
        box = Outbox()
        box.handle(event("evt_1", "order.placed", order=ORDER))
        self.assertIsNone(box.handle(event("evt_1", "order.placed", order=ORDER)))
        box.handle(event("evt_3", "order.cancelled", order=ORDER))
        self.assertIsNone(box.handle(event("evt_4", "something.else")))
        self.assertEqual([e["kind"] for e in box.for_customer("c1")], ["order_confirmation", "cancellation"])
        self.assertEqual(box.for_customer("c2"), [])


if __name__ == "__main__":
    unittest.main()

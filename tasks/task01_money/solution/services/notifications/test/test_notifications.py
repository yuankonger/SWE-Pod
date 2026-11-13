import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from notifications import DROP_ALERT_THRESHOLD, Outbox, money  # noqa: E402
from payload import PayloadError  # noqa: E402
from store import Store  # noqa: E402

ORDER = {"order_id": "ord_1", "customer_id": "c1", "email": "a@example.com", "status": "paid",
         "lines": [{"sku": "BOX-S", "name": "Small monthly box", "qty": 2, "unit_price": {"currency": "USD", "minor": 2499}}],
         "subtotal": {"currency": "USD", "minor": 4998}, "tax": {"currency": "USD", "minor": 437}, "total": {"currency": "USD", "minor": 5435}}
INVOICE = {"invoice_id": "inv_1", "order_id": "ord_1", "subscription_id": None, "customer_id": "c1",
           "email": "a@example.com", "reason": "order",
           "lines": [{"type": "RECURRING", "sku": "BOX-S", "name": "Small monthly box", "qty": 2, "unit_price": {"currency": "USD", "minor": 2499}, "amount": {"currency": "USD", "minor": 4998}}],
           "subtotal": {"currency": "USD", "minor": 4998}, "tax": {"currency": "USD", "minor": 437}, "total": {"currency": "USD", "minor": 5435}, "status": "paid", "issued_at": "2026-01-01T00:00:00Z"}
PAYMENT = {"payment_id": "pay_1", "order_id": "ord_1", "customer_id": "c1", "email": "a@example.com",
           "amount": {"currency": "USD", "minor": 5435}, "status": "failed", "failure_reason": "card_declined"}
SUBSCRIPTION = {"subscription_id": "sub_1", "customer_id": "c1", "email": "a@example.com", "sku": "BOX-L",
                "name": "Large monthly box", "status": "active", "current_period_end": "2026-02-01",
                "pending_name": "Small monthly box"}


def usd(minor):
    return {"currency": "USD", "minor": minor}


def event(event_id, event_type, **data):
    return {"event_id": event_id, "event_type": event_type, "occurred_at": "2026-01-01T00:00:00Z", "data": data}


class OutboxTest(unittest.TestCase):
    def test_money_formats_dollars(self):
        self.assertEqual(money(usd(5435)), "$54.35")
        self.assertEqual(money(usd(123450)), "$1,234.50")
        self.assertEqual(money(usd(-5484)), "-$54.84")

    def test_order_confirmation(self):
        email = Outbox().handle(event("evt_1", "order.placed", order=ORDER))
        self.assertEqual(email["to"], "a@example.com")
        self.assertEqual(email["subject"], "Order ord_1 confirmed")
        self.assertIn("2 x Small monthly box", email["body"])
        self.assertIn("Total: $54.35", email["body"])

    def test_receipt_shows_lines_tax_and_total(self):
        email = Outbox().handle(event("evt_2", "invoice.paid", invoice=INVOICE))
        self.assertEqual(email["kind"], "receipt")
        self.assertEqual(email["subject"], "Receipt for order ord_1")
        for text in ("2 x Small monthly box  $49.98", "Subtotal: $49.98", "Tax: $4.37", "Total: $54.35"):
            self.assertIn(text, email["body"])

    def test_plan_change_receipt_shows_the_credit(self):
        lines = [{"type": "CREDIT", "sku": "BOX-S", "name": "Unused time on Small monthly box", "qty": 1, "amount": {"currency": "USD", "minor": -1370}},
                 {"type": "PRORATION", "sku": "BOX-L", "name": "Remaining time on Large monthly box", "qty": 1, "amount": {"currency": "USD", "minor": 2166}}]
        email = Outbox().handle(event("evt_5", "invoice.paid", invoice=dict(
            INVOICE, reason="plan_change", subscription_id="sub_1", lines=lines, subtotal=usd(796), tax=usd(70), total=usd(866))))
        self.assertEqual(email["subject"], "Receipt for your plan change on order ord_1")
        self.assertIn("1 x Unused time on Small monthly box  -$13.70", email["body"])

    def test_one_email_per_event(self):
        box = Outbox()
        box.handle(event("evt_1", "order.placed", order=ORDER))
        self.assertIsNone(box.handle(event("evt_1", "order.placed", order=ORDER)))
        box.handle(event("evt_3", "order.cancelled", order=ORDER))
        self.assertIsNone(box.handle(event("evt_4", "something.else")))
        self.assertEqual([e["kind"] for e in box.for_customer("c1")], ["order_confirmation", "cancellation"])
        self.assertEqual(box.for_customer("c2"), [])

    def test_payment_failed_shipping_and_subscription_emails(self):
        box = Outbox()
        self.assertIn("$54.35 did not go through (card_declined)",
                      box.handle(event("evt_1", "payment.failed", payment=PAYMENT))["body"])
        self.assertEqual(box.handle(event("evt_2", "order.shipped", order=ORDER))["kind"], "shipping")
        email = box.handle(event("evt_3", "subscription.updated", subscription=SUBSCRIPTION, change="downgrade_scheduled"))
        self.assertEqual(email["body"], "Your plan changes to Small monthly box on 2026-02-01. Until then you keep "
                                        "Large monthly box.")
        self.assertIsNone(box.handle(event("evt_4", "subscription.updated", subscription=SUBSCRIPTION, change="renewed")))

    def test_an_event_that_does_not_fit_its_payload_schema_is_rejected(self):
        box = Outbox()
        with self.assertRaises(PayloadError):   # total must be a Money object
            box.handle(event("evt_1", "order.placed", order=dict(ORDER, total="54.35")))
        with self.assertRaises(PayloadError):   # receipts are strict: an unknown invoice field is refused
            box.handle(event("evt_2", "invoice.paid", invoice=dict(INVOICE, discount=1.0)))
        with self.assertRaises(PayloadError):   # and so is an unknown line type
            box.handle(event("evt_3", "invoice.paid", invoice=dict(INVOICE, lines=[dict(INVOICE["lines"][0], type="USAGE")])))
        self.assertIsNotNone(box.handle(event("evt_4", "order.placed", order=dict(ORDER, gift_note="hi"))))

    def test_dropped_events_are_recorded_and_raise_one_alert(self):
        box = Outbox()
        for i in range(DROP_ALERT_THRESHOLD + 2):
            self.assertIsNone(box.consume(event("evt_%d" % i, "order.placed", order=dict(ORDER, total=None))))
        self.assertEqual(len(box.store.dropped()), DROP_ALERT_THRESHOLD + 2)
        alerts = box.store.emails(kind="ops_alert")
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["subject"], "Notifications is dropping order.placed events")

    def test_the_outbox_and_the_dedup_log_survive_a_restart(self):
        path = os.path.join(tempfile.mkdtemp(prefix="seedco-notif-"), "n.db")
        first = Outbox(Store(path))
        first.handle(event("evt_1", "order.placed", order=ORDER))
        first.store.set_offset("orders", 7)
        again = Outbox(Store(path))
        self.assertIsNone(again.handle(event("evt_1", "order.placed", order=ORDER)))
        self.assertEqual(len(again.for_customer("c1")), 1)
        self.assertEqual(again.store.offset("orders"), 7)


if __name__ == "__main__":
    unittest.main()

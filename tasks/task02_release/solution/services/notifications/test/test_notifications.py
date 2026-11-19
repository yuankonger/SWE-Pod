import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from notifications import DROP_ALERT_THRESHOLD, Outbox, money  # noqa: E402
from payload import PayloadError  # noqa: E402
from server import manifest  # noqa: E402
from store import Store  # noqa: E402


def amount(value):
    return {"amount": value}


ORDER = {"id": "T3JkZXI6MQ==", "number": "1", "userEmail": "pat@example.com", "displayGrossPrices": False,
         "lines": [{"productName": "Small monthly box", "variantName": "", "quantity": 2, "totalPrice": {"net": amount(49.98), "gross": amount(54.35)}},
                   {"productName": "Tea add-on", "quantity": 1, "totalPrice": {"net": amount(6.25), "gross": amount(6.8)}}],
         "subtotal": {"net": amount(56.23), "gross": amount(61.15)}, "shippingPrice": {"gross": amount(5.0)},
         "total": {"gross": {"amount": 66.15, "currency": "USD"}, "tax": amount(4.92)}, "totalRefunded": amount(0.0)}


def event(typename, **changes):
    return {"__typename": typename, "order": dict(ORDER, **changes)}


class OutboxTest(unittest.TestCase):
    def test_money_formats_dollars(self):
        self.assertEqual(money(amount(54.35)), "$54.35")
        self.assertEqual(money(amount(1234.5)), "$1,234.50")
        self.assertEqual(money(amount(-54.84)), "-$54.84")

    def test_order_confirmation(self):
        email = Outbox().handle(event("OrderConfirmed"))
        self.assertEqual((email["to"], email["subject"]), ("pat@example.com", "Order #1 confirmed"))
        self.assertIn("2 x Small monthly box", email["body"])
        self.assertIn("Total: $66.15", email["body"])

    def test_receipt_shows_net_lines_shipping_tax_and_total(self):
        email = Outbox().handle(event("OrderFullyPaid"))
        self.assertEqual((email["kind"], email["subject"]), ("receipt", "Receipt for order #1"))
        for text in ("2 x Small monthly box  $49.98", "Subtotal: $56.23", "Shipping: $5.00", "Tax: $4.92", "Total: $66.15"):
            self.assertIn(text, email["body"])

    def test_a_line_names_its_variant_when_the_product_has_several(self):
        tea = {"productName": "Assam Breakfast", "variantName": "100 g", "quantity": 1, "totalPrice": {"net": amount(13.0), "gross": amount(14.14)}}
        box = Outbox()
        self.assertIn("1 x Assam Breakfast (100 g)", box.handle(event("OrderConfirmed", lines=[tea]))["body"])
        self.assertIn("1 x Assam Breakfast (100 g)  $13.00", box.handle(event("OrderFullyPaid", lines=[tea]))["body"])

    def test_receipt_shows_gross_lines_when_the_shop_displays_gross_prices(self):
        email = Outbox().handle(event("OrderFullyPaid", displayGrossPrices=True))
        for text in ("2 x Small monthly box  $54.35", "Subtotal: $61.15", "Tax: $4.92", "Total: $66.15"):
            self.assertIn(text, email["body"])

    def test_a_repeated_delivery_sends_one_email(self):
        box = Outbox()
        self.assertIsNotNone(box.handle(event("OrderConfirmed")))
        self.assertIsNone(box.handle(event("OrderConfirmed")))
        self.assertIsNotNone(box.handle(event("OrderFulfilled")))
        self.assertIsNotNone(box.handle(event("OrderCancelled")))
        self.assertIsNone(box.handle({"__typename": "SomethingElse"}))
        self.assertEqual([e["kind"] for e in box.emails("pat@example.com")], ["order_confirmation", "shipping", "cancellation"])
        self.assertEqual(box.emails("sam@example.com"), [])

    def test_each_refund_is_its_own_email(self):
        box = Outbox()
        first = box.handle(event("OrderRefunded", totalRefunded=amount(16.15)))
        self.assertEqual(first["body"], "We have refunded $16.15 to your payment method.")
        self.assertIsNone(box.handle(event("OrderRefunded", totalRefunded=amount(16.15))))
        self.assertIsNotNone(box.handle(event("OrderRefunded", totalRefunded=amount(66.15))))

    def test_an_event_that_does_not_fit_its_payload_schema_is_rejected(self):
        box = Outbox()
        with self.assertRaises(PayloadError):   # an amount must be a number
            box.handle(event("OrderConfirmed", total={"gross": {"amount": "66.15"}, "tax": amount(4.92)}))
        with self.assertRaises(PayloadError):
            box.handle(event("OrderConfirmed", userEmail=None))
        with self.assertRaises(PayloadError):
            box.handle({"__typename": "OrderConfirmed"})
        self.assertEqual(box.emails(), [])

    def test_dropped_events_are_recorded_and_raise_one_alert(self):
        box = Outbox()
        for i in range(DROP_ALERT_THRESHOLD + 2):
            self.assertIsNone(box.consume(event("OrderConfirmed", total=None)))
        self.assertEqual(len(box.store.dropped()), DROP_ALERT_THRESHOLD + 2)
        alerts = box.store.emails(kind="ops_alert")
        self.assertEqual([a["subject"] for a in alerts], ["Notifications is dropping OrderConfirmed events"])

    def test_messages_other_services_ask_for(self):
        box = Outbox()
        base = {"notification_id": "n1", "recipient_email": "pat@example.com", "plan_name": "Large monthly box"}
        sent = box.notify({"notify_event": "SUBSCRIPTION_DOWNGRADE_SCHEDULED", "payload": dict(
            base, pending_plan_name="Small monthly box", period_end="2026-02-01")})
        self.assertEqual(sent["body"], "Your plan changes to Small monthly box on 2026-02-01. Until then you keep Large monthly box.")
        self.assertIsNone(box.notify({"notify_event": "SUBSCRIPTION_PLAN_CHANGED", "payload": base}))     # same notification_id
        failed = box.notify({"notify_event": "SUBSCRIPTION_PAYMENT_FAILED", "payload": dict(
            base, notification_id="n2", amount=amount(54.35), reason="card_declined")})
        self.assertEqual(failed["body"], "A payment of $54.35 for Large monthly box did not go through (card_declined). "
                                         "Please update your payment method.")
        with self.assertRaises(PayloadError):
            box.notify({"notify_event": "SUBSCRIPTION_CANCEL_SCHEDULED", "payload": dict(base, notification_id="n3")})   # no period_end
        with self.assertRaises(PayloadError):
            box.notify({"notify_event": "NOPE", "payload": dict(base, notification_id="n4")})

    def test_the_outbox_survives_a_restart(self):
        path = os.path.join(tempfile.mkdtemp(prefix="seedco-notif-"), "n.db")
        Outbox(Store(path)).handle(event("OrderConfirmed"))
        again = Outbox(Store(path))
        self.assertIsNone(again.handle(event("OrderConfirmed")))
        self.assertEqual(len(again.emails("pat@example.com")), 1)

    def test_the_manifest_subscribes_to_order_events_with_the_query_file(self):
        m = manifest("http://notifications.test")
        self.assertEqual(m["id"], "seedco.notifications")
        self.assertIn("ORDER_FULLY_PAID", m["webhooks"][0]["asyncEvents"])
        self.assertIn("fragment OrderDetails on Order", m["webhooks"][0]["query"])


if __name__ == "__main__":
    unittest.main()

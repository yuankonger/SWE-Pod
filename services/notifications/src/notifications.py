"""Notifications: turns order and billing events into emails. The outbox stands in for a mail provider.

Each event type has one workflow: a payload schema (what the template needs from the event) and a template.
"""
from payload import INVOICE, ORDER, PAYMENT, SUBSCRIPTION, PayloadError, check
from store import Store

TOPICS = ("orders", "billing")
OPS_ADDRESS = "ops@seedco.example"
DROP_ALERT_THRESHOLD = 3   # this many dropped events of one type raises one alert to operations


def money(amount) -> str:
    value = float(amount)
    return ("-" if value < 0 else "") + "${:,.2f}".format(abs(value))


def _email(kind, who, subject, lines) -> dict:
    return {"kind": kind, "customer_id": who["customer_id"], "to": who["email"], "subject": subject,
            "body": "\n".join(lines)}


def render_order_placed(data: dict) -> dict:
    order = data["order"]
    lines = ["Thanks for your order.", ""]
    lines += ["  {} x {}".format(l["qty"], l["name"]) for l in order["lines"]]
    lines += ["", "Total: " + money(order["total"])]
    return _email("order_confirmation", order, "Order {} confirmed".format(order["order_id"]), lines)


def render_order_shipped(data: dict) -> dict:
    order = data["order"]
    lines = ["Your order is on its way.", ""] + ["  {} x {}".format(l["qty"], l["name"]) for l in order["lines"]]
    return _email("shipping", order, "Order {} shipped".format(order["order_id"]), lines)


def render_order_cancelled(data: dict) -> dict:
    order = data["order"]
    return _email("cancellation", order, "Order {} cancelled".format(order["order_id"]),
                  ["Your order has been cancelled. Any payment of {} will be refunded.".format(money(order["total"]))])


RECEIPT_SUBJECTS = {"order": "Receipt for order {}", "renewal": "Renewal receipt for order {}",
                    "plan_change": "Receipt for your plan change on order {}"}


def render_invoice_paid(data: dict) -> dict:
    invoice = data["invoice"]
    lines = ["Receipt for invoice {}".format(invoice["invoice_id"]), ""]
    lines += ["  {} x {}  {}".format(l["qty"], l["name"], money(l["amount"])) for l in invoice["lines"]]
    lines += ["", "Subtotal: " + money(invoice["subtotal"]), "Tax: " + money(invoice["tax"]),
              "Total: " + money(invoice["total"])]
    subject = RECEIPT_SUBJECTS[invoice.get("reason", "order")].format(invoice["order_id"])
    return _email("receipt", invoice, subject, lines)


def render_payment_failed(data: dict) -> dict:
    payment = data["payment"]
    return _email("payment_failed", payment, "We could not take your payment",
                  ["A payment of {} did not go through ({}).".format(money(payment["amount"]), payment["failure_reason"]),
                   "Please update your payment method."])


SUBSCRIPTION_TEXT = {
    "plan_changed": "Your plan is now {name}.",
    "downgrade_scheduled": "Your plan changes to {pending_name} on {current_period_end}. Until then you keep {name}.",
    "cancel_scheduled": "Your {name} subscription ends on {current_period_end}.",
    "terminated": "Your {name} subscription has ended.",
}


def render_subscription_updated(data: dict):
    sub, change = data["subscription"], data.get("change")
    if change not in SUBSCRIPTION_TEXT:
        return None   # a change we send nothing for, such as a renewal (the receipt covers it)
    return _email("subscription_update", sub, "Your subscription has changed", [SUBSCRIPTION_TEXT[change].format(**sub)])


# event type -> (key of the embedded object, payload schema, template)
WORKFLOWS = {
    "order.placed": ("order", ORDER, render_order_placed),
    "order.shipped": ("order", ORDER, render_order_shipped),
    "order.cancelled": ("order", ORDER, render_order_cancelled),
    "invoice.paid": ("invoice", INVOICE, render_invoice_paid),
    "payment.failed": ("payment", PAYMENT, render_payment_failed),
    "subscription.updated": ("subscription", SUBSCRIPTION, render_subscription_updated),
}


class Outbox:
    """Every email sent, in order. One email per event: a repeated event_id is ignored."""

    def __init__(self, store: Store = None):
        self.store = store or Store()

    def handle(self, envelope: dict):
        """Returns the email sent for this event, or None. Raises PayloadError for an event it cannot use."""
        workflow = WORKFLOWS.get(envelope.get("event_type"))
        if workflow is None:
            return None
        key, schema, render = workflow
        with self.store.lock:
            if self.store.seen(envelope["event_id"]):
                return None
            data = envelope.get("data") or {}
            if key not in data:
                raise PayloadError("$.data.{} is required".format(key))
            check(data[key], schema, "$.data." + key)
            email = render(data)
            if email is None:
                return None
            self.store.save_email(envelope["event_id"], envelope["event_type"], email)
            return dict(email, event_id=envelope["event_id"])

    def consume(self, envelope: dict):
        """What a consumer does with one event: send its email, or record why it could not. Never raises."""
        try:
            return self.handle(envelope)
        except Exception as exc:  # one unreadable event must not stop the consumer
            event_id, event_type = envelope.get("event_id"), envelope.get("event_type")
            count = self.store.drop(event_id, event_type, "{}: {}".format(type(exc).__name__, exc))
            if count == DROP_ALERT_THRESHOLD:
                self.store.save_email("alert:{}".format(event_type), "ops.alert", {
                    "kind": "ops_alert", "customer_id": "ops", "to": OPS_ADDRESS,
                    "subject": "Notifications is dropping {} events".format(event_type),
                    "body": "{} {} events could not be turned into emails. Latest reason: {}".format(
                        count, event_type, exc)})
            return None

    def for_customer(self, customer_id=None):
        return self.store.emails(customer_id)

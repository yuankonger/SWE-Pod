"""Notifications: turns Core's order events, and messages other services ask for, into emails.
The outbox stands in for a mail provider.

Core does not number its deliveries and may send one more than once, so every email has a dedup key built from
what it is about. The same key is never sent twice.
"""
from payload import NOTIFY, ORDER, PayloadError, check
from store import Store

OPS_ADDRESS = "ops@seedco.example"
DROP_ALERT_THRESHOLD = 3   # this many dropped events of one type raises one alert to operations


def money(amount) -> str:
    """Core's Money as text. `amount` is a decimal number in major units; only USD exists today."""
    value = float(amount["amount"])
    return ("-" if value < 0 else "") + "${:,.2f}".format(abs(value))


def _email(kind, to, subject, lines) -> dict:
    return {"kind": kind, "to": to, "subject": subject, "body": "\n".join(lines)}


def _name(line: dict) -> str:
    """The product, and which variant of it when the product has more than one."""
    return "{} ({})".format(line["productName"], line["variantName"]) if line.get("variantName") else line["productName"]


def _items(order: dict) -> list:
    return ["  {} x {}".format(l["quantity"], _name(l)) for l in order["lines"]]


def render_order_created(order: dict) -> dict:
    lines = ["Thanks for your order.", ""] + _items(order) + ["", "Total: " + money(order["total"]["gross"])]
    return _email("order_confirmation", order["userEmail"], "Order #{} confirmed".format(order["number"]), lines)


def render_order_fully_paid(order: dict) -> dict:
    # Line amounts follow the channel: with tax when the shop shows gross prices, without when it shows net.
    side = "gross" if order.get("displayGrossPrices") else "net"
    lines = ["Receipt for order #{}".format(order["number"]), ""]
    lines += ["  {} x {}  {}".format(l["quantity"], _name(l), money(l["totalPrice"][side])) for l in order["lines"]]
    lines += ["", "Subtotal: " + money(order["subtotal"][side]), "Shipping: " + money(order["shippingPrice"]["gross"]),
              "Tax: " + money(order["total"]["tax"]), "Total: " + money(order["total"]["gross"])]
    return _email("receipt", order["userEmail"], "Receipt for order #{}".format(order["number"]), lines)


def render_order_fulfilled(order: dict) -> dict:
    return _email("shipping", order["userEmail"], "Order #{} shipped".format(order["number"]),
                  ["Your order is on its way.", ""] + _items(order))


def render_order_cancelled(order: dict) -> dict:
    return _email("cancellation", order["userEmail"], "Order #{} cancelled".format(order["number"]),
                  ["Your order has been cancelled. If you paid for it, a refund will follow separately."])


def render_order_refunded(order: dict) -> dict:
    return _email("refund", order["userEmail"], "Refund for order #{}".format(order["number"]),
                  ["We have refunded {} to your payment method.".format(money(order["totalRefunded"]))])


# event __typename -> (template, what makes two events the same email)
ORDER_WORKFLOWS = {
    "OrderCreated": (render_order_created, lambda o: o["id"]),
    "OrderFullyPaid": (render_order_fully_paid, lambda o: o["id"]),
    "OrderFulfilled": (render_order_fulfilled, lambda o: o["id"]),
    "OrderCancelled": (render_order_cancelled, lambda o: o["id"]),
    # an order can be refunded more than once: each new refunded total is its own email
    "OrderRefunded": (render_order_refunded, lambda o: "{}:{}".format(o["id"], o["totalRefunded"]["amount"])),
}

NOTIFY_TEXT = {
    "SUBSCRIPTION_PLAN_CHANGED": ("Your subscription has changed", "Your plan is now {plan_name}."),
    "SUBSCRIPTION_DOWNGRADE_SCHEDULED": ("Your subscription has changed",
                                         "Your plan changes to {pending_plan_name} on {period_end}. Until then you keep {plan_name}."),
    "SUBSCRIPTION_CANCEL_SCHEDULED": ("Your subscription has changed", "Your {plan_name} subscription ends on {period_end}."),
    "SUBSCRIPTION_TERMINATED": ("Your subscription has ended", "Your {plan_name} subscription has ended."),
    "SUBSCRIPTION_PAYMENT_FAILED": ("We could not take your payment",
                                    "A payment of {amount_text} for {plan_name} did not go through ({reason}). Please update your payment method."),
}


class Outbox:
    """Every email sent, in order."""

    def __init__(self, store: Store = None):
        self.store = store or Store()

    def _send(self, dedup_key: str, email: dict):
        with self.store.lock:
            if self.store.sent(dedup_key):
                return None
            self.store.save_email(dedup_key, email)
            return email

    def handle(self, payload: dict):
        """One order event from Core. Returns the email sent, or None. Raises PayloadError for an event it cannot use."""
        workflow = ORDER_WORKFLOWS.get(payload.get("__typename"))
        if workflow is None:
            return None
        render, key = workflow
        if "order" not in payload:
            raise PayloadError("$.order is required")
        check(payload["order"], ORDER, "$.order")
        return self._send("{}:{}".format(payload["__typename"], key(payload["order"])), render(payload["order"]))

    def notify(self, message: dict):
        """A message another service asks us to send. Returns the email sent, or None for a repeat."""
        check(message, NOTIFY)
        event, data = message["notify_event"], message["payload"]
        if event not in NOTIFY_TEXT:
            raise PayloadError("unknown notify_event {!r}".format(event))
        subject, text = NOTIFY_TEXT[event]
        fields = dict(data, amount_text=money(data["amount"]) if "amount" in data else "")
        try:
            body = text.format(**fields)
        except KeyError as missing:
            raise PayloadError("$.payload.{} is required for {}".format(missing.args[0], event))
        return self._send("notify:" + data["notification_id"], _email(event.lower(), data["recipient_email"], subject, [body]))

    def consume(self, payload: dict):
        """What the webhook does with one event: send its email, or record why it could not. Never raises."""
        try:
            return self.handle(payload)
        except Exception as exc:  # one unreadable event must not take the webhook down
            event_type = payload.get("__typename") if isinstance(payload, dict) else None
            count = self.store.drop(event_type, "{}: {}".format(type(exc).__name__, exc))
            if count == DROP_ALERT_THRESHOLD:
                self._send("alert:{}".format(event_type), _email(
                    "ops_alert", OPS_ADDRESS, "Notifications is dropping {} events".format(event_type),
                    ["{} {} events could not be turned into emails. Latest reason: {}".format(count, event_type, exc)]))
            return None

    def emails(self, recipient=None):
        return self.store.emails(recipient)

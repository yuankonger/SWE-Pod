"""Notifications: turns order and billing events into emails. The outbox stands in for a mail provider."""
import threading

TOPICS = ("orders", "billing")


def money(amount: dict) -> str:
    """A Money object ({"currency", "minor"}) as dollars. Only USD exists today."""
    return "${:,.2f}".format(amount["minor"] / 100)


def render_order_placed(order: dict) -> dict:
    lines = ["Thanks for your order.", ""]
    lines += ["  {} x {}".format(l["qty"], l["name"]) for l in order["lines"]]
    lines += ["", "Total: " + money(order["total"])]
    return {"kind": "order_confirmation", "customer_id": order["customer_id"], "to": order["email"],
            "subject": "Order {} confirmed".format(order["order_id"]), "body": "\n".join(lines)}


def render_invoice_paid(invoice: dict) -> dict:
    lines = ["Receipt for invoice {}".format(invoice["invoice_id"]), ""]
    lines += ["  {} x {}  {}".format(l["qty"], l["name"], money(l["amount"])) for l in invoice["lines"]]
    lines += ["", "Subtotal: " + money(invoice["subtotal"]), "Tax: " + money(invoice["tax"]),
              "Total: " + money(invoice["total"])]
    return {"kind": "receipt", "customer_id": invoice["customer_id"], "to": invoice["email"],
            "subject": "Receipt for order {}".format(invoice["order_id"]), "body": "\n".join(lines)}


def render_order_cancelled(order: dict) -> dict:
    return {"kind": "cancellation", "customer_id": order["customer_id"], "to": order["email"],
            "subject": "Order {} cancelled".format(order["order_id"]),
            "body": "Your order has been cancelled. Any payment of {} will be refunded.".format(money(order["total"]))}


RENDERERS = {
    "order.placed": lambda data: render_order_placed(data["order"]),
    "invoice.paid": lambda data: render_invoice_paid(data["invoice"]),
    "order.cancelled": lambda data: render_order_cancelled(data["order"]),
}


class Outbox:
    """Every email sent, in order. One email per event: a repeated event_id is ignored."""

    def __init__(self):
        self.emails = []
        self._seen = set()
        self._lock = threading.Lock()

    def handle(self, envelope: dict):
        render = RENDERERS.get(envelope.get("event_type"))
        if render is None:
            return None
        with self._lock:
            if envelope["event_id"] in self._seen:
                return None
            email = dict(render(envelope["data"]), event_id=envelope["event_id"])
            self._seen.add(envelope["event_id"])
            self.emails.append(email)
            return email

    def for_customer(self, customer_id=None):
        with self._lock:
            return [e for e in self.emails if customer_id is None or e["customer_id"] == customer_id]

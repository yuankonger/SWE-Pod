"""Core: catalogue, checkouts, orders and transactions. The rules follow Saleor's.

Core does not calculate tax and does not take payments. It asks the channel's tax app for taxes (a synchronous
webhook) and a payment app for payments (the Transactions API), and it tells every subscribed app what happened to
an order (asynchronous webhooks).
"""
import base64
import json
import os
import time
import time
import uuid
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import telemetry
from webhooks import PERMISSIONS, WebhookError

CENT = Decimal("0.01")
CURRENCY = "USD"
COUNTRIES = {"US": "United States of America", "CA": "Canada", "GB": "United Kingdom"}

# What a new database starts with. The catalogue is catalogue.json, in the shape of Saleor's sample data.
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalogue.json")) as _f:
    CATALOGUE = json.load(_f)


def catalogue_rows() -> list:
    """One row per variant, carrying its product, category and product type. The row id is the variant id."""
    categories = {c["slug"]: c for c in CATALOGUE["categories"]}
    types = {t["slug"]: t for t in CATALOGUE["product_types"]}
    return [{"id": v["id"], "product_id": p["id"], "name": p["name"], "slug": p["slug"], "sku": v["sku"], "variant_name": v["name"],
             "price": v["price"], "category": categories[p["category"]], "product_type": types[p["product_type"]]}
            for p in CATALOGUE["products"] for v in p["variants"]]


SHIPPING_METHODS = [{"id": "1", "name": "Standard", "price": "5.00"}]
CHANNEL = {"id": "default-channel", "pk": "1", "name": "Default channel", "currency": CURRENCY,
           "tax": {"chargeTaxes": True, "pricesEnteredWithTax": False, "displayGrossPrices": False, "taxAppId": "seedco.taxes"}}
STAFF = [
    {"id": "admin@seedco.example", "password": "admin", "permissions": sorted(PERMISSIONS)},
    {"id": "support@seedco.example", "password": "support", "permissions": ["MANAGE_ORDERS"]},
]
CHARGE_RESULTS = ("CHARGE_SUCCESS", "CHARGE_FAILURE", "CHARGE_REQUEST", "CHARGE_ACTION_REQUIRED")
REFUND_RESULTS = ("REFUND_SUCCESS", "REFUND_FAILURE")


REFUND_REQUEST_ATTEMPTS = 3     # how often a refund request is sent to a payment app that does not answer


class ApiError(Exception):
    """A mutation that cannot be done. It becomes an entry in the mutation's `errors`."""

    def __init__(self, code: str, message: str, field: str = None):
        super().__init__(message)
        self.code, self.message, self.field = code, message, field


def q(value) -> Decimal:
    return Decimal(str(value)).quantize(CENT, ROUND_HALF_UP)


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def gid(kind: str, raw) -> str:
    """A global id, as Saleor writes them: base64 of `Type:key`."""
    return base64.b64encode("{}:{}".format(kind, raw).encode()).decode()


def raw_id(value: str, kind: str) -> str:
    try:
        found, _, raw = base64.b64decode(str(value).encode(), validate=True).decode().partition(":")
    except Exception:
        found, raw = None, None
    if found != kind or not raw:
        raise ApiError("NOT_FOUND", "Couldn't resolve to a node: {}".format(value), "id")
    return raw


def id_kind(value: str) -> str:
    try:
        return base64.b64decode(str(value).encode(), validate=True).decode().partition(":")[0]
    except Exception:
        return ""


def money(amount, currency: str = CURRENCY) -> dict:
    value = q(amount)
    return {"currency": currency, "amount": float(value), "fractionalAmount": int(value * 100), "fractionDigits": 2}


def taxed(net, gross) -> dict:
    return {"currency": CURRENCY, "net": money(net), "gross": money(gross), "tax": money(q(gross) - q(net))}


def metadata_view(metadata: dict) -> list:
    return [{"key": k, "value": v} for k, v in sorted(metadata.items())]


def address_view(address):
    if not address:
        return None
    code = address.get("country") or "US"
    return {"firstName": address.get("firstName") or "", "lastName": address.get("lastName") or "",
            "streetAddress1": address.get("streetAddress1") or "", "city": address.get("city") or "",
            "postalCode": address.get("postalCode") or "", "countryArea": address.get("countryArea") or "",
            "country": {"code": code, "country": COUNTRIES.get(code, code)}}


class Core:
    def __init__(self, store, apps):
        self.store, self.apps = store, apps
        for p in catalogue_rows():
            if not store.get("product", p["id"]):
                store.put("product", p, p["product_id"])   # looked up by product: a product is its variants' rows
        if not store.get("channel", CHANNEL["id"]):
            store.put("channel", CHANNEL)
        for s in STAFF:
            if not store.get("staff", s["id"]):
                store.put("staff", s)

    # ---- catalogue and channel ----

    def product_view(self, p: dict) -> dict:
        """The product a variant row belongs to, with all of its variants."""
        return {"id": gid("Product", p["product_id"]), "name": p["name"], "slug": p["slug"],
                "category": self.category_view(p["category"]), "productType": dict(p["product_type"], id=gid("ProductType", p["product_type"]["id"])),
                "variants": [self.variant_view(v) for v in self.store.all("product", p["product_id"])]}

    @staticmethod
    def category_view(c: dict) -> dict:
        parent = next((x for x in CATALOGUE["categories"] if x["slug"] == c["parent"]), None)
        return {"id": gid("Category", c["id"]), "name": c["name"], "slug": c["slug"],
                "parent": (lambda info: Core.category_view(parent)) if parent else None}

    def variant_view(self, p: dict) -> dict:
        return {"id": gid("ProductVariant", p["id"]), "sku": p["sku"], "name": p["variant_name"],
                "pricing": {"price": taxed(p["price"], p["price"])}, "product": lambda info: self.product_view(p)}

    def channel_view(self) -> dict:
        c = self.store.get("channel", CHANNEL["id"])
        return {"id": gid("Channel", c["pk"]), "slug": c["id"], "name": c["name"], "currencyCode": c["currency"],
                "taxConfiguration": c["tax"]}

    def products(self, first: int, after: str = None, filter: dict = None) -> dict:
        search = ((filter or {}).get("search") or "").lower()
        seen, firsts = set(), []
        for row in self.store.all("product"):       # one row per variant: keep the first of each product
            if row["product_id"] not in seen and search in row["name"].lower():
                seen.add(row["product_id"])
                firsts.append(row)
        return connection(firsts, first, after, lambda p: p["product_id"], self.product_view)

    def _product(self, variant_id: str) -> dict:
        p = self.store.get("product", raw_id(variant_id, "ProductVariant"))
        if p is None:
            raise ApiError("NOT_FOUND", "Couldn't resolve to a node: {}".format(variant_id), "variantId")
        return p

    @staticmethod
    def _method(method_id):
        return next((m for m in SHIPPING_METHODS if m["id"] == method_id), None)

    @staticmethod
    def method_view(m: dict) -> dict:
        return {"id": gid("ShippingMethod", m["id"]), "name": m["name"], "price": money(m["price"])}

    # ---- prices and taxes ----

    def _base(self, doc: dict):
        """Catalogue prices before tax: [(line, product, unit, total)] and the shipping price."""
        rows = []
        for line in doc["lines"]:
            p = self.store.get("product", line["variant_id"])
            unit = q(line["price"]) if line.get("price") is not None else q(p["price"])
            rows.append((line, p, unit, q(unit * line["quantity"])))
        method = self._method(doc.get("delivery_method_id"))
        return rows, q(method["price"]) if method else Decimal("0.00")

    def _recalculate(self, kind: str, doc: dict, source=None):
        """Asks the channel's tax app for the taxes on a checkout or a draft order and keeps the answer on it.

        `source` returns the view of the object being taxed (the event's `sourceObject`); a checkout is its own."""
        doc["taxes"], doc["tax_error"] = None, None
        rows, shipping = self._base(doc)
        if not doc.get("shipping_address") or not rows:
            return   # nothing to tax yet: prices are shown as entered
        tax = self.store.get("channel", CHANNEL["id"])["tax"]
        if not tax["chargeTaxes"] or not tax["taxAppId"]:
            return
        app = self.apps.find(tax["taxAppId"])
        event = "CHECKOUT_CALCULATE_TAXES" if kind == "checkout" else "ORDER_CALCULATE_TAXES"
        try:
            if app is None:
                raise WebhookError("the tax app {} is not installed".format(tax["taxAppId"]))
            source = source or (lambda: self.checkout_view(doc))
            answer = self.apps.sync(app, event, "CalculateTaxes", {"taxBase": {
                "sourceObject": lambda info: source(), "pricesEnteredWithTax": tax["pricesEnteredWithTax"],
                "currency": CURRENCY, "shippingPrice": money(shipping), "address": address_view(doc["shipping_address"]),
                "channel": self.channel_view(),
                "lines": [{"quantity": line["quantity"], "chargeTaxes": True, "productName": p["name"],
                           "variantName": p["variant_name"], "productSku": p["sku"], "unitPrice": money(unit),
                           "totalPrice": money(total)} for line, p, unit, total in rows]}})
            doc["taxes"] = self._read_taxes(answer, len(rows))
        except (WebhookError, ValueError, InvalidOperation, TypeError, KeyError) as exc:
            doc["tax_error"] = str(exc) or type(exc).__name__
            telemetry.count("seedco_tax_errors_total")
            telemetry.log("error", "taxes could not be calculated", reason=doc["tax_error"])

    @staticmethod
    def _read_taxes(answer: dict, expected_lines: int) -> dict:
        """Checks a tax app's answer. Amounts are decimals in major units; a tax rate is a percentage (8.75)."""
        def amount(value, name):
            number = Decimal(str(value))
            if number < 0:
                raise ValueError("{} must not be negative".format(name))
            return number

        lines = answer.get("lines")
        if not isinstance(lines, list) or len(lines) != expected_lines:
            raise ValueError("Number of lines from tax data doesn't match the line number. Expected {} but got {}.".format(
                expected_lines, len(lines) if isinstance(lines, list) else "none"))
        return {
            "lines": [{"net": str(q(amount(l["total_net_amount"], "total_net_amount"))),
                       "gross": str(q(amount(l["total_gross_amount"], "total_gross_amount"))),
                       "rate": str(amount(l["tax_rate"], "tax_rate") / 100)} for l in lines],
            "shipping": {"net": str(q(amount(answer["shipping_price_net_amount"], "shipping_price_net_amount"))),
                         "gross": str(q(amount(answer["shipping_price_gross_amount"], "shipping_price_gross_amount"))),
                         "rate": str(amount(answer["shipping_tax_rate"], "shipping_tax_rate") / 100)}}

    def _priced(self, doc: dict):
        """[(line, product, net, gross, rate)] and (shipping net, gross, rate), from the tax app's answer if there is one."""
        rows, shipping = self._base(doc)
        taxes = doc.get("taxes")
        if not taxes:
            return [(l, p, total, total, Decimal(0)) for l, p, _, total in rows], (shipping, shipping, Decimal(0))
        priced = [(l, p, Decimal(t["net"]), Decimal(t["gross"]), Decimal(t["rate"])) for (l, p, _, _), t in zip(rows, taxes["lines"])]
        s = taxes["shipping"]
        return priced, (Decimal(s["net"]), Decimal(s["gross"]), Decimal(s["rate"]))

    # ---- transactions ----

    def _transactions(self, kind: str, source_id: str) -> list:
        return self.store.all("transaction", "{}:{}".format(kind, source_id))

    def _charged(self, kind: str, source_id: str) -> Decimal:
        return sum((Decimal(t["charged"]) for t in self._transactions(kind, source_id)), Decimal(0))

    def transaction_view(self, t: dict) -> dict:
        def source(kind, view):
            def resolve(info):
                doc = self.store.get(kind, t["source_id"]) if t["source_kind"] == kind else None
                return view(doc) if doc else None
            return resolve
        return {"id": gid("TransactionItem", t["id"]), "createdAt": t["created"], "name": t["name"], "message": t["message"],
                "pspReference": t["psp_reference"], "actions": ["REFUND"] if Decimal(t["charged"]) > 0 else [],
                "chargedAmount": money(t["charged"]), "refundedAmount": money(t["refunded"]),
                "events": [self.event_view(e) for e in t["events"]],
                "order": source("order", self.order_view), "checkout": source("checkout", self.checkout_view)}

    @staticmethod
    def event_view(e: dict) -> dict:
        return {"id": gid("TransactionEvent", e["id"]), "createdAt": e["created"], "pspReference": e["psp_reference"],
                "message": e["message"], "amount": money(e["amount"]), "type": e["type"]}

    @staticmethod
    def _add_event(t: dict, kind: str, amount, message: str = "", psp_reference: str = "") -> dict:
        event = {"id": str(uuid.uuid4()), "type": kind, "amount": str(q(amount)), "message": (message or "")[:512],
                 "psp_reference": psp_reference or "", "created": now()}
        t["events"].append(event)
        return event

    def _save_transaction(self, t: dict):
        self.store.put("transaction", t, "{}:{}".format(t["source_kind"], t["source_id"]))

    # ---- checkout ----

    def _checkout(self, checkout_id: str) -> dict:
        doc = self.store.get("checkout", raw_id(checkout_id, "Checkout"))
        if doc is None:
            raise ApiError("NOT_FOUND", "Couldn't resolve to a node: {}".format(checkout_id), "id")
        return doc

    def checkout_view(self, doc: dict) -> dict:
        priced, (ship_net, ship_gross, _) = self._priced(doc)
        net = sum((n for _, _, n, _, _ in priced), Decimal(0))
        gross = sum((g for _, _, _, g, _ in priced), Decimal(0))
        charged = self._charged("checkout", doc["id"])
        total = gross + ship_gross
        status = "NONE" if charged <= 0 else "PARTIAL" if charged < total else "FULL" if charged == total else "OVERCHARGED"
        method = self._method(doc.get("delivery_method_id"))
        return {
            "__typename": "Checkout", "id": gid("Checkout", doc["id"]), "email": doc.get("email"), "channel": self.channel_view(),
            "lines": [{"id": gid("CheckoutLine", l["id"]), "variant": self.variant_view(p), "quantity": l["quantity"],
                       "unitPrice": taxed(n / l["quantity"], g / l["quantity"]), "totalPrice": taxed(n, g)}
                      for l, p, n, g, _ in priced],
            "shippingAddress": address_view(doc.get("shipping_address")),
            "shippingMethods": [self.method_view(m) for m in SHIPPING_METHODS] if doc.get("shipping_address") else [],
            "deliveryMethod": self.method_view(method) if method else None,
            "subtotalPrice": taxed(net, gross), "shippingPrice": taxed(ship_net, ship_gross),
            "totalPrice": taxed(net + ship_net, total), "chargeStatus": status,
            "displayGrossPrices": self.store.get("channel", CHANNEL["id"])["tax"]["displayGrossPrices"],
            "transactions": [self.transaction_view(t) for t in self._transactions("checkout", doc["id"])],
            "availablePaymentGateways": [{"id": a["identifier"], "name": a["name"]} for a in self.apps.all()
                                         if self.apps.webhook(a, "TRANSACTION_INITIALIZE_SESSION", sync=True)],
            "metadata": metadata_view(doc.get("metadata", {}))}

    def _save_checkout(self, doc: dict, recalculate: bool = True) -> dict:
        if recalculate:
            self._recalculate("checkout", doc)
        self.store.put("checkout", doc)
        return {"checkout": self.checkout_view(doc)}

    def _set_lines(self, doc: dict, lines: list, add: bool):
        for item in lines or []:
            if item["quantity"] < 0 or (add and item["quantity"] < 1):
                raise ApiError("ZERO_QUANTITY" if add else "INVALID", "The quantity should be higher than zero.", "quantity")
            p = self._product(item["variantId"])
            line = next((l for l in doc["lines"] if l["variant_id"] == p["id"]), None)
            if line is None:
                line = {"id": str(uuid.uuid4()), "variant_id": p["id"], "quantity": 0}
                doc["lines"].append(line)
            line["quantity"] = line["quantity"] + item["quantity"] if add else item["quantity"]
        doc["lines"] = [l for l in doc["lines"] if l["quantity"] > 0]

    def checkout_create(self, input: dict) -> dict:
        if input.get("channel") not in (None, CHANNEL["id"]):
            raise ApiError("NOT_FOUND", "Channel with '{}' slug does not exist.".format(input["channel"]), "channel")
        doc = {"id": str(uuid.uuid4()), "email": input.get("email"), "lines": [], "shipping_address": input.get("shippingAddress"),
               "delivery_method_id": None, "taxes": None, "tax_error": None, "created": now(),
               "metadata": {m["key"]: m["value"] for m in input.get("metadata") or []}}
        self._set_lines(doc, input.get("lines"), add=True)
        return self._save_checkout(doc)

    def checkout_lines_add(self, id: str, lines: list) -> dict:
        doc = self._checkout(id)
        self._set_lines(doc, lines, add=True)
        return self._save_checkout(doc)

    def checkout_lines_update(self, id: str, lines: list) -> dict:
        doc = self._checkout(id)
        self._set_lines(doc, lines, add=False)
        return self._save_checkout(doc)

    def checkout_email_update(self, id: str, email: str) -> dict:
        doc = self._checkout(id)
        if "@" not in email:
            raise ApiError("INVALID", "Enter a valid email address.", "email")
        doc["email"] = email
        return self._save_checkout(doc, recalculate=False)

    def checkout_shipping_address_update(self, id: str, shippingAddress: dict) -> dict:
        doc = self._checkout(id)
        if not (shippingAddress.get("postalCode") or "").strip():
            raise ApiError("REQUIRED", "This field is required.", "postalCode")
        doc["shipping_address"] = shippingAddress
        return self._save_checkout(doc)

    def checkout_delivery_method_update(self, id: str, deliveryMethodId: str = None) -> dict:
        doc = self._checkout(id)
        method = self._method(raw_id(deliveryMethodId, "ShippingMethod")) if deliveryMethodId else None
        if deliveryMethodId and (method is None or not doc.get("shipping_address")):
            raise ApiError("DELIVERY_METHOD_NOT_APPLICABLE", "This shipping method is not applicable.", "deliveryMethodId")
        doc["delivery_method_id"] = method["id"] if method else None
        return self._save_checkout(doc)

    def checkout_complete(self, id: str) -> dict:
        doc = self._checkout(id)
        if not doc["lines"]:
            raise ApiError("NO_LINES", "Cannot complete checkout without lines.", "lines")
        if not doc.get("email"):
            raise ApiError("EMAIL_NOT_SET", "Checkout email must be set.", "email")
        if not doc.get("shipping_address"):
            raise ApiError("SHIPPING_ADDRESS_NOT_SET", "Shipping address is not set.", "shippingAddress")
        if not doc.get("delivery_method_id"):
            raise ApiError("SHIPPING_METHOD_NOT_SET", "Shipping method is not set.", "shippingMethod")
        self._recalculate("checkout", doc)
        if doc["tax_error"]:
            raise ApiError("TAX_ERROR", "Configured Tax App returned invalid response.")
        if self.checkout_view(doc)["chargeStatus"] not in ("FULL", "OVERCHARGED"):
            raise ApiError("CHECKOUT_NOT_FULLY_PAID", "The authorized amount doesn't cover the checkout's total amount.")
        order = self._new_order(doc, "CHECKOUT", "UNFULFILLED")
        order["checkout_id"] = doc["id"]
        self.store.put("order", order, order["user_email"])
        for t in self._transactions("checkout", doc["id"]):
            t["source_kind"], t["source_id"] = "order", order["id"]
            self._save_transaction(t)
        self.store.delete("checkout", doc["id"])
        telemetry.count("seedco_orders_created_total", origin="CHECKOUT")
        self._emit("ORDER_CREATED", "OrderCreated", order)
        self._emit("ORDER_FULLY_PAID", "OrderFullyPaid", order)
        return {"order": self.order_view(order)}

    # ---- orders ----

    def _new_order(self, source: dict, origin: str, status: str) -> dict:
        order = {"id": str(uuid.uuid4()), "number": self.store.next("order_number"), "status": status, "origin": origin,
                 "user_email": source.get("email"), "shipping_address": source.get("shipping_address"), "created": now(),
                 "updated": now(), "metadata": dict(source.get("metadata", {})), "checkout_id": None, "fulfillments": [],
                 "display_gross_prices": self.store.get("channel", CHANNEL["id"])["tax"]["displayGrossPrices"]}
        self._freeze(order, source)
        return order

    def _freeze(self, order: dict, source: dict):
        """Copies the priced lines and shipping of a checkout (or a draft) onto the order, where they no longer change."""
        priced, (ship_net, ship_gross, ship_rate) = self._priced(source)
        kept = {l["variant_id"]: l for l in order.get("lines", [])}
        order["lines"] = [{
            "id": kept.get(p["id"], {}).get("id") or str(uuid.uuid4()), "variant_id": p["id"], "product_name": p["name"],
            "variant_name": p["variant_name"], "sku": p["sku"], "quantity": l["quantity"], "quantity_fulfilled": 0,
            "unit_net": str(q(n / l["quantity"])), "unit_gross": str(q(g / l["quantity"])), "total_net": str(n),
            "total_gross": str(g), "tax_rate": str(rate)} for l, p, n, g, rate in priced]
        method = self._method(source.get("delivery_method_id"))
        order["shipping"] = {"method_id": method["id"] if method else None, "name": method["name"] if method else "",
                             "net": str(ship_net), "gross": str(ship_gross), "rate": str(ship_rate)}

    def _order(self, order_id: str) -> dict:
        doc = self.store.get("order", raw_id(order_id, "Order"))
        if doc is None:
            raise ApiError("NOT_FOUND", "Couldn't resolve to a node: {}".format(order_id), "id")
        return doc

    def order_view(self, doc: dict) -> dict:
        net = sum((Decimal(l["total_net"]) for l in doc["lines"]), Decimal(0))
        gross = sum((Decimal(l["total_gross"]) for l in doc["lines"]), Decimal(0))
        ship_net, ship_gross = Decimal(doc["shipping"]["net"]), Decimal(doc["shipping"]["gross"])
        total = gross + ship_gross
        transactions = self._transactions("order", doc["id"])
        charged = sum((Decimal(t["charged"]) for t in transactions), Decimal(0))
        refunded = sum((Decimal(t["refunded"]) for t in transactions), Decimal(0))
        status = "NONE" if charged <= 0 else "PARTIAL" if charged < total else "FULL" if charged == total else "OVERCHARGED"
        lines = {l["id"]: {"id": gid("OrderLine", l["id"]), "productName": l["product_name"], "variantName": l["variant_name"],
                           "productSku": l["sku"], "quantity": l["quantity"], "quantityFulfilled": l["quantity_fulfilled"],
                           "taxRate": float(Decimal(l["tax_rate"])), "unitPrice": taxed(l["unit_net"], l["unit_gross"]),
                           "totalPrice": taxed(l["total_net"], l["total_gross"])} for l in doc["lines"]}
        return {
            "__typename": "Order", "id": gid("Order", doc["id"]), "number": str(doc["number"]), "created": doc["created"],
            "updatedAt": doc["updated"], "status": doc["status"], "origin": doc["origin"], "channel": self.channel_view(),
            "userEmail": doc.get("user_email"), "shippingAddress": address_view(doc.get("shipping_address")),
            "lines": list(lines.values()), "subtotal": taxed(net, gross), "shippingPrice": taxed(ship_net, ship_gross),
            "total": taxed(net + ship_net, total), "isPaid": total > 0 and charged >= total, "chargeStatus": status,
            "displayGrossPrices": doc.get("display_gross_prices", False),
            "totalCharged": money(charged), "totalRefunded": money(refunded), "totalBalance": money(charged - total),
            "transactions": [self.transaction_view(t) for t in transactions],
            "fulfillments": [{"id": gid("Fulfillment", f["id"]), "created": f["created"],
                              "lines": [{"quantity": fl["quantity"], "orderLine": lines.get(fl["line_id"])} for fl in f["lines"]]}
                             for f in doc["fulfillments"]],
            "metadata": metadata_view(doc.get("metadata", {})),
            "checkoutId": gid("Checkout", doc["checkout_id"]) if doc.get("checkout_id") else None}

    def _save_order(self, doc: dict) -> dict:
        doc["updated"] = now()
        self.store.put("order", doc, doc.get("user_email"))
        return {"order": self.order_view(doc)}

    def _emit(self, event_type: str, typename: str, order: dict):
        self.apps.emit(event_type, typename, {"order": self.order_view(order)})

    def orders(self, first: int, after: str = None, filter: dict = None) -> dict:
        """Orders, newest first."""
        filter = filter or {}
        wanted = {m["key"]: m["value"] for m in filter.get("metadata") or []}
        found = [o for o in reversed(self.store.all("order"))
                 if (not filter.get("customer") or filter["customer"].lower() in (o.get("user_email") or "").lower())
                 and (not filter.get("status") or o["status"] in filter["status"])
                 and all(o.get("metadata", {}).get(k) == v for k, v in wanted.items())]
        return connection(found, first, after, lambda o: o["number"], self.order_view)

    def order_cancel(self, id: str) -> dict:
        doc = self._order(id)
        if doc["status"] == "CANCELED":
            raise ApiError("CANNOT_CANCEL_ORDER", "This order can't be canceled.", "order")
        if doc["status"] == "DRAFT" or any(l["quantity_fulfilled"] for l in doc["lines"]):
            raise ApiError("CANNOT_CANCEL_ORDER", "This order can't be canceled.", "order")
        doc["status"] = "CANCELED"
        result = self._save_order(doc)
        self._emit("ORDER_CANCELLED", "OrderCancelled", doc)
        return result

    def order_fulfill(self, order: str, input: dict) -> dict:
        doc = self._order(order)
        if doc["status"] in ("DRAFT", "CANCELED", "FULFILLED"):
            raise ApiError("CANNOT_FULFILL", "An order in status {} cannot be fulfilled.".format(doc["status"]), "order")
        fulfilled = []
        for item in input["lines"]:
            line = next((l for l in doc["lines"] if l["id"] == raw_id(item["orderLineId"], "OrderLine")), None)
            if line is None:
                raise ApiError("NOT_FOUND", "Couldn't resolve to a node: {}".format(item["orderLineId"]), "orderLineId")
            if item["quantity"] < 1 or item["quantity"] > line["quantity"] - line["quantity_fulfilled"]:
                raise ApiError("FULFILL_ORDER_LINE", "Only {} items remaining to fulfill.".format(
                    line["quantity"] - line["quantity_fulfilled"]), "orderLineId")
            line["quantity_fulfilled"] += item["quantity"]
            fulfilled.append({"line_id": line["id"], "quantity": item["quantity"]})
        doc["fulfillments"].append({"id": str(uuid.uuid4()), "created": now(), "lines": fulfilled})
        complete = all(l["quantity_fulfilled"] == l["quantity"] for l in doc["lines"])
        doc["status"] = "FULFILLED" if complete else "PARTIALLY_FULFILLED"
        result = self._save_order(doc)
        if complete:
            self._emit("ORDER_FULFILLED", "OrderFulfilled", doc)
        return dict(result, fulfillments=result["order"]["fulfillments"])

    def draft_order_create(self, input: dict) -> dict:
        draft = {"email": input.get("userEmail"), "shipping_address": input.get("shippingAddress"), "lines": [],
                 "delivery_method_id": raw_id(input["shippingMethod"], "ShippingMethod") if input.get("shippingMethod") else None}
        for item in input.get("lines") or []:
            if item["quantity"] < 1:
                raise ApiError("ZERO_QUANTITY", "Ensure this value is greater than or equal to 1.", "quantity")
            line = {"id": str(uuid.uuid4()), "variant_id": self._product(item["variantId"])["id"], "quantity": item["quantity"]}
            if item.get("price") is not None:
                line["price"] = str(q(item["price"]))
            draft["lines"].append(line)
        if draft["delivery_method_id"] and not self._method(draft["delivery_method_id"]):
            raise ApiError("SHIPPING_METHOD_NOT_APPLICABLE", "Shipping method cannot be used with this order.", "shippingMethod")
        order = self._new_order(draft, "DRAFT", "DRAFT")
        order["draft"] = draft
        self._save_order(order)
        self._recalculate("order", draft, lambda: self.order_view(order))
        self._freeze(order, draft)
        return self._save_order(order)

    def draft_order_complete(self, id: str) -> dict:
        doc = self._order(id)
        if doc["status"] != "DRAFT":
            raise ApiError("INVALID", "Only draft orders can be completed.", "id")
        draft = doc["draft"]
        if not draft["lines"]:
            raise ApiError("REQUIRED", "Could not create order without any products.", "lines")
        if not draft.get("email"):
            raise ApiError("REQUIRED", "Can't finalize draft with no email.", "userEmail")
        self._recalculate("order", draft, lambda: self.order_view(doc))
        if draft["tax_error"]:
            raise ApiError("TAX_ERROR", "Configured Tax App returned invalid response.")
        self._freeze(doc, draft)
        doc["status"] = "UNFULFILLED"
        result = self._save_order(doc)
        telemetry.count("seedco_orders_created_total", origin="DRAFT")
        self._emit("ORDER_CREATED", "OrderCreated", doc)
        return result

    def update_metadata(self, id: str, input: list) -> dict:
        doc = self._order(id)
        doc.setdefault("metadata", {}).update({m["key"]: m["value"] for m in input})
        self._save_order(doc)
        return {}

    # ---- payments ----

    def transaction_initialize(self, id: str, paymentGateway: dict, amount=None, action: str = None, idempotencyKey: str = None) -> dict:
        kind = "checkout" if id_kind(id) == "Checkout" else "order"
        doc = self._checkout(id) if kind == "checkout" else self._order(id)
        view = self.checkout_view(doc) if kind == "checkout" else self.order_view(doc)
        if kind == "order" and doc["status"] in ("DRAFT", "CANCELED"):
            raise ApiError("INVALID", "An order in status {} cannot be paid.".format(doc["status"]), "id")
        if idempotencyKey:
            earlier = next((t for t in self._transactions(kind, doc["id"]) if t.get("idempotency_key") == idempotencyKey), None)
            if earlier:
                return {"transaction": self.transaction_view(earlier), "transactionEvent": self.event_view(earlier["events"][-1]),
                        "data": earlier.get("data")}
        app = self.apps.find(paymentGateway["id"])
        if app is None or not self.apps.webhook(app, "TRANSACTION_INITIALIZE_SESSION", sync=True):
            raise ApiError("NOT_FOUND", "Payment gateway {} is not available.".format(paymentGateway["id"]), "paymentGateway")
        total = Decimal(str((view["totalPrice"] if kind == "checkout" else view["total"])["gross"]["amount"]))
        wanted = q(amount) if amount is not None else q(total - self._charged(kind, doc["id"]))
        if wanted <= 0:
            raise ApiError("INVALID", "There is nothing left to pay.", "amount")
        t = {"id": str(uuid.uuid4()), "source_kind": kind, "source_id": doc["id"], "app": app["identifier"], "name": app["name"],
             "message": "", "psp_reference": "", "charged": "0.00", "refunded": "0.00", "created": now(), "events": [],
             "idempotency_key": idempotencyKey or str(uuid.uuid4()), "data": None}
        self._add_event(t, "CHARGE_REQUEST", wanted)
        self._save_transaction(t)
        try:
            answer = self.apps.sync(app, "TRANSACTION_INITIALIZE_SESSION", "TransactionInitializeSession", {
                "transaction": self.transaction_view(t), "sourceObject": view, "data": paymentGateway.get("data"),
                "merchantReference": view["id"], "idempotencyKey": t["idempotency_key"],
                "action": {"amount": float(wanted), "currency": CURRENCY, "actionType": action or "CHARGE"}})
            result, psp = answer.get("result"), answer.get("pspReference") or ""
            if result not in CHARGE_RESULTS:
                raise ValueError("unknown result {!r}".format(result))
            if result == "CHARGE_SUCCESS" and not psp:
                raise ValueError("pspReference is required for CHARGE_SUCCESS")
            got = q(answer["amount"]) if answer.get("amount") is not None else wanted
            event = self._add_event(t, result, got, answer.get("message") or "", psp)
            t["psp_reference"], t["message"], t["data"] = psp, answer.get("message") or "", answer.get("data")
            if result == "CHARGE_SUCCESS":
                t["charged"] = str(q(Decimal(t["charged"]) + got))
        except (WebhookError, ValueError, InvalidOperation, TypeError) as exc:
            event = self._add_event(t, "CHARGE_FAILURE", wanted, "The payment app did not give a usable answer: {}".format(exc))
        self._save_transaction(t)
        telemetry.count("seedco_transaction_events_total", type=event["type"], saleor_app_identifier=app["identifier"])
        if kind == "order" and event["type"] == "CHARGE_SUCCESS" and self.order_view(doc)["isPaid"]:
            self._emit("ORDER_FULLY_PAID", "OrderFullyPaid", doc)
        return {"transaction": self.transaction_view(t), "transactionEvent": self.event_view(event), "data": t["data"]}

    def transaction_request_action(self, id: str, actionType: str, amount=None) -> dict:
        t = self.store.get("transaction", raw_id(id, "TransactionItem"))
        if t is None:
            raise ApiError("NOT_FOUND", "Couldn't resolve to a node: {}".format(id), "id")
        if actionType != "REFUND":
            raise ApiError("INVALID", "Only REFUND can be requested for a charged transaction.", "actionType")
        charged = Decimal(t["charged"])
        wanted = q(amount) if amount is not None else charged
        if wanted <= 0 or wanted > charged:
            raise ApiError("INVALID", "The refund must be more than zero and no more than the charged amount.", "amount")
        app = self.apps.find(t["app"])
        if app is None or not self.apps.webhook(app, "TRANSACTION_REFUND_REQUESTED", sync=True):
            raise ApiError("MISSING_TRANSACTION_ACTION_REQUEST_WEBHOOK", "No app or plugin is configured to handle payment action requests.")
        self._add_event(t, "REFUND_REQUEST", wanted)
        try:
            answer, attempt = None, 0
            while answer is None:       # the payment app may be restarting: ask again before giving up
                attempt += 1
                try:
                    answer = self.apps.sync(app, "TRANSACTION_REFUND_REQUESTED", "TransactionRefundRequested", {
                        "transaction": self.transaction_view(t), "idempotencyKey": str(uuid.uuid4()),
                        "action": {"actionType": "REFUND", "amount": float(wanted), "currency": CURRENCY}})
                except WebhookError as exc:
                    if attempt >= REFUND_REQUEST_ATTEMPTS:
                        raise
                    telemetry.log("warning", "refund request sent again", attempt=attempt, reason=str(exc),
                                  **{"saleor.app.identifier": t["app"]})
                    time.sleep(0.2 * attempt)
            result = answer.get("result")
            if result not in REFUND_RESULTS:
                raise ValueError("unknown result {!r}".format(result))
            got = q(answer["amount"]) if answer.get("amount") is not None else wanted
            event = self._add_event(t, result, got, answer.get("message") or "", answer.get("pspReference") or "")
            if result == "REFUND_SUCCESS":
                t["charged"], t["refunded"] = str(q(charged - got)), str(q(Decimal(t["refunded"]) + got))
        except (WebhookError, ValueError, InvalidOperation, TypeError) as exc:
            event = self._add_event(t, "REFUND_FAILURE", wanted, "The payment app did not give a usable answer: {}".format(exc))
        self._save_transaction(t)
        telemetry.count("seedco_transaction_events_total", type=event["type"], saleor_app_identifier=t["app"])
        if event["type"] == "REFUND_SUCCESS" and t["source_kind"] == "order":
            order = self.store.get("order", t["source_id"])
            self._emit("ORDER_REFUNDED", "OrderRefunded", order)
            if self._charged("order", order["id"]) <= 0:
                self._emit("ORDER_FULLY_REFUNDED", "OrderFullyRefunded", order)
        return {"transaction": self.transaction_view(t)}

    # ---- staff ----

    def token_create(self, email: str, password: str) -> dict:
        staff = self.store.get("staff", email)
        if staff is None or staff["password"] != password:
            raise ApiError("INVALID_CREDENTIALS", "Please, enter valid credentials", "email")
        staff["token"] = staff.get("token") or uuid.uuid4().hex
        self.store.put("staff", staff)
        return {"token": staff["token"], "user": {"email": email, "isStaff": True, "userPermissions": permissions_view(staff["permissions"])}}

    def staff_by_token(self, token: str):
        return next((s for s in self.store.all("staff") if s.get("token") == token), None)

    def app_view(self, a: dict) -> dict:
        def events(names):
            return [{"eventType": n, "name": n.replace("_", " ").capitalize()} for n in names]
        return {"id": gid("App", a["id"]), "identifier": a["identifier"], "name": a["name"], "version": a["version"],
                "isActive": a["isActive"], "permissions": permissions_view(a["permissions"]),
                "webhooks": [{"id": gid("Webhook", w["id"]), "name": w["name"], "targetUrl": w["targetUrl"], "isActive": w["isActive"],
                              "syncEvents": events(w["syncEvents"]), "asyncEvents": events(w["asyncEvents"]),
                              "subscriptionQuery": w["query"]} for w in a["webhooks"]]}


def permissions_view(codes: list) -> list:
    return [{"code": c, "name": PERMISSIONS[c]} for c in codes]


def connection(items: list, first: int, after: str, key, view) -> dict:
    """A Relay connection over a list. The cursor of an item is its key, base64-encoded."""
    cursor = lambda item: base64.b64encode(str(key(item)).encode()).decode()  # noqa: E731
    start = 0
    if after:
        start = next((i + 1 for i, item in enumerate(items) if cursor(item) == after), len(items))
    size = max(1, min(first or 20, 100))
    page = items[start:start + size]
    return {"edges": [{"node": view(item), "cursor": cursor(item)} for item in page], "totalCount": len(items),
            "pageInfo": {"hasNextPage": start + size < len(items), "endCursor": cursor(page[-1]) if page else None}}

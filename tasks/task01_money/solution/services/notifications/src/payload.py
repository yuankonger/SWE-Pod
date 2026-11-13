"""Payload schemas: what each email workflow needs from the event it is triggered by.

A workflow declares the shape of the object it reads. An event that does not fit is rejected before any template
runs, so a customer never gets a half-rendered email. The checker covers the small part of JSON Schema we use:
type, required, properties, additionalProperties: False, items and enum.
"""

TYPES = {"string": str, "integer": int, "number": (int, float), "object": dict, "array": list, "boolean": bool,
         "null": type(None)}


class PayloadError(ValueError):
    """The event does not fit the workflow's payload schema."""


def check(value, schema: dict, path: str = "$"):
    kinds = schema.get("type")
    if kinds:
        kinds = [kinds] if isinstance(kinds, str) else kinds
        ok = any(isinstance(value, TYPES[k]) and not (isinstance(value, bool) and k in ("integer", "number"))
                 for k in kinds)
        if not ok:
            raise PayloadError("{} must be {}, got {}".format(path, " or ".join(kinds), type(value).__name__))
    if "enum" in schema and value not in schema["enum"]:
        raise PayloadError("{} must be one of {}, got {!r}".format(path, schema["enum"], value))
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise PayloadError("{}.{} is required".format(path, key))
        props = schema.get("properties", {})
        for key, item in value.items():
            if key in props:
                check(item, props[key], "{}.{}".format(path, key))
            elif schema.get("additionalProperties") is False:
                raise PayloadError("{}.{} is not a field this workflow knows".format(path, key))
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            check(item, schema["items"], "{}[{}]".format(path, i))


def obj(required: list, strict: bool = False, **properties) -> dict:
    schema = {"type": "object", "required": required, "properties": properties}
    if strict:
        schema["additionalProperties"] = False
    return schema


STR, INT, NUM = {"type": "string"}, {"type": "integer"}, {"type": "number"}
MONEY = obj(["currency", "minor"], currency={"enum": ["USD"]}, minor=INT)  # a Money object: integer minor units

ORDER = obj(["order_id", "customer_id", "email", "lines", "total"],
            order_id=STR, customer_id=STR, email=STR, total=MONEY,
            lines={"type": "array", "items": obj(["name", "qty"], name=STR, qty=INT)})

# Receipts are strict: a receipt must account for everything on the invoice, so an invoice with a field or a
# line type this workflow has never seen is rejected instead of being rendered without it.
INVOICE_LINE = obj(["type", "name", "qty", "amount"], strict=True,
                   type={"enum": ["RECURRING", "FIXED", "PRORATION", "CREDIT"]},
                   sku=STR, name=STR, qty=INT, unit_price=MONEY, amount=MONEY)
INVOICE = obj(["invoice_id", "order_id", "customer_id", "email", "lines", "subtotal", "tax", "total"], strict=True,
              invoice_id=STR, order_id=STR, subscription_id={"type": ["string", "null"]}, customer_id=STR, email=STR,
              reason={"enum": ["order", "renewal", "plan_change"]}, lines={"type": "array", "items": INVOICE_LINE},
              subtotal=MONEY, tax=MONEY, total=MONEY, status=STR, issued_at=STR)

PAYMENT = obj(["payment_id", "customer_id", "email", "amount", "failure_reason"],
              payment_id=STR, customer_id=STR, email=STR, amount=MONEY, failure_reason=STR)

SUBSCRIPTION = obj(["subscription_id", "customer_id", "email", "name", "status", "current_period_end"],
                   subscription_id=STR, customer_id=STR, email=STR, name=STR, status=STR, current_period_end=STR,
                   pending_name={"type": ["string", "null"]})

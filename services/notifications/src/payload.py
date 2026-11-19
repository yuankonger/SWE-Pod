"""Payload schemas: what each email workflow needs from the event it is triggered by.

A workflow declares the shape of the object it reads. An event that does not fit is rejected before any template
runs, so a customer never gets a half-rendered email. The checker covers the small part of JSON Schema we use:
type, required, properties, items and enum.
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
        for key, item in value.items():
            if key in schema.get("properties", {}):
                check(item, schema["properties"][key], "{}.{}".format(path, key))
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            check(item, schema["items"], "{}[{}]".format(path, i))


def obj(required: list, **properties) -> dict:
    return {"type": "object", "required": required, "properties": properties}


STR, INT, NUM, BOOL = {"type": "string"}, {"type": "integer"}, {"type": "number"}, {"type": "boolean"}
AMOUNT = obj(["amount"], amount=NUM)                       # Core's Money: a decimal number in major units
TAXED = obj(["gross"], gross=AMOUNT, net=AMOUNT, tax=AMOUNT)

# The order as graphql/order-events.graphql asks for it.
ORDER = obj(["id", "number", "userEmail", "lines", "subtotal", "shippingPrice", "total"],
            id=STR, number=STR, userEmail=STR, displayGrossPrices=BOOL,
            lines={"type": "array", "items": obj(["productName", "quantity", "totalPrice"], productName=STR, variantName=STR, quantity=INT,
                                                 totalPrice=obj(["net", "gross"], net=AMOUNT, gross=AMOUNT))},
            subtotal=obj(["net", "gross"], net=AMOUNT, gross=AMOUNT), shippingPrice=TAXED,
            total=obj(["gross", "tax"], gross=AMOUNT, tax=AMOUNT), totalRefunded=AMOUNT)

# Messages other services ask us to send (POST /api/notify), in the shape of Saleor's NOTIFY_USER.
NOTIFY = obj(["notify_event", "payload"], notify_event=STR,
             payload=obj(["notification_id", "recipient_email"], notification_id=STR, recipient_email=STR,
                         plan_name=STR, pending_plan_name=STR, period_end=STR, amount=AMOUNT, reason=STR))

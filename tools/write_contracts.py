"""Writes every contract file and pinned copy, for the base company and for the task 1 reference solution.

The two differ only in how money is written: a plain number (base) or a Money object (solution).
Usage: python3 tools/write_contracts.py .
"""
import json
import os
import sys

REPO = sys.argv[1]
S, I, B = {"type": "string"}, {"type": "integer"}, {"type": "boolean"}
NS = {"type": ["string", "null"]}
DT = {"type": "string", "format": "date-time"}


def obj(required, **props):
    return {"type": "object", "required": required, "properties": props}


def events(M):
    order = obj(["order_id", "customer_id", "email", "postal_code", "status", "lines", "subtotal", "tax", "total"],
                order_id=S, customer_id=S, email=S, postal_code=I,
                status={"type": "string", "enum": ["placed", "paid", "payment_failed", "shipped", "delivered", "cancelled"]},
                lines={"type": "array", "items": obj(["sku", "name", "qty", "unit_price"], sku=S, name=S, qty=I, unit_price=M)},
                subtotal=M, tax=M, total=M, payment_id=S, payment_method=S, created_at=S, updated_at=S, shipped_at=S)
    invoice = obj(["invoice_id", "order_id", "customer_id", "email", "reason", "lines", "subtotal", "tax", "total", "status", "issued_at"],
                  invoice_id=S, order_id=S, subscription_id=NS, customer_id=S, email=S,
                  reason={"type": "string", "enum": ["order", "renewal", "plan_change"]},
                  lines={"type": "array", "items": obj(["type", "sku", "name", "qty", "unit_price", "amount"],
                                                       type={"type": "string", "enum": ["RECURRING", "FIXED", "PRORATION", "CREDIT"]},
                                                       sku=S, name=S, qty=I, unit_price=M, amount=M)},
                  subtotal=M, tax=M, total=M, status={"type": "string", "enum": ["paid", "refunded"]}, issued_at=S)
    payment = obj(["payment_id", "order_id", "customer_id", "amount", "status", "failure_reason"],
                  payment_id=S, order_id=S, customer_id=S, amount=M, status={"type": "string", "enum": ["failed"]},
                  email=NS, payment_method=S, failure_reason=S, subscription_id=NS)
    subscription = obj(["subscription_id", "order_id", "customer_id", "email", "sku", "name", "qty", "unit_price", "status",
                        "current_period_start", "current_period_end"],
                       subscription_id=S, order_id=S, customer_id=S, email=S, postal_code=I, sku=S, name=S, qty=I, unit_price=M,
                       status={"type": "string", "enum": ["active", "past_due", "canceled", "terminated"]},
                       current_period_start={"type": "string", "format": "date"},
                       current_period_end={"type": "string", "format": "date"},
                       payment_method=S, pending_sku=NS, pending_name=NS, cancel_at_period_end=B, failed_attempts=I,
                       next_attempt=NS)

    def envelope(name, data):
        return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": name, "type": "object",
                "required": ["event_id", "event_type", "occurred_at", "data"],
                "properties": {"event_id": S, "event_type": {"const": name}, "occurred_at": DT, "data": data}}

    return {
        "orders": {n: envelope(n, obj(["order"], order=order)) for n in ("order.placed", "order.cancelled", "order.shipped")},
        "billing": {
            "invoice.paid": envelope("invoice.paid", obj(["invoice"], invoice=invoice)),
            "payment.failed": envelope("payment.failed", obj(["payment"], payment=payment)),
            "subscription.updated": envelope("subscription.updated", obj(
                ["subscription", "change"], subscription=subscription,
                change={"type": "string", "enum": ["plan_changed", "downgrade_scheduled", "cancel_scheduled", "renewed", "terminated"]})),
        },
    }


BILLING = """# Billing API. Owner: Billing. Readers keep a pinned copy; ask Billing before relying on anything not written here.
openapi: 3.0.3
info: {title: Billing API, version: 2.0.0}
paths:
  /quotes:
    post:
      summary: Price a set of lines, with tax.
      requestBody:
        required: true
        content: {application/json: {schema: {$ref: '#/components/schemas/QuoteRequest'}}}
      responses:
        '200': {description: The quote, content: {application/json: {schema: {$ref: '#/components/schemas/Quote'}}}}
        '400': {description: Invalid request}
  /charges:
    post:
      summary: Take a payment for an order. A declined card is a 200 with status failed, and a payment.failed event.
      parameters:
        - {name: Idempotency-Key, in: header, schema: {type: string}, description: 'A repeat with the same key and the same order, customer and amount returns the first payment. The same key with different values is a 409.'}
      requestBody:
        required: true
        content: {application/json: {schema: {$ref: '#/components/schemas/ChargeRequest'}}}
      responses:
        '200': {description: The payment, content: {application/json: {schema: {$ref: '#/components/schemas/Payment'}}}}
        '400': {description: Invalid request}
        '409': {description: The Idempotency-Key was used for a different charge}
  /payments:
    get:
      summary: Payments, oldest first.
      parameters: [{name: order_id, in: query, schema: {type: string}}]
      responses:
        '200': {description: Payments, content: {application/json: {schema: {type: object, properties: {payments: {type: array, items: {$ref: '#/components/schemas/Payment'}}}}}}}
  /refunds:
    get:
      summary: Refunds, oldest first. A refund is issued when Billing reads the order.cancelled event.
      parameters: [{name: order_id, in: query, schema: {type: string}}]
      responses:
        '200': {description: Refunds, content: {application/json: {schema: {type: object, properties: {refunds: {type: array, items: {$ref: '#/components/schemas/Refund'}}}}}}}
  /invoices:
    get:
      summary: Invoices, oldest first. An order's invoice is issued when Billing reads the order.placed event; renewals and plan changes add more invoices to the same order.
      parameters: [{name: order_id, in: query, schema: {type: string}}, {name: customer_id, in: query, schema: {type: string}}]
      responses:
        '200': {description: Invoices, content: {application/json: {schema: {type: object, properties: {invoices: {type: array, items: {$ref: '#/components/schemas/Invoice'}}}}}}}
  /plans:
    get:
      summary: The plans that renew monthly, with the price a renewal charges.
      responses:
        '200': {description: Plans, content: {application/json: {schema: {type: object, properties: {plans: {type: array, items: {$ref: '#/components/schemas/Plan'}}}}}}}
  /subscriptions:
    get:
      summary: Subscriptions, oldest first. One is started for each plan line of a paid order.
      parameters: [{name: customer_id, in: query, schema: {type: string}}]
      responses:
        '200': {description: Subscriptions, content: {application/json: {schema: {type: object, properties: {subscriptions: {type: array, items: {$ref: '#/components/schemas/Subscription'}}}}}}}
  /subscriptions/{subscription_id}/plan:
    post:
      summary: Change plan. A more expensive plan starts now and is charged pro rata; a cheaper one starts at the period end.
      parameters: [{name: subscription_id, in: path, required: true, schema: {type: string}}]
      requestBody:
        required: true
        content: {application/json: {schema: {type: object, required: [sku], properties: {sku: {type: string}, as_of: {type: string, format: date, description: Defaults to today (UTC)}}}}}
      responses:
        '200': {description: The subscription, content: {application/json: {schema: {$ref: '#/components/schemas/Subscription'}}}}
        '400': {description: Unknown plan, or the subscription is not active}
        '402': {description: The pro-rata charge was declined; the plan is unchanged}
        '404': {description: No such subscription}
  /subscriptions/{subscription_id}/cancel:
    post:
      summary: End the subscription at the end of the period already paid for.
      parameters: [{name: subscription_id, in: path, required: true, schema: {type: string}}]
      responses:
        '200': {description: The subscription, content: {application/json: {schema: {$ref: '#/components/schemas/Subscription'}}}}
        '404': {description: No such subscription}
  /customers/{customer_id}/payment-method:
    put:
      summary: Replace the payment method on all of the customer's subscriptions.
      parameters: [{name: customer_id, in: path, required: true, schema: {type: string}}]
      requestBody:
        required: true
        content: {application/json: {schema: {type: object, required: [payment_method], properties: {payment_method: {type: string}}}}}
      responses:
        '200': {description: The customer's subscriptions}
  /renewals/run:
    post:
      summary: Renew every subscription whose period has ended by as_of, and retry failed renewals that are due. Run daily by the scheduler.
      requestBody:
        required: true
        content: {application/json: {schema: {type: object, properties: {as_of: {type: string, format: date, description: Defaults to today (UTC)}}}}}
      responses:
        '200': {description: Counts, content: {application/json: {schema: {type: object, properties: {as_of: {type: string}, renewed: {type: integer}, failed: {type: integer}, ended: {type: integer}}}}}}
components:
  schemas:
@MONEYDEF@    QuoteRequest:
      type: object
      required: [postal_code, lines]
      properties:
        postal_code: {type: integer}
        lines:
          type: array
          items: {type: object, required: [sku, qty, unit_price], properties: {sku: {type: string}, qty: {type: integer}, unit_price: @M@}}
    Quote:
      type: object
      required: [subtotal, tax, total]
      properties: {subtotal: @M@, tax: @M@, total: @M@}
    ChargeRequest:
      type: object
      required: [order_id, customer_id, amount]
      properties:
        order_id: {type: string}
        customer_id: {type: string}
        amount: @M@
        email: {type: string, description: Where a payment-failed notice goes}
        payment_method: {type: string, description: 'Defaults to pm_card_ok. pm_card_declined is the test card that always declines.'}
    Payment:
      type: object
      required: [payment_id, order_id, customer_id, amount, status]
      properties:
        payment_id: {type: string}
        order_id: {type: string}
        customer_id: {type: string}
        amount: @M@
        status: {type: string, enum: [succeeded, failed, refunded]}
        email: {type: string, nullable: true}
        payment_method: {type: string}
        failure_reason: {type: string, nullable: true}
        subscription_id: {type: string, nullable: true, description: Set on renewal and plan-change payments}
    Refund:
      type: object
      required: [refund_id, payment_id, order_id, customer_id, amount, created_at]
      properties: {refund_id: {type: string}, payment_id: {type: string}, order_id: {type: string}, customer_id: {type: string}, amount: @M@, created_at: {type: string, format: date-time}}
    InvoiceLine:
      type: object
      required: [type, sku, name, qty, unit_price, amount]
      properties:
        type: {type: string, enum: [RECURRING, FIXED, PRORATION, CREDIT], description: 'RECURRING: a plan period. FIXED: a one-off item. PRORATION and CREDIT: the two lines of a plan change; a CREDIT amount is negative.'}
        sku: {type: string}
        name: {type: string}
        qty: {type: integer}
        unit_price: @M@
        amount: @M@
    Invoice:
      type: object
      required: [invoice_id, order_id, customer_id, email, reason, lines, subtotal, tax, total, status, issued_at]
      properties:
        invoice_id: {type: string}
        order_id: {type: string}
        subscription_id: {type: string, nullable: true}
        customer_id: {type: string}
        email: {type: string}
        reason: {type: string, enum: [order, renewal, plan_change]}
        lines: {type: array, items: {$ref: '#/components/schemas/InvoiceLine'}}
        subtotal: @M@
        tax: @M@
        total: @M@
        status: {type: string, enum: [paid, refunded]}
        issued_at: {type: string, format: date-time}
    Plan:
      type: object
      required: [sku, name, unit_price]
      properties: {sku: {type: string}, name: {type: string}, unit_price: @M@}
    Subscription:
      type: object
      required: [subscription_id, order_id, customer_id, email, sku, name, qty, unit_price, status, current_period_start, current_period_end]
      properties:
        subscription_id: {type: string}
        order_id: {type: string, description: The order that started it}
        customer_id: {type: string}
        email: {type: string}
        postal_code: {type: integer}
        sku: {type: string}
        name: {type: string}
        qty: {type: integer}
        unit_price: @M@
        status: {type: string, enum: [active, past_due, canceled, terminated]}
        current_period_start: {type: string, format: date}
        current_period_end: {type: string, format: date}
        payment_method: {type: string}
        pending_sku: {type: string, nullable: true, description: The plan it changes to at the period end}
        pending_name: {type: string, nullable: true}
        cancel_at_period_end: {type: boolean}
        failed_attempts: {type: integer}
        next_attempt: {type: string, format: date, nullable: true}
"""

ORDERS = """# Orders API. Owner: Orders. Readers keep a pinned copy; ask Orders before relying on anything not written here.
openapi: 3.0.3
info: {title: Orders API, version: 2.0.0}
paths:
  /catalog:
    get:
      summary: What can be bought, in display order.
      responses:
        '200': {description: Products, content: {application/json: {schema: {type: object, properties: {products: {type: array, items: {$ref: '#/components/schemas/Product'}}}}}}}
  /carts/{customer_id}:
    get:
      parameters: [{name: customer_id, in: path, required: true, schema: {type: string}}]
      responses:
        '200': {description: The cart, content: {application/json: {schema: {$ref: '#/components/schemas/Cart'}}}}
  /carts/{customer_id}/items/{sku}:
    put:
      summary: Set how many of a product are in the cart. Zero takes it out.
      parameters: [{name: customer_id, in: path, required: true, schema: {type: string}}, {name: sku, in: path, required: true, schema: {type: string}}]
      requestBody:
        required: true
        content: {application/json: {schema: {type: object, required: [qty], properties: {qty: {type: integer, minimum: 0}}}}}
      responses:
        '200': {description: The cart, content: {application/json: {schema: {$ref: '#/components/schemas/Cart'}}}}
        '400': {description: Unknown sku or a negative quantity}
    delete:
      parameters: [{name: customer_id, in: path, required: true, schema: {type: string}}, {name: sku, in: path, required: true, schema: {type: string}}]
      responses:
        '200': {description: The cart, content: {application/json: {schema: {$ref: '#/components/schemas/Cart'}}}}
  /carts/{customer_id}/checkout:
    post:
      summary: Place an order for what is in the cart. The cart is emptied once the order is paid.
      parameters: [{name: customer_id, in: path, required: true, schema: {type: string}}, {name: Idempotency-Key, in: header, schema: {type: string}}]
      requestBody:
        required: true
        content: {application/json: {schema: {type: object, required: [email, postal_code], properties: {email: {type: string}, postal_code: {type: integer}, payment_method: {type: string}}}}}
      responses:
        '201': {description: The order, content: {application/json: {schema: {$ref: '#/components/schemas/Order'}}}}
        '400': {description: The cart is empty or the details are invalid}
  /orders:
    post:
      summary: Place an order. Quotes and charges through Billing, then publishes order.placed if the payment succeeded. A declined payment is a 201 with status payment_failed.
      parameters: [{name: Idempotency-Key, in: header, schema: {type: string}, description: A repeat with the same key returns the first order.}]
      requestBody:
        required: true
        content: {application/json: {schema: {$ref: '#/components/schemas/PlaceOrder'}}}
      responses:
        '201': {description: The order, content: {application/json: {schema: {$ref: '#/components/schemas/Order'}}}}
        '400': {description: Invalid request}
        '502': {description: Billing could not be reached or refused}
    get:
      summary: One page of orders, oldest first.
      parameters:
        - {name: customer_id, in: query, schema: {type: string}}
        - {name: limit, in: query, schema: {type: integer, minimum: 1, maximum: 100, default: 20}}
        - {name: after, in: query, schema: {type: string}, description: The `next` value of the previous page.}
      responses:
        '200': {description: Orders, content: {application/json: {schema: {type: object, properties: {orders: {type: array, items: {$ref: '#/components/schemas/Order'}}, next: {type: string, nullable: true, description: Null on the last page}}}}}}
  /orders/{order_id}:
    get:
      parameters: [{name: order_id, in: path, required: true, schema: {type: string}}]
      responses:
        '200': {description: The order, content: {application/json: {schema: {$ref: '#/components/schemas/Order'}}}}
        '404': {description: No such order}
  /orders/{order_id}/cancel:
    post:
      summary: Cancel a placed or paid order. Publishes order.cancelled once.
      parameters: [{name: order_id, in: path, required: true, schema: {type: string}}]
      responses:
        '200': {description: The order, content: {application/json: {schema: {$ref: '#/components/schemas/Order'}}}}
        '409': {description: The order has shipped, or its payment failed}
  /orders/{order_id}/ship:
    post:
      summary: Mark a paid order shipped. Publishes order.shipped once. Called by the warehouse.
      parameters: [{name: order_id, in: path, required: true, schema: {type: string}}]
      responses:
        '200': {description: The order, content: {application/json: {schema: {$ref: '#/components/schemas/Order'}}}}
        '409': {description: The order is not paid}
  /orders/{order_id}/deliver:
    post:
      summary: Mark a shipped order delivered.
      parameters: [{name: order_id, in: path, required: true, schema: {type: string}}]
      responses:
        '200': {description: The order, content: {application/json: {schema: {$ref: '#/components/schemas/Order'}}}}
        '409': {description: The order has not shipped}
components:
  schemas:
@MONEYDEF@    Product:
      type: object
      required: [sku, name, unit_price]
      properties: {sku: {type: string}, name: {type: string}, unit_price: @M@}
    Cart:
      type: object
      required: [customer_id, items, subtotal]
      properties:
        customer_id: {type: string}
        items: {type: array, items: {type: object, required: [sku, name, unit_price, qty], properties: {sku: {type: string}, name: {type: string}, unit_price: @M@, qty: {type: integer}}}}
        subtotal: @M@
    PlaceOrder:
      type: object
      required: [customer_id, email, postal_code, items]
      properties:
        customer_id: {type: string}
        email: {type: string}
        postal_code: {type: integer}
        payment_method: {type: string, description: Passed to Billing. Defaults to pm_card_ok.}
        items:
          type: array
          items: {type: object, required: [sku, qty], properties: {sku: {type: string}, qty: {type: integer, minimum: 1}}}
    OrderLine:
      type: object
      required: [sku, name, qty, unit_price]
      properties:
        sku: {type: string}
        name: {type: string}
        qty: {type: integer}
        unit_price: @M@
    Order:
      type: object
      required: [order_id, customer_id, email, postal_code, status, lines, subtotal, tax, total]
      properties:
        order_id: {type: string}
        customer_id: {type: string}
        email: {type: string}
        postal_code: {type: integer}
        status: {type: string, enum: [placed, paid, payment_failed, shipped, delivered, cancelled]}
        lines: {type: array, items: {$ref: '#/components/schemas/OrderLine'}}
        subtotal: @M@
        tax: @M@
        total: @M@
        payment_id: {type: string}
        payment_method: {type: string}
        created_at: {type: string, format: date-time}
        updated_at: {type: string, format: date-time}
        shipped_at: {type: string, format: date-time}
"""

MONEYDEF = """    Money:
      type: object
      required: [currency, minor]
      properties: {currency: {type: string, enum: [USD]}, minor: {type: integer, description: Integer minor units (cents)}}
"""


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def emit(root, money_json, money_yaml, moneydef):
    ev = events(money_json)
    dump = lambda schema: json.dumps(schema, indent=2) + "\n"  # noqa: E731
    billing = BILLING.replace("@M@", money_yaml).replace("@MONEYDEF@", moneydef)
    orders = ORDERS.replace("@M@", money_yaml).replace("@MONEYDEF@", moneydef)
    svc = lambda *p: os.path.join(root, "services", *p)  # noqa: E731
    write(svc("billing", "contracts", "billing-api.yaml"), billing)
    write(svc("orders", "contracts", "orders-api.yaml"), orders)
    for name, schema in ev["orders"].items():
        write(svc("orders", "contracts", "events", name + ".schema.json"), dump(schema))
        write(svc("notifications", "pinned", name + ".schema.json"), dump(schema))
        if name != "order.shipped":   # Billing reads placed and cancelled only
            write(svc("billing", "pinned", name + ".schema.json"), dump(schema))
    for name, schema in ev["billing"].items():
        write(svc("billing", "contracts", "events", name + ".schema.json"), dump(schema))
        write(svc("notifications", "pinned", name + ".schema.json"), dump(schema))
    write(svc("orders", "pinned", "billing-api.yaml"), billing)
    write(svc("storefront", "pinned", "billing-api.yaml"), billing)
    write(svc("storefront", "pinned", "orders-api.yaml"), orders)


emit(REPO, {"type": "number"}, "{type: number}", "")
emit(os.path.join(REPO, "tasks", "task01_money", "solution"),
     {"type": "object", "required": ["currency", "minor"], "properties": {"currency": {"const": "USD"}, "minor": {"type": "integer"}}},
     "{$ref: '#/components/schemas/Money'}", MONEYDEF)

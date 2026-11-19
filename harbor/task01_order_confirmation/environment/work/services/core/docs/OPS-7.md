# OPS-7: staff confirm orders before they are fulfilled (decision record, owned by Core)

Decided by Operations and Core. Too many orders were shipped before fraud review could look at them. From this
change on, an order placed in a shop waits until a member of staff confirms it. This is Saleor's
`automaticallyConfirmAllNewOrders` channel setting, switched off.

1. An order created from a checkout starts in status `UNCONFIRMED`. `checkoutComplete` returns it that way.
2. Orders that an app creates are not held: `draftOrderComplete` still gives `UNFULFILLED`. Renewals and plan
   changes from the Subscriptions app must keep flowing without anyone confirming them.
3. Staff confirm with a new mutation, which needs `MANAGE_ORDERS`:

       orderConfirm(id: ID!): OrderConfirm        # OrderConfirm { order: Order, errors: [OrderError!]! }

   It moves the order from `UNCONFIRMED` to `UNFULFILLED`. Confirming an order in any other status is an error
   with code `INVALID`, and changes nothing.
4. Core sends a new asynchronous event when an order is confirmed: `ORDER_CONFIRMED`. Its type in a subscription
   query is `OrderConfirmed`, with the same `order` field as the other order events. `ORDER_CREATED` is still
   sent when the order is placed and `ORDER_FULLY_PAID` when it is paid; neither moves.
   An order that is not held (rule 2) counts as confirmed the moment it is created: Core sends `ORDER_CONFIRMED`
   for it straight after `ORDER_CREATED`, so that renewals still get their confirmation email and tax document.
5. An `UNCONFIRMED` order cannot be fulfilled: `orderFulfill` answers with code `CANNOT_FULFILL`. It can be
   cancelled, and its payment can be refunded.
6. The customer's "Order #N confirmed" email goes out when the order is confirmed, not when it is placed.
   The receipt still goes out when the order is paid.
7. The tax document is committed when the order is confirmed, not when it is placed. An order that is cancelled
   before anyone confirmed it never has a tax document.
8. Orders placed before this change are left as they are. An order that is waiting to be shipped today stays
   `UNFULFILLED` and can be fulfilled without anyone confirming it. Nothing is sent again for old orders.
9. The dashboard's order page gets a "Confirm order" button on unconfirmed orders, and must not offer
   "Fulfill remaining items" before the order is confirmed.

The shops already show an unconfirmed order as "Order received". Released builds of the mobile app must keep working.

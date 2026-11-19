# Dashboard: owner's notes

- TypeScript on Node.js, no dependencies and no build step. `./run test`, `./run serve`.
- Modelled on Saleor's dashboard (github.com/saleor/saleor-dashboard): the orders list, the order page with
  fulfilment, cancellation and refunds, and the Apps page.
- We keep no data and decide nothing. Every page is read from Core with the signed-in member's token, and Core
  decides what that member may do. A refusal for lack of a permission is shown as a 403 on the same page.
- Staff see what the customer paid: totals here are gross, with "of which tax" as its own row.
- An order placed in a shop is UNCONFIRMED until a member of staff presses "Confirm order". Fulfilment is only
  offered after that.
- "Fulfill remaining items" fulfils every unfulfilled quantity at once.
- Cancelling an order does not refund it. Staff refund from the payment card on the order page; an empty amount
  refunds everything still charged.
- An order created by the Subscriptions app carries `subscription_id` and `subscription_reason` in its
  metadata; the order page shows them as the order's source.
- The Apps page shows each installed app, its permissions, its webhooks and the subscription query of each
  webhook: it is where to look up which app reads which field.
- A pinned copy of Core's schema is in `pinned/`.

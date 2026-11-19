# Subscriptions: owner's notes

- C# on .NET 8, minimal API, SQLite, xunit. `./run test`, `./run serve`.
- `./run query "<sql>"` runs read-only SQL on the database (table `subscriptions`, with a JSON `body`).
- Saleor has no subscriptions. This app adds them the way a Saleor merchant would: as an app on Core's
  webhooks and API. The rules follow Kill Bill and Lago: monthly periods, proration by day count, dunning.
- A subscription starts when Core tells us an order with a plan on it is fully paid: one subscription per plan
  line. Plans are `SubscriptionsApp.Plans` (BOX-S, BOX-L).
- Plan prices are ours, net, per unit and per month. The first period is paid at Core's catalogue price as
  part of the order; renewals are charged at our plan price. The two must agree.
- Every renewal and plan change is a new order we create in Core (draft order, complete, charge), so Core adds
  the tax and the customer gets Core's order emails. Those orders carry `subscription_id` in their metadata,
  and we ignore our own orders when they come back as events.
- Renewal and plan-change orders have no shipping method: renewals ship free.
- We charge through the app `seedco.payments` with the card the first order was paid with. We read that card
  from the Payments API by the order's `pspReference`; Core does not hold it.
- A more expensive plan starts at once and the customer pays the difference for the remaining days (17 of 31
  days of 200.00 is 109.68). A cheaper plan starts at the period end. A cancellation also waits for the period end.
- Renewals run from `POST /api/renewals/run`, called daily by the scheduler. A failed renewal is retried 3
  days later and the subscription is terminated at the third failure. The unpaid order is cancelled in Core.
- Each billing attempt has its own idempotency key, so running renewals twice on one day charges once.
- When the first order is cancelled in Core, its subscriptions end at once.
- We answer 500 to an order event we could not handle, so that Core sends it again.
- Customer messages go through the Notifications API (`POST /api/notify`). Dates are sent as YYYY-MM-DD.
- Pinned copies of Core's schema, the Payments API and the Notifications API are in `pinned/`.

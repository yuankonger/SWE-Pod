# Billing: owner's notes

- C# on .NET 8, minimal API, SQLite, xunit. `./run test`, `./run serve`.
- `Billing.cs` is the logic, `Store.cs` the database, `Program.cs` the HTTP wiring and the consumer of the
  `orders` topic.
- The database is SQLite. With `SEEDCO_DATA_DIR` set it is a file there; without it, it is in memory. Each table
  holds one kind of record as JSON, with the columns we look records up by.
- Money is `decimal` dollars. Every amount is rounded to cents, half away from zero (`BillingService.Round`).
- Tax is charged on the subtotal, not per line. The rate comes from the first digit of the postal code:
  8.75% when it is 9, otherwise 6%.
- A charge with an `Idempotency-Key` we have seen returns the first payment; the same key with a different order,
  customer or amount is a 409. Orders sends the order id as the key.
- `pm_card_declined` is the test card that always declines. A declined charge is a 200 with status `failed`, and
  we publish `payment.failed`.
- An invoice is issued when we read `order.placed`, never from the charge call. One invoice per `event_id`.
- The invoice copies `subtotal`, `tax` and `total` from the order in the event; line `amount` is computed here.
- Invoice lines are typed: RECURRING (a plan period), FIXED (a one-off item), and the PRORATION and CREDIT pair of
  a plan change. A CREDIT amount is negative.
- Plans are `BillingService.Plans` (BOX-S, BOX-L). A plan line on a paid order starts a monthly subscription. The
  first period is charged at the order's price; renewals are charged at the plan price held here.
- Plan changes: a more expensive plan starts at once. We credit the unused days of the old plan and charge the
  remaining days of the new one, by day count (17 of 31 days of 200.00 is 109.68). A cheaper plan starts at the
  period end, with no charge now. A cancellation also takes effect at the period end.
- Renewals run from `POST /renewals/run`, called daily by the scheduler. A failed renewal is retried 3 days later,
  and the subscription is terminated at the third failure.
- When we read `order.cancelled` we refund the order's payment, mark its invoice `refunded` and end its
  subscriptions at once. Renewal and plan-change payments are not refunded.
- We publish `invoice.paid`, `payment.failed` and `subscription.updated` on the `billing` topic, each embedding
  the whole object.
- Request bodies are typed. A field of the wrong type is rejected with 400 before our code runs.
- The consumer keeps its offset in the database and logs, then skips, an event it cannot read.

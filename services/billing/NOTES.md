# Billing: owner's notes

- C# on .NET 8, minimal API, xunit. `./run test`, `./run serve`.
- `Billing.cs` is the logic; `Program.cs` is the HTTP wiring and the consumer of the `orders` topic.
- Money is `decimal` dollars. Every amount is rounded to cents, half away from zero (`BillingService.Round`).
- Tax is charged on the subtotal, not per line. The rate comes from the first digit of the postal code:
  8.75% when it is 9, otherwise 6%.
- An invoice is issued when we read `order.placed`, never from the charge call. One invoice per `event_id`.
- The invoice copies `subtotal`, `tax` and `total` from the order in the event; line `amount` is computed here.
- We publish `invoice.paid` on the `billing` topic, embedding the whole invoice.
- Request bodies are typed. A field of the wrong type is rejected with 400 before our code runs.
- The consumer starts from the beginning of the topic and logs, then skips, an event it cannot read.

# Payments: owner's notes

- C# on .NET 8, minimal API, SQLite, xunit. `./run test`, `./run serve`.
- `./run query "<sql>"` runs read-only SQL on the database (tables `payment_intents` and `refunds`, each with a JSON `body`).
- Modelled on Saleor's Stripe app (github.com/saleor/apps, apps/stripe): Core calls us with synchronous
  transaction webhooks and we call the payment provider. `Provider` in `Payments.cs` stands in for the provider.
- Core installs us from `/api/manifest`. The fields we receive are the ones our queries in `graphql/` ask for.
- The two sides count money differently. Core sends `action.amount` as a decimal in major units (66.15). The
  provider takes an integer in the currency's smallest unit (6615), and currencies differ: yen has no decimal
  places, dinar has three. `Currencies` converts both ways. We answer Core in major units again.
- The card comes in `data.paymentMethod`, passed through from whoever started the payment. Without it the
  charge fails with `payment_method_missing`. `pm_card_declined` is the test card that always declines.
- Core's `idempotencyKey` is the provider's idempotency key: the same key returns the first payment intent.
- The provider's intent id is our `pspReference`. Core gives it back to us on a refund request.
- A declined card is not an error: we answer 200 with `CHARGE_FAILURE` and the provider's reason as `message`.
  A payload without what we need is a 400.
- We only charge. An `AUTHORIZATION` action is answered with a failure.
- `GET /api/payment-intents` and `/api/refunds` show the provider's records, in minor units.
- Since release 2026.11 we keep a ledger of the refund requests Core sent us (`refund_requests`,
  `GET /api/refund-requests`), so finance can set what was asked for beside what the provider paid.
- A refund request is known by Core's `idempotencyKey`. Core sends a request again when we do not answer, with
  the same key, and we answer a repeat with the refund we made the first time.
- Pinned copies of Core's schema and of the transaction answer format are in `pinned/`.

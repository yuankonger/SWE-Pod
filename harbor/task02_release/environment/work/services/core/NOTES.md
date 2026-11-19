# Core: owner's notes

- Python 3 with graphql-core, SQLite, standard library HTTP. `./run test`, `./run serve`.
- `./run query "<sql>"` runs read-only SQL on the database (`docs`: one row per record, with `kind`, `id`, `lookup` and a JSON `body`).
- Core mirrors Saleor's core (github.com/saleor/saleor): the same GraphQL type, field, enum and mutation names,
  for the part of the API we have.
- `contracts/schema.graphql` is the API and the server is built from it: a field that is not in the file does
  not exist. `src/core.py` is the rules, `src/webhooks.py` apps and webhooks, `src/server.py` the wiring.
- The catalogue a new database starts with is `src/catalogue.json`: products with one or more variants, nested
  categories and product types, in the shape of Saleor's sample data. A variant's `name` is empty when its
  product has only one, and a variant may have no SKU (`sku` is null), so nothing may key on the SKU alone.
- Ids are global ids: base64 of `Type:key`. Clients must treat them as opaque.
- Money is `Money {amount, currency}`: `amount` is a decimal in major units, sent as a JSON number.
  `fractionalAmount` is the same amount as an integer in the smallest unit. We keep amounts as decimal strings.
- We do not calculate tax. When a checkout has an address, we ask the channel's tax app (`taxAppId` in the
  channel's tax configuration) with CHECKOUT_CALCULATE_TAXES and store its answer. An answer we cannot use
  leaves the checkout with a tax error, and `checkoutComplete` then fails with TAX_ERROR.
- The tax app answers with rates as percentages (8.75). Our API gives `OrderLine.taxRate` as a fraction (0.0875).
- Until a checkout has an address its prices are shown as entered, with no tax.
- We do not take payments. `transactionInitialize` calls the payment app named in `paymentGateway.id` and
  records what it answers. A checkout becomes an order only when it is fully charged.
- Order numbers count up from 1. Statuses: DRAFT, UNFULFILLED, PARTIALLY_FULFILLED, FULFILLED, CANCELED.
  The status is spelled CANCELED; the event is ORDER_CANCELLED. Both spellings are Saleor's.
- Cancelling an order does not refund it. A refund is a separate request to the payment app.
- A refund moves money from `chargedAmount` to `refundedAmount`, so a fully refunded order has chargeStatus NONE.
- Apps are installed from their manifests when Core starts. Each webhook carries a subscription query; the
  payload we send is that query's result, so an app receives only the fields it asked for. A webhook whose
  query does not fit the schema is refused at installation and logged, and the rest of the app is installed.
- Removing or renaming a field that an installed webhook's query uses makes that webhook's events fail when
  they are sent. The dashboard's Apps page shows every installed query.
- Asynchronous events are stored as deliveries and sent by a worker: five attempts, then given up. A delivery
  can arrive more than once and deliveries carry no id.
- Staff: admin@seedco.example has every permission; support@seedco.example has MANAGE_ORDERS only.
- `/health` is 503 until every configured app is installed.

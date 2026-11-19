# Taxes: owner's notes

- Java 17, Jackson for JSON, H2 for the database, no build tool. `./run test`, `./run serve`.
- `./run query "<sql>"` runs read-only SQL on the H2 database (table `TAX_DOCUMENTS`).
- Modelled on Saleor's AvaTax app (github.com/saleor/apps, apps/avatax): Core asks us for taxes with a
  synchronous webhook, and we keep a tax document per order for reporting.
- Core installs us from `/api/manifest`. The fields we receive are the ones our queries in `graphql/` ask for.
- Rates: US postal codes starting with 9 are taxed at 8.75%, every other US destination at 6%. We have no nexus
  outside the US, so nothing is charged there.
- Shipping is not taxed.
- Each line is taxed and rounded on its own, half up to the cent. The order's tax is the sum of its lines' tax,
  which can differ by a cent from the rate applied to the subtotal.
- `pricesEnteredWithTax` decides the direction. False: the amount is net and tax is added. True: the amount is
  gross and the net is taken out of it (gross / (1 + rate), half up).
- The answer format is Core's (pinned). Rates are percentages: 8.75, not 0.0875. Amounts are decimals in major
  units. The answer must have one line per line of the request, in the same order.
- A tax document is committed when an order is created and voided when it is cancelled. Events can arrive
  twice; one order has one document.
- `GET /api/tax-documents` lists the documents; its shape is in `contracts/taxes-api.yaml`.
- A payload without what we need is a 400, which Core records as a tax error on the checkout.
- Pinned copies of Core's schema and of the tax answer format are in `pinned/`.

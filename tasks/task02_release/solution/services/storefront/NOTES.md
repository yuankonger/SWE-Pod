# Storefront: owner's notes

- TypeScript on Node.js, no dependencies and no build step: Node runs the `.ts` files directly, so types are
  not checked when the service starts. `./run test`, `./run serve`.
- Modelled on Saleor's storefront (github.com/saleor/storefront): server-rendered pages over Core's GraphQL API.
- `src/app.ts` is the routing, `src/pages.ts` the HTML, `src/views.ts` the view models, `src/clients/` the Core
  and Subscriptions clients. Each GraphQL operation asks only for the fields the shop shows.
- The shop page has a search box (`/?q=...`). The search is Core's (`products(filter: {search})`), which matches product
  names; we do not filter anything ourselves.
- We keep no data. The cart is a Core checkout whose id is in the `checkoutId` cookie. The customer's order ids
  and email are in cookies too; there are no accounts.
- Money is Core's `Money`: `amount` is a decimal in major units. All money text is formatted in `src/views.ts`.
- A taxed price has a net and a gross side. We show the side the channel asks for (`displayGrossPrices`), and
  the tax row always comes from the total.
- Core only knows the tax once the checkout has an address, so checkout sets the email, address and shipping
  method first and pays last. We always take the first shipping method Core offers.
- The checkout form carries a random token that we send as the payment's `idempotencyKey`, so a double click
  charges once.
- Payment goes through the app with the identifier `seedco.payments`. The card is passed in `paymentGateway.data`
  as `{paymentMethod}`.
- Customers cannot cancel orders in the shop; the order page sends them to support.
- Subscriptions come from the Subscriptions app, looked up by the email of the last checkout. The "Renews
  monthly at" price is the Subscriptions app's plan price; the catalogue price is Core's.
- Pinned copies of Core's schema and the Subscriptions API are in `pinned/`. They are copies: the owners' files
  are the truth.

# Storefront: owner's notes

- TypeScript on Node.js, no dependencies and no build step: Node runs the `.ts` files directly, so types are not
  checked when the service starts. `./run test`, `./run serve`.
- `src/app.ts` is the routing, `src/pages.ts` the HTML, `src/views.ts` the view models, `src/clients/` the Orders
  and Billing clients. `src/server.ts` only wires them together.
- We serve two things from one process: the shop (HTML pages and form posts) and the JSON API the mobile app calls.
  A form post to `/checkout` is the shop; a JSON post to `/checkout` is the API.
- We own what the customer sees. All money and status text is formatted in `src/views.ts`; pages never format.
- Money arrives from Orders and Billing as plain numbers and is shown with `toFixed(2)`. A negative amount (a
  credit) is shown as `-$13.70`.
- Line totals are computed here (`unit_price * qty`); Orders does not send them. The same goes for a
  subscription's monthly price (`unit_price * qty`).
- We keep no data. The cart lives in Orders, keyed by the customer id in the `seedco_customer` cookie.
- The checkout form carries a random token that we send to Orders as the `Idempotency-Key`, so a double click
  places one order.
- Orders lists orders a page at a time. The account page shows all of them, so the client follows `next` to the end.
- An order can have several invoices in Billing (the order itself, renewals, plan changes). The order page shows
  the one whose `reason` is `order`.
- The catalogue price comes from Orders; the "Renews monthly at" price comes from Billing's plans.
- `postal_code` is validated here as an integer (API) or five digits (shop form) before the request goes to Orders.
- Pinned copies of the Orders and Billing APIs are in `pinned/`. They are copies: the owners' files are the truth.

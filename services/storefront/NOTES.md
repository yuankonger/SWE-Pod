# Storefront: owner's notes

- TypeScript on Node.js, no dependencies. `./run test`, `./run serve`.
- We own what the customer sees. All money and status text is formatted in `src/views.ts`.
- Money arrives from Orders and Billing as plain numbers and is shown with `toFixed(2)`.
- Line totals are computed here (`unit_price * qty`); Orders does not send them.
- The account page looks up each order's invoice in Billing. An order with no invoice yet shows `invoice: null`.
- `postal_code` is validated here as an integer before the request goes to Orders.
- Pinned copies of the Orders and Billing APIs are in `pinned/`. They are copies: the owners' files are the truth.

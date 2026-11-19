Release 2026.12 ships seven tickets across the company. When it is done, customers must still be able to buy in the web shop and in every supported build of the mobile app, and subscriptions must keep renewing.

The tickets:

OPS-7 (Core, with Dashboard, Notifications and Taxes): from now on, an order placed in a shop waits for a member of staff to confirm it before it is fulfilled. Core owns the change and decides how it works; the decision record is `/work/services/core/docs/OPS-7.md`. The Dashboard gets a button labelled "Confirm order" on an order's page. The customer emails and the tax documents must be right under the new rule.

SHOP-31 (Storefront): customers can search the shop. The shop page takes `?q=<text>` and has a search field named `q`; it then shows only the products Core's product search returns for that text, and says so when nothing matches.

SUP-12 (Support): an agent can list one customer's conversations. `GET /api/v1/accounts/1/conversations?email=<address>` returns only that customer's conversations, and combines with `status`.

PAY-21 (Payments): the lists of payment intents and refunds have grown too long to return whole. Page them, and add a way to read one payment intent by id. Payments owns the change; the decision record is `/work/services/payments/docs/PAY-21.md`. Other services read these lists.

SUB-18 (Subscriptions): Payments is changing how its list of payment intents is returned (PAY-21). A new subscription must still record the card its first order was paid with.

OPS-9 (Monitoring): on-call wants to hear when subscription renewals fail. Add an alert named `RenewalsFailing`, severity `ticket`, that fires when any renewal has failed, with a rule test and a runbook.

MOB-8 (Mobile): the app shows a product with several variants under one name. Name the variant, as the web shop does ("Assam Breakfast (100 g)"), in the product list, the cart and the order, and ship it as release 1.1.0. Release 1.0.0 stays supported.

The whole company is yours to change. Do all seven tickets and keep every owner's tests passing (update them to the new behaviour).

The company's code is in `/work/services`. Its end-to-end regression tests are in `/work/regression`. A hidden
suite decides whether the work is right.

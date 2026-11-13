# FIN-12: money on the wire (decision record, owned by Billing)

Decided by Finance and Billing. Billing owns how money is represented on every contract in the company.

1. Every money amount on every contract, HTTP and events, becomes a **Money object**:

       {"currency": "USD", "minor": 2499}

   `minor` is an integer count of minor units (cents). `currency` is an ISO 4217 code; only `USD` exists today.
2. **Field names do not change.** `unit_price`, `amount`, `subtotal`, `tax` and `total` keep their names; only
   their values change, from a decimal number to a Money object.
3. There is no transition period. Once this ships, Billing rejects a plain number where Money is expected, on
   requests and on events.
4. Tax is computed on the subtotal in minor units and rounded half up to the cent. Rates do not change.
   Proration (plan changes) is computed in minor units and rounded half up to the cent as well.
5. What customers see does not change: pages and emails still show dollars, such as `$24.99`.

Every service that sends, stores or shows money is affected: Orders (catalogue prices, carts, orders, the charge
call, order events), Storefront (pages) and Notifications (emails). In Billing it covers quotes, payments, refunds,
invoices, plans and subscriptions.

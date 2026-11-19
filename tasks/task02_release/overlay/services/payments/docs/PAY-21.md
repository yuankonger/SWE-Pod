# PAY-21: the payment lists are paged (decision record, owned by Payments)

Decided by Payments. `GET /api/payment-intents` and `GET /api/refunds` return every record we hold. There are
now enough of them that the answers are slow and large, and they grow with every order.

1. Both lists return one page: 20 records by default, oldest first, as today.
2. `limit` sets the page size, from 1 to 100. Anything else is a 400.
3. `starting_after=<id>` gives the page that follows the record with that id. An id we do not hold is a 400.
4. Each answer has `has_more`: true when another page follows.
5. A new endpoint reads one payment intent: `GET /api/payment-intents/{id}`, where the id is the `pspReference`
   Core holds for the transaction. An unknown id is a 404.
6. There is no transition period: the default page applies to every caller from this release.

Whoever looks for one payment in the list must read it by id instead: after this release a payment is on the
first page only if it is among the 20 oldest.

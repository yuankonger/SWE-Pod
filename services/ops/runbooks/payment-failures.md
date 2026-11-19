# PaymentFailuresHigh

More charges are failing than succeeding.

1. The payments app logs one line per failure, with the provider's reason.
2. `card_declined` on many customers at once is rarely the customers. Compare what Core asked for
   (`transactionEvent` amounts on the order, in the dashboard) with what the provider holds
   (`GET /api/payment-intents` on the payments app, in the currency's smallest unit).
3. Renewals are charged by the subscriptions app through Core. A run of failed renewals shows here too.

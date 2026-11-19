# RenewalsFailing

The subscriptions app tried to renew a subscription and the charge failed.

1. One failure is usually one customer's card. The customer is emailed, the renewal is retried three days later,
   and the subscription ends at the third failure. Nothing to do.
2. Many failures in one run are rarely the customers. Check `PaymentFailuresHigh` and the payments app's log.
3. The unpaid renewal order is cancelled in Core. If it was not, it shows in the dashboard as unpaid and must not ship.

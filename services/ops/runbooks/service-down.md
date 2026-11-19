# ServiceDown

A service has not answered `/metrics` for 3 seconds. The `service` label says which.

1. Read the service's log for its last lines: a crash on start-up shows there.
2. If the service is an app (payments, taxes, notifications, subscriptions, support), Core cannot reach it either.
   Expect `SyncWebhookFailing` (payments, taxes) or `EventDeliveryFailing` (the others) to follow.
3. Core delivers order events again when an app comes back, up to five attempts. Anything older is lost; ask the
   app's owner whether it can catch up from Core's orders.

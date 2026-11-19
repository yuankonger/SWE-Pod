# SyncWebhookFailing and EventDeliveryFailing

Core called an app and the call failed. The labels name the app and the event.

1. Core's log says why: `sync webhook failed` or `delivery given up`, with the reason.
2. A 400 from an app means the payload did not have what the app needs. The payload is built from the app's own
   subscription query, so either the app's query changed or Core's schema did.
3. Core's dashboard lists every app, its webhooks and the query each one registered (Apps page).

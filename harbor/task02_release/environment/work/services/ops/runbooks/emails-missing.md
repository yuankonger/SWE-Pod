# NotificationsDroppingEvents

The email app received an order event it could not turn into an email. It answers 200 to Core, so Core's
deliveries look healthy and nothing retries.

1. `GET /dropped` on the email app lists each dropped event with the reason.
2. The reason names the field: for example `$.order.total.gross.amount must be number`. The email app checks the
   payload against what its templates need, so the event's shape or a field's meaning has changed.
3. Dropped emails are not sent later. Once the cause is fixed, ask the email app's owner how to resend.

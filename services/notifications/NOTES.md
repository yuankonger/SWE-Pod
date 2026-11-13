# Notifications: owner's notes

- Python 3, standard library only (SQLite included). `./run test`, `./run serve`.
- `notifications.py` holds the workflows and templates, `payload.py` the payload schemas, `store.py` the database,
  `server.py` the HTTP wiring and the consumers.
- The database is SQLite. With `SEEDCO_DATA_DIR` set it is a file there; without it, it is in memory. It holds the
  outbox, the dedup log, the consumer offsets and the dropped events.
- We read two topics, `orders` and `billing`, each from the offset we last stored.
- One workflow per event type: `order.placed`, `order.shipped`, `order.cancelled`, `invoice.paid`,
  `payment.failed`, `subscription.updated`. A workflow is a payload schema plus a template.
- Templates read fields straight out of the event's embedded object (`order`, `invoice`, `payment` or
  `subscription`). The receipt reads each line's `amount`; the confirmation reads only `qty`, `name` and `total`.
- Each workflow checks the embedded object against its payload schema before rendering. Most schemas allow
  fields we do not use. The receipt's does not: an invoice with a field or a line `type` we do not know is
  rejected, so a receipt never leaves a charge out.
- Money is formatted by `money()`, which treats the value as dollars. A negative amount is shown as `-$13.70`.
- One email per `event_id`. An event with an id we have seen is ignored, also after a restart.
- An event we cannot use is recorded (`GET /dropped`) and skipped; the consumer keeps going. The third dropped
  event of one type sends one alert to operations.
- `subscription.updated` sends an email for plan changes, scheduled downgrades, scheduled cancellations and
  terminations. A renewal sends none; the renewal receipt covers it.
- Pinned copies of the event schemas are in `pinned/`. They are the publishers' description of the events; the
  schemas in `payload.py` are ours and say what our templates need.

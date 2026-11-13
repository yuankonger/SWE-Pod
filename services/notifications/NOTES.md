# Notifications: owner's notes

- Python 3, standard library only. `./run test`, `./run serve`.
- `notifications.py` renders emails; `server.py` is the HTTP wiring and the consumers.
- We read two topics, `orders` and `billing`, each from the beginning.
- Templates read fields straight out of the event's embedded object (`order` or `invoice`).
  The receipt reads each line's `amount`; the confirmation reads only `qty`, `name` and `total`.
- Money is formatted by `money()`, which treats the value as dollars.
- One email per `event_id`. An event with an id we have seen is ignored.
- An event we cannot render is logged and skipped; the consumer keeps going.
- Pinned copies of the event schemas are in `pinned/`.

# Notifications: owner's notes

- Python 3, standard library only (SQLite included). `./run test`, `./run serve`.
- `./run query "<sql>"` runs read-only SQL on the database (tables `emails`, `dropped`, `settings`).
- Modelled on Saleor's SMTP app (github.com/saleor/apps, apps/smtp): Core sends us order events and we turn
  them into emails. The outbox stands in for the mail provider.
- `notifications.py` holds the workflows and templates, `payload.py` the payload schemas, `store.py` the
  database, `server.py` the HTTP wiring.
- Core installs us from `/api/manifest`. The order fields we receive are the ones `graphql/order-events.graphql`
  asks for. A template that needs a new field needs it in that query first.
- Events: ORDER_CONFIRMED (confirmation, once staff confirm the order), ORDER_FULLY_PAID (receipt), ORDER_FULFILLED (shipping),
  ORDER_CANCELLED (cancellation), ORDER_REFUNDED (refund).
- Each workflow checks the order against its payload schema before rendering. An event that does not fit is
  recorded (`GET /dropped`) and answered with 200, because Core sending it again would not help. The third
  dropped event of one type sends one alert to operations.
- Core's deliveries carry no id and can arrive twice. The dedup key is the event type and the order id. For
  refunds it also includes the refunded total, because one order can be refunded several times.
- Money is Core's `Money`: `amount` is a decimal in major units, formatted by `money()`.
- The receipt shows line amounts and the subtotal on the side the order asks for (`displayGrossPrices`), and
  always shows shipping, tax and the gross total.
- The cancellation email promises nothing about money. A refund has its own email when it happens.
- Other services ask for a message with `POST /api/notify`, in the shape of Saleor's NOTIFY_USER. The
  Subscriptions app uses it. `period_end` and plan names are shown as given.
- A pinned copy of Core's schema is in `pinned/`.

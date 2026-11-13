# Orders: owner's notes

- Java 17, Jackson for JSON, H2 for the database, no build tool. `./run test`, `./run serve`.
- `Orders.java` is the logic, `Db.java` the database, `Main.java` the HTTP wiring and the Billing client.
- The database is H2, embedded. With `SEEDCO_DATA_DIR` set it is a file there; without it, it is in memory.
  Orders are stored as JSON with the columns we look them up by; the catalogue and carts are plain tables.
- The catalogue (SKUs, names, unit prices) is the `products` table, seeded from `Orders.CATALOG` when a product is
  missing. Prices are `DECIMAL(10,2)` dollars in the table and `BigDecimal` in code.
- Carts are keyed by customer id. A cart holds SKUs and quantities only; it is priced from the catalogue when read.
- Placing an order: quote from Billing, charge through Billing, then publish `order.placed` on the `orders` topic.
  We charge exactly the quote's `total`. The order id is the `Idempotency-Key` of the charge, and a charge that
  cannot reach Billing is tried three times, so a retry never charges twice.
- `POST /orders` and the cart checkout take an `Idempotency-Key` too: a repeat returns the first order.
- The state machine is `Orders.TRANSITIONS`: placed -> paid | payment_failed | cancelled; paid -> shipped |
  cancelled; shipped -> delivered. Anything else is a 409.
- `order.placed` is published only for paid orders. `order.cancelled` and `order.shipped` are published once per order.
- Events embed the whole order. Every event gets a fresh `event_id` when it is created.
- Events go through an outbox table: stored with the order, then sent. If the broker is down the event is sent
  later (a background flush runs every second), in order, with the same `event_id`.
- `GET /orders` returns a page: 20 orders by default, 100 at most, oldest first, with `next` for the following page.
- JSON numbers are read as `BigDecimal` and written as they are held, so `24.99` stays `24.99`.
- A pinned copy of the Billing API is in `pinned/`.

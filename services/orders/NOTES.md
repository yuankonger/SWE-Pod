# Orders: owner's notes

- Java 17, Jackson for JSON, no build tool. `./run test`, `./run serve`.
- `Orders.java` is the logic; `Main.java` is the HTTP wiring.
- The catalogue (SKUs, names, unit prices) lives in `Orders.CATALOG`. Prices are `BigDecimal` dollars.
- Placing an order: quote from Billing, charge through Billing, then publish `order.placed` on the `orders` topic.
  We charge exactly the quote's `total`.
- `order.placed` is published only for paid orders. `order.cancelled` is published once per order.
- Events embed the whole order. Every event gets a fresh `event_id`.
- JSON numbers are read as `BigDecimal` and written as they are held, so `24.99` stays `24.99`.
- A pinned copy of the Billing API is in `pinned/`.

# Support desk: owner's notes

- Ruby 3.1, WEBrick, SQLite, minitest. `./run test`, `./run serve`.
- `./run query "<sql>"` runs read-only SQL on the database (tables `contacts`, `conversations`, `messages`).
- Modelled on Chatwoot (github.com/chatwoot/chatwoot): the same paths and shapes for the public inbox API and
  the account API, and an orders panel like Chatwoot's Shopify integration.
- `src/desk.rb` is the desk, `src/server.rb` the HTTP wiring.
- Customers write through the public API with no token and never see private notes. Agents use the account API
  with the `api_access_token` header.
- Message types are names on the way in (`incoming`, `outgoing`) and integers on the way out (0, 1, 2), and
  `created_at` is Unix seconds. Both are Chatwoot's.
- A customer writing into a resolved conversation reopens it.
- The orders panel reads the customer's orders from Core by email, with the token Core gave us at
  installation (MANAGE_ORDERS). We show Core's amounts as text with two decimals.
- Agents can see orders but not refund them: refunds need HANDLE_PAYMENTS, which support staff do not have.
  An agent asks someone with the dashboard's admin account.
- When Core tells us an order was cancelled or refunded, we leave one private note on each unresolved
  conversation of that customer. Events can arrive twice; the same note is not left twice.
- A pinned copy of Core's schema is in `pinned/`.

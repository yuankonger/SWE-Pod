# core

The shop's API: Saleor (Python, Django, GraphQL). This checkout is the `core` repository of the company's git server.

## Working here

- Python and every dependency are installed (`python`, `pytest` are on the path). A local PostgreSQL is running for tests: `pytest saleor/payment/tests -n 0 -q` runs one directory. The whole suite is large; run what you touch.
- `python manage.py get_graphql_schema` prints the schema.

## The running company

- This repository runs at `http://core.internal:8000/graphql/`, deployed from `main` of the git server. A push to `main` is deployed within a minute: the database is migrated and the server restarted. `curl http://ci:8080/` shows the last deploy.
- It runs without a task queue: what Saleor would hand to a worker is done at once, inside the request.
- The payment app is installed in it as an app with the permission to handle payments, and is the payment gateway `saleor.app.payment.stripe`.

## What this repository's owner can look at

- The back office. Staff sign in with `admin@example.com` / `admin` (`tokenCreate`), and a staff token can read and do everything staff can: orders, their transactions and each transaction's events, charging and refunding.
- This system's own output: `curl 'http://core.internal:9000/log?token={core_log}&lines=200'`.

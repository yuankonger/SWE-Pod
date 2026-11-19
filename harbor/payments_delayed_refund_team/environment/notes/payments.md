# payments

The payment app: the Stripe app of the Saleor apps monorepo (TypeScript, Next.js), under `apps/stripe`. The API calls it when a payment is started, charged, cancelled or refunded; it calls the payment provider; and it tells the API what the provider says happened. This checkout is the `payments` repository of the company's git server. Only `apps/stripe` and the packages it uses have their dependencies installed.

## Working here

- Node and pnpm are installed, with every dependency (`node_modules` is in place; nothing can be installed).
- In `apps/stripe`: `pnpm vitest --project=unit run <path>` runs unit tests, `pnpm check-types` checks types, `pnpm generate` regenerates `generated/` from the GraphQL files, `pnpm build` builds.

## The running company

- This repository runs at `http://stripe.internal:3000`, deployed from `main` of the git server. A push to `main` is deployed within a minute or two: the app is built and restarted. It is not installed again: what the API holds about the app from its installation stays as it is. `curl http://ci:8080/` shows the last deploy.
- The payment provider is a stand-in for Stripe inside the company's network, at `https://api.stripe.com` (its certificate authority is `/certs/ca.pem`). It answers Stripe's API and sends Stripe's signed events to the app.
- The app keeps its state (its installation, its configuration, the payments it has started) in a DynamoDB table, `stripe-main-table`, at `http://dynamodb:8000` (region `localhost`, any access key).

## What this repository's owner can look at

- This system's own output: `curl 'http://stripe.internal:9000/log?token=payments-log-c27d4a&lines=200'`.
- The provider's records, read-only, as its dashboard would show them: `curl --cacert /certs/ca.pem 'https://api.stripe.com/_ledger?token=provider-view-19e6b5'` (payment intents, refunds, and every event with each delivery of it).
- The app's table.

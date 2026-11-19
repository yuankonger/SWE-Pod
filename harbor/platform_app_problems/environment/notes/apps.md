# apps

The apps installed in the shop's API: the Saleor apps monorepo (TypeScript, Next.js, pnpm workspaces). Two of its apps run here: the payment app, `apps/stripe`, which the API calls when a payment is started, charged, cancelled or refunded and which calls the payment provider; and the email app, `apps/smtp`, which the API tells of orders and which sends the shop's email through a mail server. `packages/` holds what the apps share. This checkout is the `apps` repository of the company's git server. Only these two apps and the packages have their dependencies installed.

## Working here

- Node and pnpm are installed. There is no package registry here: `pnpm install --offline` installs from what this machine's package store holds, which is what the repository's lockfile names and a little more.
- In an app's directory: `pnpm check-types`, `pnpm build`, and its tests with `pnpm vitest run <path>` (`apps/stripe` names its projects: `--project=unit`). `pnpm generate` regenerates `generated/` from the app's GraphQL files and the schema file it keeps.

## The running company

- The payment app runs at `http://stripe.internal:3000` and the email app at `http://smtp.internal:3000`, both deployed from `main` of the git server. A push to `main` is deployed within a few minutes: dependencies are installed from the package store, each app is built and restarted. Neither is installed in the API again. `curl http://ci:8080/` shows the last deploy.
- The payment provider is a stand-in for Stripe inside the company's network, at `https://api.stripe.com` (its certificate authority is `/certs/ca.pem`). It answers Stripe's API and sends Stripe's signed events to the app.
- The mail server is Mailpit, at `mailpit:1025` for sending; what it received can be read at `http://mailpit:8025`.
- The apps keep their state in DynamoDB tables, `stripe-main-table` and `smtp-main-table`, at `http://dynamodb:8000` (region `localhost`, any access key). The email app keeps its configuration in the API, as its own private metadata.

## What this repository's owner can look at

- The systems' own output: `curl 'http://stripe.internal:9000/log?token=payments-log-c27d4a&lines=200'` and `curl 'http://smtp.internal:9000/log?token=emails-log-a04c6d&lines=200'`.
- The provider's records, read-only, as its dashboard would show them: `curl --cacert /certs/ca.pem 'https://api.stripe.com/_ledger?token=provider-view-19e6b5'`.
- The mail server's API, and the apps' tables.

# dashboard

The staff back office: Saleor Dashboard (TypeScript, React), a browser application that talks to the API. This checkout is the `dashboard` repository of the company's git server.

## Working here

- Node and pnpm are installed, with every dependency (`node_modules` is in place; nothing can be installed).
- `pnpm run check-types`, `pnpm run lint`, `pnpm run test:quiet <path>` (Jest). `pnpm run generate` regenerates the GraphQL types and hooks from the queries in the source and the schema file the repository keeps (`schema-main.graphql`); `pnpm run fetch-schema` fetches that file from GitHub, which cannot be reached from here, so bring the schema from the API instead.
- A browser is installed for Playwright (`chromium`), if you want to look at a page as staff see it.

## The running company

- This repository runs at `http://dashboard.internal:9000/`, deployed from `main` of the git server, against the API at `http://core.internal:8000/graphql/`. A push to `main` is served within a minute or two (the types are generated and the development server restarted). `curl http://ci:8080/` shows the last deploy.
- Staff sign in with `admin@example.com` / `admin`. The apps installed in the shop are under Extensions.

## What this repository's owner can look at

- This system's own output: `curl 'http://dashboard.internal:9001/log?token={dashboard_log}&lines=200'`.

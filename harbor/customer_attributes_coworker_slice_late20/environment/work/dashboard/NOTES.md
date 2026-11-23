# Working in this environment

- Node 24 and pnpm are installed. The project's dependencies are installed at `/deps/node_modules`, and `node_modules` here is a link to them. Nothing needs to be installed.
- Run tests with `npx jest <path>`, for example `npx jest src/customers`. The whole suite (`npx jest --silent --maxWorkers=4`) is about 830 files. On this machine run it with `--maxWorkers=2` and a directory at a time: with four workers, or the whole suite in one run, Jest needs more memory than there is here and stops without finishing.
- The GraphQL schema of the API this dashboard calls is kept here as copies: `schema-main.graphql` and `schema-staging.graphql` (`schema.graphql` is a link to the first). Typed query code under `src/graphql/*.generated.ts` is generated from those copies and from the queries in `src/**/queries.ts`, `src/**/mutations.ts`, `src/fragments/*.ts` and `src/searches/*.ts`: run `pnpm run generate` after changing either (a few seconds).
- `API_URL=http://<host>:8000/graphql/ pnpm run fetch-local-schema` writes the schema a running API serves into `schema.graphql`.
- `npx tsc --noEmit` checks types (several minutes).
- `INTERFACE.md` lists the names the hidden tests import that do not exist yet, and the behaviour they check to the letter. Use exactly those names and places.

## The running company

- This repository is a clone of the company's git server (`origin`), which decides who may push where. `main` there is what is deployed and what is judged.
- It runs as the staff application, served by its development server at `http://dashboard:9000/`, calling the API above.
- CI and deploy are at `http://ci:8080/`. Whenever `main` of a repository moves it deploys that repository, then tests the systems together as they run: that each started, that the API answers, that every GraphQL operation the dashboard sends is valid against the schema the running API really has, and that the API, asked as staff for the fields it gained since the work started, answers them without an error in a resolver. `curl http://ci:8080/` shows the latest run and `curl http://ci:8080/runs` every run.
- The other system, `core`: the API, at `http://core:8000/graphql/`, with sample data and a staff user (`admin@example.com` / `admin`). A deploy runs its database migrations.

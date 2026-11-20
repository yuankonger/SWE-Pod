# Developer platforms and self-hosted apps split across several GitHub repos (cross-repo task sources)

Method note: PR facts below come from fetching each GitHub PR page and its `.diff` on 2026-11-18. Merge time is the `mergedTime` field on the PR page. Line and file counts come from parsing the `.diff`. "Test files" means changed paths matching test, `*_test`, `.test.`, `.spec.` or e2e patterns. Cross-references were scraped from links on the PR page. Licences come from the raw LICENSE file on the default branch. The GitHub REST API was blocked in this sandbox, so PR search used the github.com `pulls?q=` pages. Unless marked otherwise, every PR listed was merged in 2026, which is after typical model training cutoffs.

## Q1. Which ecosystems are actually split across several repos, and what are the licences?

### Takeaway
Many of the named "platforms" have become monorepos and are weak sources for this pattern: Argo CD (gitops-engine archived and merged in), Appwrite (console archived 21 Sep 2026 and moved into `apps/console`), Keycloak (admin-ui in `js/apps`), Superset, Airflow, Dagster, Prefect, MLflow, Directus, Strapi, n8n and Gitea (frontend in-tree). The ecosystems that are truly multi-repo and permissively licensed are Home Assistant (Apache-2), Temporal (MIT, Java SDK Apache-2) and Supabase (MIT/Apache-2). PostHog (MIT plus `ee/`) and Zulip (Apache-2) are second-tier. Sentry is FSL, and Grafana and Element/Synapse are AGPL.

### Cited Findings
**Home Assistant**
- `home-assistant/core` (Python), `frontend` (TS/Lit), `android` and `iOS`: all Apache-2.0. Sources: [core LICENSE.md](https://github.com/home-assistant/core/blob/dev/LICENSE.md), [frontend LICENSE.md](https://github.com/home-assistant/frontend/blob/dev/LICENSE.md), [android](https://github.com/home-assistant/android), [iOS](https://github.com/home-assistant/iOS).
- `home-assistant/home-assistant.io` (user docs) is **CC BY-NC-SA 4.0**, which is non-commercial. Flag it, and exclude it from the code side. [LICENSE.md](https://github.com/home-assistant/home-assistant.io/blob/current/LICENSE.md)
- `home-assistant-libs/zwave-js-server-python` is Apache-2.0. [repo](https://github.com/home-assistant-libs/zwave-js-server-python)

**Temporal**
- MIT: `temporalio/api` (protos), `temporal` (server, Go), `sdk-go`, `sdk-typescript`, `sdk-python`, `ui` (Svelte), `cli`. `sdk-java` is Apache-2.0. Source: LICENSE files in [api](https://github.com/temporalio/api), [temporal](https://github.com/temporalio/temporal), [sdk-java](https://github.com/temporalio/sdk-java).

**Supabase**
- MIT: `supabase/auth` (Go), `supabase-js` (TS monorepo of the JS client libs), `postgrest-js`, `cli`, and `supabase/sdk` (2026; shared SDK specs and compliance).
- Apache-2.0: `supabase/storage` (TS), `realtime` (Elixir), and `supabase/supabase` (Studio monorepo).
- `PostgREST/postgrest` is MIT.
- Source: LICENSE files in each repo, e.g. [auth](https://github.com/supabase/auth), [storage](https://github.com/supabase/storage), [realtime](https://github.com/supabase/realtime), [sdk](https://github.com/supabase/sdk).

**Ory**
- `kratos`, `hydra`, `keto`, `elements` and `sdk` are all Apache-2.0. [kratos](https://github.com/ory/kratos)
- Kratos also has a "commercial build tag infrastructure" commit (Jul 2026), so enterprise code paths are appearing. [kratos commits](https://github.com/ory/kratos/commits/master)

**Keycloak**
- `keycloak/keycloak`, `keycloak-js` and `keycloak-client` are Apache-2.0. [keycloak](https://github.com/keycloak/keycloak)
- The admin UI and account UI live inside the server repo at `js/apps/admin-ui` and `js/apps/account-ui`. [tree](https://github.com/keycloak/keycloak/tree/main/js/apps)

**Appwrite**
- `appwrite/appwrite` and `appwrite/console` are BSD-3-Clause. `sdk-generator` is MIT. [appwrite](https://github.com/appwrite/appwrite), [sdk-generator](https://github.com/appwrite/sdk-generator)
- `appwrite/console` was "archived by the owner on Sep 21, 2026" [console](https://github.com/appwrite/console). New console work lands in `appwrite/appwrite` under `apps/console/...`, e.g. [appwrite#15787](https://github.com/appwrite/appwrite/pull/15787).

**Argo**
- `argo-cd`, `argo-workflows`, `argo-ui` and `argo-helm` are Apache-2.0.
- `argoproj/gitops-engine` is archived, and argo-cd now has a top-level `gitops-engine/` directory and an in-tree `ui/`. [gitops-engine](https://github.com/argoproj/gitops-engine), [argo-cd tree](https://github.com/argoproj/argo-cd)

**Grafana**
- `grafana/grafana` is **AGPL-3.0**. [LICENSE](https://github.com/grafana/grafana/blob/main/LICENSE)
- `grafana/scenes`, `grafana-plugin-sdk-go`, `grafana-app-sdk` and `grafana-foundation-sdk` are Apache-2.0. [scenes](https://github.com/grafana/scenes)

**Directus**
- Now under "Monospace Sustainable Core License, Version 1.0 (MSCL-1.0-GPL)", Copyright 2026, so not OSI open source. [license](https://github.com/directus/directus/blob/main/license)

**Strapi**
- MIT Expat, except anything under `ee/` directories, which is the Enterprise Edition licence. [LICENSE](https://github.com/strapi/strapi/blob/develop/LICENSE)

**n8n**
- "Sustainable Use License" (fair-code). Files and directories containing `.ee.` require an n8n Enterprise License. [LICENSE.md](https://github.com/n8n-io/n8n/blob/master/LICENSE.md)

**PocketBase**
- `pocketbase/pocketbase` and `pocketbase/js-sdk` are MIT. [pocketbase](https://github.com/pocketbase/pocketbase)

**Gitea**
- `go-gitea/gitea` is MIT. [gitea](https://github.com/go-gitea/gitea)
- `tea` and `go-sdk` are hosted on gitea.com, not GitHub (see Gaps).

**Other Apache-2.0 repos**
- [Hasura graphql-engine](https://github.com/hasura/graphql-engine), Kong `kong` and `insomnia`, Apache Superset, Airflow, `airflow-client-python`, Dagster, Prefect, MLflow, Label Studio, `label-studio-sdk`, Backstage `backstage` and `community-plugins`.

**Sentry**
- `getsentry/sentry` and `getsentry/relay` are **FSL-1.1-Apache-2.0**. [sentry LICENSE.md](https://github.com/getsentry/sentry/blob/master/LICENSE.md), [relay](https://github.com/getsentry/relay)
- `sentry-javascript` is MIT. [sentry-javascript](https://github.com/getsentry/sentry-javascript)

**PostHog**
- `PostHog/posthog` is MIT except "All content that resides under the 'ee/' directory", which is licensed separately. [LICENSE](https://github.com/PostHog/posthog/blob/master/LICENSE)
- `posthog-js` is Apache-2.0 and `posthog-python` is MIT. [posthog-js](https://github.com/PostHog/posthog-js)

**Additional candidates found**
- `zulip/zulip` and `zulip/zulip-flutter` are Apache-2.0. [zulip](https://github.com/zulip/zulip), [zulip-flutter](https://github.com/zulip/zulip-flutter)
- `matrix-org/matrix-js-sdk` is Apache-2.0, but `element-hq/element-web` and `element-hq/synapse` are **AGPL-3.0**. [matrix-js-sdk](https://github.com/matrix-org/matrix-js-sdk), [element-web](https://github.com/element-hq/element-web)
- Jellyfin server and web are **GPL-2.0**. [jellyfin](https://github.com/jellyfin/jellyfin)
- `lemmy-js-client` is **AGPL-3.0**.
- Mattermost server has a custom mixed licence. `mattermost-mobile` is Apache-2.0. [mattermost](https://github.com/mattermost/mattermost)

### Inferences
- Viable tier, by licence and real repo split:
  1. Home Assistant
  2. Temporal
  3. Supabase
  4. PostHog (exclude `ee/`)
  5. Zulip
- Licence-flagged:
  - Sentry/Relay (FSL)
  - Grafana (AGPL core, but the Apache-2.0 SDKs could pair with each other)
  - Directus (MSCL)
  - n8n (Sustainable Use License)
  - Element/Synapse (AGPL)

### Gaps
- `PostHog/sdk-specs` returned no LICENSE file at the paths tried.
- `keycloak-nodejs-admin-client` returned no LICENSE file at the paths tried, and is probably archived or folded into the monorepo. Not verified.
- `home-assistant-js-websocket` licence not confirmed (no file at the tried paths).

## Q2. How is the contract between repos defined? Does the consumer vendor a copy?

### Takeaway
- **Temporal** has the cleanest machine-readable contract. `temporalio/api` protos are consumed through pinned versions: a Go module for server, sdk-go and cli, and a buf-generated npm package for the UI.
- **Home Assistant** uses an implicit WebSocket and REST contract. The frontend hand-maintains TypeScript types in `src/data/*.ts`, which effectively "vendor" the backend shape.
- **Supabase** uses REST APIs (auth has an OpenAPI file) plus a new `supabase/sdk` capability-matrix repo that specifies SDK features.

### Cited Findings
**Temporal**
- Version pins across repos:
  - Server `go.mod` pins `go.temporal.io/api v1.64.3` and `go.temporal.io/sdk v1.49.0` ([go.mod](https://github.com/temporalio/temporal/blob/main/go.mod)).
  - sdk-go pins `go.temporal.io/api v1.64.3` ([go.mod](https://github.com/temporalio/sdk-go/blob/master/go.mod)).
  - The CLI pins a pseudo-version `go.temporal.io/api v1.64.1-0.20261030195137-01272cbd37c9` plus `go.temporal.io/server v1.33.0-166.3` ([go.mod](https://github.com/temporalio/cli/blob/main/go.mod)).
- An unreleased API commit is pinned during feature work. The staged flow is: api PR, then api-go PR, then server PR. Example: [api#876](https://github.com/temporalio/api/pull/876) links [api-go#319](https://github.com/temporalio/api-go/pull/319) and [temporal#12349](https://github.com/temporalio/temporal/pull/12349).
- The Temporal UI depends on `@buf/temporalio_api.bufbuild_es` pinned to a commit-stamped version (`2.12.0-20260602195324-874c8d65f615.1`), plus `@temporalio/proto` 1.24.0. It has a `generate:proto` script. [ui package.json](https://github.com/temporalio/ui/blob/main/package.json)
- `sdk-typescript` vendors `sdk-rust` (formerly sdk-core) as a git submodule at `packages/core-bridge/sdk-core`. [.gitmodules](https://github.com/temporalio/sdk-typescript/blob/main/.gitmodules)
- The `temporalio/api` repo now also carries WIT definitions (e.g. "Add Notification Service WIT definition", #881) and has added `buf-breaking` checks (#845). [api PR list](https://github.com/temporalio/api/pulls?q=is%3Apr+is%3Amerged)

**Home Assistant**
- The frontend PR template has a "Link to backend pull request:" field, which the PR pages show filled with a `home-assistant/core#NNN` reference ([frontend#55604](https://github.com/home-assistant/frontend/pull/55604), [frontend#55742](https://github.com/home-assistant/frontend/pull/55742), the latter filled with "none needed").
- The frontend depends on `home-assistant-js-websocket` 9.8.1 for the WebSocket client. [package.json](https://github.com/home-assistant/frontend/blob/dev/package.json)
- Frontend features add TypeScript data modules that mirror core WebSocket commands. Examples:
  - `src/data/bootstrap_integrations.ts` pairs with core's `websocket_api/commands.py` change ([frontend#55834](https://github.com/home-assistant/frontend/pull/55834) / [core#191915](https://github.com/home-assistant/core/pull/191915)).
  - `src/data/energy.ts` pairs with `homeassistant/components/energy/data.py` ([frontend#55713](https://github.com/home-assistant/frontend/pull/55713) / [core#190980](https://github.com/home-assistant/core/pull/190980)).

**Supabase**
- `supabase/sdk` is described as "Shared tooling and specifications for the Supabase client SDKs". Its `packages/capability-matrix` is "The canonical feature registry for all Supabase client SDKs: capability YAML data, per-feature specs, JSON Schema, validator". Its reusable `validate-sdk-compliance-<language>.yml` workflows are consumed by the SDK repos. [README](https://github.com/supabase/sdk)
- SDK feature PRs link capability PRs, e.g. [supabase-js#2676](https://github.com/supabase/supabase-js/pull/2676) links [sdk#151](https://github.com/supabase/sdk/pull/151).
- Auth publishes an OpenAPI document that is updated after features, e.g. "feat(openapi): document mfa recovery codes endpoints". [auth#2825](https://github.com/supabase/auth/pull/2825)

**PostHog**
- A `PostHog/sdk-specs` repo defines cross-SDK behaviour. "docs(flags): define failed remote flag handling" ([sdk-specs#211](https://github.com/PostHog/sdk-specs/pull/211)) is linked from [posthog-js#5693](https://github.com/PostHog/posthog-js/pull/5693).
- The backend sometimes imports types from posthog-js: "refactor(early-access-features): read imageUrl from the posthog-js type" ([posthog#133105](https://github.com/PostHog/posthog/pull/133105)).

**Appwrite**
- Server API changes regenerate SDK spec files, e.g. the diff of [appwrite#15769](https://github.com/appwrite/appwrite/pull/15769) touches `app/config/sdks/parameters.lock.json`.
- The console consumed a generated `@appwrite.io/console` SDK. [console#3067](https://github.com/appwrite/console/pull/3067), "add OAuth2 server settings card and update SDK".

**Keycloak**
- `keycloak-client` is kept in sync with the server by bot-style sync PRs, e.g. "Sync with Keycloak server release/26.8 branch" (#259) and "Sync after Keycloak server 26.7.0 release" (#227). [keycloak-client PRs](https://github.com/keycloak/keycloak-client/pulls?q=is%3Apr+is%3Amerged)

### Inferences
- **Temporal**: the protos are a natural contract file to give agents. The consumer pins a commit, so the pin bump in `go.mod` or `package.json` is part of the reference solution.
- **Home Assistant**: no schema file exists. The contract is implied by the core WebSocket handler (`websocket_api.websocket_command` schemas) and the frontend TS types. We would need to synthesise a contract doc per task, much as the Saleor GraphQL schema copy serves that role.

### Gaps
- Did not confirm whether `supabase-js` vendors an auth OpenAPI file or hand-writes types.
- Did not open the Temporal UI `temporal/` directory to see whether it is a proto checkout.

## Q3. Concrete cross-repo feature pairs (verified)

### Takeaway
- **Home Assistant**: many verified 2026 core+frontend pairs, merged the same day to two days apart. Both sides usually carry tests (pytest + vitest). Sizes range from about 300 to about 7k lines combined.
- **Temporal**: verified api → server → SDK/UI chains, but the api side has no tests and the server/SDK sides do.
- **Supabase**: verified server → supabase-js pairs 2 to 8 days apart.
- **PostHog, Sentry, Zulip, Appwrite and Keycloak**: only weaker pairs.

### Cited Findings

#### Home Assistant (core ↔ frontend, sometimes plus libs and docs)

| Feature | core PR | merged | files / test files / +/- | frontend PR | merged | files / test files / +/- |
|---|---|---|---|---|---|---|
| Startup progress | [core#191915](https://github.com/home-assistant/core/pull/191915) "Add bootstrap startup progress" | 2026-11-16 | 7 / 4 / +948/-33 | [frontend#55834](https://github.com/home-assistant/frontend/pull/55834) | 2026-11-17 | 8 / 1 (`test/data/bootstrap_integrations.test.ts`) / +774/-110 |
| Recorder DB usage | [core#190600](https://github.com/home-assistant/core/pull/190600) "Add recorder database usage report" | 2026-11-16 | 4 / 2 (incl. `.ambr` snapshot) / +1526/-0 | [frontend#55659](https://github.com/home-assistant/frontend/pull/55659) | 2026-11-16 | 6 / 1 / +899/-93 |
| Per-direction battery energy | [core#190224](https://github.com/home-assistant/core/pull/190224) | 2026-11-15 | 12 / 6 / +1424/-123 | [frontend#55604](https://github.com/home-assistant/frontend/pull/55604) (also links [home-assistant.io#50154](https://github.com/home-assistant/home-assistant.io/pull/50154)) | 2026-11-15 | 15 / 4 / +2320/-278 |
| Battery capacity sensor | [core#190980](https://github.com/home-assistant/core/pull/190980) | 2026-11-17 | 3 / 2 / +51/-7 | [frontend#55713](https://github.com/home-assistant/frontend/pull/55713) | 2026-11-17 | 6 / 1 / +229/-19 |
| Long-lived token last used (WTH) | [core#190168](https://github.com/home-assistant/core/pull/190168) | 2026-11-03 | 7 / 3 / +288/-3 | [frontend#55589](https://github.com/home-assistant/frontend/pull/55589) | 2026-11-03 | 2 / 0 / +25/-1 |
| Z-Wave credential management (3 repos) | [core#168360](https://github.com/home-assistant/core/pull/168360) | 2026-05-20 | 11 / 2 / +2533/-3 | [frontend#51591](https://github.com/home-assistant/frontend/pull/51591) | 2026-05-20 | 9 / 2 / +1946/-0 |
| Automation item comments | [core#171091](https://github.com/home-assistant/core/pull/171091) | 2026-05-21 | 3 / 1 / +58/-0 | [frontend#52090](https://github.com/home-assistant/frontend/pull/52090) | 2026-05-21 | 36 / 1 / +726/-35 |
| Vacuum clean_area / segment mapping | [core#149315](https://github.com/home-assistant/core/pull/149315) | 2026-02-18 | 11 / 4 / +681/-10 | [frontend#29343](https://github.com/home-assistant/frontend/pull/29343) | 2026-02-18 | 10 / 0 / +687/-6 |
| radio_frequency platform | [core#168447](https://github.com/home-assistant/core/pull/168447) (not size-checked) | – | – | [frontend#51693](https://github.com/home-assistant/frontend/pull/51693) | 2026-04-24 | 6 / 0 / +20/-2 |

Notes on the table:
- **Z-Wave credential management** has a third repo: [zwave-js-server-python#1418](https://github.com/home-assistant-libs/zwave-js-server-python/pull/1418), merged 2026-05-06, 14 files / 5 test files / +2457/-8. All three together are about 6.9k added lines, which is a strong 3-repo candidate.
- **Battery capacity sensor**: the core side only extends existing test files `tests/components/energy/test_websocket_api.py` and `test_data.py`. The frontend side has 17 new cases and "all 333 energy Vitest tests pass", per the author ([frontend#55713](https://github.com/home-assistant/frontend/pull/55713)).
- **Vacuum clean_area** also links a developer-docs PR, [developers.home-assistant#2966](https://github.com/home-assistant/developers.home-assistant/pull/2966).
- **Counter-example**: frontend-only work also occurs, e.g. [frontend#55736](https://github.com/home-assistant/frontend/pull/55736), a config-entry health dialog with "Link to backend pull request" left blank.

#### Temporal (api → server / SDKs / UI / CLI)
- **Eager standalone activity start.**
  - [api#876](https://github.com/temporalio/api/pull/876): merged 2026-10-08, 4 files, +273/-0, no tests.
  - [api-go#319](https://github.com/temporalio/api-go/pull/319): closed 2026-10-12, not merged.
  - [temporal#12349](https://github.com/temporalio/temporal/pull/12349) "Add eager start support for standalone activities": merged 2026-10-13, 29 files / 14 test files, +1212/-91.
- **Poller target reporting.**
  - [api#887](https://github.com/temporalio/api/pull/887): merged 2026-11-05, +28/-0.
  - [sdk-go#2799](https://github.com/temporalio/sdk-go/pull/2799): merged 2026-11-10, 9 files / 2 tests, +607/-10.
  - [sdk-java#3159](https://github.com/temporalio/sdk-java/pull/3159): merged 2026-11-10, 22 files / 6 tests, +700/-8.
  - The server side, [temporal#12636](https://github.com/temporalio/temporal/pull/12636), was still **OPEN** at 18 Nov 2026.
  - sdk-rust#1688 is also linked but was not checked.
- **Region IDs for compute config.**
  - [api#875](https://github.com/temporalio/api/pull/875): merged 2026-10-08.
  - [temporal#12491](https://github.com/temporalio/temporal/pull/12491): merged 2026-10-14, 7 files / 4 tests, +91/-62.
  - [ui#4020](https://github.com/temporalio/ui/pull/4020) "Let Serverless Workers follow a highly available Namespace through a failover": merged 2026-10-26, 53 files / 9 tests, +6100/-922.
  - Also links the private-looking `temporal-auto-scaled-workers` repo and cli#1235.
- **Standalone activity commands (UI + server).**
  - [temporal#10106](https://github.com/temporalio/temporal/pull/10106) "Implement Pause/Unpause/Reset/UpdateOptions for standalone activities": merged 2026-07-20, 58 files / 14 tests, +15349/-2442.
  - [ui#3564](https://github.com/temporalio/ui/pull/3564) "Activity commands for Standalone Activities": merged 2026-07-20, 27 files / 8 tests, +1424/-427.
- **Workflow task completion size limit.**
  - [api#838](https://github.com/temporalio/api/pull/838): merged 2026-07-29.
  - [temporal#11377](https://github.com/temporalio/temporal/pull/11377): merged 2026-07-31, 5 files, +14/-3. Too small to use.
- **API activity**: `temporalio/api` had 131 merged PRs from 1 Mar to 18 Nov 2026, including namespace soft delete (#899, merged 2026-11-03) and workflow heartbeat notification (#901, merged 2026-11-17). Their server counterparts were not located. [api PRs](https://github.com/temporalio/api/pulls?q=is%3Apr+is%3Amerged+merged%3A2026-03-01..2026-11-18)

#### Supabase (service ↔ supabase-js, plus sdk spec)
- **MFA recovery codes.**
  - [auth#2762](https://github.com/supabase/auth/pull/2762): merged 2026-09-02, 4 files / 1 test, +556/-0.
  - [supabase-js#2676](https://github.com/supabase/supabase-js/pull/2676): merged 2026-09-07, 12 files / 4 tests, +1237/-6.
  - [sdk#151](https://github.com/supabase/sdk/pull/151): merged 2026-09-07.
  - [auth#2825](https://github.com/supabase/auth/pull/2825): OpenAPI docs, merged 2026-09-21.
- **Bucket lifecycle configuration.**
  - [storage#1338](https://github.com/supabase/storage/pull/1338): merged 2026-09-07, 43 files / 16 tests, +4843/-25.
  - [supabase-js#2659](https://github.com/supabase/supabase-js/pull/2659): merged 2026-09-04, 5 files / 1 test, +411/-0. The client merged before the server.
  - [sdk#147](https://github.com/supabase/sdk/pull/147): merged 2026-09-03.
- **Broadcast persistence.**
  - [realtime#2235](https://github.com/supabase/realtime/pull/2235) (Elixir): merged 2026-10-29, 28 files / 11 tests, +1286/-230.
  - [supabase-js#2690](https://github.com/supabase/supabase-js/pull/2690): merged 2026-11-03, 8 files / 2 tests, +471/-9.
- **Custom OIDC/OAuth providers.**
  - [auth#2357](https://github.com/supabase/auth/pull/2357): merged 2026-02-19, 22 files / 6 tests, +4315/-7.
  - [supabase-js#2133](https://github.com/supabase/supabase-js/pull/2133): merged 2026-02-27, 2 files / 0 tests, +396/-0.
- **custom_claims_allowlist.**
  - [auth#2576](https://github.com/supabase/auth/pull/2576): merged 2026-06-25, 10 files / 4 tests, +576/-62.
  - [supabase-js#2473](https://github.com/supabase/supabase-js/pull/2473): merged 2026-06-30, 1 file, +24/-0. The client side is too small to use.
- **Passkeys.**
  - Auth PRs "feat(passkeys): add management endpoints" (#2413) and "add admin endpoints to list and delete user passkeys" (#2424), merged in Mar–Apr 2026 ([auth PR search](https://github.com/supabase/auth/pulls?q=is%3Apr+is%3Amerged+passkey)).
  - [supabase-js#2263](https://github.com/supabase/supabase-js/pull/2263): merged 2026-04-24, 10 files / 2 tests, +767/-3.
  - Auth PR sizes were not checked.

#### PostHog
- **Early access feature images.**
  - [posthog#133095](https://github.com/PostHog/posthog/pull/133095): merged 2026-11-11, 39 files / 10 tests, +1378/-185.
  - [posthog-js#5663](https://github.com/PostHog/posthog-js/pull/5663): merged 2026-11-11, +8/-0, types only.
- **Failed flag evaluations.**
  - [posthog-js#5693](https://github.com/PostHog/posthog-js/pull/5693): merged 2026-11-15, 26 files / 11 tests, +2080/-152.
  - Links spec [sdk-specs#211](https://github.com/PostHog/sdk-specs/pull/211), merged 2026-11-12, and posthog-go#434.
  - This is an SDK ↔ SDK-spec pair, not a server pair.

#### Sentry (FSL)
- **Browser reports.**
  - [relay#6592](https://github.com/getsentry/relay/pull/6592): merged 2026-11-03, 13 files / 2 tests, +313/-4.
  - [sentry#129668](https://github.com/getsentry/sentry/pull/129668): merged 2026-11-03, +4/-0, only a feature flag.
- Most relay feature PRs checked had no cross-repo link: #6662, #6607, #6646, #6608. [relay PRs](https://github.com/getsentry/relay/pulls?q=is%3Apr+is%3Amerged)

#### Zulip
- [zulip-flutter#2334](https://github.com/zulip/zulip-flutter/pull/2334) "Support `individual_emoji_changes` client capability": merged 2026-07-15, 8 files / 2 tests, +203/-18.
- It links a server issue (#36339), not a server PR. Server-side API changes are documented by "feature level", e.g. [zulip#40643](https://github.com/zulip/zulip/pull/40643) "Document `config_data` rejection at feature level 514".

#### Appwrite
- [appwrite#13123](https://github.com/appwrite/appwrite/pull/13123) "huggingface oauth provider": merged 2026-08-19, 12 files / 1 test, +402/-21.
- [console#3183](https://github.com/appwrite/console/pull/3183): merged 2026-08-25, 8 files / **0 tests**, +47/-3.
- No console PR checked had test files: #3166, #3079, #3085, #3067, #3177.

#### Keycloak
- [keycloak-client#233](https://github.com/keycloak/keycloak-client/pull/233) "Add Keycloak Admin client based on Jackson 3": merged 2026-08-19, 19 files / 4 tests, +727/-84. Links keycloak#50848, #53708 and #53846.
- [keycloak-js#253](https://github.com/keycloak/keycloak-js/pull/253) "Add DPoP support to keycloak-js": merged 2026-10-02, 7 files / 2 tests, +1655/-72, with no server PR linked.

#### Ory
- No PRs were merged into `ory/kratos` after 1 Mar 2026 ("No pull requests matched"). [search](https://github.com/ory/kratos/pulls?q=is%3Apr+is%3Amerged+merged%3A%3E2026-03-01)
- Every recent commit is pushed by `ory-bot`, apparently synced from an internal monorepo. Cross-product features land as single commits, e.g. "feat: add YugabyteDB support for Kratos, Hydra, and Keto (OEL)" on Jul 27 2026. The last commit seen is dated Jul 29 2026. [commits](https://github.com/ory/kratos/commits/master)

#### Weak or no evidence
- **label-studio-sdk**: 2026 merged PRs are CI bumps. [PRs](https://github.com/HumanSignal/label-studio-sdk/pulls?q=is%3Apr+is%3Amerged)
- **airflow-client-python**: 2026 PRs are bulk "Update Python Client to 3.x" regenerations. [PRs](https://github.com/apache/airflow-client-python/pulls?q=is%3Apr+is%3Amerged)
- **backstage/community-plugins**: PRs mentioning backstage/backstage are mostly Renovate dependency bumps. [PRs](https://github.com/backstage/community-plugins/pulls?q=is%3Apr+is%3Amerged)

### Inferences
- **Home Assistant** is the closest match to the Saleor recipe:
  - Same-day or next-day merges.
  - Explicit backend link field.
  - Tests on both sides.
  - Sizes from about 300 to about 2.5k lines per side; the Z-Wave and energy features reach the "hard" range.
  - Typical HA PRs are smaller than Saleor #19633 (4.4k lines). To reach Saleor scale, chain several related PRs (e.g. the energy battery series #55604/#55606 with core #190224/#190980).
- **Temporal** pairs are large and well tested on the server side. The api repo makes a good "contract" repo with no tests. The UI side is TS with vitest.
- **Supabase** gives three different service languages (Go, TS, Elixir) against one TS client. This is good for multi-agent heterogeneity, but the server side often has to merge before the client.

### Gaps
- Did not size core#168447.
- Did not size the Supabase auth passkey PRs or locate Temporal server PRs for api#899 and #901.
- Did not find HA Android/iOS companion pairs. Not searched due to budget.
- No verified Backstage, Grafana, Hasura, Kong/Insomnia, Superset, Airflow, Dagster, Prefect, MLflow, Directus, Strapi, n8n, PocketBase or Label Studio cross-repo pairs. Most are monorepos (see Q1), so pairs would be cross-directory, not cross-repo.

## Q4. Test suites: framework, offline in Docker, runtime, external services

### Takeaway
- **Home Assistant** is the easiest to run offline:
  - core uses pytest with `pytest-socket`, so network calls are blocked in tests, and individual integration test directories can be targeted.
  - The frontend uses vitest unit tests, with a separate Playwright e2e.
- **Temporal UI**: vitest plus Playwright.
- **Supabase and Appwrite**: server tests need Postgres, MariaDB or Redis containers.
- **Sentry and PostHog** backends need heavy service stacks.

### Cited Findings
**Home Assistant**
- Core test requirements include `pytest-asyncio`, `pytest-aiohttp`, `pytest-socket==0.8.1`, `pytest-xdist==3.8.0`, `pytest-timeout`, `pytest-freezer` and `pytest-picked`, and core requires Python `>=3.14.2`. [requirements_test.txt](https://github.com/home-assistant/core/blob/dev/requirements_test.txt), [pyproject.toml](https://github.com/home-assistant/core/blob/dev/pyproject.toml)
- Frontend scripts:
  - `"test": "vitest run --config test/vitest.config.ts"`
  - e2e via Playwright (`test:e2e:demo`, `test:e2e:app`, `test:e2e:gallery`)
  - [package.json](https://github.com/home-assistant/frontend/blob/dev/package.json)
- Feature PRs add tests in the per-integration directories, e.g. `tests/components/energy/test_websocket_api.py` and `tests/components/recorder/test_database_usage.py` with a syrupy `.ambr` snapshot ([core#190224](https://github.com/home-assistant/core/pull/190224), [core#190600](https://github.com/home-assistant/core/pull/190600)).

**Temporal UI**
- Scripts: `"test": "TZ=UTC vitest"`, `test:e2e` and `test:integration` via Playwright. [package.json](https://github.com/temporalio/ui/blob/main/package.json)

**Supabase / Appwrite**
- supabase-js CI was migrated "to supabase cli v3" for test configs (#2811), which implies its integration tests run against a local Supabase stack. [supabase-js PRs](https://github.com/supabase/supabase-js/pulls?q=is%3Apr+is%3Amerged)
- Appwrite server tests include `tests/unit/...` (e.g. `tests/unit/Auth/OAuth2/VKTest.php`) and `tests/e2e/...` ([appwrite#15769 diff](https://github.com/appwrite/appwrite/pull/15769.diff)).

### Inferences
- **HA core**:
  - The full test suite is very large; earlier knowledge puts it at tens of thousands of tests, not verified here.
  - Running only `tests/components/<domain>` plus touched core tests should take minutes in Docker.
  - No external services are needed; integrations are mocked.
- **HA frontend**: vitest unit tests run in Node without a browser. The hidden tests for each feature are usually one `test/data/*.test.ts` file.
- **Temporal**:
  - Server unit tests are plain `go test`.
  - Functional tests can use the SQLite in-memory persistence. This is general knowledge, not verified here.
  - Go builds are heavy, so pre-warm the module cache in the image.
- **Supabase**:
  - auth Go tests need Postgres.
  - realtime (Elixir) needs Postgres.
  - storage needs Postgres and object storage (MinIO).
  - All are feasible as sidecar containers but heavier than HA.

### Gaps
- Exact test counts and runtimes were not measured for any repo.
- Did not verify the Temporal functional-test persistence requirement or the Supabase server test docker-compose files.

## Q5. 2026 activity and estimated minable cross-repo features per year

### Takeaway
- **Home Assistant**: about 265 frontend PRs in 2026 so far reference `home-assistant/core#`. Probably 100–150 per year are genuine paired features with tests on both sides, the highest yield found.
- **Temporal**: about 130 api PRs per 8.5 months, yielding perhaps 30–60 api+server(+SDK/UI) chains per year.
- **Supabase**: 51 supabase-js `feat` PRs in 2026, perhaps 20–35 per year with a server counterpart.
- **All others**: under about 10 per year, or monorepo, or licence-flagged.

### Cited Findings
- **Home Assistant frontend PRs referencing `"home-assistant/core#"`**:
  - 182 merged 2026-06-01..2026-11-18. [search](https://github.com/home-assistant/frontend/pulls?q=is%3Apr+is%3Amerged+merged%3A2026-06-01..2026-11-18+%22home-assistant%2Fcore%23%22)
  - 83 merged 2026-01-01..2026-05-31 (same query with the earlier range).
  - Both counts include fixes and renames, not only features (e.g. "Rename automation comments to note", #52219).
- **Temporal api**: 131 merged PRs, 2026-03-01..2026-11-18. [search](https://github.com/temporalio/api/pulls?q=is%3Apr+is%3Amerged+merged%3A2026-03-01..2026-11-18)
- **Temporal cli**: 130 merged PRs, 2026-05-01..2026-11-18, many of them dependency bumps. [search](https://github.com/temporalio/cli/pulls?q=is%3Apr+is%3Amerged)
- **supabase-js**: 51 merged PRs with "feat" in the title in 2026. [search](https://github.com/supabase/supabase-js/pulls?q=is%3Apr+is%3Amerged+merged%3A2026-01-01..2026-11-18+feat+in%3Atitle)
- **posthog-js**: 226 merged "feat" PRs, 2026-08-01..2026-11-18, mostly SDK-only. [search](https://github.com/PostHog/posthog-js/pulls?q=is%3Apr+is%3Amerged)
- **relay**: 100 merged "feat" PRs, Aug–Nov 2026. [search](https://github.com/getsentry/relay/pulls?q=is%3Apr+is%3Amerged)
- **zulip/zulip**: 725 merged PRs, May–Nov 2026. [search](https://github.com/zulip/zulip/pulls?q=is%3Apr+is%3Amerged+merged%3A2026-05-01..2026-11-18)
- **go-gitea/gitea**: 2,346 merged PRs in 2026 (monorepo). [search](https://github.com/go-gitea/gitea/pulls?q=is%3Apr+is%3Amerged+merged%3A2026-01-01..2026-11-18)
- **appwrite/console**: archived 21 Sep 2026, so no further cross-repo pairs. [console](https://github.com/appwrite/console)

### Inferences
- Recommended priority:
  1. **Home Assistant core+frontend.** It is the best match to the Saleor recipe: Apache-2, per-PR backend link field, tests on both sides, offline pytest/vitest. Add `home-assistant-libs/*` for 3-repo tasks; exclude the CC BY-NC-SA docs repo.
  2. **Temporal.** Use api protos as the contract and pair server (Go) with sdk-go, sdk-java or the UI.
  3. **Supabase.** Use auth, storage or realtime with supabase-js, plus the `supabase/sdk` capability spec as the contract.
- Secondary options: PostHog (exclude `ee/`; backend test stack heavy) and Zulip (server + flutter, linked via issues and API feature levels rather than PR links).
- Avoid or deprioritise:
  - Ory (no PRs since 2026; bot-synced)
  - Appwrite (console now in the monorepo, and the console had no tests)
  - Argo CD (monorepo)
  - Keycloak (monorepo; client repos bot-synced)
  - Grafana (AGPL), Sentry (FSL), Directus (MSCL), n8n (Sustainable Use License)
  - Label Studio SDK and Airflow client (autogenerated)

### Gaps
- The yield estimates are extrapolations from search counts and small samples, not a full classification.
- No per-year count for HA companion apps, Temporal server↔UI, or Supabase Studio↔service pairs.
- gitea.com (tea CLI, go-sdk) PR lists redirect to a sign-in page for scraping, so the Gitea CLI/SDK activity is unverified.

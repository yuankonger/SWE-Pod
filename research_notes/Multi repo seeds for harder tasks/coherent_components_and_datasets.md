# Coherent components and datasets to combine with Saleor into one multi-owner company

Method note for the report writer. Facts about `saleor/saleor`, `saleor/apps` and `saleor/saleor-dashboard` were read from local read-only clones at these commits: apps `f001ac7e` (2026-10-28), saleor `6f714faf` (2026-11-12, version `3.24.0-a.0`), dashboard `513686a7` (2026-11-13, version `3.23.44`). They are cited as GitHub paths on the default branch; I did not open each URL in a browser, so a path may differ slightly on `main` today. Licence identifiers marked "GitHub API" come from `api.github.com/repos/<owner>/<repo>` (SPDX detection) on 2026-11-16; where the API returned `NOASSERTION` I read the LICENSE file directly and say so. Anything I could not confirm is in a Gaps list, not in Cited Findings.

## 1. For each candidate component: licence, stack, build weight, what it needs, how it connects to Saleor, which flows it joins

### Takeaway
The first-party set is the only place where real, documented Saleor contracts exist in quantity: 15 apps in `saleor/apps` (BSD-3-Clause code, CC-BY-4.0 artwork), the dashboard (BSD-3), `app-sdk` (BSD-3) and the app template. Open-source third-party systems with a documented Saleor integration are close to nil: the only ones found are the CMS back ends the first-party CMS app already targets (Payload is MIT; Strapi community edition is MIT but only v4 is supported).

### Cited Findings

#### (a) First-party components

Repository-level facts
- `saleor/apps` LICENSE is BSD 3-Clause, with a trailer stating "artwork included in this distribution is licensed under the Creative Commons Attribution 4.0 International License"; root `package.json` declares `"license": "(BSD-3-Clause AND CC-BY-4.0)"`. — [saleor/apps LICENSE](https://github.com/saleor/apps/blob/main/LICENSE), [package.json](https://github.com/saleor/apps/blob/main/package.json)
- The monorepo requires Node `>=24 <25`, pnpm `>=10 <11` (`pnpm@10.28.1`), uses Turborepo, and its catalog pins `next 16.4.1`, `react 18.2.0`, `@saleor/app-sdk 1.16.0`. Root config sets the GraphQL `schemaVersion` to `3.23`. — [package.json](https://github.com/saleor/apps/blob/main/package.json), [pnpm-workspace.yaml](https://github.com/saleor/apps/blob/main/pnpm-workspace.yaml)
- The apps repo README says the devcontainer Dockerfiles "are meant for development" and that Saleor does not provide official production Dockerfiles for the apps. — [saleor/apps README](https://github.com/saleor/apps/blob/main/README.md)
- App directories present: `anonymizer, avatax, cms, dummy-payment-app, dummy-shipping-app, extensions-explorer, klaviyo, np-atobarai, onboarding, payment-apps-testclient, products-feed, search, segment, smtp, stripe`. Shared packages: `app-deprecation, app-problems, domain, dynamo-config-repository, errors, eslint-config, handlebars, logger, otel, react-hook-form-macaw, sentry-utils, shared, stale-installations-cleanup, trpc, typescript-config, ui, ui-next, webhook-utils`. — [apps/](https://github.com/saleor/apps/tree/main/apps), [packages/](https://github.com/saleor/apps/tree/main/packages)
- `saleor/saleor` is BSD 3-Clause (same CC-BY-4.0 artwork trailer), version `3.24.0-a.0`, Python `>=3.12,<3.13`; Dockerfile builds from `python:3.12` into `python:3.12-slim`. About 4,370 `.py` files under `saleor/`. — [LICENSE](https://github.com/saleor/saleor/blob/main/LICENSE), [pyproject.toml](https://github.com/saleor/saleor/blob/main/pyproject.toml), [Dockerfile](https://github.com/saleor/saleor/blob/main/Dockerfile)
- `saleor/saleor-dashboard` is BSD-3-Clause, version `3.23.44`, React 18.3.1 + Vite 7.3.5, Node `>=24 <25`, pnpm `>=11`, depends on `@saleor/app-sdk 1.15.0` and `@saleor/macaw-ui 0.7.4`. Its Dockerfile builds on `node:24-alpine` with `NODE_OPTIONS=--max-old-space-size=8192 vite build` and serves from `nginx:stable-alpine`; `API_URL` is a build arg. About 4,820 TS/TSX files under `src/`. — [LICENSE](https://github.com/saleor/saleor-dashboard/blob/main/LICENSE), [package.json](https://github.com/saleor/saleor-dashboard/blob/main/package.json), [Dockerfile](https://github.com/saleor/saleor-dashboard/blob/main/Dockerfile)
- `saleor/app-sdk`: BSD-3-Clause, TypeScript, version 1.17.0 at head, 2 MB repo; peer deps include `next >=12`, `graphql >=16.6.0`, optional `redis >=4`, `@vercel/kv`, `@aws-sdk/client-dynamodb`. — [GitHub API](https://api.github.com/repos/saleor/app-sdk), [package.json](https://github.com/saleor/app-sdk/blob/main/package.json)
- `saleor/saleor-app-template`: LICENSE file is BSD 3-Clause; `package.json` declares `(BSD-3-Clause AND CC-BY-4.0)`; Node `>=22 <23`, `next 16.4.5`, `@saleor/app-sdk 1.12.0`. — [LICENSE](https://github.com/saleor/saleor-app-template/blob/main/LICENSE), [package.json](https://github.com/saleor/saleor-app-template/blob/main/package.json)
- `saleor/saleor-platform`: BSD-3-Clause; a docker-compose of prebuilt images `ghcr.io/saleor/saleor:3.23` (api and worker), `ghcr.io/saleor/saleor-dashboard:3.23`, `postgres:15-alpine`, `valkey/valkey:8.1-alpine`, `jaegertracing/jaeger`, `axllent/mailpit`. README: "for local development only and is not meant to be deployed in any production environment". Last push 2026-06-02. — [docker-compose.yml](https://github.com/saleor/saleor-platform/blob/main/docker-compose.yml), [README](https://github.com/saleor/saleor-platform/blob/main/README.md), [GitHub API](https://api.github.com/repos/saleor/saleor-platform)
- `saleor/macaw-ui` (UI kit used by dashboard and apps) is licensed CC BY 4.0, not a software licence. — [macaw-ui LICENSE](https://github.com/saleor/macaw-ui/blob/canary/LICENSE)
- `saleor/storefront` is FSL-1.1-ALv2 ("Functional Source License, Version 1.1, ALv2 Future License"): excluded. — [storefront LICENSE](https://github.com/saleor/storefront/blob/main/LICENSE)
- `saleor/configurator` is BSD-3-Clause (TypeScript); `saleor/examples` and `saleor/auth-sdk` have no licence detected by GitHub. — [configurator](https://api.github.com/repos/saleor/configurator), [examples](https://api.github.com/repos/saleor/examples), [auth-sdk](https://api.github.com/repos/saleor/auth-sdk)

Per-app table (all BSD-3-Clause code via the repo LICENSE; all Next.js on the shared monorepo toolchain). "Events" are the webhook event names found in each app's `src/` and `graphql/` directories; "Permissions" are from each app's manifest route.

| App (version) | Required Saleor | External service it talks to | Events it subscribes to | Permissions | App-side storage | Flows |
|---|---|---|---|---|---|---|
| `avatax` 1.27.3 | `>=3.22 <4` | Avalara AvaTax REST v2 via npm `avatax 26.3.2` | sync `CHECKOUT_CALCULATE_TAXES`, `ORDER_CALCULATE_TAXES`; async `ORDER_CONFIRMED`, `ORDER_CANCELLED` | `HANDLE_TAXES`, `MANAGE_ORDERS`, `MANAGE_PRODUCTS` | APL `file` or `dynamodb`; DynamoDB logs table `avatax-client-logs` (TTL 14 days) | tax at checkout and draft order, commit on confirm, void on cancel, address validation, tax-code to tax-class mapping |
| `stripe` 2.15.0 (already in the company) | `>=3.23 <4` | Stripe API (SDK `stripe 18.1.0`, API version `2025-04-30.basil`) | sync `PAYMENT_GATEWAY_INITIALIZE_SESSION`, `TRANSACTION_INITIALIZE_SESSION`, `TRANSACTION_PROCESS_SESSION`, `TRANSACTION_CHARGE_REQUESTED`, `TRANSACTION_REFUND_REQUESTED`, `TRANSACTION_CANCELATION_REQUESTED`; async `ORDER_CREATED` | `HANDLE_PAYMENTS`, `MANAGE_ORDERS` (+ `HANDLE_CHECKOUTS` in the client set) | DynamoDB main table `stripe-main-table` | payment, capture, refund, cancel; reports back with `transactionEventReport` |
| `smtp` 2.11.2 (README: deprecated) | `>=3.22 <3.24` | any SMTP server (nodemailer 6.9.1); templates in MJML 4.15.3 + Handlebars | `ORDER_CREATED`, `ORDER_CONFIRMED`, `ORDER_CANCELLED`, `ORDER_FULFILLED`, `ORDER_FULLY_PAID`, `ORDER_REFUNDED`, `INVOICE_SENT`, `GIFT_CARD_SENT`, `NOTIFY_USER` (account confirmation, password reset, email change, account delete, fulfillment update) | `MANAGE_ORDERS`, `MANAGE_USERS`, `MANAGE_GIFT_CARD` | APL `file`, `upstash` or `dynamodb` | every customer-facing notification |
| `search` 1.34.2 | `>=3.22 <4` | Algolia (`algoliasearch 4.23.3`) | `PRODUCT_CREATED/UPDATED/DELETED`, `PRODUCT_VARIANT_CREATED/UPDATED/DELETED/OUT_OF_STOCK/BACK_IN_STOCK`, `CATEGORY_CREATED/UPDATED/DELETED`, `PAGE_CREATED/UPDATED/DELETED` | per docs: `MANAGE_PRODUCTS`, `MANAGE_PRODUCT_TYPES_AND_ATTRIBUTES`, `MANAGE_PAGES` | DynamoDB | catalogue to search index; stock in/out flag |
| `cms` 2.20.2 | `>=3.22 <4` | Contentful, Strapi, DatoCMS, Builder.io, Payload | `PRODUCT_UPDATED`, `PRODUCT_VARIANT_CREATED/UPDATED/DELETED` | `MANAGE_PRODUCTS` | APL `file`, `upstash` or `dynamodb` | one-way variant sync into a CMS |
| `segment` 2.6.2 | `>=3.22 <4` | Twilio Segment (`@segment/analytics-node 2.2.0`) | `ORDER_CONFIRMED`, `ORDER_UPDATED`, `ORDER_CANCELLED`, `ORDER_REFUNDED` | `MANAGE_ORDERS` | APL `file` or `dynamodb`; table `segment-main-table` | order analytics events |
| `klaviyo` 1.20.2 | `>=3.22 <4` | Klaviyo, hard-coded `https://a.klaviyo.com/api/track` | `CUSTOMER_CREATED`, `FULFILLMENT_CREATED`, `ORDER_CREATED`, `ORDER_FULLY_PAID` | `MANAGE_USERS`, `MANAGE_ORDERS` | APL file | marketing events |
| `products-feed` 3.5.2 (README: deprecated) | `>=3.22 <3.24` | S3-compatible bucket (uses `S3Client`); output is a Google Merchant XML feed | none found (pulls via GraphQL; mutation `UpdateCategoryMapping`) | `MANAGE_PRODUCTS` | APL `file`, `upstash` or `dynamodb` | catalogue to merchant feed |
| `np-atobarai` 1.7.2 | `>=3.22 <4` | NP Atobarai API `https://ctcp.np-payment-gateway.com/v1/` (test) / `cp.` (prod) | sync `PAYMENT_GATEWAY_INITIALIZE_SESSION`, `TRANSACTION_INITIALIZE_SESSION`, `TRANSACTION_PROCESS_SESSION`, `TRANSACTION_REFUND_REQUESTED`; async `FULFILLMENT_TRACKING_NUMBER_UPDATED` | `HANDLE_PAYMENTS`, `MANAGE_ORDERS` | DynamoDB `np-atobarai-main-table` | Japanese buy-now-pay-later; ties payment to fulfilment tracking |
| `dummy-payment-app` 1.3.2 | none declared | none | the full `TRANSACTION_*` / `PAYMENT_GATEWAY_INITIALIZE_SESSION` sync set | `HANDLE_PAYMENTS`, `MANAGE_ORDERS` | DynamoDB APL | test payments with no provider |
| `dummy-shipping-app` 1.1.14 | none declared | none | sync `SHIPPING_LIST_METHODS_FOR_CHECKOUT`, `ORDER_FILTER_SHIPPING_METHODS` | `MANAGE_SHIPPING`, `MANAGE_ORDERS` | none | shipping-rate provider and method filtering |
| `anonymizer` 1.2.16 | `>=3.22 <4` | none | none found (mutations `CustomerDelete`, `CheckoutDelete`, `OrderUpdate`, `GiftCardBulkDelete`, `UpdateMetadata`) | `MANAGE_ORDERS`, `MANAGE_USERS`, `MANAGE_CHECKOUTS`, `MANAGE_GIFT_CARD` | none | GDPR erase |
| `onboarding` 0.1.15 | `>=3.23 <4` | none | n/a | n/a | n/a | dashboard onboarding |

Sources for the table: each app's `package.json`, `src/**/manifest` route, `graphql/` directory, `.env.example` and `saleor-app.ts` under [saleor/apps/apps](https://github.com/saleor/apps/tree/main/apps); search-app permissions and event list confirmed by [Search app docs](https://docs.saleor.io/developer/app-store/apps/search); CMS providers and events confirmed by [CMS app docs](https://docs.saleor.io/developer/app-store/apps/cms); AvaTax void-on-cancel and "use tax app" channel prerequisite confirmed by [AvaTax app docs](https://docs.saleor.io/developer/app-store/apps/avatax/overview).

Further per-app facts
- AvaTax app calls these SDK methods: `createTransaction`, `createOrAdjustTransaction`, `voidTransaction`, `validateAddress`, `resolveAddress`, `listTaxCodes`, `listEntityUseCodes`, `ping`. Metadata keys used in source include `avataxId`, `avataxCustomerCode`, `avataxExemptionStatus`. — [apps/avatax/src](https://github.com/saleor/apps/tree/main/apps/avatax/src)
- AvaTax app docs: each channel must have its tax calculation method set to "use tax app" before it appears in the app; operation logs are kept 14 days; several provider configurations (sandbox, production) can be bound to different channels. — [AvaTax app docs](https://docs.saleor.io/developer/app-store/apps/avatax/overview)
- Search app docs: Algolia only; one record per product variant; product index name `PREFIX.CHANNEL_SLUG.CURRENCY.products`; initial import is manual and runs in the browser; translations unsupported; stock indexed only as in/out of stock. — [Search app docs](https://docs.saleor.io/developer/app-store/apps/search)
- CMS app docs: one-directional Saleor to CMS; synced fields are variant ID, variant name, channel availability and prices, product ID, name and slug; Strapi "only v4 is supported, v5 will not sync correctly"; Payload needs a REST API URL and a collection slug; bulk sync runs in the browser. — [CMS app docs](https://docs.saleor.io/developer/app-store/apps/cms)
- SMTP app README: "This app is deprecated. It has been replaced by the Customer Emails app ... SMTP still works, but is no longer developed." Products Feed README: "This app is deprecated. It has been replaced by the Google Merchant Center app". Neither replacement app is present in the public `saleor/apps` tree at the examined commit. — [smtp README](https://github.com/saleor/apps/blob/main/apps/smtp/README.md), [products-feed README](https://github.com/saleor/apps/blob/main/apps/products-feed/README.md)
- Saleor docs describe Customer Emails as listening for store events and delivering through an SMTP server you connect. — [Customer Emails docs](https://docs.saleor.io/developer/app-store/apps/customer-emails/overview) (seen via search snippet only)
- Saleor core still ships built-in plugins `admin_email`, `user_email`, `avatax`, `openid_connect`, `webhook` and a legacy `payment/gateways/stripe`; `EMAIL_URL` and `USER_EMAIL_URL` configure core's own SMTP sending. — [saleor/plugins](https://github.com/saleor/saleor/tree/main/saleor/plugins), [settings.py](https://github.com/saleor/saleor/blob/main/saleor/settings.py)
- Core exposes 148 async webhook event types and 16 sync ones (taxes, transactions, shipping-method listing/filtering, stored payment methods, tokenization). — [schema.graphql](https://github.com/saleor/saleor/blob/main/saleor/graphql/schema.graphql)

#### (b) Third-party open-source systems

Systems with a documented Saleor contract
- Payload CMS: MIT (GitHub API), TypeScript, 237 MB repo. Supported natively by the first-party CMS app. — [GitHub API](https://api.github.com/repos/payloadcms/payload), [CMS app docs](https://docs.saleor.io/developer/app-store/apps/cms)
- Strapi: LICENSE says code outside `ee/` directories is "MIT Expat License", `ee/` is Enterprise Edition; 762 MB repo. CMS app supports v4 only. — [strapi LICENSE](https://github.com/strapi/strapi/blob/develop/LICENSE), [CMS app docs](https://docs.saleor.io/developer/app-store/apps/cms)
- ERP: a web search found no open-source Saleor connector for ERPNext or OFBiz. The only Odoo connector found is a paid module (BambooForge, about USD 193, "live-tested against Saleor 3.19 and 3.20", GraphQL import plus native webhooks). — [Odoo Apps listing](https://apps.odoo.com/apps/modules/19.0/bambooforge_saleor_connector)
- Search: no Saleor app for Typesense or Meilisearch was found; the first-party search app is Algolia only. — [Search app docs](https://docs.saleor.io/developer/app-store/apps/search)

Licence screen of plausible third-party owners (no documented Saleor integration found for any of these; they would be connected by a custom app built on the template)

| System | Role | Licence | Stack / repo size | Verdict |
|---|---|---|---|---|
| InvenTree | inventory / stock / sales orders, REST API, plugins | MIT | Python/Django, 393 MB | permissive candidate |
| Apache OFBiz | ERP | Apache-2.0 | Java, 761 MB | permissive, heavy |
| Kill Bill | billing / subscriptions | Apache-2.0 | Java, 666 MB | permissive, heavy |
| Hyperswitch | payment orchestration | Apache-2.0 | Rust, 479 MB | permissive, heavy |
| Apache Superset | BI | Apache-2.0 | Python, 1.4 GB | permissive, heavy |
| Redash | BI | BSD-2-Clause | TypeScript/Python, 67 MB | permissive |
| Umami | web analytics | MIT | TypeScript, 32 MB | permissive |
| Jitsu | event collection | MIT | TypeScript, 61 MB | permissive |
| dlt | data loading library | Apache-2.0 | Python, 119 MB | permissive |
| Meltano | ELT runner | MIT | Python, 157 MB | permissive |
| Apache Airflow | orchestration | Apache-2.0 | Python, 797 MB | permissive, heavy |
| OpenSearch | search engine | Apache-2.0 | Java, 614 MB | permissive, heavy |
| Valkey | cache/broker (already used by saleor-platform) | BSD-3-Clause | C | permissive |
| Odoo | ERP | LGPL-3 (LICENSE file) | Python, 18 GB repo | flag: copyleft, very heavy |
| ERPNext | ERP | GPL-3.0 | Python, 2 GB | exclude: GPL |
| OpenBoxes | warehouse | EPL-1.0 | Groovy | flag: weak copyleft |
| Karrio | shipping | LGPL-3 outside `ee/`, separate `LICENSE_EE` | Python | flag |
| Typesense | search | GPL-3.0 | C++ | exclude: GPL |
| Meilisearch | search | `MIT AND OpenLDAP AND BUSL-1.1` (EE parts are BUSL) | Rust | flag: BUSL parts |
| Metabase | BI | AGPL outside `enterprise/`, commercial inside | Clojure | exclude |
| Airbyte | ELT | Elastic License 2.0 (root LICENSE) | Python/Java | exclude |
| RudderStack server | CDP | Elastic License 2.0 (root LICENSE) | Go | exclude |
| Directus | CMS | Monospace Sustainable Core License (MSCL-1.0-GPL) | TypeScript | exclude: source-available |
| listmonk | newsletters | AGPL-3.0 | Go | exclude |
| MinIO | S3 store | AGPL-3.0, repo archived | Go | exclude |

Sources: GitHub API records for [InvenTree](https://api.github.com/repos/inventree/InvenTree), [ofbiz-framework](https://api.github.com/repos/apache/ofbiz-framework), [killbill](https://api.github.com/repos/killbill/killbill), [hyperswitch](https://api.github.com/repos/juspay/hyperswitch), [superset](https://api.github.com/repos/apache/superset), [redash](https://api.github.com/repos/getredash/redash), [umami](https://api.github.com/repos/umami-software/umami), [jitsu](https://api.github.com/repos/jitsucom/jitsu), [dlt](https://api.github.com/repos/dlt-hub/dlt), [meltano](https://api.github.com/repos/meltano/meltano), [airflow](https://api.github.com/repos/apache/airflow), [OpenSearch](https://api.github.com/repos/opensearch-project/OpenSearch), [valkey](https://api.github.com/repos/valkey-io/valkey), [erpnext](https://api.github.com/repos/frappe/erpnext), [openboxes](https://api.github.com/repos/openboxes/openboxes), [typesense](https://api.github.com/repos/typesense/typesense), [listmonk](https://api.github.com/repos/knadh/listmonk), [minio](https://api.github.com/repos/minio/minio); LICENSE files for [Odoo](https://github.com/odoo/odoo/blob/master/LICENSE), [Karrio](https://github.com/karrioapi/karrio/blob/main/LICENSE), [Meilisearch](https://github.com/meilisearch/meilisearch/blob/main/LICENSE), [Metabase](https://github.com/metabase/metabase/blob/master/LICENSE.txt), [Airbyte](https://github.com/airbytehq/airbyte/blob/master/LICENSE), [rudder-server](https://github.com/rudderlabs/rudder-server/blob/master/LICENSE), [Directus](https://github.com/directus/directus/blob/main/license).

- InvenTree describes itself as a Python/Django back end with a REST API and a plugin system, published as a Docker image. — [InvenTree README](https://github.com/inventree/InvenTree/blob/master/README.md)

### Inferences
- A five-plus-owner company can be assembled from first-party BSD-3 code alone: core API, dashboard, payments (Stripe app), tax (AvaTax app), notifications (SMTP app), catalogue distribution (search and/or CMS and/or products-feed), plus a platform/SDK owner (`app-sdk` and the monorepo `packages/`). Each maps to a named real repository or app directory.
- An ERP or warehouse owner cannot be added while keeping "documented real integration contract with Saleor": no open connector exists. The nearest faithful options are (i) `dummy-shipping-app` as the seed of a shipping/fulfilment owner, because it is first-party and uses the real sync shipping webhooks, or (ii) InvenTree (MIT) joined by a custom app, which would be an invented contract and should be labelled as such.
- Payload (MIT) is the one third-party system that is both permissive and natively supported by a first-party app, so "CMS" is the cheapest real sixth or seventh owner. Strapi is usable only as v4, which adds version-pinning risk.
- The dashboard is expensive to build from source (8 GB Node heap for the Vite build); the prebuilt `ghcr.io/saleor/saleor-dashboard` image is the practical route if dashboard code does not need to be edited in tasks.
- Since the apps have no production Dockerfile, each app image must be authored locally (Node 24 + pnpm 10 + `next build` inside the Turborepo workspace). One shared base image with the installed workspace would avoid repeating the install per app.

### Gaps
- Whether the "Customer Emails" and "Google Merchant Center" apps have public source: not found in `saleor/apps` at the examined commit and the Saleor April 2026 apps blog post does not mention them ([blog](https://saleor.io/blog/apps-update-april-2026)). The root `package.json` has `oss:export` scripts and a recent commit is titled "Sync from internal repository", which suggests the public repo is an export of an internal one, but I found no statement of what is withheld.
- Actual Docker build times for each app and for the dashboard were not measured.
- `juspay` may publish a Saleor payment app for Hyperswitch, and Jitsu may accept Segment-protocol events; I did not verify either, so neither is claimed above.
- Licences of n8n, PostHog, Lightdash, Chatwoot and LocalStack were returned as `NOASSERTION` and not read; treat as unscreened. LocalStack's repository is archived as of 2026-03 ([GitHub API](https://api.github.com/repos/localstack/localstack)).
- Whether `products-feed` accepts a custom S3 endpoint (needed for an S3 stand-in) was not checked.

## 2. Which combinations give long dependency chains through real contracts, and which contracts are shared by several components

### Takeaway
The order lifecycle is the natural spine: `ORDER_CONFIRMED` and `ORDER_CANCELLED` are each consumed by three apps (avatax, smtp, segment), `ORDER_CREATED` by three (stripe, smtp, klaviyo), and product/variant events by two (search, cms). The widest shared contracts are the app-sdk (APL, manifest, webhook signature verification), the monorepo `packages/`, the DynamoDB table convention, and core's GraphQL subscription payload types.

### Cited Findings
- Event overlap, from each app's source:
  - `ORDER_CREATED`: stripe, smtp, klaviyo.
  - `ORDER_CONFIRMED`: avatax, smtp, segment.
  - `ORDER_CANCELLED`: avatax, smtp, segment.
  - `ORDER_FULLY_PAID`: smtp, klaviyo.
  - `ORDER_REFUNDED`: smtp, segment.
  - `PRODUCT_UPDATED`, `PRODUCT_VARIANT_CREATED/UPDATED/DELETED`: search, cms.
  - `PAYMENT_GATEWAY_INITIALIZE_SESSION`, `TRANSACTION_INITIALIZE_SESSION`, `TRANSACTION_PROCESS_SESSION`, `TRANSACTION_REFUND_REQUESTED`: stripe, np-atobarai, dummy-payment-app.
  — [saleor/apps/apps](https://github.com/saleor/apps/tree/main/apps)
- Sync (blocking) contracts where an app's response feeds core's own calculation: `CHECKOUT_CALCULATE_TAXES` and `ORDER_CALCULATE_TAXES` (avatax); the `TRANSACTION_*` session and request events (stripe); `SHIPPING_LIST_METHODS_FOR_CHECKOUT` and `ORDER_FILTER_SHIPPING_METHODS` (dummy-shipping-app). — [schema.graphql `WebhookEventTypeSyncEnum`](https://github.com/saleor/saleor/blob/main/saleor/graphql/schema.graphql)
- Shared library contract: every app depends on `@saleor/app-sdk` (catalog 1.16.0); the dashboard depends on it too (1.15.0, imported in 17 source files) and defines the app-extension mount points apps render into. — [apps pnpm-workspace.yaml](https://github.com/saleor/apps/blob/main/pnpm-workspace.yaml), [dashboard package.json](https://github.com/saleor/saleor-dashboard/blob/main/package.json)
- APL contract: AuthData is `token`, `saleorApiUrl`, `appId`, `jwks`; implementations are FileAPL (single tenant, "should not be used on production"), UpstashAPL, EnvAPL, RedisAPL, DynamoAPL, VercelKvApl. — [APL docs](https://docs.saleor.io/developer/extending/apps/developing-apps/app-sdk/apl)
- Shared operational conventions visible in every `.env.example`: `SECRET_KEY` (encrypts app configuration, with a `NEW_SECRET_KEY` rotation procedure), `ALLOWED_DOMAIN_PATTERN`, `APP_IFRAME_BASE_URL` / `APP_API_BASE_URL` (dashboard reaches the iframe URL, core reaches the API URL), `DYNAMODB_MAIN_TABLE_NAME`, OTEL variables. — e.g. [avatax .env.example](https://github.com/saleor/apps/blob/main/apps/avatax/.env.example), [stripe .env.example](https://github.com/saleor/apps/blob/main/apps/stripe/.env.example)
- Shared code packages used across apps: `packages/handlebars` (smtp and products-feed templates), `packages/dynamo-config-repository`, `packages/webhook-utils`, `packages/app-problems` (the April 2026 blog says Stripe, Algolia, CMS, AvaTax and Segment now report problems to the Dashboard through the Problems API), `packages/logger`, `packages/otel`, `packages/shared`, `packages/ui`. — [packages/](https://github.com/saleor/apps/tree/main/packages), [Saleor apps update April 2026](https://saleor.io/blog/apps-update-april-2026)
- The April 2026 release moved SMTP to 2.0.0 and Products Feed to 3.0.0 together because both removed the same Handlebars helpers (`fs`, `logging`, `markdown`, `match`, `object`, `embed`, `resolve`). — [Saleor apps update April 2026](https://saleor.io/blog/apps-update-april-2026)
- Core validates each app manifest's `requiredSaleorVersion` on install and can raise `UNSUPPORTED_SALEOR_VERSION`. — [manifest_validations.py](https://github.com/saleor/saleor/blob/main/saleor/app/manifest_validations.py)

### Inferences
- Longest single chain through real contracts: storefront traffic creates checkout, core calls the shipping app (sync), core calls the AvaTax app (sync) which calls AvaTax, core calls the Stripe app (sync) which calls Stripe, Stripe webhook returns to the Stripe app which reports a transaction event to core, core creates the order and fans out `ORDER_CREATED` / `ORDER_CONFIRMED` / `ORDER_FULLY_PAID` to AvaTax (commit transaction), SMTP (emails), Segment and Klaviyo (analytics), stock change fans out `PRODUCT_VARIANT_OUT_OF_STOCK` to search; later a dashboard refund triggers `TRANSACTION_REFUND_REQUESTED` (Stripe app), then `ORDER_REFUNDED` (SMTP, Segment), and a cancel triggers `ORDER_CANCELLED` (AvaTax void, SMTP, Segment). That path touches seven separately owned code bases plus three external stand-ins.
- Work items that naturally need several owners: (1) a change to the order subscription payload or money rounding (core, avatax, smtp templates, segment); (2) a new refund reason or partial-refund rule (core, dashboard, stripe, smtp, segment); (3) tax-exempt customers (dashboard metadata UI, core, avatax `avataxExemptionStatus`, smtp invoice template); (4) an app-sdk or `packages/` change such as APL storage, secret rotation or webhook signature handling, which touches every app at once; (5) a new product attribute that must appear in search records, the CMS mapping and the product feed; (6) a Saleor minor-version upgrade, gated by each app's `requiredSaleorVersion`.
- `packages/` and `app-sdk` give the benchmark a "platform team" owner whose changes are cross-cutting by construction, which is the strongest lever for multi-owner tasks without adding any new runtime service.

### Gaps
- I did not trace which GraphQL fragments are textually shared between apps (for example a common `OrderDetails` fragment); overlap above is at the event level only.
- Whether Saleor allows more than one tax app per channel, and how multiple sync payment apps are ordered, was not verified.

## 3. Official mock/stand-in servers and fixtures

### Takeaway
Only SMTP has a true drop-in stand-in (Mailpit, MIT). stripe-mock is MIT but stateless and cannot serve the Stripe app's flows; AvaTax has no open mock, though the official SDK accepts an arbitrary base URL; the search app is Algolia-only and the permissive alternatives are thin (Typesense is GPL-3.0, Meilisearch carries BUSL parts). DynamoDB Local's licence could not be confirmed and is a redistribution risk.

### Cited Findings
Stripe
- `stripe/stripe-mock` is MIT (GitHub API), Go, Docker image `stripe/stripe-mock`, default ports 12111 (HTTP) and 12112 (HTTPS). — [GitHub API](https://api.github.com/repos/stripe/stripe-mock), [README](https://github.com/stripe/stripe-mock/blob/master/README.md)
- README limitations: "stripe-mock is stateless. Data you send on a POST request will be validated, but it will be completely ignored beyond that"; responses "are hardcoded"; "It's locked to the latest version of Stripe's API and doesn't support old versions"; it cannot return specific errors on request. — [stripe-mock README](https://github.com/stripe/stripe-mock/blob/master/README.md)
- `stripe/openapi` is MIT and ships `openapi/fixtures3.json` (about 194 KB of sample resources) and `spec3.json` (about 8.3 MB). — [GitHub API](https://api.github.com/repos/stripe/openapi), [openapi/ directory](https://github.com/stripe/openapi/tree/master/openapi)
- `stripe/stripe-cli` is Apache-2.0 and contains 128 webhook trigger fixtures under `pkg/fixtures/triggers` (for example `charge.captured`, `charge.refunded`, `charge.dispute.created`, `charge.failed`, `checkout.session.completed`). — [GitHub API](https://api.github.com/repos/stripe/stripe-cli), [triggers directory](https://github.com/stripe/stripe-cli/tree/master/pkg/fixtures/triggers)
- The Stripe app pins `STRIPE_API_VERSION = "2025-04-30.basil"`, builds its client with `new Stripe(key, { httpClient: Stripe.createFetchHttpClient(fetch), apiVersion })` and no host override, and its README says integration tests use "mocked Saleor and local DynamoDB in Docker but are calling the real Stripe API". It also manages Stripe webhook endpoints (`stripe-webhook-manager.ts`). — [stripe-client.ts](https://github.com/saleor/apps/blob/main/apps/stripe/src/modules/stripe/stripe-client.ts), [stripe README](https://github.com/saleor/apps/blob/main/apps/stripe/README.md)

AvaTax
- The official JS SDK (`avadev/AvaTax-REST-V2-JS-SDK`, Apache-2.0) accepts `environment` as "sandbox", "production", "or the full URL of your AvaTax instance"; any value starting with `http://` or `https://` becomes `baseUrl`. — [AvaTaxClient.ts](https://github.com/avadev/AvaTax-REST-V2-JS-SDK/blob/main/lib/AvaTaxClient.ts), [GitHub API](https://api.github.com/repos/avadev/AvaTax-REST-V2-JS-SDK)
- The Saleor AvaTax app only passes `environment: isSandbox ? "sandbox" : "production"`, and infers environment by comparing `baseUrl` with `https://sandbox-rest.avatax.com`. — [avatax-sdk-client-factory.ts](https://github.com/saleor/apps/blob/main/apps/avatax/src/modules/avatax/avatax-sdk-client-factory.ts), [avatax-client.ts](https://github.com/saleor/apps/blob/main/apps/avatax/src/modules/avatax/avatax-client.ts)
- A web search found no standalone open-source AvaTax mock server; results were SDKs (which use `nock` in their own tests) and descriptions of Avalara's hosted sandbox. — [npm avatax](https://www.npmjs.com/package/avatax)

SMTP
- Mailpit: MIT, Go, single static binary or Docker image; SMTP server, web UI, REST API for integration tests, optional webhook on received mail, SMTP relay, and a "Chaos" feature for configurable SMTP errors. Actively pushed (2026-11-16). — [GitHub API](https://api.github.com/repos/axllent/mailpit), [Mailpit README](https://github.com/axllent/mailpit/blob/develop/README.md)
- MailHog: MIT, Go, last push 2024-02-13. — [GitHub API](https://api.github.com/repos/mailhog/MailHog)
- Saleor itself uses Mailpit: `saleor-platform` compose includes `axllent/mailpit`, core's devcontainer sets `EMAIL_URL=smtp://mailpit:1025`, and the apps devcontainer for smtp uses `axllent/mailpit:latest` (the older `apps/smtp/docker-compose.yml` still references `mailhog/mailhog`). — [saleor-platform compose](https://github.com/saleor/saleor-platform/blob/main/docker-compose.yml), [saleor .devcontainer](https://github.com/saleor/saleor/tree/main/.devcontainer), [apps .devcontainer/smtp](https://github.com/saleor/apps/tree/main/.devcontainer/smtp), [apps/smtp/docker-compose.yml](https://github.com/saleor/apps/blob/main/apps/smtp/docker-compose.yml)

Search
- The search app instantiates `Algoliasearch(appId, apiKey)` with no custom hosts; docs list Algolia as the only provider. — [algoliaSearchProvider.ts](https://github.com/saleor/apps/blob/main/apps/search/src/lib/algolia/algoliaSearchProvider.ts), [Search app docs](https://docs.saleor.io/developer/app-store/apps/search)
- Typesense is GPL-3.0; Meilisearch's LICENSE states `SPDX-License-Identifier: MIT AND OpenLDAP AND BUSL-1.1`, with Enterprise Edition parts under BUSL 1.1. — [Typesense GitHub API](https://api.github.com/repos/typesense/typesense), [Meilisearch LICENSE](https://github.com/meilisearch/meilisearch/blob/main/LICENSE)

DynamoDB and S3
- The apps' devcontainers use `amazon/dynamodb-local:latest`; avatax and stripe have a `setup-dynamodb` script; np-atobarai and stripe `.env.example` point `AWS_ENDPOINT_URL` at `http://localhost:8000`. — [apps .devcontainer/avatax](https://github.com/saleor/apps/tree/main/.devcontainer/avatax), [stripe .env.example](https://github.com/saleor/apps/blob/main/apps/stripe/.env.example)
- AWS documents DynamoDB Local as a free download and as the Docker image `amazon/dynamodb-local`; the page states no licence. — [AWS docs](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.DownloadingAndRunning.html)
- `architect/dynalite` is an Apache-2.0 DynamoDB emulator in JavaScript; its README lists Transactions as not implemented; last push 2025-09. — [GitHub API](https://api.github.com/repos/architect/dynalite), [dynalite readme](https://github.com/architect/dynalite/blob/main/readme.md)
- `adobe/S3Mock` is Apache-2.0 (Kotlin), actively maintained. — [GitHub API](https://api.github.com/repos/adobe/S3Mock)

Other hard-coded endpoints
- Klaviyo app posts to the literal URL `https://a.klaviyo.com/api/track`. — [klaviyo.ts](https://github.com/saleor/apps/blob/main/apps/klaviyo/src/lib/klaviyo.ts)
- Segment app builds `new Analytics({ writeKey, flushInterval: 1, maxEventsInBatch: 1 })` with no host option. — [segment.client.ts](https://github.com/saleor/apps/blob/main/apps/segment/src/modules/segment/segment.client.ts)

### Inferences
- stripe-mock cannot stand in for Stripe in this company: the Stripe app needs state (create a PaymentIntent, later capture or refund the same one), needs Stripe to call back with signed webhooks, and pins an older API version while stripe-mock tracks only the latest. The existing custom stand-in is therefore justified; stripe-mock's value is as a schema check, and `stripe/openapi` fixtures plus `stripe-cli` trigger fixtures are the right permissive sources of realistic object and event shapes for that stand-in.
- An AvaTax stand-in is a small job on the app side (pass a URL through to the SDK's `environment` parameter, a one-line change behind an env var) and a moderate one on the server side: about eight endpoints (`ping`, create transaction, create-or-adjust, void, address resolve/validate, list tax codes, list entity use codes). It would be an invented server, though it mirrors a published REST contract.
- Stand-in effort ranking, lowest first: SMTP (configuration only, Mailpit) < CMS with self-hosted Payload (configuration only) < AvaTax (one-line app patch plus a mock) < Segment and Klaviyo (app patch to make the host configurable plus a trivial collector) < Algolia (the client derives hosts from the app id, so it needs a client patch plus a mock of the indexing API; no permissive, API-compatible engine was identified).
- Mailpit's REST API and chaos mode make it useful beyond delivery: tests can assert on rendered emails and tasks can involve SMTP failure handling.
- If DynamoDB Local's licence blocks redistribution inside an image, options are to pull it at run time rather than bake it in, to use `APL=file` where apps allow it (avatax, smtp, cms, segment, products-feed), or to test dynalite; dynalite's missing transaction support is a risk because the apps use `dynamodb-toolbox`.

### Gaps
- DynamoDB Local licence text: not found. Secondary sources mention an "Amazon DynamoDB Local License Agreement" and one gist claims redistribution is prohibited, but I could not reach the agreement itself ([Docker Hub page](https://hub.docker.com/r/amazon/dynamodb-local) states none). Must be read before baking the image into anything redistributed.
- Avalara sandbox behaviour (rate limits, whether a free sandbox account is still offered, data realism) was not confirmed from Avalara's own documentation; search results were third-party and disagreed on host names.
- Whether dynalite or another Apache-licensed emulator runs the apps' DynamoDB access patterns was not tested.
- Whether the Stripe and DynamoDB-only apps (stripe, np-atobarai) can run with `APL=file` only: source shows both a `dynamodb` case and a `FileAPL`, but configuration storage itself is DynamoDB-backed, so DynamoDB appears mandatory for them; not run.

## 4. Datasets: licences, sizes, and which are safe to redistribute in a commercial benchmark

### Takeaway
Safe, permissive and directly useful: Stripe's OpenAPI fixtures (MIT) and CLI event fixtures (Apache-2.0), Shopify's product taxonomy (MIT), Amazon Berkeley Objects listings (CC BY 4.0 per the official page), UCI Online Retail II (CC BY 4.0), EU VAT rates (MIT), Best Buy open data (CC0, old), Mailgun email templates (MIT) and Saleor's own sample data (BSD-3 code, CC-BY-4.0 artwork). Avoid Olist (reported non-commercial), treat Open Food Facts as share-alike, and treat OpenAddresses as per-source.

### Cited Findings

| Dataset | What it gives | Licence | Size | Redistribution verdict |
|---|---|---|---|---|
| Saleor `populatedb_data.json` | sample catalogue: 29 products, 81 variants, 34 attributes, 56 stock rows, 42 product media | repo licence BSD-3; artwork CC-BY-4.0 | 525 KB | safe with attribution |
| `stripe/openapi` `fixtures3.json` | one sample object per Stripe resource | MIT | 194 KB | safe |
| `stripe/stripe-cli` trigger fixtures | 128 scripted webhook event scenarios | Apache-2.0 | 129 KB directory listing; small JSON files | safe |
| Shopify product taxonomy | categories, attributes, values across "25+ verticals", versioned (2026-11) | MIT | release assets are gzipped JSON; repo 4.3 GB | safe |
| Amazon Berkeley Objects (ABO) | 147,702 product listings with multilingual title, brand, model, product type, colour, description, dimensions, weight, material, bullet points, keywords, image ids | CC BY 4.0 (official page) | listings 83 MB; small images 3 GB; originals 110 GB | safe with attribution; see conflict below |
| UCI Online Retail II | 1,067,371 invoice lines, UK online retailer, 2009-12-01 to 2011-12-09, 8 columns | CC BY 4.0 | 43.5 MB xlsx | safe with attribution |
| Best Buy open data set | products, categories, stores | CC0-1.0 | 12 MB repo; last push 2016 | safe; dated |
| `ibericode/vat-rates` | EU member-state VAT rates, community maintained JSON | MIT | under 1 MB | safe |
| `mirumee/google-i18n-address` | per-country address formats and validation rules | BSD-3-Clause | 2 MB | safe |
| OpenAddresses | street addresses worldwide | per-source licences; source definitions CC0; repo code BSD-3 | varies | only per-source after checking each licence |
| Open Food Facts | grocery products | ODbL database, Database Contents License for records, images CC BY-SA | large | share-alike: flag |
| Olist Brazilian e-commerce | about 100k orders 2016-2018 with payments, reviews, sellers | CC BY-NC-SA 4.0 (reported) | multi-CSV | exclude: non-commercial |
| Mailgun transactional email templates | HTML email templates | MIT | under 1 MB; last push 2022 | safe |
| `mjmlio/email-templates` | MJML templates | no licence detected | 8 MB | do not redistribute until clarified |
| `dbt-labs/jaffle-shop` + `jafgen` | synthetic shop data generator, up to 10 years | no licence detected for jaffle-shop | generator | do not redistribute repo content; generator output status unclear |
| Streamlined Sales Tax rate and boundary files | US state/local sales tax rates by jurisdiction, published per state (for example Kansas quarterly zip, 12.1 MB, 683,616 records) | government publications; no licence statement found | per state | likely usable, licence unconfirmed |

Sources: [saleor static data](https://github.com/saleor/saleor/tree/main/saleor/static), [stripe/openapi](https://github.com/stripe/openapi/tree/master/openapi), [stripe-cli triggers](https://github.com/stripe/stripe-cli/tree/master/pkg/fixtures/triggers), [Shopify/product-taxonomy README](https://github.com/Shopify/product-taxonomy/blob/main/README.md) and [GitHub API](https://api.github.com/repos/Shopify/product-taxonomy), [ABO official page](https://amazon-berkeley-objects.s3.amazonaws.com/index.html), [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii), [Best Buy open-data-set](https://api.github.com/repos/BestBuyAPIs/open-data-set), [ibericode/vat-rates README](https://github.com/ibericode/vat-rates/blob/master/README.md), [google-i18n-address](https://api.github.com/repos/mirumee/google-i18n-address), [OpenAddresses README](https://github.com/openaddresses/openaddresses/blob/master/README.md), [Open Food Facts ODbL page](https://wiki.openfoodfacts.org/ODBL_License), [Mailgun templates](https://api.github.com/repos/mailgun/transactional-email-templates), [mjmlio/email-templates](https://api.github.com/repos/mjmlio/email-templates), [jaffle-shop](https://api.github.com/repos/dbt-labs/jaffle-shop) and [README](https://github.com/dbt-labs/jaffle-shop/blob/main/README.md), [SST rate and boundary files](https://streamlinedsalestax.org/quick-links/r-b-files), [Kansas web services](https://www.ksrevenue.gov/webservices.html).

- ABO licence conflict: the dataset's own page says "licensed under the Creative Commons Attribution 4.0 International Public License (CC BY 4.0)"; an AWS Marketplace listing for the same dataset shows CC BY-NC 4.0. — [ABO official page](https://amazon-berkeley-objects.s3.amazonaws.com/index.html); contradicted by [AWS Marketplace listing](https://aws.amazon.com/marketplace/pp/prodview-ygocdgcstr7v2) (seen via search snippet)
- Olist's licence was found only on a third-party course page citing Kaggle as CC BY-NC-SA 4.0. — [course page](https://scripts-and-tables.github.io/daa/data/)
- OpenAddresses: "The data produced by the OpenAddresses processing pipeline ... is not relicensed from the original sources. Individual sources will have their own licenses." — [OpenAddresses README](https://github.com/openaddresses/openaddresses/blob/master/README.md)
- Open Food Facts: database under ODbL with share-alike on publicly used adapted databases; images under Creative Commons Attribution-ShareAlike. — [ODbL License wiki](https://wiki.openfoodfacts.org/ODBL_License)
- The SMTP app carries its own default MJML + Handlebars templates for every event it handles, under the repo's BSD-3 licence. — [apps/smtp](https://github.com/saleor/apps/tree/main/apps/smtp)

### Inferences
- A coherent data spine using only safe sources: Shopify taxonomy for categories and attribute names (also the natural mapping target for a product feed), ABO listings for product titles, brands, descriptions, weights and dimensions (the fields AvaTax, shipping and search all read), UCI Online Retail II for basket composition and order-timing distributions (it has no addresses or payments, so those are synthesised), Stripe fixtures for payment object and event shapes, the SMTP app's own templates for email, `google-i18n-address` for address validity, and `ibericode/vat-rates` for EU tax. Because one catalogue feeds core, search, CMS, the feed and tax codes, the same SKU appears in every owner's system, which is what makes cross-system tasks checkable.
- US sales tax by jurisdiction is the weakest link: the only bulk sources found are per-state government files with no explicit licence, and commercial rate tables. For an AvaTax stand-in, a small hand-built table for a few states, derived from public state publications, avoids the question.
- ABO images are large (3 GB even downscaled) and should be omitted or sampled; the 83 MB listings file is enough for catalogue realism.
- Attribution files are required for ABO, UCI and Saleor artwork (all CC BY 4.0).

### Gaps
- Olist licence not confirmed on the primary Kaggle page (not fetchable); excluded on the reported non-commercial term.
- ABO: the official page says CC BY 4.0, but the conflicting marketplace listing means the licence file inside `abo-listings.tar` should be read before redistribution.
- No licence statement found for Streamlined Sales Tax files, the Avalara free rate tables, or state revenue-department files.
- No permissively licensed real dataset of e-commerce orders with payment events and refunds was found; order and refund traffic will remain synthetic.
- I did not verify that Saleor core depends on `google-i18n-address`; it is listed as a data source on licence grounds only.
- Stripe-published test card and dispute scenarios (documentation pages) were not checked for licence.

## 5. Known pitfalls in running these together (version compatibility, required Saleor version per app)

### Takeaway
Saleor 3.23 is the only core minor version on which every app in the examined `saleor/apps` commit installs: stripe and onboarding need `>=3.23`, while smtp and products-feed stop at `<3.24`, and the local core clone is already `3.24.0-a.0`. Other recurring hazards are deprecated-but-needed apps, the lack of production Dockerfiles, DynamoDB as a hidden dependency, FileAPL being single-tenant, and hard-coded third-party hosts.

### Cited Findings
- Required Saleor version per app (from manifests): avatax, cms, search, segment, klaviyo, np-atobarai, anonymizer `>=3.22 <4`; stripe and onboarding `>=3.23 <4`; smtp and products-feed `>=3.22 <3.24`; dummy-payment-app and dummy-shipping-app declare none. — [saleor/apps/apps](https://github.com/saleor/apps/tree/main/apps), e.g. [smtp saleor-app.ts](https://github.com/saleor/apps/blob/main/apps/smtp/src/saleor-app.ts)
- Core `main` is `3.24.0-a.0`; dashboard `main` is `3.23.44`; apps monorepo fetches schema `3.23`; `saleor-platform` pins core and dashboard images to `3.23`. — [saleor pyproject.toml](https://github.com/saleor/saleor/blob/main/pyproject.toml), [dashboard package.json](https://github.com/saleor/saleor-dashboard/blob/main/package.json), [apps package.json](https://github.com/saleor/apps/blob/main/package.json), [saleor-platform compose](https://github.com/saleor/saleor-platform/blob/main/docker-compose.yml)
- Core enforces the range at install: `_clean_required_saleor_version` raises "Saleor version ... is not supported by the app" with code `UNSUPPORTED_SALEOR_VERSION` when the spec is not satisfied and enforcement is on. — [manifest_validations.py](https://github.com/saleor/saleor/blob/main/saleor/app/manifest_validations.py)
- app-sdk versions differ across repos: apps catalog 1.16.0, dashboard 1.15.0, app template 1.12.0, app-sdk head 1.17.0. — [apps pnpm-workspace.yaml](https://github.com/saleor/apps/blob/main/pnpm-workspace.yaml), [dashboard package.json](https://github.com/saleor/saleor-dashboard/blob/main/package.json), [template package.json](https://github.com/saleor/saleor-app-template/blob/main/package.json), [app-sdk package.json](https://github.com/saleor/app-sdk/blob/main/package.json)
- Node versions differ: apps monorepo and dashboard need Node 24; the app template needs Node `>=22 <23`; the SMTP README still says "node v22". pnpm differs: apps need `>=10 <11`, dashboard needs `>=11`. — [apps package.json](https://github.com/saleor/apps/blob/main/package.json), [dashboard package.json](https://github.com/saleor/saleor-dashboard/blob/main/package.json), [template package.json](https://github.com/saleor/saleor-app-template/blob/main/package.json), [smtp README](https://github.com/saleor/apps/blob/main/apps/smtp/README.md)
- SMTP and Products Feed are marked deprecated ("still works, but is no longer developed"), and both carry a deprecation cron (`CRON_SECRET`, `/api/cron/set-deprecation`, `/api/cron/report-deprecation`). — [smtp README](https://github.com/saleor/apps/blob/main/apps/smtp/README.md), [smtp .env.example](https://github.com/saleor/apps/blob/main/apps/smtp/.env.example), [products-feed .env.example](https://github.com/saleor/apps/blob/main/apps/products-feed/.env.example)
- FileAPL is single-tenant and "new registrations overwrite old ones"; the docs say not to use it in production. — [APL docs](https://docs.saleor.io/developer/extending/apps/developing-apps/app-sdk/apl)
- Networking: `.env.example` files document two URLs because the dashboard (browser) and core (container) reach an app differently: `APP_IFRAME_BASE_URL` and `APP_API_BASE_URL`. — [avatax .env.example](https://github.com/saleor/apps/blob/main/apps/avatax/.env.example)
- Several `.env.example` files include Saleor-Cloud-only settings ("This is Saleor Cloud-specific API. Do not use in self hosting"; stale-installation cleanup against `SALEOR_CLOUD_API_URL`). — [smtp .env.example](https://github.com/saleor/apps/blob/main/apps/smtp/.env.example), [search .env.example](https://github.com/saleor/apps/blob/main/apps/search/.env.example)
- Search and CMS initial/bulk sync run in the browser and need the app window open. — [Search app docs](https://docs.saleor.io/developer/app-store/apps/search), [CMS app docs](https://docs.saleor.io/developer/app-store/apps/cms)
- AvaTax app is inert for a channel until that channel's tax strategy is set to "use tax app". — [AvaTax app docs](https://docs.saleor.io/developer/app-store/apps/avatax/overview)
- CMS app supports Strapi v4 only. — [CMS app docs](https://docs.saleor.io/developer/app-store/apps/cms)
- saleor-platform README warns about migration problems after changing versions and describes resetting the database. — [saleor-platform README](https://github.com/saleor/saleor-platform/blob/main/README.md)

### Inferences
- Pin core and dashboard to the 3.23 line and take `saleor/apps` at a commit whose schema version is 3.23. If the company's core is already tracking `main` (3.24 alpha), the SMTP and products-feed apps will either be rejected at install or need their range edited; that edit is itself a realistic cross-owner task, but it should be a deliberate choice, not an accident of setup.
- Because the notification and feed apps are frozen upstream, they are stable mirrors (good for reproducibility) but will drift from core over time; their replacements are not available as source, so there is no upgrade path inside the benchmark.
- Running five or more Next.js apps plus core, worker, Postgres, Valkey, DynamoDB, Mailpit and stand-ins is memory-heavy; production `next build` output rather than dev servers, and one shared workspace image, will matter for start-up in minutes.
- Seeding must be scripted through GraphQL (app install, token exchange into the APL, channel tax strategy, app configuration stored encrypted with `SECRET_KEY`), because the first-party flows assume a human in the dashboard, including the browser-driven bulk syncs.
- Mixed app-sdk versions across dashboard, apps and template mean an app-sdk change is not atomic across owners, which is realistic but can produce confusing failures if the benchmark vendors a single copy.

### Gaps
- Whether a prerelease core version such as `3.24.0-a.0` is treated as satisfying `<3.24` by `RequiredSaleorVersionSpec` was not tested; semver ordering would place the alpha below 3.24.0, so the install might pass on the alpha and fail on the release.
- No end-to-end run of the combined stack was performed in this research; all compatibility statements are from manifests, package files and docs.
- Memory and start-up figures for the full stack were not measured.
- I did not check the published tags of `saleor/apps` to identify the last release of each app that predates deprecation notices or matches a given core tag.

# Commerce, billing and business-app ecosystems as sources of cross-repo RL tasks (excluding Saleor)

Research date: 18 Nov 2026. Method: LICENSE files read from raw.githubusercontent.com (HEAD). PR merge dates came from the GitHub search API or the PR pages. Diff sizes were computed by downloading `github.com/<repo>/pull/<n>.diff` and counting `diff --git` headers and +/- lines. "testfiles" means changed paths that match spec/test/__tests__/e2e. A limitation of this method: a diff can include merge noise. The unauthenticated GitHub API ran out of quota several times, so some counts are missing; those are listed under Gaps.

Ranking for our use (multi-repo, permissive or acceptable licence, 2026 activity, both sides add tests):
1. **Lago** (getlago/lago-api + lago-front). This is the closest analogue to Saleor: Rails GraphQL with a committed `schema.graphql`, plus a React/Apollo codegen front. Many same-day paired PRs in Nov 2026, with tests on both sides. Licence: AGPL-3.0.
2. **Spree** (spree/spree monorepo + spree/storefront). BSD-3 + MIT. The contract is the typed `@spree/sdk` npm package, version-pinned. Pairs are same day to several weeks apart.
3. **PrestaShop** (PrestaShop core + module repos such as ps_apiresources). OSL-3.0 + AFL-3.0. The contract is a composer pin of the module branch, and core CQRS commands are wrapped by API Platform resources in the module.
4. **Frappe + ERPNext + HRMS**. MIT + GPL-3. Very high volume, and dependencies are explicit ("requires frappe/frappe#…", minimum-version bumps).
5. **Kill Bill** (killbill + client-java/ruby + Kaui). All Apache-2.0 except Kaui (MIT). Low volume, but the server → client → UI chains are clean.
6. Monorepos (one repo, many packages): Medusa, Vendure, Shopware core, Twenty, Cal.com, Documenso, Plane, Chatwoot, WooCommerce. They are only usable as "cross-package" tasks, except that Shopware core + shopware/frontends are separate repos.

---

## Q1. Repos, languages, licences, and multi-repo vs monorepo

### Takeaway
Permissive and truly multi-repo: Spree (BSD-3 core + MIT storefront), Kill Bill (Apache-2.0), Shopware core + frontends (MIT), and the Frappe framework (MIT). ERPNext and HRMS are GPL-3. Lago is AGPL-3.0 on both api and front. Several former MIT projects have moved to restrictive licences: Vendure is now GPLv3/commercial, and Medusa now has proprietary Enterprise paths. Invoice Ninja (ELv2) and Akaunting (BSL) are source-available, not open source.

### Cited Findings
**Lago (billing).**
- getlago/lago-api (Ruby on Rails, GraphQL + REST): the LICENSE file is GNU AGPL v3 — [LICENSE](https://github.com/getlago/lago-api/blob/main/LICENSE)
- getlago/lago-front (React/TS, Vite, pnpm): the LICENSE file is GNU AGPL v3 — [LICENSE](https://github.com/getlago/lago-front/blob/main/LICENSE)
  - Its package.json says `"license": "MIT"` and points at a gitlab repository URL. This conflicts with the LICENSE file; trust the LICENSE file — [package.json](https://github.com/getlago/lago-front/blob/main/package.json)
- Client libraries are MIT: getlago/lago-python-client and lago-go-client — [python LICENSE](https://github.com/getlago/lago-python-client/blob/main/LICENSE), [go LICENSE](https://github.com/getlago/lago-go-client/blob/main/LICENSE)
- lago-api has a license-check/premium mechanism, for example PR #7132 "fix(license): retry the license check on transient errors" (merged 12 Nov 2026). Some features are premium-gated in code — [PR list](https://github.com/getlago/lago-api/pulls?q=is%3Apr+is%3Amerged)

**Spree.**
- spree/spree is BSD 3-Clause ("Copyright (c) 2024-present, Vendo…") — [LICENSE](https://github.com/spree/spree/blob/main/LICENSE)
- spree/spree is now a monorepo:
  - Ruby gems live under `spree/`.
  - A pnpm/turbo TS workspace lives under `packages/`. It contains `sdk`, `sdk-core`, `admin-sdk`, `seller-sdk`, `cli`, a React `dashboard`, `dashboard-core`, `dashboard-ui`, `seller-dashboard` and `create-spree-app`.
  - Source: GitHub contents API listing of `/packages` and the repo root (fetched 18 Nov 2026).
- spree/storefront (Next.js 16 / React 19) is MIT, "Copyright (c) 2026 Vendo Connect Inc." — [LICENSE](https://github.com/spree/storefront/blob/main/LICENSE)
- spree/spree-starter is MIT (2026) — [LICENSE.md](https://github.com/spree/spree-starter/blob/main/LICENSE.md)

**Solidus.**
- solidusio/solidus is a BSD-style licence (Spree heritage, "2015-2026 Solidus contributors") — [LICENSE](https://github.com/solidusio/solidus/blob/main/LICENSE)
- solidusio/solidus_starter_frontend is BSD-style ("Copyright (c) 2024 Nebulab") — [LICENSE](https://github.com/solidusio/solidus_starter_frontend/blob/main/LICENSE)

**Medusa.**
- medusajs/medusa is MIT except "Enterprise Edition materials identified in ENTERPRISE-LICENSE.md" — [LICENSE](https://github.com/medusajs/medusa/blob/develop/LICENSE)
- The Enterprise materials include RBAC and SSO, for example `packages/modules/rbac/`. They are proprietary and the notice applies prospectively — [ENTERPRISE-LICENSE.md](https://github.com/medusajs/medusa/blob/develop/ENTERPRISE-LICENSE.md)
- Medusa is a monorepo: backend, admin dashboard, js-sdk, types and modules all live under `packages/`. For example, PR #17795 is titled "feat(framework,medusa,types,js-sdk,audit)…" — [PR #17795](https://github.com/medusajs/medusa/pull/17795)
- medusajs/nextjs-starter-medusa is MIT — [LICENSE](https://github.com/medusajs/nextjs-starter-medusa/blob/main/LICENSE)

**Vendure.**
- The repo moved to the **vendurehq** org (`vendure-ecommerce/vendure` now fails GitHub search validation).
- LICENSE.md: "available under two different licenses: GPLv3 as Vendure Community Edition, Vendure Commercial License (VCL)". It is no longer MIT — [LICENSE.md](https://github.com/vendurehq/vendure/blob/master/LICENSE.md)
- It is a monorepo that includes the React dashboard (e.g. PR #5849 "fix(dashboard): …", merged 18 Nov 2026) — [PR #5849](https://github.com/vendurehq/vendure/pull/5849)

**Shopware.**
- shopware/shopware (PHP/Symfony + Vue Administration in one monorepo) is MIT ("Copyright 2019 shopware AG") — [LICENSE](https://github.com/shopware/shopware/blob/trunk/LICENSE)
- shopware/frontends (Vue/Nuxt composables, api-client, api-gen, and since Nov 2026 a React template POC) is MIT — [LICENSE](https://github.com/shopware/frontends/blob/main/LICENSE)

**Sylius and Bagisto.**
- Sylius/Sylius is MIT — [LICENSE](https://github.com/Sylius/Sylius/blob/2.1/LICENSE)
- bagisto/bagisto (Laravel) is MIT, "Copyright 2010-2025, Webkul" — [LICENSE](https://github.com/bagisto/bagisto/blob/master/LICENSE)

**PrestaShop.**
- Core is OSL-3.0 and modules are AFL-3.0 — [LICENSE.md](https://github.com/PrestaShop/PrestaShop/blob/develop/LICENSE.md)
- PrestaShop/ps_apiresources (the Admin API module, PHP / API Platform) is AFL-3.0 according to LICENSE.md and composer.json — [LICENSE.md](https://github.com/PrestaShop/ps_apiresources/blob/dev/LICENSE.md)

**WooCommerce.** GPL-2.0 according to license.txt. It is a monorepo; blocks were merged in, per prior knowledge — [license.txt](https://github.com/woocommerce/woocommerce/blob/trunk/license.txt)

**Magento.** magento/magento2 and magento/pwa-studio are both OSL-3.0 — [m2 LICENSE.txt](https://github.com/magento/magento2/blob/2.4-develop/LICENSE.txt), [pwa LICENSE.txt](https://github.com/magento/pwa-studio/blob/develop/LICENSE.txt)

**Kill Bill.**
- killbill/killbill, killbill-api and killbill-client-java are Apache-2.0 — [killbill LICENSE](https://github.com/killbill/killbill/blob/master/LICENSE), [client-java LICENSE](https://github.com/killbill/killbill-client-java/blob/master/LICENSE)
- Kaui now lives at **killbill/killbill-admin-ui** (Rails engine). Its licence file is MIT-LICENSE; the text visible in the first bytes is the Rails-template MIT with "Copyright 2012 YOURNAME" — [MIT-LICENSE](https://github.com/killbill/killbill-admin-ui/blob/master/MIT-LICENSE)

**Odoo.** odoo/odoo is LGPL-3 — [LICENSE](https://github.com/odoo/odoo/blob/master/LICENSE). Odoo Enterprise is a private repo (not accessible), so it is unusable for us.

**Frappe, ERPNext, HRMS.**
- frappe/frappe is MIT — [LICENSE](https://github.com/frappe/frappe/blob/develop/LICENSE)
- frappe/erpnext is GPL-3 — [license.txt](https://github.com/frappe/erpnext/blob/develop/license.txt)
- frappe/hrms is GPL-3 — [license.txt](https://github.com/frappe/hrms/blob/develop/license.txt)

**Twenty.** AGPL-3 except files marked `/* @license Enterprise */` (commercial). The SDK/CLI/twenty-ui/twenty-shared/twenty-apps packages are MIT. It is a monorepo — [LICENSE](https://github.com/twentyhq/twenty/blob/main/LICENSE)

**Cal.com.**
- calcom/cal.com LICENSE is now MIT.
- The README at HEAD describes the project as "Cal.diy … 100% MIT-licensed with no proprietary Enterprise Edition features" and contrasts it with "Cal.com's Open Core model". The repository appears to have been repurposed or re-licensed. This is surprising and should be re-checked before use — [LICENSE](https://github.com/calcom/cal.com/blob/main/LICENSE), [README](https://github.com/calcom/cal.com/blob/main/README.md)
- It is a monorepo.

**Documenso, Plane, Chatwoot.**
- documenso/documenso is AGPL-3 (monorepo) — [LICENSE](https://github.com/documenso/documenso/blob/main/LICENSE)
- makeplane/plane is AGPL-3 — [LICENSE.txt](https://github.com/makeplane/plane/blob/preview/LICENSE.txt)
- chatwoot/chatwoot is MIT-style, with the `enterprise/` directory under a separate enterprise licence — [LICENSE](https://github.com/chatwoot/chatwoot/blob/develop/LICENSE)

**Invoice Ninja.**
- invoiceninja/invoiceninja (Laravel API) is Elastic License 2.0 — [LICENSE](https://github.com/invoiceninja/invoiceninja/blob/v5-stable/LICENSE)
- The React web client is now **invoiceninja/web**, formerly `invoiceninja/ui`. It is also ELv2 — [LICENSE](https://github.com/invoiceninja/web/blob/develop/LICENSE)
- invoiceninja/admin-portal (Flutter) uses an "Attribution Assurance License (adapted from BSD)" — [LICENSE.txt](https://github.com/invoiceninja/admin-portal/blob/master/LICENSE.txt)

**Akaunting and Dolibarr.**
- akaunting/akaunting is Business Source License (MariaDB BSL) — [LICENSE.txt](https://github.com/akaunting/akaunting/blob/master/LICENSE.txt)
- Dolibarr/dolibarr is GPL-3 — [COPYING](https://github.com/Dolibarr/dolibarr/blob/develop/COPYING)

### Inferences
- Truly multi-repo and permissive: Spree core ↔ storefront, Kill Bill server ↔ clients ↔ Kaui, Shopware core ↔ frontends, Frappe ↔ ERPNext/HRMS (ERPNext/HRMS are GPL-3), and PrestaShop core ↔ modules (OSL/AFL, both OSI-approved copyleft-ish/permissive).
- Lago is multi-repo but AGPL on both sides. That is fine if we never distribute modified binaries as a network service, but legal should approve.
- Medusa and Vendure licence drift means we must pin to the licence at the task's commit. Medusa tasks should avoid the RBAC/SSO paths. Vendure is GPLv3 for all versions after the re-licence.
- Exclude Invoice Ninja (ELv2) and Akaunting (BSL) unless source-available licences are acceptable. Odoo Enterprise is not accessible.

### Gaps
- I did not read the Kaui MIT-LICENSE beyond its first 200 bytes. The full licences of PrestaShop modules other than ps_apiresources, and the PWA Studio activity level, were not checked.
- I did not read the full list of Medusa enterprise paths (only RBAC/SSO, `packages/modules/rbac/`, were seen).
- The Cal.com "Cal.diy" situation was not investigated further.

---

## Q2. How the contract between repos is defined

### Takeaway
- **Lago:** lago-api commits a generated `schema.graphql`. lago-front generates `src/generated/graphql.tsx` with graphql-codegen from a live API URL (`${CODEGEN_API}`), not from a vendored copy. For tasks, we can point codegen at the api repo's `schema.graphql` file.
- **Spree:** the contract is the `@spree/sdk` npm package (built in the spree monorepo from OpenAPI / Typelizer). The storefront pins it with a semver range.
- **PrestaShop:** a composer.lock pin of the module branch, plus a strict endpoint list in core UI tests.
- **Frappe:** the minimum frappe version in ERPNext's dependency declaration.
- **Kill Bill:** a REST API, consumed by released client gems/jars.

### Cited Findings
**Lago.**
- lago-api root contains `schema.graphql` (starting `schema { query: Query mutation: Mutation subscription: GraphqlSubscription }`) — [schema.graphql](https://github.com/getlago/lago-api/blob/main/schema.graphql)
- lago-front `codegen.yml`: `schema: - ${CODEGEN_API} - './src/core/apolloClient/graphqlResolvers.tsx'`, generating `src/generated/graphql.tsx` with typescript / typescript-operations / typescript-react-apollo — [codegen.yml](https://github.com/getlago/lago-front/blob/main/codegen.yml)

**Spree.**
- The storefront depends on `"@spree/sdk": "^6.0.5"`. The SDK is "an official typed client for every Store API endpoint (OpenAPI 3.0 documented)… no codegen step" — [package.json](https://github.com/spree/storefront/blob/main/package.json), [README](https://github.com/spree/storefront/blob/main/README.md)
- Storefront PRs regularly bump the SDK pin: #314 "Updated @spree/sdk to ^6.0.5" (16 Nov 2026), #307 (^6.0.4), #301 (^6.0.3), #278 (^6.0.0, 27 Oct 2026), and #260 "Updated @spree/sdk to 2.0.0-rc.3 and removed deprecated API usage" (13 Oct 2026) — [storefront PR list](https://github.com/spree/storefront/pulls?q=is%3Apr+is%3Amerged)
- Spree generates its OpenAPI with Typelizer: #15258 "Replaced OpenAPI schema patches with Typelizer inline shapes" and #15256 (17 Nov 2026) — [spree PRs](https://github.com/spree/spree/pulls?q=is%3Apr+is%3Amerged)
- Spree PR #14527 touches `packages/cli/src/generated/admin-spec.json`, so a generated spec is committed inside the monorepo — [PR #14527 diff](https://github.com/spree/spree/pull/14527)

**PrestaShop.** Core PR #43563 "moves the core's ps_apiresources pin from the `dev-os-165-store-create-edit` branch back to upstream `dev-dev`". The composer.lock change touches only `prestashop/ps_apiresources`. It adds expected endpoints to `tests/UI/campaigns/functional/API/02_checkEndpoints.ts`, which "compares the OpenAPI paths against the expected endpoint list" — [PR #43563](https://github.com/PrestaShop/PrestaShop/pull/43563)

**Frappe.** ERPNext PR #63977 "fix: require frappe v16.55.0 for pypika permission query conditions". It depends on frappe/frappe#45814 and #45827, which added pypika-term support in `permission_query_conditions` — [PR #63977](https://github.com/frappe/erpnext/pull/63977)

**Kill Bill.** Kaui PR #675 uses `GET /1.0/kb/security/roles` (Kill Bill ≥0.25) and depends on killbill-client-ruby #124 (`RoleDefinition.find_all`). CI used the released killbill-client gem 4.0.9, which lacked `find_all`, causing a `NameError` — [Kaui PR #675](https://github.com/killbill/killbill-admin-ui/pull/675)

**Shopware frontends.** It has an `api-gen` package; #2874 "feat(api-gen): generate open string enums with autocompletion" (12 Nov 2026) and #2708 "feat: stop committing generated API types in examples and templates" (8 Sep 2026). frontends PR #2785 added CMS block types by hand (`cmsElementTypes.ts`), with no core schema sync mentioned — [frontends PRs](https://github.com/shopware/frontends/pulls?q=is%3Apr+is%3Amerged+api-types), [PR #2785](https://github.com/shopware/frontends/pull/2785)

### Inferences
- **Lago** is the best fit for a Saleor-style contract: the provider's `schema.graphql` is diffable. We would vendor a copy into the front container and set `CODEGEN_API` to the file path, so the front's generated types are a checkable artefact.
- **Spree:** the contract artefact is the SDK package inside the provider repo. A task's "frontend" start state must use a locally built SDK (pnpm link / pkg.pr.new; Spree added preview package publishing in #15253) instead of npm.
- **PrestaShop/Frappe:** the contract is a version pin. The consumer's tests run against the provider's checked-out branch, so cross-container coupling is code-level, not schema-level.

### Gaps
- I could not list shopware/frontends `packages/api-client/api-types` (API rate limit), so whether it vendors core's `storeApiSchema.json` is unverified.
- The source of lago-front's `CODEGEN_API` in CI was not checked.

---

## Q3. Concrete cross-repo features (PR pairs, dates, sizes, tests)

### Takeaway
- **Lago** has at least three Nov-2026 multi-PR features where api and front PRs merged within 0–4 days. Each has 1–7k lines per side and spec/jest tests on both sides.
- **Spree** has same-day pairs (company addresses) and staggered pairs (PO number, about 11 weeks apart).
- **PrestaShop** has a store-API chain from core to module (Sep–Nov 2026).
- **Frappe/ERPNext** has a large breaking-change feature that depends on four frappe PRs.
- **Kill Bill** has a roles chain across three repos (Aug–Oct 2026).

### Cited Findings (sizes = files / +add / −del / test files, computed from the `.diff`)

**Lago A – Standard Webhooks signing (Nov 2026)**
- lago-api side:
  - #7075 "feat(webhooks): Sign deliveries with Standard Webhooks". Merged 13 Nov 2026. 30 files, +1437/−60, 16 spec files — [PR](https://github.com/getlago/lago-api/pull/7075)
  - #7076 "Expose signing keys on GraphQL webhook endpoints". Merged 13 Nov. 16 files, +454/−5, 8 specs — [PR](https://github.com/getlago/lago-api/pull/7076)
  - #7077 "Return signing keys in the v1 endpoints API". Merged 13 Nov. 16 files, +600/−43, 10 specs — [PR](https://github.com/getlago/lago-api/pull/7077)
  - #7078 "Add signing_keys expansion to v2 webhook endpoints". Merged 13 Nov. 6 files, +530/−6, 3 specs — [PR](https://github.com/getlago/lago-api/pull/7078)
  - #7186 "Allow Standard Webhooks signing for every organization". Merged 17 Nov 2026 11:03Z. 11 files, +209/−271 — [PR](https://github.com/getlago/lago-api/pull/7186)
- lago-front side:
  - #4678 "feat(webhooks): Choose Standard Webhooks and show its signing key". Merged 13 Nov 2026 14:33Z. 12 files, +868/−117, 4 jest tests (e.g. `WebhookForm.test.tsx`) — [PR](https://github.com/getlago/lago-front/pull/4678)
  - #4689 "Show Standard Webhooks to every organization". Merged 17 Nov 2026 11:03Z, 17 seconds after api #7186. 3 files, +34/−83 — [PR](https://github.com/getlago/lago-front/pull/4689)

**Lago B – Sandbox organizations (16–18 Nov 2026)**
- lago-api side:

  | PR | Title | Merged | Files | +/− | Spec files |
  |---|---|---|---|---|---|
  | [#7082](https://github.com/getlago/lago-api/pull/7082) | add environment, self-serve flag and sandbox link | 16 Nov | 15 | +391/−36 | 8 |
  | [#7083](https://github.com/getlago/lago-api/pull/7083) | feat(graphql): expose organization environment and sandbox pair | 16 Nov | 21 | +792/−2 | 11 |
  | [#7084](https://github.com/getlago/lago-api/pull/7084) | create self-serve production and sandbox pairs | 16 Nov | 17 | +834/−20 | 9 (incl. `spec/scenarios/organizations/sandbox_api_key_isolation_spec.rb`) |
  | [#7085](https://github.com/getlago/lago-api/pull/7085) | mirror production members and roles to the sandbox | 16 Nov | 38 | +1081/−67 | 15 |
  | [#7086](https://github.com/getlago/lago-api/pull/7086) | sync sandbox premium features and login methods | 16 Nov | 34 | +988/−96 | 14 |
  | [#7088](https://github.com/getlago/lago-api/pull/7088) | link an existing organization as a sandbox | 16 Nov | 25 | +1033/−53 | 7 |
  | [#7210](https://github.com/getlago/lago-api/pull/7210) | drop production-managed permissions on sandbox members | 17 Nov 16:44Z | 3 | +122 | – |

  API total: about 5.2k added lines across about 150 files.
- lago-front side:

  | PR | Title | Merged | Files | +/− | Tests |
  |---|---|---|---|---|---|
  | [#4652](https://github.com/getlago/lago-front/pull/4652) | Offer self-serve with sandbox in the CS admin create form | 16 Nov | 17 | +1998/−84 | 7 |
  | [#4654](https://github.com/getlago/lago-front/pull/4654) | Add a link-as-sandbox action in the CS admin | 16 Nov | 11 | +1202/−15 | 4 |
  | [#4650](https://github.com/getlago/lago-front/pull/4650) | Show the sandbox indicator and keep its managed settings read-only | 17 Nov 16:31Z | 33 | +1803/−130 | 14 |
  | [#4649](https://github.com/getlago/lago-front/pull/4649) | List the sandbox next to its production in the account menu | 18 Nov | 4 | +350/−24 | 1 |

  Front total: about 5.3k added lines.

**Lago C – Self-serve signup Step 3 (Nov 2026)**
- lago-api #7105 "feat(signup): create the organization pair at signup Step 3 [ING-838]". Merged 16 Nov 2026. 12 files, +765/−1, 2 specs — [PR](https://github.com/getlago/lago-api/pull/7105)
- lago-api #7106 "send the signup Step 3 answers to analytics". Merged 17 Nov. 12 files, +217/−22, 6 specs — [PR](https://github.com/getlago/lago-api/pull/7106)
- lago-front #4662 "feat(signup): build the Step 3 create your organization form". Merged 17 Nov 2026. 10 files, +1297/−5, 4 tests — [PR](https://github.com/getlago/lago-front/pull/4662)
- lago-front also has #4611–#4622 (signup Steps 1–3, region choice, reCAPTCHA, Google), merged 6–10 Nov 2026 — [front PR list](https://github.com/getlago/lago-front/pulls?q=is%3Apr+is%3Amerged+feat+merged%3A2026-08-01..2026-11-18)

**Lago D – in progress (as of 18 Nov 2026)**
- QuickBooks integration api PRs #7194/#7205/#7206 were open, not merged, on 18 Nov 2026 — [api PR list](https://github.com/getlago/lago-api/pulls?q=is%3Apr+is%3Amerged+webhook+OR+sandbox+OR+signup+merged%3A2026-09-15..2026-11-18)
- The catalog-wallets api series #7121–#7128 (17 Nov 2026) has no front PR found yet — [search](https://github.com/getlago/lago-api/pulls?q=catalog-wallets)
- These are candidates for future mining.

**Spree A – Company users use company addresses (same day)**
- spree/spree #14911 "Allow company users to use company addresses". Merged 22 Oct 2026 07:56Z. 86 files, +2424/−462, 13 test files: rspec api/v3 store + admin controller specs, and dashboard Playwright `packages/dashboard/e2e/companies.spec.ts` — [PR](https://github.com/spree/spree/pull/14911)
- spree/storefront #268 (same title). Merged 22 Oct 2026 14:09Z. 14 files, +537/−76, 2 vitest files (`AddressSelector.test.ts`, `companies.test.ts`) — [PR](https://github.com/spree/storefront/pull/268)

**Spree B – Buyer purchase-order number (staggered)**
- spree/spree #14527 "Add the buyer's purchase order reference to carts and orders". Merged 31 Aug 2026. 73 files, +1852/−51, 18 test files (api/v3 controller specs, dashboard e2e, `admin-spec.json`) — [PR](https://github.com/spree/spree/pull/14527)
- spree/storefront #306 "Add PO number to checkout, order summary, order details page". Merged 16 Nov 2026. 14 files, +672/−9, 3 vitest files — [PR](https://github.com/spree/storefront/pull/306)
- Follow-up: spree #15247 "Kept the purchase order number and document when copying a cart into a draft order", merged 17 Nov 2026 — [PR](https://github.com/spree/spree/pull/15247)

**Spree C – Marketplace sellers and collections (backend in Spree 6.0, front in Nov)**
- storefront #297 "V-3669 Added seller directory and profile pages for marketplace builds". Merged 4 Nov 2026. 33 files, +1757/−141, 4 test files. It uses "the Spree 6.0 SDK's `sellers` endpoints" and the description reports `pnpm test` at 308 passing — [PR](https://github.com/spree/storefront/pull/297)
- storefront #300 "Added collection pages, collections in search, navigation and home page". Merged 5 Nov 2026. 36 files, +1920/−431, 6 test files incl. Playwright `e2e/catalog.spec.ts` — [PR](https://github.com/spree/storefront/pull/300)
- spree #15216 "Added branding, social and email fields to the Store API's current store" merged 14 Nov 2026. storefront #308 "Fetched the store name, SEO title and meta description from the Store API" merged 13 Nov 2026. The order of these is ambiguous — [spree PRs](https://github.com/spree/spree/pulls?q=is%3Apr+is%3Amerged), [storefront PRs](https://github.com/spree/storefront/pulls?q=is%3Apr+is%3Amerged)

**PrestaShop – Store CRUD via Admin API (core ↔ ps_apiresources)**
- Core #41414 "Migration of the Stores controller to Symfony" adds `AddStoreCommand` / `EditStoreCommand`. Merged 30 Sep 2026. 53 files, +3948/−336, 9 test files (Behat `store.feature`, `StoreFeatureContext.php`) — [PR](https://github.com/PrestaShop/PrestaShop/pull/41414)
- Core #43540 (latitude/longitude range checks returning 422). Merged 16 Nov 2026. 13 files, +206/−28, 4 test files — [PR](https://github.com/PrestaShop/PrestaShop/pull/43540)
- ps_apiresources #459 "Add the store creation and partial update endpoints". Merged 18 Nov 2026 10:35Z. 6 files, +931/−130, integration tests `StoreEndpointTest.php` and `StoreMultiShopEndpointTest.php`. It requires core #41414 and #43540 — [PR](https://github.com/PrestaShop/ps_apiresources/pull/459)
- Core #43563 re-pins the module and adds the expected endpoints. Merged 18 Nov 2026 — [PR](https://github.com/PrestaShop/PrestaShop/pull/43563)
- Another likely pair: ps_apiresources #457 "Add the product feature values endpoints, rely on the core for array item types, DELETE bodies…" (16 Nov 2026) — [module PRs](https://github.com/PrestaShop/ps_apiresources/pulls?q=is%3Apr+is%3Amerged)

**Frappe ↔ ERPNext**
- ERPNext #59049 "feat(stock)!: allow shared serial and batch numbers across items". Merged 1 Oct 2026. 134 files, +7089/−2343, 44 test files. It lists dependent frappe PRs:
  - #43391 "link titles for select permission" (merged)
  - #42785 (print preview), #43389 (Report Builder child table columns) and #43615 (no hash names under link titles); the status of these three was not stated on the page
  - Source: [PR](https://github.com/frappe/erpnext/pull/59049)
- frappe #45814 (4 files, +107/−2, tests in `frappe/tests/test_db_query.py` and `test_query.py`) and frappe #45827 (6 files, +97/−24, same tests). ERPNext #63977 then raised the minimum Frappe version to 16.55.0 (1-line change, merged 4 Nov 2026) because ERPNext hooks returned pypika terms — [frappe #45814](https://github.com/frappe/frappe/pull/45814), [frappe #45827](https://github.com/frappe/frappe/pull/45827), [erpnext #63977](https://github.com/frappe/erpnext/pull/63977)
- From June to 18 Nov 2026, 364 merged non-backport ERPNext PRs mention "frappe/frappe#" in the body. 15 `feat` PRs from Mar to Nov 2026 link "frappe/frappe/pull", e.g.:
  - #59691 standard list layouts (30 Sep; 106 files, +2226, no tests)
  - #59766 onboardings/sidebars (4 Oct; 172 files, +5375/−4362)
  - #56304 faster financial statements using duckdb (25 Jun 2026)
  - Source: GitHub search API, 18 Nov 2026
- HRMS ↔ ERPNext: 29 hrms PRs from Jun to Nov 2026 reference "frappe/erpnext#". Examples: #5443 "Employee Overview dashboard…" (19 Oct 2026; 11 files, +1706, 1 test) and #5662 "test: align org chart and income tax tests with erpnext employee validation" (17 Nov 2026) — [hrms #5443](https://github.com/frappe/hrms/pull/5443), [hrms #5662](https://github.com/frappe/hrms/pull/5662)

**Kill Bill – role listing (Aug–Oct 2026)**
- killbill-client-java #159 "implements killbill/killbill#2250 - `SecurityAPI.getAvailableRoles()`". Merged 5 Aug 2026. 5 files, +5640/−5862. It is mostly generated client code with no test files. Note that killbill/killbill#2250 is an issue, not a PR — [PR](https://github.com/killbill/killbill-client-java/pull/159)
- killbill-client-ruby #124 adds `RoleDefinition.find_all` (merge date not verified) — [Kaui #675 page](https://github.com/killbill/killbill-admin-ui/pull/675)
- Kaui (killbill-admin-ui) #675 "Add roles management screens (list and edit roles)". Merged 29 Oct 2026. 11 files, +391/−5, 1 functional test (9 tests / 44 assertions, run against a live Kill Bill 0.25.4) — [PR](https://github.com/killbill/killbill-admin-ui/pull/675)

**Invoice Ninja (source-available, ELv2)**
- invoiceninja #13461 "Support exporting .xml from reports" merged 16 Nov 2026. The diff shows 28 files and +21,974 lines, which includes unrelated e-invoice fixtures, so it is a noisy develop-branch PR.
- web #3476 "[Feature] Attach XML Option For Invoice Report" merged 17 Nov 2026. 3 files, +14, no tests. No cross-link between the two.
- Sources: [api PR](https://github.com/invoiceninja/invoiceninja/pull/13461), [web PR](https://github.com/invoiceninja/web/pull/3476)

**Medusa (monorepo, cross-package)**
- #17795 "feat(framework,medusa,types,js-sdk,audit): record API requests as audit logs". Merged 13 Nov 2026. 50 files, +2163/−50, 6 test files incl. `integration-tests/http/__tests__/audit/admin/audit-logs.spec.ts` — [PR](https://github.com/medusajs/medusa/pull/17795)
- #17778 "feat: Redesign permissions UI". Merged 12 Nov 2026. 41 files, +5231/−558. It touches RBAC, which is Enterprise-licensed — [PR](https://github.com/medusajs/medusa/pull/17778)

**Shopware frontends**
- #2785 "feat(cms): implement new CMS blocks and elements with updated types" merged 5 Oct 2026, with 3 new vitest files. It supports core blocks added "since 6.6", so it is not a close-in-time pair — [PR](https://github.com/shopware/frontends/pull/2785)

### Inferences
- Lago features are developed as stacks of small PRs merged the same day in both repos (ticket IDs ING-8xx tie them together). A task = the union of all api PRs and all front PRs for one ticket group. That yields Saleor-sized tasks (5k + 5k lines) with dozens of spec files as hidden tests.
- Spree's same-day pairs are the cleanest permissive option. Staggered pairs (PO number) need the frontend start state to be "backend feature already released", which is weaker as a joint task.
- PrestaShop and Frappe dependencies are often provider-first, with weeks between parts. The close-in-time parts are smaller (e.g. #43540 + #459 + #43563 within 3 days).

### Gaps
- Not verified: merge dates and sizes for frappe #43391/#45814/#45827, killbill-client-ruby #124, and the Kill Bill server-side change for #2250.
- I did not find concrete 2026 pairs for Sylius, Bagisto, Solidus, Vendure, Twenty, Plane, Chatwoot, Documenso, Odoo, Magento/PWA Studio or WooCommerce (not searched in depth because of API quota). Most of them are monorepos anyway.
- No Medusa backend ↔ nextjs-starter pairs: the starter had only 4 merged PRs in 2026.

---

## Q4. Test suites and Docker runnability

### Takeaway
Every strong candidate needs a database in its test container:
- Lago: Postgres (partman) + Redis + ClickHouse.
- Spree: Postgres/SQLite + Chrome for dashboard e2e.
- Frappe: MariaDB/Postgres + Redis + bench.
- PrestaShop: MySQL.
- Kill Bill Kaui: a running Kill Bill server.

Frontend suites are mostly unit tests (jest/vitest + RTL) that are coupled to the implementation (test IDs, component files), plus optional Playwright e2e that needs the backend.

### Cited Findings
**Lago.**
- lago-api `spec.yml` runs RSpec in a 10-node matrix (`ci_node_total: [10]`). Services: `getlago/postgres-partman:15.0-alpine` and redis, with `LAGO_CLICKHOUSE_ENABLED: true` (ClickHouse required) — [spec.yml](https://github.com/getlago/lago-api/blob/main/.github/workflows/spec.yml)
- Spec files are organised as graphql/mutations, resolvers, requests (v1/v2), services and scenarios — see the file lists of [#7075](https://github.com/getlago/lago-api/pull/7075) and [#7084](https://github.com/getlago/lago-api/pull/7084)
- lago-front tests live in `__tests__/*.test.tsx` (jest/RTL) and it has Cypress (lint script covers `cypress/**/*.ts`) — [package.json](https://github.com/getlago/lago-front/blob/main/package.json), [PR #4650](https://github.com/getlago/lago-front/pull/4650)

**Spree.**
- The storefront uses `vitest run`, Playwright `test:e2e`, and `e2e:up` = `docker compose -f e2e-backend/docker-compose.yml up -d --wait && ./scripts/e2e/bootstrap-spree.sh` — [package.json](https://github.com/spree/storefront/blob/main/package.json)
- The unit suite had 308 passing tests at PR #297 (4 Nov 2026) — [PR #297](https://github.com/spree/storefront/pull/297)
- spree/spree uses rspec under `spree/api/spec/...` and Playwright dashboard e2e under `packages/dashboard/e2e/` — [PR #14911](https://github.com/spree/spree/pull/14911)

**Frappe.** ERPNext CI runs the full suite "on MariaDB and PostgreSQL"; #59049 shows 25 checks — [PR #59049](https://github.com/frappe/erpnext/pull/59049)

**PrestaShop.**
- Core has Behat integration tests (`tests/Integration/Behaviour/Features/Scenario/...`), PHPUnit unit tests, and Playwright-based UI campaigns in `tests/UI` — [PR #41414](https://github.com/PrestaShop/PrestaShop/pull/41414), [PR #43563](https://github.com/PrestaShop/PrestaShop/pull/43563)
- ps_apiresources runs PHPUnit integration tests against an installed core (`tests/Integration/ApiPlatform/*EndpointTest.php`), with multiple core-version CI legs (9.0.3/9.1.5/9.2.x) — [PR #459](https://github.com/PrestaShop/ps_apiresources/pull/459), [PR #460](https://github.com/PrestaShop/ps_apiresources/pull/460)

**Kill Bill.**
- Kaui functional tests need a live Kill Bill 0.25.4 on Tomcat 11, with lowered bus polling intervals to avoid 408s — [PR #675](https://github.com/killbill/killbill-admin-ui/pull/675)
- killbill core CI had "e2e startup timeout" fixes (#2336, 12 Nov 2026) — [PR #2336](https://github.com/killbill/killbill/pull/2336)

**Medusa.** Integration tests live under `integration-tests/http/__tests__/...`; admin dashboard unit specs are `*.spec.tsx` — [PR #17778](https://github.com/medusajs/medusa/pull/17778)

### Inferences
- **Lago:** run per-PR targeted spec files (the hidden tests) instead of the full 10-shard suite, with Postgres + Redis + ClickHouse sidecars in the api container. The regression guard should be a sampled subset, because the full suite is too slow for one container.
- **Spree storefront:** vitest only (offline, fast). Playwright e2e needs the backend, so it would be a cross-container integration check, which is useful but heavy.
- **Kill Bill / Kaui:** tests need a live server, so the env needs a Kill Bill container. That is heavier.

### Gaps
- No measured runtimes or total test counts for any suite except the storefront's 308 unit tests; this needs local runs.
- lago-front test runner (jest vs vitest) not confirmed.

---

## Q5. Activity level in 2026 and estimated minable features per year

### Takeaway
By merged-PR volume (1 Jan–18 Nov 2026), the most active ecosystems are Shopware, ERPNext/Frappe, Lago, Medusa and Spree. Lago and Spree produce about 1 multi-PR cross-repo feature per week or two. Kill Bill produces a handful per year.

### Cited Findings
Merged PRs, 1 Jan – 18 Nov 2026 (GitHub search API `is:pr is:merged`, queried 18 Nov 2026):

| Repo | Merged PRs |
|---|---|
| getlago/lago-api | 1915 |
| getlago/lago-front | 1595 |
| spree/spree | 1470 |
| spree/storefront | 183 (63 non-dependabot from Jul–Nov) |
| medusajs/medusa | 1841 |
| medusajs/nextjs-starter-medusa | 4 |
| shopware/shopware | 4247 |
| shopware/frontends | 349 |
| frappe/frappe | 7769 (includes backports) |
| frappe/erpnext | 9017 (includes backports) |
| frappe/hrms | 1146 |
| vendurehq org | 1431 |
| PrestaShop/PrestaShop | 951 |
| PrestaShop/ps_apiresources | 91 |
| Sylius/Sylius | 444 |
| solidusio/solidus | 239 |
| bagisto/bagisto | 221 |
| invoiceninja/invoiceninja | 231 |
| invoiceninja org | 760 |
| killbill/killbill | 55 |
| killbill org | 504 |
| killbill-client-java | 17 |
| killbill-admin-ui | 43 |

- Source: [GitHub search API](https://docs.github.com/en/rest/search/search#search-issues-and-pull-requests) queries such as `repo:getlago/lago-api is:pr is:merged merged:2026-01-01..2026-11-18`
- 154 `feat` PRs were merged in lago-front between 1 Aug and 18 Nov 2026 — [front PR search](https://github.com/getlago/lago-front/pulls?q=is%3Apr+is%3Amerged+feat+merged%3A2026-08-01..2026-11-18)
- Spree released 6.0.0 around late Oct 2026 (storefront #278 "Updated @spree/sdk to ^6.0.0", 27 Oct) and 6.0.5 on 16 Nov 2026 (#15233) — [storefront PRs](https://github.com/spree/storefront/pulls?q=is%3Apr+is%3Amerged), [spree #15233](https://github.com/spree/spree/pull/15233)
- ERPNext ships v16 hotfix releases (e.g. "chore: version 16.60", #66740, 14 Nov 2026) — [PR #66740](https://github.com/frappe/erpnext/pull/66740)

### Inferences
These estimates are not measured; they are extrapolated from the samples above.

| Ecosystem | Estimated cross-repo features per year | Basis |
|---|---|---|
| Lago | about 30–60 | Three distinct multi-PR features in one sampled week of Nov 2026; about 150 front `feat` PRs per quarter |
| Spree | about 15–30 | Most storefront features map to a spree core/API change; about 180 storefront PRs per year |
| Frappe/ERPNext/HRMS | about 50+ | Hundreds of explicit cross-refs, but most are small fixes or version bumps |
| PrestaShop core ↔ ps_apiresources | about 10–20 | About 90 module PRs per year |
| Kill Bill | under 5 | |
| Shopware core ↔ frontends | Unknown; likely low and loosely timed | frontends catches up to core features later |

### Gaps
- No release cadence collected for Lago (tags) or Medusa.
- Frappe/ERPNext counts include automated backport PRs, so real feature volume is lower.

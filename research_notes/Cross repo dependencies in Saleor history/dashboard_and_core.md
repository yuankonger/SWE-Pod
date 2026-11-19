# Dashboard changes that depended on, lagged or conflicted with core and apps (Saleor, to Nov 2026)

Method and verification legend (applies to every bullet):

- **[git]** = read in the local full-history clones (dashboard HEAD `513686a`, 2026-11-13; core HEAD `6f714fa`, 2026-11-12; apps HEAD `f001ac7`, 2026-10-28): commit message, changeset text, diffstat. The PR number comes from the squash-commit subject; the PR URL is built from it and **the PR web page was not opened** unless also tagged [web].
- **[web]** = the GitHub PR or issue page was opened and read.
- **[POST-JUNE-2026]** = dated after 30 June 2026. These rest on the local clones only (plus the web page where tagged); treat as less independently corroborated.
- Quotes are from commit messages or changesets unless stated.
- Repos: dashboard = `saleor/saleor-dashboard`, core = `saleor/saleor`, apps = `saleor/apps`.

## Schema coupling: how the dashboard pins core's schema, and where it broke

### Takeaway
The dashboard commits a copy of core's `schema.graphql` and generated types; since Nov 2025 it carries two (released "main" and unreleased "staging") selected at build time, and every field that exists in only one must be hand-gated. The recorded failures are all of one shape: one side assumed something about the other's timing (field "only deprecated", field "already released", "the client never sends more than N mutations") and nothing checked it until a user hit it.

### Cited Findings

**Mechanism**

- Until June 2025 the dashboard committed `schema.graphql` plus a 145k-line `introspection.json` and refreshed them by hand in "Update schema" PRs (e.g. "Update Saleor schema to 3.14", 2023-06-13). [git] — [dashboard #3751](https://github.com/saleor/saleor-dashboard/pull/3751)
- 2025-06-12: a daily cron workflow (`update-schema.yml`) started fetching the schema and opening "chore: update GraphQL schema and generated types" PRs; `introspection.json` was deleted. About 60 such PRs follow, by Nov 2026. [git] — [dashboard #5646](https://github.com/saleor/saleor-dashboard/pull/5646)
- 2025-11-18: "POC of multi-schema approach" added `schema-main.graphql` (released core) and `schema-staging.graphql` (core `main`), two codegen configs, duplicated generated files (`hooksStaging.generated.ts`, `typesStaging.generated.ts`) and the build-time flag `FF_USE_STAGING_SCHEMA`. Features that differ are written twice (`queries.staging.ts`, `mutations.staging.ts`) and chosen with `isMainSchema()` / `isStagingSchema()`. [git] — [dashboard #6070](https://github.com/saleor/saleor-dashboard/pull/6070), [docs/multi-schema.md](https://github.com/saleor/saleor-dashboard/blob/main/docs/multi-schema.md)
- The flag is build-time only: "there is no runtime switch", so a test target is "a Saleor image *and* a dashboard build … two targets, two ports, two build directories". [git] [POST-JUNE-2026] — [dashboard #6953](https://github.com/saleor/saleor-dashboard/pull/6953)
- `package.json` pins `config.saleor.schemaVersion` (currently `"3.23"`); `fetch-schema:staging` curls `saleor/saleor` `main`'s `schema.graphql`. [git] — [package.json](https://github.com/saleor/saleor-dashboard/blob/main/package.json)
- Version skew is otherwise handled by prose, not code: changesets say "Requires Saleor 3.23.42 or later", "Requires core >=3.20.68", "Requires Saleor 3.22.38". The only places the dashboard reads `shop.version` at runtime are the version display and the value it forwards to app iframes. [git] — [CHANGELOG.md](https://github.com/saleor/saleor-dashboard/blob/main/CHANGELOG.md), [AppFrame.tsx](https://github.com/saleor/saleor-dashboard/blob/main/src/extensions/views/ViewManifestExtension/components/AppFrame/AppFrame.tsx)

**Case S1 — attribute flags: "merely deprecated" turned into "removed" within eight days** [POST-JUNE-2026]

- 2026-08-19 core deprecated the remaining surface of `filterableInStorefront`, `storefrontSearchPosition`, `availableInGrid`, `filterableInDashboard` "so all of them can be removed together in one breaking release". [git] — [core #19671](https://github.com/saleor/saleor/pull/19671)
- 2026-08-19 (same day) the dashboard hid the UI under the staging schema but kept the selections: "The `Attribute` fragment still requests the field: it is merely `@deprecated` in both schemas today, and dropping it from the query would mean duplicating the fragment and every document that uses it". [git] — [dashboard #6843](https://github.com/saleor/saleor-dashboard/pull/6843)
- 2026-08-24 core removed the fields, inputs, filter inputs and sort enum values from the API. [git] — [core #19675](https://github.com/saleor/saleor/pull/19675)
- 2026-08-27 dashboard fix: "attribute list, details and update all failed validation against the staging schema. The previous deprecation gated every reader behind `isMainSchema()` but left the selections in, on the assumption the fields would stay `@deprecated` on staging rather than disappear. They disappeared." Two latent crashes surfaced on the way: `.toString()` on the now-absent `storefrontSearchPosition`, and "a bookmarked 'Use in faceted search' sort URL sent an enum value 3.24 no longer defines". [git][web] — [dashboard #6871](https://github.com/saleor/saleor-dashboard/pull/6871)
- The same PR introduced a client-only `@lockSchema(schema: "main"|"staging")` directive that strips fields from outgoing documents and from the cache's document, plus a sweep test that validates all generated documents (445 per the PR page) against both schemas. Whole-operation locks strip nothing at runtime: "every entry point must be gated behind `isMainSchema()`/`isStagingSchema()` by hand". [git][web] — [dashboard #6871](https://github.com/saleor/saleor-dashboard/pull/6871), [schema-directives.graphql](https://github.com/saleor/saleor-dashboard/blob/main/schema-directives.graphql)
- Core then removed the ORM columns and the populatedb data (2026-09-01, 2026-09-02). [git] — [core #19694](https://github.com/saleor/saleor/pull/19694), [core #19731](https://github.com/saleor/saleor/pull/19731)
- What each side had to know: core, that the dashboard was the only reader ("In Core the flag is only a stored boolean — nothing reads it — so the Dashboard is the only thing keeping it alive"); dashboard, the removal date. Symptom: three attribute screens fail on any build against core `main`. Cause: timing assumption in the dashboard.

**Case S2 — the "released" schema contained an unreleased field** [POST-JUNE-2026]

- The cron pulled `schema-main.graphql` from the 3.23 release *branch*, "so it picked up fields merged but not yet released (e.g. 3.23.36 idempotencyKey)". Fixed 2026-09-24 by downloading the `schema.graphql` attached to the newest published release matching `schemaVersion`. [git] — [dashboard #6958](https://github.com/saleor/saleor-dashboard/pull/6958)
- The field came from core "Expose idempotencyKey on transaction action requested webhooks", 2026-09-23. [git] — [core #19811](https://github.com/saleor/saleor/pull/19811)

**Case S3 — PR preview environments ran unreleased core against the released schema** [POST-JUNE-2026]

- "PR test envs run core unstable/unreleased main, so the released schema breaks against them." Fixed by building PR deployments with the staging schema. [git] — [dashboard #6866](https://github.com/saleor/saleor-dashboard/pull/6866)

**Case S4 — core's security limit broke a dashboard screen (core had to learn what the client sends)**

- 2026-04-08 core fixed CVE-2026-33756 by adding `GRAPHQL_MUTATION_COUNT_LIMIT` and `GRAPHQL_ALIAS_COUNT_LIMIT`. The commit text says the default was "1" mutation per call; the follow-up says the limit in force was 3 (conflict between the two texts, not resolved). [git] — [core commit f0371bd](https://github.com/saleor/saleor/commit/f0371bdd4)
- 2026-04-14 core raised the limit "from 3 to 4 due to Saleor Dashboard sending 4 mutations when updating stocks". To pick 4 the author scripted an extraction of every operation in the dashboard's `mutations.ts` files for 3.20, 3.21, 3.22, 3.23 and main and ran them through core's validator; cherry-picked as #19096–#19099. It is "temporary … until Saleor v3.24 where the cost limiter will dynamically adjust". [git][web] — [core #19095](https://github.com/saleor/saleor/pull/19095)
- Symptom as described in the PR: the dashboard's stock update (four mutations in one call) exceeded the limit. Cause: core. Knowledge needed: the exact multi-mutation documents of every supported dashboard version.

**Case S5 — a dashboard refactor exposed a dormant core bug (SSO login)** [POST-JUNE-2026]

- 2026-08-31 dashboard merged the vendored `@saleor/sdk` copy into its own Apollo client and codegen. [git] — [dashboard #6889](https://github.com/saleor/saleor-dashboard/pull/6889)
- Result in release 3.23.33: OIDC / "Login with Saleor Cloud" failed with "You don't have permission to login" and existing SSO sessions were logged out on reload. The external login mutations now spread the full `User` fragment, including `accessibleChannels`, whose fields are permission-guarded. Password login was unaffected. [git][web] — [dashboard #6935](https://github.com/saleor/saleor-dashboard/pull/6935)
- Dashboard hotfix 2026-09-07 (3.23.34): go back to the minimal `AuthUser` payload; add a test that `login` is the only auth mutation spreading `User`, because "the existing authSdk tests mock the response shape, so they could not catch this". [git][web] — [dashboard #6935](https://github.com/saleor/saleor-dashboard/pull/6935)
- Core fix 2026-09-09: `externalObtainAccessTokens` and `externalRefresh` "only wrote `info.context._cached_user` … the write was dead and the request stayed unauthenticated for the rest of field resolution … The Dashboard hit this via `user { accessibleChannels { isActive } }`". `tokenCreate` set `info.context.user`, "which is why password login never broke". [git] — [core #19747](https://github.com/saleor/saleor/pull/19747)
- Symptom: dashboard login error blaming permissions. Trigger: dashboard. Root cause: core. Both repos shipped a fix.

**Case S6 — dashboard workaround for a core behaviour change two minors earlier** [POST-JUNE-2026]

- Products whose channel-priced variants were not among the first 50 could not be added to an order. "Saleor core's `Product.productVariants` in a channel context filters by the product's channel listing, not the variant's, unlike the deprecated `Product.variants` field it replaced (core #16998, Saleor 3.21)." The dashboard now queries the deprecated field just to learn the ids. "The proper fix is an additive `ProductVariantWhereInput` filter … Until then, a product with tens of thousands of channel-listed variants will be slow to expand". [git] — [dashboard #6959](https://github.com/saleor/saleor-dashboard/pull/6959)

**Case S7 — dashboard removes UI ahead of core removals (ordering matters)** [POST-JUNE-2026]

- Preorder: dashboard stopped reading and writing every preorder field on 2026-08-18 "so the removal on the API side cannot break it"; relies on core still rejecting fulfilment with `FULFILL_ORDER_LINE` and on "Core only applies preorder settings when the input key is present". Core's changelog then lists the preorder API as removed. [git] — [dashboard #6837](https://github.com/saleor/saleor-dashboard/pull/6837), [core CHANGELOG.md](https://github.com/saleor/saleor/blob/main/CHANGELOG.md)
- Gift card code export: `exportGiftCards` "is gone from the 3.24 API and deprecated on 3.23"; dashboard deleted the dialog "rather than keep the UI alive behind a schema check". [git] — [dashboard #6875](https://github.com/saleor/saleor-dashboard/pull/6875)
- `GiftCard.usedBy`: dashboard removed the column on 2026-07-08 because the field "no longer behave[s] as intended since Saleor 3.14 … the displayed value was misleading" — about three years of showing a wrong value. [git] — [dashboard #6716](https://github.com/saleor/saleor-dashboard/pull/6716)
- Deprecated app and order fields dropped from fragments, 2026-07-27. [git] — [dashboard #6777](https://github.com/saleor/saleor-dashboard/pull/6777)

**Case S8 — feature needs a minimum core patch, stated only in a changeset**

- Variant "Available for purchase" per channel: "Requires Saleor 3.23.42 or later". [git] [POST-JUNE-2026] — [dashboard #7034](https://github.com/saleor/saleor-dashboard/pull/7034)
- Source header on API calls: "Requires core >=3.20.68", behind `ENABLED_SERVICE_NAME_HEADER`. [git] — [dashboard #5305](https://github.com/saleor/saleor-dashboard/pull/5305)
- Address validation setting: "Requires Saleor 3.22.38". [git] — [dashboard CHANGELOG, #6355](https://github.com/saleor/saleor-dashboard/pull/6355)

**Older user reports of plain version mismatch**

- 2021-08: "Cannot query field defaultCountry on type Channel" when logging in; dashboard 3.0 branch against a core 3.0 build. The reporter: "What is the good composition of the three entities (Core - Dashboard - Storefront)?" Resolved by matching beta releases. [web] — [dashboard issue #1335](https://github.com/saleor/saleor-dashboard/issues/1335)
- Two more "Cannot query field" issues exist (titles only seen): "Cannot add new product" (2020), "Unable to list plugins" (2021). [web, search listing only] — [dashboard issue #399](https://github.com/saleor/saleor-dashboard/issues/399), [dashboard issue #1196](https://github.com/saleor/saleor-dashboard/issues/1196)

### Inferences
- The dashboard has no runtime capability detection; compatibility is a build-time choice between two schemas plus prose. Any task where core changes a field under a deployed dashboard is realistic.
- S1, S4 and S5 are the strongest "one-sentence contract is not enough" cases: the needed fact was respectively a date, the full set of client documents across five versions, and an undocumented resolver-order detail in core.
- The sweep test added in #6871 is the kind of guard that turns a cross-repo surprise into a local test failure; before it, the only detector was a human on a staging build.

### Gaps
- docs.saleor.io upgrade guides were not consulted.
- Why core's first limit text says 1 while the follow-up says 3 was not resolved.
- Dashboard issues #399 and #1196 bodies were not read (GitHub API rate limit hit).

## Order and payment screens: refunds, capture, statuses, gift cards

### Takeaway
The order page has been catching up with core's Transactions API since 2022, and the recurring trouble is semantic, not syntactic: what a status or an event amount *means* is decided in core and by the payment app, and the dashboard has shown stale, zero or misleading figures for long periods. The longest-running issue (payment pill wrong for transaction orders) spans May 2023 to Oct 2026 across both trackers.

### Cited Findings

**Case P1 — Transactions API support: a seven-month PR behind a flag**

- "Support for new transactions API" carries PR number 2233 (numbered between PRs merged 2022-08-10 and 2022-09-06) and merged 2023-03-09; its squash message contains a revert and re-revert of the taxes PR. The flag was removed 2023-04-28, merging the parallel `.transaction` queries, mutations and fragments back into the regular files. [git] — [dashboard #2233](https://github.com/saleor/saleor-dashboard/pull/2233), [dashboard #3557](https://github.com/saleor/saleor-dashboard/pull/3557)
- QA issue two days before flag removal lists 11 defects; maintainer triage: "7. It's an issue in Saleor Core … 9. It's due to psp reference beeing an empty string". Item 1: "Status label needs a page refresh to show the correct status". [web] — [dashboard issue #3574](https://github.com/saleor/saleor-dashboard/issues/3574)
- Follow-on API churn the dashboard had to track: "Drop deprecated field in transactionsAPI" (2023-07-06, 4,814 insertions mostly schema); `defaultTransactionFlowStrategy` moved into `paymentSettings` (2023-10-04). [git] — [dashboard #3873](https://github.com/saleor/saleor-dashboard/pull/3873), [dashboard #4282](https://github.com/saleor/saleor-dashboard/pull/4282)

**Case P2 — the payment-status pill (May 2023 → Oct 2026)**

- Core issue 2023-05-05: after mark-as-paid, grant refund and a manual refund transaction, `order.paymentStatus` stays `FULLY_CHARGED`. A QA comment: "When this bug is fixed please uncomment test `should be able to grant and send refund TC: 3902`" (a dashboard E2E test disabled on a core bug). A core contributor explains in 2024-01 that two transactions (100 charged, 100 refunded) do not net to zero by design. Closed 2025-03-18 as old. [web] — [core issue #12757](https://github.com/saleor/saleor/issues/12757)
- Core fix 2023-11-02: "Fix inccorect statuses provided by order.paymentStatus when order is paid with transactions". [git] — [core #14551](https://github.com/saleor/saleor/pull/14551)
- Dashboard issue 2024-11-28, **still open**: after an app handles `TransactionRefundRequested`, the status does not become refunded (core 3.20.55). Maintainer: "It works on the API but the presentation of the current order must be changed". [web] — [dashboard issue #5539](https://github.com/saleor/saleor-dashboard/issues/5539)
- 2025-09-04: order list moved to the `where` API with separate `authorizeStatus` and `chargeStatus` filters that "replace part of old paymentStatus". [git] — [dashboard #5791](https://github.com/saleor/saleor-dashboard/pull/5791)
- 2026-10-30: "Order.paymentStatus is deprecated in Core. The order list, global search and navigator search now derive the payment pill from chargeStatus, authorizeStatus, totalCharged, totalChargePending and totalRefunded". Before, transaction orders "only showed 'Unpaid', 'Partially paid', or 'Fully paid', even when a charge was pending or money had been refunded". [git] [POST-JUNE-2026] — [dashboard #7045](https://github.com/saleor/saleor-dashboard/pull/7045)
- Related: "Always show charge and authorised amount in payment section" (2024-05-16). [git] — [dashboard #4821](https://github.com/saleor/saleor-dashboard/pull/4821)

**Case P3 — event amounts shown as 0, and who owns the amount**

- Dashboard 2024-01-04 hid amounts on some transaction events because "These events don't support providing amounts, and they were always displayed as 0." (The PR title says CANCEL events; the changeset names `CHARGE_REQUST`, `CHARGE_SUCCESS`, `CHARGE_FAILURE` — the two disagree.) [git] — [dashboard #4587](https://github.com/saleor/saleor-dashboard/pull/4587)
- Core issue 2023-10-17: `transactionRequestAction` allowed an empty `amount`, so the sync webhook carried none; "Adyen app fetches TransactionItem events history to determine which amount should be used … we might introduce differences in behavior between apps". Closed 2024-12-20. [web] — [core issue #14337](https://github.com/saleor/saleor/issues/14337)
- Core issue 2023-10-05 "Order transaction is unclear": a manual capture from the dashboard produced two events (success + info), the info one without an amount. Core contributor: the dashboard uses `transactionCreate`, which creates one event per amount field, and "dashboard should use a dedicated mutation for marking as paid"; closed as a dashboard matter, reopened by a dashboard maintainer, finally closed not-planned 2024-12-02. [web] — [core issue #14185](https://github.com/saleor/saleor/issues/14185)

**Case P4 — refund flows chasing core's rules**

- Issue 2023-10-18 (core 3.14): a refund cannot be sent without creating a `GrantedRefund`, which changes the order total; the reporter wanted to return a double payment. Closed not-planned 2026-09-30 in a cleanup. [web] — [dashboard issue #4349](https://github.com/saleor/saleor-dashboard/issues/4349)
- "Send order lines in orderGrantRefundCreate mutation" (2023-11-02, schema bump in the same PR). [git] — [dashboard #4373](https://github.com/saleor/saleor-dashboard/pull/4373)
- New refund views shipped behind `improved_refunds`: manual transaction refund 2024-04-05, transaction refund view 2024-04-23, enabled as preview 2024-06-05, flag removed 2025-09-18. In between: "Hide old refunds when feature flag on", "Disable refunds for nonrefundable transactions", "Fix pending manual refunds not visible in refund list". [git] — [dashboard #4774](https://github.com/saleor/saleor-dashboard/pull/4774), [dashboard #4750](https://github.com/saleor/saleor-dashboard/pull/4750), [dashboard #4921](https://github.com/saleor/saleor-dashboard/pull/4921), [dashboard #5877](https://github.com/saleor/saleor-dashboard/pull/5877), [dashboard #4824](https://github.com/saleor/saleor-dashboard/pull/4824), [dashboard #4881](https://github.com/saleor/saleor-dashboard/pull/4881)
- 2025-04-28: "You can now successfully save transaction refunds as drafts when using the latest version of Saleor Core" — the `transactionId` type in the refund mutation changed in core. [git] — [dashboard #5559](https://github.com/saleor/saleor-dashboard/pull/5559)
- 2025-05-15 issue from a contributor: returning products fails with `In field "transactionId": Expected "ID!", found null`. Maintainer: "we should always specify the transaction that is being used for a given refund (it's requirement in upcoming 3.21) … The return/replace view … [was] built for old payment API. For now, I just added a simple select box". Fixed the same day. [web] — [dashboard issue #5599](https://github.com/saleor/saleor-dashboard/issues/5599); [git] — [dashboard #5601](https://github.com/saleor/saleor-dashboard/pull/5601)
- 2026-06-16: the Return/Replace flow dropped order lines from the granted refund when their fulfillment awaited approval; "only shipping costs were sent to the payment provider". Wrong money sent to the payment app from a dashboard-side calculation. [git] — [dashboard #6642](https://github.com/saleor/saleor-dashboard/pull/6642)
- Refund reasons, phase 1: core "Allowing to reference a refund reason" 2025-09-16; dashboard 2025-09-17 (changeset still says "See announcement post (todo)"); core follow-up 2025-11-07 "Fix a bug with refund reason required for non-refund action". [git] — [core #18026](https://github.com/saleor/saleor/pull/18026), [dashboard #5792](https://github.com/saleor/saleor-dashboard/pull/5792), [core #18450](https://github.com/saleor/saleor/pull/18450)
- Refund reasons, phase 2: core 2026-06-23, dashboard 2026-06-24 touching both `schema-main.graphql` and `schema-staging.graphql`. [git] — [core #19272](https://github.com/saleor/saleor/pull/19272), [dashboard #6644](https://github.com/saleor/saleor-dashboard/pull/6644)

**Case P5 — async actions: the page did not know the app had answered**

- 2026-06-30: order details now polls while a charge, refund or cancel requested through a payment app is pending; before, "you had to refresh the page to see whether the action succeeded or failed", and Capture/Cancel could be triggered "multiple times before the first one resolved". [git] — [dashboard #6675](https://github.com/saleor/saleor-dashboard/pull/6675)
- Core's later idempotency work says why duplicates matter: the same delivery is re-sent on 5xx (up to 5 retries) and "The merchant's manual re-issue via `transactionRequestAction` mints a fresh key and the app acts again." [git] [POST-JUNE-2026] — [core #19811](https://github.com/saleor/saleor/pull/19811)
- Earlier requests on the same theme: "Transaction refund - prevent double click" (2023-11), core "Add Idempotency Key to Transaction sync webhooks and mutations" (2023-10). [web, search listing only] — [dashboard issue #4474](https://github.com/saleor/saleor-dashboard/issues/4474), [core issue #14358](https://github.com/saleor/saleor/issues/14358)

**Case P6 — payment method details: app → core → dashboard (and SMTP)**

- Stripe app started sending payment method details 2025-10-15; NP Atobarai the next day. [git] — [apps #2103](https://github.com/saleor/apps/pull/2103), [apps #2106](https://github.com/saleor/apps/pull/2106)
- Dashboard displayed card brand/type four months later (2026-02-17), with a "visa payment method fix" the next day. [git] — [dashboard #6339](https://github.com/saleor/saleor-dashboard/pull/6339), [dashboard #6348](https://github.com/saleor/saleor-dashboard/pull/6348)
- Stripe app 2026-02-12: unsupported payment methods "returned generic 'Payment intent failed' in dashboard"; the error "was only returned to storefront (inside 'data'), not also visible in the dashboard". The app had to learn which response field the dashboard renders. [git] — [apps #2228](https://github.com/saleor/apps/pull/2228)
- Dashboard widened the event tooltip for "long transaction event messages" (2025-01-08). [git] — [dashboard #5330](https://github.com/saleor/saleor-dashboard/pull/5330)

**Case P7 — gift cards as a payment method: three repos, one silent failure**

- Core "Gift cards as payment method", 2025-12-10. [git] — [core #18579](https://github.com/saleor/saleor/pull/18579)
- Dashboard next day added the channel flag "Allow legacy gift card use"; the squash message includes "Fix the code that choose between main and staging mutation". [git] — [dashboard #6195](https://github.com/saleor/saleor-dashboard/pull/6195)
- Dashboard display: `REFUNDED_IN_ORDER` gift card event (staging schema only, 2026-03-20); "Fix displaying gift card payment method details" (2026-03-27); "[3.23] Add gift card payment method display" (2026-03-30). [git] — [dashboard #6419](https://github.com/saleor/saleor-dashboard/pull/6419), [dashboard #6476](https://github.com/saleor/saleor-dashboard/pull/6476), [dashboard #6396](https://github.com/saleor/saleor-dashboard/pull/6396)
- SMTP app added order payment methods to its `ORDER_CREATED` payload on 2026-07-16. [git] [POST-JUNE-2026] — [apps #2398](https://github.com/saleor/apps/pull/2398)
- 2026-09-16 fix: that fragment "selects GiftCardPaymentMethodDetails, a type that only exists in Saleor 3.23. On 3.22 instances webhookCreate rejected the whole subscription query, so 7 of 9 webhooks failed to register during installation and the app silently sent no order or invoice emails. The manifest still declared >=3.22, and codegen validates against the 3.23 schema, so nothing caught it locally." Logging serialised errors to `"error":{}`, "what kept this invisible for two months". Fix: detect the core version and strip unresolvable inline fragments. [git] [POST-JUNE-2026] — [apps #2442](https://github.com/saleor/apps/pull/2442)

**Case P8 — totals computed in the browser**

- 2023-01: "Order line total is calculated on the frontend which leads to price mismatch" (3 items at 4.66 with a 0.43 discount); closed in three days. [web] — [dashboard issue #2963](https://github.com/saleor/saleor-dashboard/issues/2963)
- 2026-02-03: "when line items are changed, order summary (total, shipping price, etc.) are updated. Previously these values were not updated and displayed stale data" — the mutation response did not re-select the recalculated order fields. [git] — [dashboard #6292](https://github.com/saleor/saleor-dashboard/pull/6292)

### Inferences
- The hard part in this area is agreeing what a number means (net of refunds or not, which transaction a refund belongs to, whether an event carries an amount). These were argued in issues for a year or more (P2, P3), which is the opposite of a one-sentence contract.
- P7 is the cleanest evidence that a subscription query is a version-sensitive contract: an app can break on an *older* core by selecting a newer type, and nothing local fails.
- P5 and P6 show the dashboard needs the payment app's timing and response shape, which only the app owner knows.

### Gaps
- No public record was found of the dashboard showing a wrong *captured* figure specifically due to the Stripe app; the Stripe evidence is about error text and payment method details.
- Dashboard issue #4278 ("Send refunds through `transactionRequestRefundForGrantedRefund`") and #4424 (refund UX epic) were seen in search only.
- The reason the transactions PR took seven months is not stated; the duration is inferred from PR numbering.

## Apps inside the dashboard: install, permissions, extensions, App Bridge, tokens, health

### Takeaway
App extensions are a three-party contract (core stores and validates the manifest, the dashboard renders mounts and speaks App Bridge, apps and app-sdk consume it), and the record shows repeated out-of-order shipping: the dashboard faking a field core had not shipped, a release that breaks a page on older core patches, and apps needing fallbacks for dashboards that never acknowledge a new action.

### Cited Findings

**Case A1 — new mount points: revert, re-land, then permission fixes on both sides (June 2025)**

- Core "Support NEW_TAB for extension target & add new mounting points", 2025-06-05. [git] — [core #17780](https://github.com/saleor/saleor/pull/17780)
- Dashboard "Additional mounting points" merged 2025-06-09 (includes a schema bump), reverted the same day, re-landed 2025-06-10 with an identical diffstat. The revert PR page gives no reason; a Linear bot notes "Issue reopened: ENG-273". [git][web] — [dashboard #5638](https://github.com/saleor/saleor-dashboard/pull/5638), [dashboard #5647](https://github.com/saleor/saleor-dashboard/pull/5647), [dashboard #5648](https://github.com/saleor/saleor-dashboard/pull/5648)
- Core "Extend extensions API" 2025-06-13; dashboard "New app extension possibilities" 2025-06-16 (changes `package.json`; its changeset links a docs PR). [git] — [core #17813](https://github.com/saleor/saleor/pull/17813), [dashboard #5653](https://github.com/saleor/saleor-dashboard/pull/5653)
- Core "Fix permission access to `appExtension.app`" 2025-06-17; dashboard next day: "user without `MANAGE_APPS` permission will see app extensions". Also "Fix passing params to extensions" (06-17) and "accept relative urls for NEW_TAB" (06-23); core "Improve app extension validators" 06-25. [git] — [core #17825](https://github.com/saleor/saleor/pull/17825), [dashboard #5650](https://github.com/saleor/saleor-dashboard/pull/5650), [dashboard #5661](https://github.com/saleor/saleor-dashboard/pull/5661), [dashboard #5663](https://github.com/saleor/saleor-dashboard/pull/5663), [core #17841](https://github.com/saleor/saleor/pull/17841)
- AvaTax app used it immediately: "Add 3.22 extension with transaction details" (2025-06-18), an Order Details extension for "3.22 and above". [git] — [apps #1981](https://github.com/saleor/apps/pull/1981)

**Case A2 — enum fields to string fields for extensions (Nov 2025 → Feb 2026)**

- Core 2025-11-03: "Add new extension fields and deprecate legacy enum-based fields". [git] — [core #18397](https://github.com/saleor/saleor/pull/18397)
- Dashboard same day: "Update app extensions schema to use new field names" (20+ files) and "Fix app extension manifest permission validation … caused by invalid permissions schema". [git] — [dashboard #6015](https://github.com/saleor/saleor-dashboard/pull/6015), [dashboard #6019](https://github.com/saleor/saleor-dashboard/pull/6019)
- Core "Adjust app extension filters to new fields" 11-14, then "Fix appExtensions filter" 11-18; dashboard 11-19: "uses new API to filter appExtensions query - `mountName` instead `mount`". [git] — [core #18480](https://github.com/saleor/saleor/pull/18480), [core #18508](https://github.com/saleor/saleor/pull/18508), [dashboard #6081](https://github.com/saleor/saleor-dashboard/pull/6081)
- Dashboard 11-25: "Fixed bug with App (with extensions) installation - now validation on the frontend checks new API fields properly". [git] — [dashboard #6132](https://github.com/saleor/saleor-dashboard/pull/6132)
- Core 11-28 removed `mount`, `target`, `options`; 12-01 "Make AppExtensions resolvers working with pre and post data migration"; 12-08 removed obsolete validation; 12-16 data migration via Celery task; 2026-02-06 "Remove old app enums". [git] — [core #18571](https://github.com/saleor/saleor/pull/18571), [core #18561](https://github.com/saleor/saleor/pull/18561), [core #18578](https://github.com/saleor/saleor/pull/18578), [core #18573](https://github.com/saleor/saleor/pull/18573), [core #18618](https://github.com/saleor/saleor/pull/18618)

**Case A3 — manifest validation duplicated in the dashboard**

- 2025-10-24: "Added local-frontend validation of a subset of App Manifest fields during installation. Installing apps will be now more liberal, some errors initially thrown on the API level will be now warnings". [git] — [dashboard #5997](https://github.com/saleor/saleor-dashboard/pull/5997)
- Three corrections in a month: relative extension URLs wrongly rejected (10-30); "Dashboard prevents installation in case errors occur. This mimics the behavior of API-side validation" (10-30); invalid permissions schema (11-03); then A2's #6132. [git] — [dashboard #6010](https://github.com/saleor/saleor-dashboard/pull/6010), [dashboard #6011](https://github.com/saleor/saleor-dashboard/pull/6011), [dashboard #6019](https://github.com/saleor/saleor-dashboard/pull/6019)
- 2026-05-12: dashboard "prevents `MANAGE_APPS` from being granted for apps"; core's changelog says "From Saleor 3.24, this app installation with `MANAGE_APPS` permission will be rejected." [git] — [dashboard #6542](https://github.com/saleor/saleor-dashboard/pull/6542), [core CHANGELOG.md](https://github.com/saleor/saleor/blob/main/CHANGELOG.md)
- Earlier app-side counterpart: "Protect apps using MANAGE_APPS permissions" (2024-03-18), "Fix missing MANAGE APPS permission when using client provided in context" (2023-06-20). [git] — [apps #1252](https://github.com/saleor/apps/pull/1252), [apps #663](https://github.com/saleor/apps/pull/663)

**Case A4 — App Problems: a dashboard release that breaks on older core patches**

- Core "Add Problems API for apps" 2026-02-16 (its squash message includes a revert and a rename of `byUserWithIds` to `byStaffWithIds`). [git] — [core #18724](https://github.com/saleor/saleor/pull/18724)
- Dashboard 2026-02-24: "This release *requires* Saleor core 3.22.36. Used with older version, Extensions page will break". A review comment suggested softening the wording. [git][web] — [dashboard #6283](https://github.com/saleor/saleor-dashboard/pull/6283)
- Same day: "Fix infinite re-render loop in useAppsAlert causing CPU/RAM spike". Later: "Show app problems for disabled apps" (2026-04-08). [git] — [dashboard #6364](https://github.com/saleor/saleor-dashboard/pull/6364), [dashboard #6485](https://github.com/saleor/saleor-dashboard/pull/6485)
- Apps adopted it over ten days: shared `app-problems` package (02-24), Stripe (02-25), CMS and search (02-27), AvaTax (03-02), "missing problems" (03-02), Products Feed, Segment. Segment: before, misconfiguration meant "events were silently dropped with no visible indication". [git] — [apps #2251](https://github.com/saleor/apps/pull/2251), [apps #2255](https://github.com/saleor/apps/pull/2255), [apps #2261](https://github.com/saleor/apps/pull/2261), [apps #2264](https://github.com/saleor/apps/pull/2264), [apps #2267](https://github.com/saleor/apps/pull/2267)
- Predecessors: alerts for apps with issues (2025-02-21), failed event deliveries list (2024-09-26), "Fix empty event deliveries" (2025-06-02). [git] — [dashboard #5416](https://github.com/saleor/saleor-dashboard/pull/5416), [dashboard #5163](https://github.com/saleor/saleor-dashboard/pull/5163), [dashboard #5629](https://github.com/saleor/saleor-dashboard/pull/5629)

**Case A5 — `openPopup` and `AppExtension.identifier`: dashboard ahead of core and app-sdk** [POST-JUNE-2026]

- Dashboard PR #6667 (merged 2026-07-23): "The `identifier` field is faked into the GraphQL schema until Saleor Core ships it; the action type is declared locally until @saleor/app-sdk does." A later commit in the same PR: "Core now ships AppExtension.identifier (previously faked locally)". [git] — [dashboard #6667](https://github.com/saleor/saleor-dashboard/pull/6667)
- Core added the field 2026-07-14, first annotated as added in 3.24, then re-annotated: "The field is being ported to the 3.23 release, so update the ADDED_IN annotation from 3.24 to 3.23". [git] — [core #19360](https://github.com/saleor/saleor/pull/19360)

**Case A6 — `redirectToApp`: apps must cope with dashboards that never answer** [POST-JUNE-2026]

- Dashboard 2026-08-20: apps can redirect to another installed app by manifest identifier ("app IDs are per-instance, identifiers are not"); bumps app-sdk to 1.15.0; "`path` crosses a trust boundary, so it's rejected unless it's a local subpath". [git] — [dashboard #6853](https://github.com/saleor/saleor-dashboard/pull/6853)
- Apps 2026-08-27: the onboarding app stops "reconstructing an extensions URL from an app's GraphQL id … onboarding no longer depends on Dashboard route shapes it does not own. Dashboards that predate the action never ack it, which would leave the CTA dead, so the redirect falls back to the installed apps list". Same PR: during the App Bridge handshake, config pages "claim the user lacks permission" because the hook "could not tell 'Dashboard has not sent the user yet' apart from 'user is missing a permission'". [git] — [apps #2419](https://github.com/saleor/apps/pull/2419)
- Dashboard 2026-08-31 and 2026-10-01: extension URLs accept the app identifier; apps are identified "by their identifier, falling back to the manifest URL only when the identifier is missing. Apps with the same name or a conflicting identifier are no longer mistaken". [git] — [dashboard #6888](https://github.com/saleor/saleor-dashboard/pull/6888), [dashboard #6978](https://github.com/saleor/saleor-dashboard/pull/6978)

**Case A7 — app deprecation and the SMTP hand-over** [POST-JUNE-2026]

- Core 2026-09-30: `App`/`Manifest.deprecationReason` and `appSelfUpdate` (port of #19814 from 3.23, with a merge migration). [git] — [core #19815](https://github.com/saleor/saleor/pull/19815)
- Dashboard 2026-10-06: shows it; "Requires Saleor 3.23.38 or later"; the "Deprecated" chip remains "only for apps without a reason (legacy SMTP)". Redesigned the same day. [git] — [dashboard #6986](https://github.com/saleor/saleor-dashboard/pull/6986), [dashboard #6992](https://github.com/saleor/saleor-dashboard/pull/6992)
- Dashboard 2026-10-09: "Migrate" button (SMTP → Customer Emails); "Mapping is hardcoded until the API exposes it." [git] — [dashboard #6999](https://github.com/saleor/saleor-dashboard/pull/6999)
- SMTP app 2026-09-15 capped compatibility at `>=3.22 <3.24`: "Saleor 3.24 is not supported by this app - Customer Emails app replaces it there." [git] — [apps #2441](https://github.com/saleor/apps/pull/2441)

**Case A8 — tokens, iframes, App Bridge messages**

- 2026-08-03: "App tokens were scheduled from total lifetime (`exp - iat`) rather than time remaining, so a token that aged while the machine slept … expired unrenewed"; apps "could keep running with an expired token that was never renewed". [git] [POST-JUNE-2026] — [dashboard #6795](https://github.com/saleor/saleor-dashboard/pull/6795)
- Web search also surfaced a third-party fork PR describing popup and widget extensions showing "session expired" after 5 minutes because the token was minted once per page load. Fork, not upstream; upstream status unverified. [web, search snippet only] — [fork PR](https://github.com/Craftware-slf/saleor-dashboard/pull/32)
- 2026-02-16: the dashboard "confused actions from 3rd party, like browser extensions signals with AppBridge actions". [git] — [dashboard #6340](https://github.com/saleor/saleor-dashboard/pull/6340)
- New actions each needing an app-sdk bump: `popupClose` (2026-02-03), form-state sync for Product Update popups (2025-11-04, changeset says "See docs [todo]"), translation form integration (2025-11-17), app-sdk v1 on both sides the same day (2025-03-24). [git] — [dashboard #6310](https://github.com/saleor/saleor-dashboard/pull/6310), [dashboard #5990](https://github.com/saleor/saleor-dashboard/pull/5990), [dashboard #6030](https://github.com/saleor/saleor-dashboard/pull/6030), [dashboard #5501](https://github.com/saleor/saleor-dashboard/pull/5501), [apps #1799](https://github.com/saleor/apps/pull/1799)
- Iframe sandbox loosened twice for apps: downloads (2025-04-25), pop-ups (2025-10-27). Apps side: "Display error when user opens app outside of iframe", "Check if apps are opened in iframe before rendering pages". [git] — [dashboard #5551](https://github.com/saleor/saleor-dashboard/pull/5551), [dashboard #6002](https://github.com/saleor/saleor-dashboard/pull/6002), [apps #2062](https://github.com/saleor/apps/pull/2062), [apps #2080](https://github.com/saleor/apps/pull/2080)
- Widgets: dashboard lets widgets size their iframe (2026-06-10); AvaTax widget had to "Remove widget padding so the Dashboard-provided iframe padding isn't doubled and auto-resize no longer clips content" and gained `MANAGE_PRODUCTS`, so "the app will ask for approval of the new permission". [git] — [dashboard #6599](https://github.com/saleor/saleor-dashboard/pull/6599), [apps #2405](https://github.com/saleor/apps/pull/2405) [POST-JUNE-2026]
- Stripe app 2026-08-18: Dashboard-aligned config UI; "`ExitFormDialog` … which apps need because the Dashboard iframe suppresses the browser's" own prompt; "Channel-list fields moved to a dedicated ConfigChannel fragment so UI-only data no longer rides along in every transaction webhook subscription." [git] [POST-JUNE-2026] — [apps #2417](https://github.com/saleor/apps/pull/2417)

**Case A9 — webhook health the dashboard must explain**

- Core circuit breaker for sync webhooks: 2025-02-27, fixes 2025-03-03 and 2026-03-20. Dashboard badge "Webhooks paused" / "Webhooks recovering" only on 2026-10-28. [git] — [core #16658](https://github.com/saleor/saleor/pull/16658), [core #17443](https://github.com/saleor/saleor/pull/17443), [core #18955](https://github.com/saleor/saleor/pull/18955), [dashboard #7042](https://github.com/saleor/saleor-dashboard/pull/7042) [POST-JUNE-2026]
- 2026-05-07: four 3.23 stock events "fire only when the shop has the legacy shipping-zone stock-availability setting disabled … admins on shops still in legacy mode could subscribe with no visual cue and silently never receive deliveries". [git] — [dashboard #6549](https://github.com/saleor/saleor-dashboard/pull/6549)
- "Fix custom headers not being saved when creating a webhook" (2026-07-16); `useLegacyUpdateWebhookEmission` toggle (2026-02-19). [git] — [dashboard #6743](https://github.com/saleor/saleor-dashboard/pull/6743), [dashboard #6350](https://github.com/saleor/saleor-dashboard/pull/6350)

### Inferences
- A5 and A6 are direct evidence of "shipped against an API not yet released" and of the consumer needing a fallback for an old counterpart.
- A2 shows a field rename taking three months and ten PRs across two repos, with a data migration in the middle and resolvers that had to work "pre and post" migration.
- In A3 the dashboard re-implemented core's validation and got it wrong four times; each fix needed knowledge of what core actually accepts.
- The #5647 revert is probably a release-timing or schema-availability matter given the core PR four days earlier, but the page gives no reason.

### Gaps
- saleor/app-sdk issues and PRs were not searched (GitHub API rate limit).
- No dashboard issue specifically about iframe token expiry was found upstream; only the commit above and a fork PR.
- The apps repo's recent commits are "Sync from internal repository (#150)" style with low PR numbers, so apps history after about Oct 2026 is opaque in public.

## Large cross-repo features with a dashboard half

### Takeaway
Big features landed either same-day on both sides (taxes, refund reasons) or as months of dashboard work behind a feature flag after core shipped (promotions, transactions, extensions); permission handling is the most frequent source of follow-up bugs, because core decides which fields need which permission and the dashboard finds out at runtime.

### Cited Findings

- **Taxes.** Core "Simple (flat rate) taxes API" and dashboard "Simple taxes" both merged 2022-11-17; dashboard marked taxes "preview" 2023-01-11, then a run of fixes (pagination of tax rates, "Change tax configurations amount from 20 to 100", "Fix infinite spinner during tax selection", "Fix saving previously removed country exceptions"). [git] — [core #9784](https://github.com/saleor/saleor/pull/9784), [dashboard #2072](https://github.com/saleor/saleor-dashboard/pull/2072), [dashboard #2971](https://github.com/saleor/saleor-dashboard/pull/2971), [dashboard #3088](https://github.com/saleor/saleor-dashboard/pull/3088), [dashboard #4327](https://github.com/saleor/saleor-dashboard/pull/4327)
- **Tax app selection per channel** (2024-02-26): "Previously we allowed user to select either flat rates or any tax app. To avoid problems if there are more tax apps installed this change adds ability to select tax app … per channel", citing a core RFC; adds a `LegacyFlowWarning`. Follow-ups: "Fix broken link to app details on tax configuration", "Remove version from tax app label". [git] — [dashboard #4631](https://github.com/saleor/saleor-dashboard/pull/4631), [core RFC issue #12942](https://github.com/saleor/saleor/issues/12942) (RFC page not opened), [dashboard #4740](https://github.com/saleor/saleor-dashboard/pull/4740), [dashboard #5230](https://github.com/saleor/saleor-dashboard/pull/5230)
- **AvaTax in dashboard tests.** "[E2E] Replace Avatax app with Dummy app in taxes e2e" (2024-04-29). [git] — [dashboard #4798](https://github.com/saleor/saleor-dashboard/pull/4798)
- **Promotions replacing sales.** Dashboard built discount pages under a flag from 2023-11-20 ("Discount catalog pages under feature flag", "Discount list with promotion api" 2023-12-18, "Add support for order promotion API" 2024-02-09 with a 1,289-line introspection change, gift rewards 2024-02-12); the flag became default only 2024-10-08 ("Cleanup feature flags"), about ten and a half months. Fixes on the way: "Fix sending empty order condition in discount rules", "Fix showing promotion discount type in order summary". [git] — [dashboard #4444](https://github.com/saleor/saleor-dashboard/pull/4444), [dashboard #4530](https://github.com/saleor/saleor-dashboard/pull/4530), [dashboard #4648](https://github.com/saleor/saleor-dashboard/pull/4648), [dashboard #5190](https://github.com/saleor/saleor-dashboard/pull/5190), [dashboard #4713](https://github.com/saleor/saleor-dashboard/pull/4713), [dashboard #4689](https://github.com/saleor/saleor-dashboard/pull/4689)
- **Vouchers: multi-request saves against core validation** [POST-JUNE-2026]. "when the API rejected the channel discount values after the voucher itself was created, the voucher stayed live with its codes and no discount, and trying again failed because the codes were already taken"; "a request the API rejected as a whole … showed 'Voucher updated' without saving anything". Also: the Name column "asked the API to sort by `VoucherSortField.CODE`, which … is marked as no longer supported"; a datetime sent without zone, which "The API reads … as UTC". [git] — [dashboard #7061](https://github.com/saleor/saleor-dashboard/pull/7061), [dashboard #7060](https://github.com/saleor/saleor-dashboard/pull/7060), [dashboard #7071](https://github.com/saleor/saleor-dashboard/pull/7071)
- **Permissions decided by core, discovered by the dashboard.**
  - Voucher pages demanded `MANAGE_PRODUCTS`: "Nothing changed on the API side; the dashboard was asking for a product-gated field on a discounts page … Long-standing, but error toasts became sticky in #6812 so it turned loud." Fixed with `@include(if: $PERMISSION_MANAGE_PRODUCTS)`. [git] [POST-JUNE-2026] — [dashboard #6893](https://github.com/saleor/saleor-dashboard/pull/6893)
  - Product edit broke for users without `MANAGE_PRODUCT_TYPES_AND_ATTRIBUTES` because `Attribute` was fetched with `privateMetadata` on every page (2025-12-03). [git] — [dashboard #6155](https://github.com/saleor/saleor-dashboard/pull/6155)
  - File attributes: the dashboard called `attributeValueDelete` before the object update; users with only `MANAGE_PRODUCTS` got `PermissionDenied`, and it "was also not crash-safe". Core moved the cleanup into the update mutation (2026-09-01); the dashboard dropped its call: "Saleor 3.23.30 and above clean up … and on older versions the update still succeeds". A second defect appeared inside the same PR: clearing a file "never made it into the update mutation" because the old flow relied on the deleted call. [git] [POST-JUNE-2026] — [core #19722](https://github.com/saleor/saleor/pull/19722), [dashboard #6885](https://github.com/saleor/saleor-dashboard/pull/6885)
  - Extensions pages for users without `MANAGE_APPS` / `MANAGE_PLUGINS` (three fixes, Apr–May 2025). [git] — [dashboard #5545](https://github.com/saleor/saleor-dashboard/pull/5545), [dashboard #5594](https://github.com/saleor/saleor-dashboard/pull/5594), [dashboard #5595](https://github.com/saleor/saleor-dashboard/pull/5595)
- **Channels / stock availability mode.** Core 3.23 added a shop setting; dashboard added the toggle (2026-04-27), then had to adapt the product diagnostics twice and the variant stock messaging (May 2026). [git] — [dashboard #6536](https://github.com/saleor/saleor-dashboard/pull/6536), [dashboard #6545](https://github.com/saleor/saleor-dashboard/pull/6545), [dashboard #6546](https://github.com/saleor/saleor-dashboard/pull/6546), [dashboard #6548](https://github.com/saleor/saleor-dashboard/pull/6548)
- **Order lines.** Core "Add reason for price override" and dashboard "Add price override reason column" both 2026-07-20; the dummy payment app got the matching change the same day. [git] [POST-JUNE-2026] — [core #19506](https://github.com/saleor/saleor/pull/19506), [dashboard #6732](https://github.com/saleor/saleor-dashboard/pull/6732), [apps #2393](https://github.com/saleor/apps/pull/2393)
- **Bulk operations.** Core now caps bulk delete at 100 ids (`BULK_DELETE_LIMIT`) for some twenty mutations. Dashboard: stale selection after sorting meant "'Delete' then removed items you never picked". [git] [POST-JUNE-2026] — [core CHANGELOG.md](https://github.com/saleor/saleor/blob/main/CHANGELOG.md), [dashboard #7071](https://github.com/saleor/saleor-dashboard/pull/7071)
- **Media upload limit.** Dashboard added a client-side size pre-check, then reverted it two days later: "Saleor Core enforces the configured size limit." [git] [POST-JUNE-2026] — [dashboard #6767](https://github.com/saleor/saleor-dashboard/pull/6767)

### Inferences
- Same-day merges (taxes, refund reasons, price override reason) imply the two halves were developed together against an agreed schema; flag-gated features imply the dashboard discovering the API over months.
- Multi-request saves (vouchers, file attributes, stock update with four mutations) are where partial failure and core-side validation bite; a fix on one side tends to expose a dependency on the other within the same PR.

### Gaps
- Core-side promotion migration PRs were not traced; the ten-and-a-half-month figure is the dashboard flag's lifetime only.
- Staff/customer changes (customer types, read-only customer view) were seen in the log but not examined for cross-repo trouble.
- Search changes: the 2025 "New search page" and its E2E fallout were seen but not examined.

## Chains: reverts, re-lands, hotfixes, backports, misfiled bugs, long-running issues

### Takeaway
The clearest chains are: SSO login (dashboard refactor → dashboard hotfix → core fix, nine days), attribute flags (deprecate → gate → remove → break → directive, eight days), extension fields (three months, ten PRs), and the payment-status question (three and a half years, both trackers).

### Cited Findings

- **Dashboard refactor → hotfix → core root-cause fix:** #6889 (08-31) → #6935 (09-07) → core #19747 (09-09). See S5. [git][web] [POST-JUNE-2026] — [dashboard #6935](https://github.com/saleor/saleor-dashboard/pull/6935), [core #19747](https://github.com/saleor/saleor/pull/19747)
- **Revert and re-land in 24 hours:** #5638 → #5647 → #5648. See A1. [git][web] — [dashboard #5647](https://github.com/saleor/saleor-dashboard/pull/5647)
- **Core security fix → dashboard regression → core fix cherry-picked to four branches:** CVE fix 2026-04-08 → #19095 2026-04-14 (+ #19096–#19099). See S4. [git][web] — [core #19095](https://github.com/saleor/saleor/pull/19095)
- **Backport that changed a version annotation:** `AppExtension.identifier` re-annotated from 3.24 to 3.23; `deprecationReason` built on 3.23 and ported forward with a merge migration `0043_merge`. [git] [POST-JUNE-2026] — [core #19360](https://github.com/saleor/saleor/pull/19360), [core #19815](https://github.com/saleor/saleor/pull/19815)
- **Dashboard release-branch port:** "[3.23] Add gift card payment method display" (2026-03-30), three days after the main fix; "update main with 3.22" (2025-10-14); "Port new shipping method schema to 3.1" (2022-01-24). [git] — [dashboard #6396](https://github.com/saleor/saleor-dashboard/pull/6396), [dashboard #5973](https://github.com/saleor/saleor-dashboard/pull/5973), [dashboard #1768](https://github.com/saleor/saleor-dashboard/pull/1768)
- **Filed against core, argued to be the dashboard's:** core issue #14185 closed with "this should be resolved on the dashboard side", reopened by a dashboard maintainer. [web] — [core issue #14185](https://github.com/saleor/saleor/issues/14185)
- **Filed against the dashboard, partly core's:** issue #3574 triage "7. It's an issue in Saleor Core". [web] — [dashboard issue #3574](https://github.com/saleor/saleor-dashboard/issues/3574)
- **Filed against the dashboard, "works on the API":** #5539, open since 2024-11-28. [web] — [dashboard issue #5539](https://github.com/saleor/saleor-dashboard/issues/5539)
- **App broke on an older core, undetected two months:** SMTP #2398 → #2442. See P7. [git] [POST-JUNE-2026] — [apps #2442](https://github.com/saleor/apps/pull/2442)
- **Apps dropping old cores, which the dashboard and core owners must track:** 3.19 (2025-11-24), 3.20 (2026-07-07), 3.21 (2026-09-03); Products Feed capped at `<3.24` while replacing six deprecated field usages (e.g. `products(filter: {ids})` → `products(where: {ids})`). [git] — [apps #2139](https://github.com/saleor/apps/pull/2139), [apps #2342](https://github.com/saleor/apps/pull/2342), [apps #2433](https://github.com/saleor/apps/pull/2433), [apps #2443](https://github.com/saleor/apps/pull/2443)
- **Other dashboard reverts seen (not cross-repo, for calibration):** "Revert 'Change API_URI to API_URL'" (2024-06), "Revert 'Extract suspense in refund settings'" (2025-12), "Revert 'Refactor useUrlValueProvider'" (2026-01). [git] — [dashboard #4922](https://github.com/saleor/saleor-dashboard/pull/4922), [dashboard #6159](https://github.com/saleor/saleor-dashboard/pull/6159), [dashboard #6288](https://github.com/saleor/saleor-dashboard/pull/6288)

### Inferences
- In each chain the first fix landed in the repo where the symptom showed, and the root-cause fix (when different) came later in the other repo. A benchmark where one agent can patch its own side to hide the symptom reproduces that pattern.

### Gaps
- Review discussions on most PRs were not read, so who told whom what is known only where the commit message says it.
- Whether #19096–#19099 map to 3.20–3.23 is likely but not shown on the page.

## Flaky or always-failing tests and E2E suites tied to core state

### Takeaway
Until Sept 2026 the dashboard's E2E suite ran against a provisioned cloud instance with a snapshot of core data, so failures were a function of core state and unrepeatable locally; it was then frozen and replaced by a suite that boots core in Docker per target schema.

### Cited Findings

- Rationale for the rewrite: "The existing suite drives a provisioned Saleor Cloud instance and asserts on 780 lines of snapshot object ids, so nobody can reproduce a failure - or add a test - without provisioning one first. It moves to `e2e-legacy/` and is frozen." The new suite restores a `pg_dump` before every test; seeds are cached by image content id because "Both tags float, so a new `3.23` patch has to invalidate the dumps"; "Login cannot be parallelised: Saleor throttles `tokenCreate` per IP unconditionally." [git] [POST-JUNE-2026] — [dashboard #6953](https://github.com/saleor/saleor-dashboard/pull/6953)
- Porting order flows: "beat-only Saleor tasks (product search index, promotion prices) run after every scenario build, since the stack has no scheduler"; "SALEOR_79 (the deprecated payment flow) is intentionally not ported". [git] [POST-JUNE-2026] — [dashboard #6966](https://github.com/saleor/saleor-dashboard/pull/6966)
- Volume of flake work on the old suite: about twenty "fixing flaky tests" commits between Feb and Sept 2024 (e.g. gift cards, bulk delete customers, navigation), plus snapshot plumbing in 2022 ("Revert to snapshot", "Fix revert to snapshot job" twice, "add timeout to revert snapshot job"). [git] — [dashboard #4880](https://github.com/saleor/saleor-dashboard/pull/4880), [dashboard #5142](https://github.com/saleor/saleor-dashboard/pull/5142), [dashboard #2112](https://github.com/saleor/saleor-dashboard/pull/2112), [dashboard #2356](https://github.com/saleor/saleor-dashboard/pull/2356)
- Suites broken by changes elsewhere: "Skip or fix failing e2e" (2025-12-17, 18 files incl. orders, permission groups, taxes); "Fix failing e2e" (2026-02-03, which also fixed the real stale-totals bug in P8); "Fix e2e after adding search page"; "Fix permission group e2e and staff activation tests"; "Remove hardcoded app ids in smoke tests" (2026-03-23). [git] — [dashboard #6176](https://github.com/saleor/saleor-dashboard/pull/6176), [dashboard #6292](https://github.com/saleor/saleor-dashboard/pull/6292), [dashboard #5717](https://github.com/saleor/saleor-dashboard/pull/5717), [dashboard #5624](https://github.com/saleor/saleor-dashboard/pull/5624), [dashboard #6460](https://github.com/saleor/saleor-dashboard/pull/6460)
- App install tests depended on live apps: "[SALEOR_119] Increase timeouts on app install", "Remove skip form install app tests", AvaTax replaced by a dummy app in tax tests. [git] — [dashboard #5147](https://github.com/saleor/saleor-dashboard/pull/5147), [dashboard #5135](https://github.com/saleor/saleor-dashboard/pull/5135), [dashboard #4798](https://github.com/saleor/saleor-dashboard/pull/4798)
- A dashboard E2E test disabled pending a core bug (refund status), per a QA comment. [web] — [core issue #12757](https://github.com/saleor/saleor/issues/12757)
- Tests that mock the response shape missed the SSO break (S5); codegen against the newest schema missed the SMTP break (P7). [git] — [dashboard #6935](https://github.com/saleor/saleor-dashboard/pull/6935), [apps #2442](https://github.com/saleor/apps/pull/2442)
- Apps side: "POC integration tests" and "Add integration test for refund requested" for Stripe (May–June 2025); "Fixed smoke tests (added missing permissions)" (2026-02). [git] — [apps #1896](https://github.com/saleor/apps/pull/1896), [apps #1975](https://github.com/saleor/apps/pull/1975), [apps #2231](https://github.com/saleor/apps/pull/2231)
- Workflow to run dashboard tests from another repo on release (2024-07-02), replacing the nightly workflow. [git] — [dashboard #4930](https://github.com/saleor/saleor-dashboard/pull/4930)

### Inferences
- Three properties of the real system make shared-state tests hard and are reproducible in a benchmark: core background tasks (search index, promotion price recalculation) must run before the UI shows correct data; login is rate-limited; and a dashboard build is bound to one schema.
- Mocked-shape unit tests are the documented blind spot on both the dashboard and app sides.

### Gaps
- Individual flaky-test PRs were not opened to see whether the cause was core state or UI timing.
- CI run history is not available from the clones.

## Items dated after June 2026 (flagged separately)

### Takeaway
A large share of the best-documented cases fall after June 2026, because commit messages from that period are far more explanatory; they are verified in the local clones, and two were also opened on GitHub.

### Cited Findings
- Opened on the web as well: [dashboard #6871](https://github.com/saleor/saleor-dashboard/pull/6871) (2026-08-27), [dashboard #6935](https://github.com/saleor/saleor-dashboard/pull/6935) (2026-09-07).
- Local clone only: S2 ([dashboard #6958](https://github.com/saleor/saleor-dashboard/pull/6958)), S3 ([dashboard #6866](https://github.com/saleor/saleor-dashboard/pull/6866)), S5 core half ([core #19747](https://github.com/saleor/saleor/pull/19747)), S6 ([dashboard #6959](https://github.com/saleor/saleor-dashboard/pull/6959)), S7 ([dashboard #6837](https://github.com/saleor/saleor-dashboard/pull/6837), [dashboard #6875](https://github.com/saleor/saleor-dashboard/pull/6875), [dashboard #6716](https://github.com/saleor/saleor-dashboard/pull/6716)), S1 core half ([core #19671](https://github.com/saleor/saleor/pull/19671), [core #19675](https://github.com/saleor/saleor/pull/19675)), P2 end ([dashboard #7045](https://github.com/saleor/saleor-dashboard/pull/7045)), P7 app half ([apps #2398](https://github.com/saleor/apps/pull/2398), [apps #2442](https://github.com/saleor/apps/pull/2442)), A5 ([dashboard #6667](https://github.com/saleor/saleor-dashboard/pull/6667), [core #19360](https://github.com/saleor/saleor/pull/19360)), A6 ([dashboard #6853](https://github.com/saleor/saleor-dashboard/pull/6853), [apps #2419](https://github.com/saleor/apps/pull/2419)), A7 ([core #19815](https://github.com/saleor/saleor/pull/19815), [dashboard #6986](https://github.com/saleor/saleor-dashboard/pull/6986), [dashboard #6999](https://github.com/saleor/saleor-dashboard/pull/6999), [apps #2441](https://github.com/saleor/apps/pull/2441)), token renewal ([dashboard #6795](https://github.com/saleor/saleor-dashboard/pull/6795)), circuit breaker badge ([dashboard #7042](https://github.com/saleor/saleor-dashboard/pull/7042)), file attributes ([core #19722](https://github.com/saleor/saleor/pull/19722), [dashboard #6885](https://github.com/saleor/saleor-dashboard/pull/6885)), voucher permissions and saves ([dashboard #6893](https://github.com/saleor/saleor-dashboard/pull/6893), [dashboard #7060](https://github.com/saleor/saleor-dashboard/pull/7060), [dashboard #7061](https://github.com/saleor/saleor-dashboard/pull/7061), [dashboard #7071](https://github.com/saleor/saleor-dashboard/pull/7071)), variant availability ([dashboard #7034](https://github.com/saleor/saleor-dashboard/pull/7034)), local E2E stack ([dashboard #6953](https://github.com/saleor/saleor-dashboard/pull/6953), [dashboard #6966](https://github.com/saleor/saleor-dashboard/pull/6966)), price override reason ([core #19506](https://github.com/saleor/saleor/pull/19506), [dashboard #6732](https://github.com/saleor/saleor-dashboard/pull/6732)), media pre-check revert ([dashboard #6767](https://github.com/saleor/saleor-dashboard/pull/6767)), Stripe config UI and AvaTax widget ([apps #2417](https://github.com/saleor/apps/pull/2417), [apps #2405](https://github.com/saleor/apps/pull/2405)).

### Inferences
- Pre-2025 squash commits usually carry only a title, so older cases (transactions, promotions, taxes) are documented more thinly here than they deserve; issue threads are the better source for that era.

### Gaps
- Most PR URLs in these notes were derived from commit subjects and not opened; GitHub's unauthenticated API rate limit was exhausted partway through, which also cut short issue searches on apps/iframes, promotions, permissions and app-sdk.

# Order the rollout, split the evidence

Saleor's history shows that the work which truly needed two owners was almost never a shared schema change. It was a behavioural rule or a piece of runtime state that only the other owner held, and it was usually discovered after shipping. The best single inspiration for a harder task is the September 2026 double-refund chain: an issue filed against the Stripe app could only be fixed after core exposed an idempotency key, in a specific patch release, and the app's fix took effect only after the subscription query stored in core's database was migrated for each installation ([apps #2446, opened](https://github.com/saleor/apps/issues/2446), [core #19811, opened](https://github.com/saleor/saleor/pull/19811)). Second are rule collisions that upstream has not fixed, above all the open report in which a transient Stripe error becomes a permanent "0 charged" because of core's event-time rule ([apps #2448, opened](https://github.com/saleor/apps/issues/2448)). Third are version gates and stored state that outlive a deploy, such as the Stripe app's semver gate that silently dropped card details once core reached 3.23 ([apps #2447, opened](https://github.com/saleor/apps/issues/2447)). These three attack four of the current task's five weaknesses directly and all date from after June 2026, so a model is unlikely to recall them. The fifth weakness, that one agent could read all the evidence, is not something the history fixes. The history shows what evidence was split in practice (the provider's records, the app's own store, core's delivery log), and the benchmark must enforce that split. The new evidence also revises the earlier report: payment incidents move from "no team advantage" to the lead candidate once they are redesigned as a missing datum plus a rollout. The caveat is corroboration. Most pull-request links below were built from commit subjects in local clones and the pages were not opened, and the richest cases are the newest and least independently checked.

**Context, stated once.** The benchmark runs a live company built from real Saleor code (core, the Stripe app and the dashboard, with a local stand-in for Stripe and synthetic customer traffic). Pushes to main deploy, and a hidden verifier judges the running company. In the team condition one AI agent owns each repository; a solo agent with the same total budget is the baseline. The current task is a delayed-refund incident made of two coupled reversions (the app reports refund events under the wrong provider id; core stopped de-duplicating refund events). One agent solved it in about 12 minutes for about $5 with full reward. Its weaknesses were a one-sentence contract, no dependence on deployment order, all evidence readable by one agent, a core fault recognised from memory of upstream code, and nothing to negotiate.

**How to read the links.** "Opened" in a link label means a researcher read that page on github.com, through the GitHub API, or on docs.saleor.io. Every other pull-request link was built from the number in a squash-commit subject in a full-history local clone (core to 2026-11-12, dashboard to 2026-11-13, apps to 2026-10-28). For those, the commit message or diff was read and the web page was not. Issue links were opened unless marked "listing only". "Post-June 2026" marks items dated after 30 June 2026, which rest on the clones alone unless also marked opened.

## The real contract is a table of behavioural rules that changed in patch releases

The current task's contract fits in one sentence because it uses one row of a much larger table. Between core and a payment app the rules are behavioural. Core de-duplicates on transaction, event type and `pspReference`, and treats an amount mismatch as an error, not a duplicate. A request event is paired with its later success or failure by `pspReference`. An event without a `pspReference` is left out of amount calculations. A success is ignored if a failure with the same reference has a newer `time`. The `actions` an app returns are honoured by the dashboard and not enforced by core ([Transactions docs, opened](https://docs.saleor.io/developer/payments/transactions), [Lifecycle docs, opened](https://docs.saleor.io/developer/payments/lifecycle)). The Stripe app delegates de-duplication to core by design and treats `alreadyProcessed` as success ([Stripe app docs, opened](https://docs.saleor.io/developer/app-store/apps/stripe/overview)).

Core changed these rules repeatedly inside patch releases, and usually ported each change to two or three live branches under different pull-request numbers. Examples:

- `pspReference` became optional for some responses in 2024 ([#16491](https://github.com/saleor/saleor/pull/16491)).
- `amount` became optional for failure events ([#16705](https://github.com/saleor/saleor/pull/16705)).
- A request event the app never acknowledged stopped counting as pending ([#17002](https://github.com/saleor/saleor/pull/17002)).
- In 3.21 the cancel request began to carry an amount where it had always been null ([#17690](https://github.com/saleor/saleor/pull/17690), [3.20 to 3.21 guide, opened](https://docs.saleor.io/upgrade-guides/core/3-20-to-3-21)).

Three or four minors are patched in parallel at any time, with between 57 and 122 patch tags per minor (counted from the clone's tags; [releases](https://github.com/saleor/saleor/releases)). So "which core am I talking to" is a question about the patch version, not the minor.

The app encodes its half of each rule in its own code. It chooses which Stripe amount field to report per intent status ([resolver](https://github.com/saleor/apps/blob/main/apps/stripe/src/modules/saleor/resolve-saleor-money-from-stripe-payment-intent.ts)), which timestamp to send ([apps #1918](https://github.com/saleor/apps/pull/1918)), and which provider id serves as `pspReference` for each event type. The refund-identity fix that the current task reverts took three app PRs in five days in May 2025 ([apps #1911](https://github.com/saleor/apps/pull/1911), [apps #1915](https://github.com/saleor/apps/pull/1915), [apps #1922](https://github.com/saleor/apps/pull/1922)). That history is public and predates the model's knowledge, which is consistent with the fault being recognised.

Two structural facts follow. First, in every verified payment case the symptom appeared somewhere other than the cause: in Stripe's records, in the dashboard, or in order totals. Second, explicit cross-repository links are rare. In all the threads read, only two exist: core #19811 naming apps #2446 as its reason, and a core issue closed as a duplicate of an apps issue ([core #18773, opened](https://github.com/saleor/saleor/issues/18773), [apps #2218, opened](https://github.com/saleor/apps/issues/2218)). The dependencies are real but mostly unrecorded. Many were reconstructed by the researchers from dates and diffs, and are flagged as inference where that is so.

## Six patterns ranked against the five weaknesses

The ratings below are judgments from the case evidence. No agent has been run on any of them. "Unmemorised" means the flagship case is dated after June 2026 or is still unfixed upstream.

| Rank | Pattern | Two-sided knowledge | Rollout order and version skew | Repair under traffic | Evidence split between owners | Unmemorised |
|---|---|---|---|---|---|---|
| 1 | The provider must expose a datum before the consumer can fix anything | Strong | Strong | Partial (prior damage must be reconciled; a design choice) | Strong | Strong |
| 2 | Rules that are each locally correct collide; open upstream | Strong | Weak | Strong | Strong | Strong |
| 3 | Version gates and stored state that outlive a deploy | Partial | Strong | Partial | Strong | Strong |
| 4 | Backfills and repairs that fight live traffic | Weak (mostly one owner) | Strong | Strong | Weak | Mixed |
| 5 | A symptom-side patch hides the other owner's root cause | Partial | Partial | Weak | Strong | Mixed |
| 6 | Unbuilt features whose open questions are contract questions | Strong | Partial | Weak | Weak | Strong |

### 1. The fix has to start in the other repository

**The flagship case is the idempotency key (post-June 2026).** An issue against the Stripe app stated that a re-invoked `TRANSACTION_REFUND_REQUESTED` webhook reaches Stripe as a new call, and that the app "has no mechanism for recognizing that the refund action was already submitted" ([apps #2446, opened](https://github.com/saleor/apps/issues/2446)). The core PR opened the same day calls itself "the enabling half of saleor/apps#2446" and says "Core has to expose the key before the app can consume it". Its body carries the retry facts only core's owner knows. The same delivery is re-sent on any 5xx up to five times. The broker can redeliver on a pod kill. A timeout never retries. A merchant's manual re-issue mints a fresh key, a gap the PR deliberately leaves open ([core #19811, opened](https://github.com/saleor/saleor/pull/19811)).

The order was:

1. The core patch, first tagged as 3.23.36 on 2026-09-24 ([3.23.36 release](https://github.com/saleor/saleor/releases/tag/3.23.36)).
2. The app release 2.10.0 five days later, which adds the field to three subscription queries and forwards it to Stripe's refund, capture and cancel calls ([apps commit a3c91997](https://github.com/saleor/apps/commit/a3c91997), [Stripe app changelog](https://github.com/saleor/apps/blob/main/apps/stripe/CHANGELOG.md)).
3. A per-installation webhook migration that rewrites the query stored in core ([migration script](https://github.com/saleor/apps/blob/main/apps/stripe/scripts/run-webhooks-migration.ts)).

Until the third step the payload has no key and the app silently falls back to the old behaviour with a warning log ([helper source](https://github.com/saleor/apps/blob/main/apps/stripe/src/modules/saleor/transaction-requested-event-helpers.ts)).

The contract here does not fit in a sentence. It needs core's retry semantics, the exact patch version, the fact that a subscription query is data in core's database, and Stripe's idempotency-key semantics. Core's key is per requested action, so two legitimate partial refunds of the same amount stay distinct, a point the issue raises itself.

The dashboard is a third party to the same fact:

- Its schema cron picked the field up from the 3.23 branch before it was released, and had to be changed to read the published release's schema ([dashboard #6958](https://github.com/saleor/saleor-dashboard/pull/6958)).
- Until 2026-06-30 its order page let staff trigger capture or cancel several times before the first resolved ([dashboard #6675](https://github.com/saleor/saleor-dashboard/pull/6675)).
- A sibling hole remains open in core: the automatic release task generates a new key on each run ([core #19812, opened](https://github.com/saleor/saleor/issues/19812)).

**The same shape recurs wherever an app shipped a heuristic first.**

- **Prices entered with tax.** The AvaTax app could not tell Avalara whether prices included tax until core added `Channel.taxConfiguration` to the payload ([core #15610, opened](https://github.com/saleor/saleor/pull/15610), [apps #1275, opened](https://github.com/saleor/apps/pull/1275)).
- **Order-level discounts.** The app could not distribute them correctly until core added a discount type ([core #16630, opened](https://github.com/saleor/saleor/pull/16630), [apps #1552, opened](https://github.com/saleor/apps/pull/1552)).
- **Ship-from override.** An app feature reading private metadata was merged, reverted five days later, and re-landed only after core granted tax apps access to those fields on the 3.22 release branch ([apps #2098, opened](https://github.com/saleor/apps/pull/2098), [apps #2104, opened](https://github.com/saleor/apps/pull/2104), [core #18374, opened](https://github.com/saleor/saleor/pull/18374), [apps #2135](https://github.com/saleor/apps/pull/2135)). No source states the reason for the revert; the permission explanation is the researchers' inference from the sequence.
- **File attributes (core and dashboard, post-June 2026).** The dashboard called a delete mutation that needed a different permission and was not crash-safe. Core moved the cleanup inside its update mutation, and the dashboard then dropped its call while deliberately tolerating older cores ([core #19722](https://github.com/saleor/saleor/pull/19722), [dashboard #6885](https://github.com/saleor/saleor-dashboard/pull/6885)).
- **Variant availability (post-June 2026).** A dashboard workaround shipped first, the core field three months later, and the dashboard's use of it five days after that, with "Requires Saleor 3.23.42 or later" stated only in a changeset ([dashboard #6762](https://github.com/saleor/saleor-dashboard/pull/6762), [core #19911](https://github.com/saleor/saleor/pull/19911), [dashboard #7034](https://github.com/saleor/saleor-dashboard/pull/7034)).
- **Order number in Stripe metadata (post-June 2026).** This adds a human step. Existing installations need a new permission that the app cannot grant itself, so a staff member must approve it in the dashboard before the feature turns on ([apps commit f001ac7e](https://github.com/saleor/apps/commit/f001ac7e), [order-sync installer](https://github.com/saleor/apps/blob/main/apps/stripe/src/modules/order-sync/order-sync-installer.ts)).

### 2. Each side is correct alone and the combination loses money

These cases are the best defence against recall because upstream has not fixed them.

**A transient Stripe error becomes a permanent zero (open, post-June 2026).** On a 429 or 5xx from Stripe during `transactionProcess`, the app answers `CHARGE_FAILURE` under the payment-intent id with no `time`, so core stamps "now". The Stripe webhook then reports `CHARGE_SUCCESS` with the event's creation time, which is older. Core does not count a success older than a failure with the same reference. The result is "Stripe has the money, the transaction shows 0 charged, and the checkout is not completed". A maintainer accepted the report ([apps #2448, opened](https://github.com/saleor/apps/issues/2448)). The fix proposed in the issue depends on a core rule from 2024: omit the `pspReference` on the failure, which removes the event from the calculation ([core #16491](https://github.com/saleor/saleor/pull/16491)). Neither repository's tests can see the fault, and transactions already damaged stay wrong after a code fix.

**Core loses totals on duplicate and overlapping reports (open, post-June 2026).** A redelivered identical report returns `alreadyProcessed: true` while the charged total stays at 0, and two overlapping charge reports end at 7.00 where 18.00 is correct ([core #19852, opened](https://github.com/saleor/saleor/issues/19852), [core #19854, opened](https://github.com/saleor/saleor/issues/19854)). Because the app stops on `alreadyProcessed`, it cannot repair this state from its side. These reports need caution: both say "No production incident is claimed", and a follow-up was closed by a maintainer as bot-generated.

**Other open reports in the same family (post-June 2026).**

- A refund request is lost for good when a worker dies ([core #20022, opened](https://github.com/saleor/saleor/issues/20022)).
- A crash between a gift-card balance commit and its charge event leaves the card charged and the order unpaid ([core #20023, opened](https://github.com/saleor/saleor/issues/20023)).
- One refused webhook publish after checkout completion drops the order confirmation and the remaining webhooks ([core #19835, opened](https://github.com/saleor/saleor/issues/19835)).
- A request to validate refund grants against reported refund totals has no PR ([core #19645, opened](https://github.com/saleor/saleor/issues/19645)).

**Older, fixed cases show the same structure with public answers.**

- The app used `amount_received`, which is 0 while an ACH or SEPA intent is processing, so core never considered the checkout paid ([apps #2086](https://github.com/saleor/apps/pull/2086)).
- An app could not send amount 0 on a failure because core raised on amount mismatch. That took from January 2024 to May 2025 to unwind across both repositories ([core #15231, opened](https://github.com/saleor/saleor/issues/15231), [core #16688, opened](https://github.com/saleor/saleor/pull/16688), [apps #1937](https://github.com/saleor/apps/pull/1937)). One part is still open ([core #19383, opened](https://github.com/saleor/saleor/pull/19383)).
- Core's own serialisation of event reports against checkout completion took about a dozen PRs across three branches between May and December 2025, including a lock moved a week after it was added ([#17789](https://github.com/saleor/saleor/pull/17789), [#17913](https://github.com/saleor/saleor/pull/17913), [#18642](https://github.com/saleor/saleor/pull/18642)). That the Stripe app's launch exposed these races is an inference from timing; no commit says so.

### 3. A version gate or stored query is still wrong after everyone has deployed

**The semver gate (fix is post-June 2026).** The Stripe app sent payment-method details only when `semver.satisfies(version, "3.22")` held. A bare `3.22` means 3.22.x, so the check is false for 3.23 ([validator source](https://github.com/saleor/apps/blob/main/packages/shared/src/saleor-version-compatibility-validator.ts), [apps #2447, opened](https://github.com/saleor/apps/issues/2447)). The gate shipped on 2025-10-15 ([apps #2103](https://github.com/saleor/apps/pull/2103)). Saleor 3.23.0 was tagged on 2026-04-08, and the fix arrived on 2026-10-01 ([apps commit 3601e299](https://github.com/saleor/apps/commit/3601e299)).

Three details make it a coordination problem:

- **The trigger was a core upgrade, not an app change.**
- **The fault was intermittent.** Only the Stripe-webhook path was gated, so details were lost only when the webhook beat the shopper's return or when core completed the checkout itself. Core then de-duplicated the later synchronous response and never applied its details.
- **The version checked is not live.** It is read back from a per-transaction row in the app's own store, written at initialise time and kept forever. Two consecutive edits reasoned about the gate without noticing it was false ([apps #2433](https://github.com/saleor/apps/pull/2433)).

Core does not backfill these details either: "Transactions created before 3.22 will not have these new details" ([3.22.0 release, opened](https://github.com/saleor/saleor/releases/tag/3.22.0)).

**The subscription query rejected by an older core (post-June 2026).** An SMTP app change selected `GiftCardPaymentMethodDetails`, a type that exists only in 3.23. On 3.22, `webhookCreate` rejected the whole query, 7 of 9 webhooks failed to register, and the install still returned 200. The app "silently sent no order or invoice emails" for two months. Code generation validated against the 3.23 schema, and the error was logged as an empty object ([apps #2398, opened](https://github.com/saleor/apps/pull/2398), [apps #2442, opened](https://github.com/saleor/apps/pull/2442)). The SMTP app is not in the benchmark company, but the mechanism is exactly the risk in the idempotency rollout. An installation on 3.23.0 to 3.23.35 satisfies the app's `>=3.23 <4` manifest but has no `idempotencyKey` field. Whether its webhook migration is rejected is an unconfirmed inference.

**The dashboard has the same class of fault at build time.** It builds against two committed core schemas with no runtime switch ([multi-schema doc](https://github.com/saleor/saleor-dashboard/blob/main/docs/multi-schema.md)).

- **Attribute fields removed (post-June 2026).** Core deprecated four attribute fields and removed them five days later. The dashboard had hidden the UI but kept the selections "on the assumption the fields would stay `@deprecated` on staging rather than disappear. They disappeared", and three screens failed validation ([core #19671](https://github.com/saleor/saleor/pull/19671), [dashboard #6843](https://github.com/saleor/saleor-dashboard/pull/6843), [core #19675](https://github.com/saleor/saleor/pull/19675), [dashboard #6871, opened](https://github.com/saleor/saleor-dashboard/pull/6871)).
- **App Problems release.** It "requires Saleor core 3.22.36. Used with older version, Extensions page will break" ([dashboard #6283, opened](https://github.com/saleor/saleor-dashboard/pull/6283)).
- **A field faked ahead of core.** The dashboard "faked" a field into its schema before core shipped it ([dashboard #6667](https://github.com/saleor/saleor-dashboard/pull/6667), [core #19360](https://github.com/saleor/saleor/pull/19360)).

**The migration that carries a contract change can itself fail.** The AvaTax webhook-migration script disabled live webhooks because it wrote `enabled` where the updater reads `isActive` ([apps #1717](https://github.com/saleor/apps/pull/1717)). A change to fail the deploy when a migration fails was reverted three days later ([apps #1581](https://github.com/saleor/apps/pull/1581), [apps #1582](https://github.com/saleor/apps/pull/1582)).

### 4. Backfills that never ran, and repairs that deadlock with checkout

This pattern is mostly core's alone, so it is weak evidence for needing several owners. It is the strongest evidence for "state that must be repaired while traffic runs", and it combines well with patterns 1 to 3.

**The policy.** Old code must run on the new schema, no lock may last longer than one second, and long data changes must run as batched, idempotent, self-re-queuing tasks ([zero-downtime policy, opened](https://docs.saleor.io/developer/community/zero-downtime-migrations)).

**The most repeated failure is a migration recorded as applied whose task never ran.**

- A January 2026 fix for address rows shared between a checkout and its order had to be re-fired by a new migration one day later. The 3.22 port is titled "Add missing celery conf and reapply migration", and four tags were cut that day ([#18651, opened](https://github.com/saleor/saleor/pull/18651), [#18671, opened](https://github.com/saleor/saleor/pull/18671), [#18670](https://github.com/saleor/saleor/pull/18670)). The pages give no rationale; the unregistered-task cause is inferred from the title and diff.
- A June 2025 denormalisation needed three migrations for one backfill ([#17859](https://github.com/saleor/saleor/pull/17859), [#17880](https://github.com/saleor/saleor/pull/17880), [#17882](https://github.com/saleor/saleor/pull/17882)).

**Backfills have deadlocked with live checkout three times.** ([#12503](https://github.com/saleor/saleor/pull/12503), [#16976](https://github.com/saleor/saleor/pull/16976), [#19001](https://github.com/saleor/saleor/pull/19001)).

**Several race fixes shipped with a separate repair for rows already damaged.**

- A data-repair migration for payments corrupted by a checkout race ([#15994](https://github.com/saleor/saleor/pull/15994)).
- A repair command for category trees corrupted by concurrent writes (post-June 2026, [#19668](https://github.com/saleor/saleor/pull/19668)).
- An order stuck `OVERCHARGED` "for good" because recalculated totals were saved without refreshing statuses (post-June 2026, [#19766](https://github.com/saleor/saleor/pull/19766)).

A code fix does not heal live data, and a repair run before the fix is live races with new damage. That second point is the researchers' inference, not a recorded incident.

### 5. The first patch lands where the symptom shows

In each cross-repository chain found, the first fix went into the repository that displayed the symptom. The root-cause fix, when different, came later in the other one.

**SSO login (post-June 2026).** A dashboard refactor made external login mutations select permission-guarded fields, and login failed with "You don't have permission to login". The dashboard hot-fixed by selecting less ([dashboard #6889](https://github.com/saleor/saleor-dashboard/pull/6889), [dashboard #6935, opened](https://github.com/saleor/saleor-dashboard/pull/6935)). Two days later core fixed the dormant cause: two auth mutations wrote the user to a dead cache key and left the request unauthenticated ([core #19747](https://github.com/saleor/saleor/pull/19747)). The dashboard's tests mocked the response shape and could not catch it.

**Core's mutation limit.** A security limit on mutations per request broke the dashboard's four-mutation stock update. To choose the limit, the core author had to extract every multi-mutation document from five dashboard versions ([core #19095, opened](https://github.com/saleor/saleor/pull/19095)).

**The payment-status pill.** It was wrong for transaction orders from a 2023 core issue to an October 2026 dashboard change, with a dashboard issue still open under the maintainer's remark "It works on the API but the presentation of the current order must be changed" ([core #12757, opened](https://github.com/saleor/saleor/issues/12757), [dashboard #5539, opened](https://github.com/saleor/saleor-dashboard/issues/5539), [dashboard #7045](https://github.com/saleor/saleor-dashboard/pull/7045)).

**App identity across reinstalls.** This took four app releases over 16 months. Core mints a new app id on reinstall and routes actions to the active app ([core #14933](https://github.com/saleor/saleor/pull/14933)). Stripe sends every account event to every endpoint and disables endpoints after days of non-2xx answers. The app first answered foreign events with 400 and later reversed to 200 plus a reported problem ([apps #1964](https://github.com/saleor/apps/pull/1964), [apps #2239](https://github.com/saleor/apps/pull/2239), [apps commit 205859ef](https://github.com/saleor/apps/commit/205859ef)).

**What this means for the benchmark.** The pattern says what to grade and where evidence naturally lives. A verifier that checks only the visible symptom rewards the symptom-side patch. The other owner's root cause shows up only in a different surface: core's delivery records, the provider's ledger, or the app's own store.

### 6. Features upstream designed and never built

The unbuilt maintainer RFCs are the only material in which nothing can be recalled and something must be negotiated, because their open questions are contract questions.

- **Payment requests (pay-by-link).** The RFC assigns a mutation and event to core, an optional sync webhook to the payment app, and the notification to an email app; the webhook payload was never specified ([core #12976, opened](https://github.com/saleor/saleor/issues/12976)).
- **Programmatic charging of stored payment methods.** It leaves the mutation name and the database design unresolved ([core #13401, opened](https://github.com/saleor/saleor/issues/13401)).
- **Additional fees.** It asks how fees reach the tax app and how the dashboard refunds one ([core #14031, opened](https://github.com/saleor/saleor/issues/14031), [discussion #14470, opened](https://github.com/saleor/saleor/discussions/14470)).
- **Newer specs (post-June 2026).** Buyer-aware price lists and cart-contents promotion conditions have had no maintainer reply ([core #19380, opened](https://github.com/saleor/saleor/issues/19380), [core #19796, opened](https://github.com/saleor/saleor/issues/19796)).

Most of these name owners the benchmark company does not have. Inside core, the Stripe app and the dashboard, the usable remainders are capability gaps.

- **Disputes.** Core accepts chargeback and refund-reverse events while the Stripe app subscribes to no dispute event and its source contains no such string ([Stripe app docs, opened](https://docs.saleor.io/developer/app-store/apps/stripe/overview), [core commit e61981461](https://github.com/saleor/saleor/commit/e61981461)).
- **Stored payment methods.** Core has had the tokenisation webhooks since 2023 with no Stripe-app or dashboard implementation ([core #12843, opened](https://github.com/saleor/saleor/issues/12843), [core #13879](https://github.com/saleor/saleor/pull/13879)).
- **Multiple captures.** The app's docs say they are not supported.

This pattern ranks last for two reasons. Feature work needs far more verifier and reference-solution effort than an incident. And the earlier report's evidence still applies: breadth with a stated edit per owner is cheap for one agent.

### Tax and email cases prove the point but need owners the company lacks

**Order-level discounts.** The best-documented case of irreducible two-sided knowledge in the whole history is who applies order-level discounts on the tax path. The AvaTax app changed strategy three times between May and September 2024 ([apps #1342, opened](https://github.com/saleor/apps/pull/1342), [apps #1396, opened](https://github.com/saleor/apps/pull/1396), [apps #1552, opened](https://github.com/saleor/apps/pull/1552)). Core changed its own propagation and then partly reverted it ([core #16696, opened](https://github.com/saleor/saleor/pull/16696), [core #16986, opened](https://github.com/saleor/saleor/pull/16986)). An app developer following the docs double-discounted until core fixed its resolver ([core #15531, opened](https://github.com/saleor/saleor/issues/15531), [core #15880](https://github.com/saleor/saleor/pull/15880)).

**HTTP status codes.** A status changed meaning for apps three times: retry, then no retry on 4xx from 3.18, then a count toward disabling the webhook once the circuit breaker arrived. Apps moved errors to 202 in response ([core #14566](https://github.com/saleor/saleor/pull/14566), [core #16658, opened](https://github.com/saleor/saleor/pull/16658), [apps #2136, opened](https://github.com/saleor/apps/pull/2136)). The SMTP app got it wrong in both directions within a year: 500 to 400 to stop duplicate emails, then 400 to 503 because core dropped events the app had failed for its own reasons ([apps #2123, opened](https://github.com/saleor/apps/pull/2123), [SMTP app changelog](https://github.com/saleor/apps/blob/main/apps/smtp/CHANGELOG.md)).

These transfer as mechanisms. The Stripe app faces the same three-party status protocol with Stripe on the other side. They do not transfer as tasks unless the company adds a tax or email owner.

## The new evidence reorders the earlier shortlist

The earlier report ("Hide the invariants, not the files") ranked seven projects for a miniature mirror company and judged that only promotions and a second channel gave a team a structural advantage. It was written before the benchmark ran on real Saleor code and before the first task's result. Four of its conclusions change.

**Payment incidents move from third to first, redesigned.** The earlier report rated them "no team advantage" because a compound fault is one coupled problem. The histories now show that the real incidents break into an enabling half and a consuming half with a mandatory order and a per-installation migration in between. That is a dependency between owners, not parallel labour. The earlier report's caution survives in part: the work is still small in lines, and nothing shows a team beats a solo agent on it at equal budget.

**The mixed-version candidate gets much cheaper.** It was ranked second with a heavy harness cost: two generations of a service running at once. The histories show skew at patch granularity (fields first available in 3.23.36, 3.22.36, 3.23.38 and 3.23.42) and inside stored subscription queries. One deployed core plus a stored query that predates the app's release reproduces it.

**Promotions and the second channel drop for this purpose.** They remain the cases where each owner has hours of separable work. But their hidden rules were published in 2023 and 2024, their contract is a schema, and neither stresses rollout order between the three repositories the company has.

**The memory mitigation improves.** The earlier report proposed adopting a historical variant of a published rule. The better source is behaviour that upstream built after June 2026, or has not built at all.

Two smaller corrections:

- The earlier report said the AvaTax app changed discount strategy three times in seven months. The dated PRs span May to September 2024.
- It cited #16974 for a migration-task deadlock. The clone shows #16976.

## What remains unverified

**Links and pages.** Most PR links were built from commit subjects and never opened. GitHub's unauthenticated rate limit cut short several issue searches, and review threads were not read for almost any PR, so who told whom what is known only where a commit message says it. Numbers taken from `main` are often ports, and the original PR against the oldest branch has a different number.

**Post-June 2026 material.** It is the least corroborated. Core and dashboard items come from the clones alone, apart from the few marked opened. Since 2026-09-17 the public apps repository receives "Sync from internal repository" commits. Stripe app changes after that date are known only from the public changelog and squashed diffs, and the internal PR numbers in those commits cannot be opened. Several open core reports from this period are written in a uniform audit style by external accounts with little maintainer triage, so their upstream fate is undetermined.

**Inferences presented as such.**

- That the Stripe app's launch exposed core's event-report races.
- That the ship-from revert was a permission failure.
- That the January 2026 re-fired migration was an unregistered task.
- That an installation on 3.23.0 to 3.23.35 would have its webhook migration rejected.
- That a repair run before its fix races with new damage.

**Conflicts between the notes, left unresolved.**

- The deferred-payload landing PR is given as #16999 in one note and #16808 in another.
- The first mutation limit is described as 1 in one commit text and 3 in the follow-up.
- The SMTP app's answer for a missing recipient is 202 in its changelog and 400 in a commit title.

**Not found or not examined.**

- A public post-mortem with outage duration or customer impact for any case.
- A case where the dashboard showed a wrong captured amount because of the Stripe app.
- A public statement of whether `requiredSaleorVersion` is re-checked when core is upgraded under an installed app.
- The app-sdk repository, GitHub Discussions on payments, Discord and the maintainers' private tracker.
- The legacy Stripe app's issues, which are deleted.

**Nothing here was run.** The ratings in the ranking table are judgments. No study shows that any of these patterns makes a team of agents beat a solo agent, and the earlier report's evidence that teams lose on tasks that fit one agent still stands.

## Conclusion

The history answers a narrower question than "what is hard". It shows that between these repositories the unit of dependency is a fact about time: which patch a field arrived in, which query is stored, which event is older, which rows were written before the change. A harder task is therefore built from sequence, not volume. A fault whose fix must begin in core, an app change that is inert until a stored query is migrated, and damaged transactions that must be reconciled while synthetic traffic keeps creating new ones give deployment order a wrong answer and a visible cost. That is what the current task lacked.

The idempotency chain and the open event-time collision can be combined into one incident. Because one is post-cutoff and the other is unfixed, there is no upstream answer to remember. For the unfixed half there is also no upstream reference solution, so the benchmark has to write and defend its own.

What the history cannot supply is the partition of evidence. Every case above was eventually solved by people who could see both sides, and a solo agent with all three repositories and the stand-in's logs is in that position. The real cases identify three natural owner-private surfaces: the provider's ledger, the app's per-transaction store, and core's delivery attempts. Whether the team condition means anything depends on the harness confining each surface to its owner, and on the verifier grading the root-cause surface as well as the symptom. Otherwise the pattern found in every real chain, patching where the symptom shows, will pass.

# Hide the invariants, not the files

SeedCo's hardest task was easy because it was broad and specified, and the evidence says breadth is not what stops current agents. On public benchmarks the same model loses a factor of three to six when a task grows from one issue to a whole feature or release, loses about two thirds of its score when the requirement detail that hidden tests enforce is withheld, and scores 10 to 28% when it must find an unnamed fault in a live, noisy system; nothing in the literature ties failure to the number of services or languages. A seven-ticket release with four independent tickets, a visible eight-check regression suite and a base company of roughly 6,000 lines exercises none of those levers, which is why 38 model calls sufficed. The reference repositories contain projects that do exercise them: Saleor's replacement of sales by promotion rules (a 32,217-line, 318-file landing PR and about 136 follow-up PRs), its mixed-version discipline (legacy flags, frozen clients, per-tenant webhook migration), the Stripe app's eighteen months of retry and race fixes, multichannel, the Lago and Kill Bill billing-boundary work, the tax rewrite, and Chatwoot's identity migration. Seven of these are ranked below as SeedCo tasks. Only two (promotions, and a second channel with its own legal entity) give a team of agents a structural advantage; the others are hard for one agent and no easier for ten. Three cautions apply throughout: nothing here was built or run, most real-world "hardness" is read from PR sizes, reverts and changelogs with no post-mortems, and no study measures how much naming the mirrored system lets a model recall hidden rules from memory.

## Hidden detail, preserved behaviour and live faults are the levers with measured effects

### What the benchmarks under 50% have in common

Issue-sized benchmarks are saturated in vendor-reported numbers, while the benchmarks still below about 50% share three traits: a large required output, diagnosis in a live system with no pointer to the fault, or grading that goes beyond tests passing. The table gives the measured effect of each lever. Model names are as the sources give them, and several sources are more than twelve months old, which is marked.

| Lever | Measured effect | Source |
|---|---|---|
| Size counted as merged changes or lines | GPT-5: 65.0% on SWE-bench Verified, **20.83% on SWE-EVO** (mean 610 lines, 21 files, 874 tests of which 81 fail-to-pass). Instances no configuration solved average **14.84 merged PRs**; the easiest average 1.67 | [SWE-EVO, Dec 2025](https://arxiv.org/html/2512.18470v2) |
| Feature-sized work against hidden tests | Claude Opus 4.5: 74.4% on SWE-bench Verified, **11.0% on FeatureBench** (mean 790 lines, 16 files, 62.7 fail-to-pass checks). Showing the tests lifts resolved rates from 3.3% and 16.7% to 60.0% and 63.3% | [FeatureBench, Feb 2026](https://arxiv.org/html/2602.10975v1) |
| Withheld requirement detail | With the problem statement only, GPT-5 falls from 25.9% to **8.40%** and Claude Opus 4.1 from 22.7% to **8.20%** (Sep 2025, older than 12 months) | [SWE-bench Pro](https://arxiv.org/html/2509.16941v2) |
| Unnamed fault in a live system | Best agent **25.3%** on realistic incident reports and **10.0%** on hard ones; removing source access degrades every metric | [ORCA-bench, Jul 2026](https://arxiv.org/pdf/2607.28545) |
| Noise and compound faults | Ambient noise costs 3 to 10 points of diagnosis; compound, metastable and low-level faults cut end-to-end success from about 58–64% to **15–28%** | [SREGym, Jul 2026](https://arxiv.org/html/2605.07161) |
| Safety graded apart from end state | Best Safe Pass **27.1%** against 92.5% for a human DBA; 72.2% of correct diagnoses still failed to reach the required state, and 17.3% of runs that reached it failed a safety rule such as a lock-wait limit | [DBA-Bench, Oct 2026](https://www.alphaxiv.org/abs/2607.22165.md) |
| Events arriving during the run | Safe Pass in **2 of 40** persistent runs of one to two hours; later events undid earlier verified repairs | [DBA-Bench](https://www.alphaxiv.org/abs/2607.22165.md) |
| Regression control over a long history | Most of 18 models keep every previously passing test passing in **fewer than 25%** of tasks | [SWE-CI, Mar 2026](https://arxiv.org/html/2603.03823v2) |
| Quality or reliability grading | Best tests-only rate 62.1%, best "tasteful" rate **34.7%**; the 80% time horizon is about 3.1 hours against 17.4 hours at 50% | [Senior SWE-bench, Jul 2026](https://senior-swe-bench.snorkel.ai/blog/2026-07-30-refresh), [METR data](https://metr.org/assets/benchmark_results_1_1.yaml) |

The failure analyses say the same thing from the other side. On large tasks, frontier agents rarely fail on syntax or tool use. More than 60% of GPT-5's SWE-EVO failures were instruction-following failures, meaning parts of the release notes were missed or misread ([SWE-EVO](https://arxiv.org/html/2512.18470v2)). In Factory's ProgramBench study single agents stopped on their own judgment while far from done, and their self-written checks covered only what they had chosen to build ([Factory, Aug 2026](https://factory.com/news/what-it-takes-for-coding-agents-to-complete-large-software-tasks)). On SWE-Marathon, runs that needed context compaction passed 0 of 71, long runs of identical tool calls took Claude Code's pass rate from 41.9% to 3.2%, and more tokens did not help ([SWE-Marathon summary, Jun 2026](https://www.emergentmind.com/papers/2606.07682)). In live systems, agents lock onto the first plausible anomaly and attempt mitigation without a correct diagnosis ([SREGym](https://arxiv.org/html/2605.07161)). A task is hard for a current agent when the set of things to get right is larger than the agent enumerates up front and the hidden checks cover parts the visible material does not point at.

### Which SeedCo design choices are weak levers

**Number of services and languages.** No published analysis found correlates failure with the count of services or languages, and the multi-service benchmarks do not report it. The lowest scores come from live multi-service systems, but the lever there is the hidden fault, not the service count ([ORCA-bench](https://arxiv.org/pdf/2607.28545)). Ten owners in six languages make a task wide; the result on `task02_release` shows that width with a small, stated edit per owner is cheap.

**File count.** About 50 files in the reference solution is well above SWE-EVO's 21, yet SWE-EVO sits near 21% and `task02_release` was solved in five minutes. The difference is the 874 tests per SWE-EVO task, about 793 of which must keep passing, and requirements given as release notes rather than tickets ([SWE-EVO](https://arxiv.org/html/2512.18470v2)).

**Independent tickets.** Four of the seven tickets in `task02_release` are independent by design (`README.md`, task table). Independent small tickets add calls, not difficulty. What correlates with failure is the number of dependent changes folded into one outcome.

**Tickets that name the change.** Every measured ablation says the statement carries most of the difficulty: withholding requirements and interfaces costs about two thirds of the score, and release notes alone cost SWE-EVO another four points. A ticket that says which behaviour to add in which service removes the discovery step.

**A small visible regression suite over a small base.** `task02_release` has 18 feature and 8 regression criteria over a company of about 6,000 source lines (`README.md`; line counts by file extension in `services/`). There is little existing behaviour to break and agents can read the checks that guard it. The benchmarks where regressions dominate grade against hundreds of preserved tests ([SWE-CI](https://arxiv.org/html/2603.03823v2)).

**The $20 budget and single-run scoring.** A cap bites only near the limit: SWE-bench Pro's 50-turn, $2 cap cut GPT-5 from 41.8% to 25.9% (older than 12 months), and 31.4% of SWE-Marathon failures were timeouts on work estimated at 40 to 400 expert hours ([SWE-bench Pro](https://arxiv.org/html/2509.16941v2), [SWE-Marathon](https://www.emergentmind.com/papers/2606.07682)). At $1.56 of $20 the cap is inert. Scoring one attempt is also the easiest regime; requiring every trial to pass stays hard for much longer.

**End-state-only grading.** Checking the company after the agent finishes lets symptom patches and unsafe rollouts pass. DBA-Bench's split of diagnosis, final state and safety is what keeps its headline score at 27%.

Three practical warnings follow from the same sources. Once tasks are hard, agents attack the verifier: 13.8% of SWE-Marathon trials contained an exploit-shaped action, and blocking retrieval of gold patches cost one model 21.48 points on SWE-bench Pro ([SWE-Marathon](https://www.emergentmind.com/papers/2606.07682), [SWE-Bench Pro Verified, Sep 2026](https://huggingface.co/papers/2609.08149.md)). SeedCo's reference solutions are generated by `tools/derive_solutions.py`, so that tool and its edit sets must never reach an agent's workspace. Wall-clock performance targets are not reproducible across machines (only 39 of 102 GSO reference patches pass their own validity rules on every replay), so use counted quantities such as external calls per request ([audit, Jul 2026](https://huggingface.co/papers/2607.01211)). And no published effect size exists for concurrency bugs, slow feedback loops or seeded data volume as isolated variables, so those levers rest on case evidence only.

### When a team of agents has a real advantage

The direct evidence is thin and mostly from vendors. Factory's three-role system raised Fable 5's median on the 24 hardest ProgramBench tasks from 56.7 to 89.3, at 14 times the spend on one task and with the validator taking 2% of it; the gain came from an independent definition of "done" that kept the implementer working, not from parallel labour ([Factory](https://factory.com/news/what-it-takes-for-coding-agents-to-complete-large-software-tasks)). Anthropic's sixteen-agent compiler build parallelised well while there were many independent failing tests and collapsed on one monolithic problem where every agent hit the same bug ([Anthropic, Feb 2026](https://www.anthropic.com/engineering/building-c-compiler)). On tasks that fit one agent, teams lose: on ParallACT a single agent holding both requirements passes 62% of contradictory instances against 16% for two parallel agents, and CooperBench found messaging did not raise success (17.14% with, 17.64% without) ([ParallACT](https://arxiv.org/html/2611.00314), [CooperBench](https://arxiv.org/html/2601.13295)). A team therefore helps on a SeedCo task only if each owner's share is hours of separately verifiable work, the total exceeds what one session sustains, or one role holds acceptance cases the implementers cannot see. No study locates the crossover point at matched budget.

## Seven projects, ranked, that would make SeedCo an order of magnitude harder

The ranking weighs how many measured levers a task uses, how well the real project documents its hidden rules, and how much new harness it needs. It is a judgment; no agent has been run on any of these. Sizes are GitHub figures for the named PRs and overstate nothing but understate programmes, because feature-branch PRs aggregate ten or more reviewed sub-PRs.

| Rank | SeedCo task | Real project | Real size | Main levers | Team advantage |
|---|---|---|---|---|---|
| 1 | Promotion rules replace sales | Saleor promotions, dashboard discount rules, AvaTax discount strategies | 32k-line landing PR; about 136 follow-ups | Size, hidden rules, live migration, legacy flag | Yes |
| 2 | Release a new Core generation with old clients live | Dashboard multi-schema, SMTP 3.22 incident, webhook migration runner, zero-downtime policy | Small diffs; years of reverts | Rollout safety, hidden old-client payloads, events during the run | Partial (ordering) |
| 3 | Payment incidents from symptoms only | Stripe app hardening, Core checkout races, Kill Bill Janitor | Each fix under 320 lines; about 60 Core race and deadlock PRs | Hidden compound fault, concurrency, diagnosis graded apart | No |
| 4 | Second channel and legal entity | Saleor multichannel, Lago billing entities | 553 commits, 283 files; about 296 Lago PRs | Size, preserved behaviour, backfill | Yes (strongest) |
| 5 | Billing boundaries, proration, dunning and renewals | Lago time zones and dunning, Kill Bill repair and overdue, WooCommerce and Shopify renewals | 50 PRs in five weeks; about 101 dunning PRs | Hidden numeric rules, live data migration, clock events | Limited |
| 6 | Tax pipeline with cached prices and outage containment | Saleor tax rewrite, AvaTax app, Lago tax failures | 12.7k-line, 241-file PR open six months | External call in price path, counted calls, status semantics | Medium |
| 7 | Customer identity change, history backfill, signed webhooks | Chatwoot BSUID migration, imports, webhook hardening | 11 + 8 + about 15 PRs | Identity and dedup, idempotent re-run, rollout without breakage | Low to medium |

### 1. Promotion rules replace sales across the company

**The real project.** Saleor replaced its Sale model with promotions and rules over releases 3.14 to 3.21. The landing PR is **+32,217/−6,208 across 318 files and 83 commits**, open four months; groundwork added a denormalised discounted price with a backfill, and follow-ons added order promotions (+7,797, 139 files) and draft-order promotions (178 commits, 60 review comments) ([RFC #12539](https://github.com/saleor/saleor/issues/12539), [#12980](https://github.com/saleor/saleor/pull/12980), [#12713](https://github.com/saleor/saleor/pull/12713), [#14696](https://github.com/saleor/saleor/pull/14696), [#15459](https://github.com/saleor/saleor/pull/15459)). The dashboard kept the old sales screens and the new rules screens in one build for about 22 months ([dashboard #4476](https://github.com/saleor/saleor-dashboard/pull/4476), [#4648](https://github.com/saleor/saleor-dashboard/pull/4648), [3.21→3.22 guide](https://docs.saleor.io/upgrade-guides/core/3-21-to-3-22)). The AvaTax app then changed its discount strategy three times in seven months to follow Core ([apps #1342](https://github.com/saleor/apps/pull/1342), [#1396](https://github.com/saleor/apps/pull/1396), [#1552](https://github.com/saleor/apps/pull/1552)).

**What made it hard.** Old sales stayed readable through the old API until edited through a rule mutation, after which the old API could no longer handle them; every sale was migrated by a background task for zero downtime ([RFC #12539](https://github.com/saleor/saleor/issues/12539)). The stacking rule was reversed after release: from 3.19 only the best rule within a promotion applies ([#15309](https://github.com/saleor/saleor/pull/15309)). The recalculation flag moved between models and a bug in that path was still being fixed in November 2026 ([#15338](https://github.com/saleor/saleor/pull/15338), [#19984](https://github.com/saleor/saleor/pull/19984)). Dashboard release 3.23.44 still carries nine promotion fixes, including a rule edit that removed every channel but the first and a `0.05` input saved as 5% ([dashboard changelog](https://github.com/saleor/saleor-dashboard/blob/main/CHANGELOG.md)). Rounding itself changed in 3.12: 12.5% off $13 became $11.37 where it had been $11.38 ([#12041](https://github.com/saleor/saleor/pull/12041)).

| | |
|---|---|
| SeedCo owners | `core` (rule model, migration of seeded sales, asynchronous price recalculation, old sale API), `dashboard` (rule editor beside the old screen), `storefront` and `mobile` (the released mobile build still reads sale fields), `taxes` (how discounts are distributed over lines and shipping), `notifications` (totals in emails), `subscriptions` (renewal price under a promotion), `support` (order totals beside conversations), `ops` (recalculation backlog alert) |
| Prerequisite | SeedCo has no sales or vouchers today (a search of `services/` finds neither), so the base company must first ship sales with seeded history |
| Told | The business outcome: marketing wants rules with conditions and rewards, existing sales keep working, no downtime |
| Hidden | Which rule wins; the rounding mode; old-API behaviour before and after a sale is edited; the legacy-flag default by channel age; the discount shape `taxes` needs; the mobile build's exact queries |
| Feature checks | Rule create, edit and delete through the API; variant prices correct after recalculation completes; best-rule selection; order and email totals; tax request content at the provider stub for calculate and for commit |
| Regression checks | Every seeded variant's price and every seeded order's totals unchanged after migration; old sale API responses; mobile replay; checkout prices correct while the backfill is running |
| Levers | Size in dependent changes, withheld rules, large preserved behaviour, live migration, legacy flag |
| Team | **Yes.** At least five owners have substantive, separately testable work joined by one contract (the discount shape on lines). The contract must be agreed before parallel work is safe |

### 2. Release a new Core generation while old clients and installed apps stay live

**The real projects.** Since November 2025 the Saleor dashboard builds against two Core schemas at once, with fields tagged as belonging to one schema only ([dashboard #6070](https://github.com/saleor/saleor-dashboard/pull/6070), [multi-schema doc](https://github.com/saleor/saleor-dashboard/blob/main/docs/multi-schema.md)). The motivating failure is sharp: the dashboard kept selecting three attribute fields that Core 3.24 removes, so every attribute page returned validation errors until a 17-file fix ([dashboard #6871](https://github.com/saleor/saleor-dashboard/pull/6871)). The same class hit a self-hoster running dashboard 3.20.18 against Core 3.17.62 ([saleor #17023](https://github.com/saleor/saleor/issues/17023)). On the app side, a 92-line SMTP feature selected a type that exists only in Core 3.23; on 3.22 the whole subscription query was rejected, **7 of 9 webhooks failed to register and the app silently sent no order emails** for two months, with codegen and the manifest both green ([apps #2398](https://github.com/saleor/apps/pull/2398), [#2442](https://github.com/saleor/apps/pull/2442)). Payload changes reach installed tenants through a webhook-migration runner whose history includes a merged-then-reverted failure policy and a bug that disabled tenants' webhooks ([apps #1318](https://github.com/saleor/apps/pull/1318), [#1581](https://github.com/saleor/apps/pull/1581), [#1582](https://github.com/saleor/apps/pull/1582), [#1717](https://github.com/saleor/apps/pull/1717)). Core's own rule is that old code must work with the new schema, migrations may not hold locks for more than one second, and data moves in batched, idempotent background tasks; those tasks have themselves deadlocked ([zero-downtime policy](https://docs.saleor.io/developer/community/zero-downtime-migrations), [#12503](https://github.com/saleor/saleor/pull/12503), [#16974](https://github.com/saleor/saleor/pull/16974)). The order id change from integer to UUID kept old ids valid for old orders ([#9324](https://github.com/saleor/saleor/pull/9324)).

**What made it hard.** A GraphQL client fails whole when it selects one removed field, behaviour-only changes break old clients with no schema signal (3.21's `accountRegister` stopped returning an error for an existing user), and stored state outlives the version that wrote it ([3.20→3.21 guide](https://docs.saleor.io/upgrade-guides/core/3-20-to-3-21), [apps #2433](https://github.com/saleor/apps/pull/2433)).

| | |
|---|---|
| SeedCo owners | `core` (new generation: removed and renamed fields, new order ids, one behaviour-only change, batched backfill), `mobile` (released builds, replay only), `dashboard` and `storefront` (work against both generations), `notifications`, `payments`, `taxes`, `support` (subscriptions migrated per installation, version-gated payloads), `ops` (migration progress and failed-registration alerts) |
| Told | The target generation and one sentence: no customer-visible errors during the release |
| Hidden | The frozen build's exact queries; which app selects a field the old generation lacks; that the verifier sends traffic throughout the upgrade; one installation that is unreachable during migration; rows written under the old generation |
| Feature checks | Mobile replay passes before, during and after; each app's registered webhooks equal its manifest on both generations; emails sent for orders on both; old order ids resolve; dashboard pages load with no validation errors on either generation |
| Safety checks (graded apart) | Zero failed requests during the upgrade, counted; backfill in bounded batches; no installation left with disabled webhooks; the unreachable installation skipped and reported |
| Regression checks | The full existing suite on both generations |
| Levers | Rollout safety, events during the run, withheld old-client payloads, reliability over repeated trials |
| Team | **Partial.** The coordination content is real (who moves first under expand and contract) but each consumer's edit is small, so a single agent holding everything probably still wins. This is the best candidate for showing that a no-messaging team fails |
| Harness cost | Two generations of a service must run at once and the verifier must act during the episode, which SeedCo's verifier does not do today |

### 3. Payment incidents diagnosed from symptoms only

**The real projects.** The Stripe app was a from-scratch build of 104 PRs (+32.3k/−8.9k lines) in twelve weeks, and its difficulty arrived afterwards. Core retries a transaction action webhook up to five times, and until the app forwarded Core's idempotency key each late retry created a second refund ([Stripe app changelog](https://github.com/saleor/apps/blob/main/apps/stripe/CHANGELOG.md)). Two concurrent initialise requests with the same key failed on a conditional write ([apps #2181](https://github.com/saleor/apps/pull/2181)); a failed store write left an orphaned payment intent ([#2208](https://github.com/saleor/apps/pull/2208)); events from another installation were first processed, then rejected with HTTP 400, which made Stripe retry for three days and threaten to disable the endpoint, and are now acknowledged with 200 and ignored ([#2035](https://github.com/saleor/apps/pull/2035), [#2239](https://github.com/saleor/apps/pull/2239), [changelog](https://github.com/saleor/apps/blob/main/apps/stripe/CHANGELOG.md)). Core has 36 merged PRs titled "race condition" and 26 titled "deadlock" (both counts include ports to release branches), from a 30-line lock between checkout completion and payment webhooks in 2023 to lock-ordering fixes in March 2026 ([#14885](https://github.com/saleor/saleor/pull/14885), [#17776](https://github.com/saleor/saleor/pull/17776), [#19001](https://github.com/saleor/saleor/pull/19001)). Kill Bill's Janitor reconciles payments whose outcome is unknown; its balance bug stayed open eleven months and a race in it has been open since 2022 ([#1216](https://github.com/killbill/killbill/pull/1216), [#1599](https://github.com/killbill/killbill/issues/1599), [payment guide](https://docs.killbill.io/latest/userguide_payment.html)).

**What made it hard.** Each fix is small. The defect is visible only under redelivery or concurrency, and correct behaviour cannot be derived from one service's code because three parties (Core's retry policy, the app's store, the provider's status semantics) each look correct alone.

| | |
|---|---|
| SeedCo owners | `payments` (idempotency, store and provider consistency, foreign events), `core` (completion against event-report race, retry policy), `subscriptions` (renewal charge with unknown outcome), `dashboard` (payment status), `support` and `notifications` (one refund shown, one email), `ops` (alert rule and runbook) |
| Told | Symptoms only: support conversations about double refunds, one alert, a finance mismatch in seeded data, among unrelated anomalies |
| Hidden | Two or three co-occurring faults; Core's retry count; the provider stub's reaction to repeated 4xx; seeded damage that must be reconciled |
| Feature checks | One provider call and one idempotency key per logical refund under five redeliveries; one order per checkout under concurrent completion and event report; both concurrent initialise calls succeed with one intent; unknown outcomes resolved by polling; seeded duplicates corrected |
| Diagnosis check (graded apart) | A root-cause note that names each fault and no others, scored by entity match as ITBench-AA does ([ITBench-AA](https://artificialanalysis.ai/es/articles/itbench-aa-launch)) |
| Regression checks | The existing payment, refund and renewal paths |
| Levers | Hidden compound fault, noise, concurrency, diagnosis and repair graded separately, all-trials-pass |
| Team | **No.** This is one coupled problem and parallel agents collide on it, as in the compiler case. It is the control task that is hard for one agent and no easier for a team |

### 4. Open a second channel with its own currency and legal entity

**The real projects.** Saleor's multichannel PR is the largest in the repository by commits: **+27,822/−9,653, 283 files, 553 commits**, with every priced or published model moved to per-channel listings and a channel argument added to every storefront query ([#6242](https://github.com/saleor/saleor/pull/6242)). The dashboard followed with 26 title-matching PRs on a long-lived branch, the largest touching 86 to 98 files ([dashboard #609](https://github.com/saleor/saleor-dashboard/pull/609), [#1045](https://github.com/saleor/saleor-dashboard/pull/1045)). Lago's equivalent, billing entities, runs to about 296 title-matching PRs from February 2025 and re-scopes customers, invoices, fees, taxes, invoice numbering and dunning, with a backfill giving every organisation a first entity ([PR search](https://github.com/getlago/lago-api/pulls?q=is%3Apr+%22billing+entity%22+OR+%22billing+entities%22+in%3Atitle+sort%3Acreated-asc), [#3394](https://github.com/getlago/lago-api/pull/3394)). The Stripe app keyed its provider webhook by channel and reversed to configuration id one day later ([apps #1854](https://github.com/saleor/apps/pull/1854), [#1857](https://github.com/saleor/apps/pull/1857)).

**What made it hard.** Volume with a compatibility burden: old data must land in a default channel and every old client must behave as before. Saleor took the break in a major version, so its own compatibility burden was lower than SeedCo's would be with a frozen mobile build.

| | |
|---|---|
| SeedCo owners | All ten: per-channel prices and availability in `core`; channel in URLs and queries in `storefront`; channel pickers and staff scoping in `dashboard`; default-channel behaviour for `mobile`; configuration per channel in `payments`; tax configuration and document numbering in `taxes`; sender and templates in `notifications`; plans and dunning per currency in `subscriptions`; routing in `support`; labels and alerts in `ops` |
| Told | The outcome: a second market with its own currency and legal entity |
| Hidden | How old clients default; numbering continuity for the first entity; per-currency rounding; which staff may see which channel |
| Feature checks | An order in the second currency traced end to end to its tax document, charge and email; per-channel lists; separate numbering sequences |
| Regression checks | Every existing-channel response identical to before, which calls for a regression suite an order of magnitude larger than today's eight checks |
| Levers | Size in dependent changes, preserved behaviour, backfill |
| Team | **Yes, the strongest case.** Every owner has separately verifiable work once the channel identity contract is fixed. The risk is that it is merely broad unless each owner's share is deep |
| Unverified | SeedCo's code already mentions channels in about 20 files; how much per-channel behaviour exists was not checked |

### 5. Billing boundaries, proration, dunning and renewals for subscriptions

**The real projects.** Lago moved billing boundaries from UTC dates to customer-time-zone datetimes in 50 PRs over five weeks, needed four fixes within days of the boundary change, and added an explicit guard so a subscription is not billed twice on its creation or billing date ([PR search](https://github.com/getlago/lago-api/pulls?q=is%3Apr+timezone+in%3Atitle+sort%3Acreated-asc), [#662](https://github.com/getlago/lago-api/pull/662)). Its dunning work is about 101 PRs in two phases, with rules that group overdue invoices into one payment request per currency and restart a campaign when it is reassigned ([dunning docs](https://getlago.com/docs/guide/dunning/automatic-dunning)). Kill Bill's invoicing recomputes the full view on each run and diffs it against what is stored; its documentation gives a worked repair example to the cent ($239.95 repair, $9.63 prorated charge, $230.32 credit), its 0.21.8 change altered the items produced without altering any amount, and an alignment bug for annual add-ons has been open since 2023 ([invoice subsystem](https://docs.killbill.io/latest/invoice_subsystem.html), [0.21.8 notes](https://github.com/killbill/killbill/releases/tag/killbill-0.21.8), [#1881](https://github.com/killbill/killbill/issues/1881)). Subscriptions bolted onto commerce platforms add their own failures: WooCommerce's April 2026 incident left subscriptions stuck on manual renewal after plan switches, cloned sites charge customers twice, about 25% of one merchant's renewals failed on deadlocks after a storage migration, and Shopify fails a billing attempt on out-of-stock items and requires a client idempotency key ([Woo advisory](https://developer.woocommerce.com/?p=8769973), [Woo staging doc](https://woocommerce.com/document/subscriptions-handles-staging-sites/), [DevPress report](https://devpress.com/woocommerce-hpos-address-table-deadlocks/), [Shopify contracts](https://shopify.dev/docs/apps/build/purchase-options/subscriptions/contracts/build-a-subscription-contract)). Medusa's official recipe builds each renewal order by copying the original cart's tax and adjustment lines ([Medusa recipe](https://docs.medusajs.com/resources/recipes/subscriptions/examples/standard)).

| | |
|---|---|
| SeedCo owners | `subscriptions` (most of the work), `core` (renewal orders), `payments` (off-session charge, payment request), `taxes` (tax recomputed at renewal), `notifications` (dunning emails), `support`, `ops` |
| Told | Outcomes: bill in the customer's time zone, prorate plan changes, chase overdue renewals |
| Hidden | Nobody is billed twice or skipped at the migration boundary, including seeded subscriptions that straddle a daylight-saving change; proration figures; a plan switch keeps automatic renewal; a second scheduler instance must not charge; renewal uses current price and tax, not a snapshot |
| Feature checks | A scripted timeline on a clock the verifier controls, compared with expected invoices, orders, provider charges and emails |
| Regression checks | Every seeded subscription's next charge date and amount, unless the change is meant to move it |
| Levers | Withheld numeric rules, live data migration, clock-driven events, idempotency |
| Team | **Limited.** Most of the volume sits in one owner. A team gains only if one role holds the timeline cases as an independent acceptance instrument |
| Harness cost | A controllable clock across services; whether SeedCo has one was not checked |

### 6. Tax pipeline with cached prices, flat rates and outage containment

**The real projects.** Saleor's tax rewrite came in two feature branches: synchronous tax webhooks (+6,836/−1,889, 135 files, 52 review comments) and flat-rate taxes (**+12,666/−6,357, 241 files, open six months**) ([#9526](https://github.com/saleor/saleor/pull/9526), [#9784](https://github.com/saleor/saleor/pull/9784)); the dashboard's matching PR was 131 files over five and a half months ([dashboard #2072](https://github.com/saleor/saleor-dashboard/pull/2072)). The rules that matter are stated in the RFC: prices are stored until invalidated or expired, and completion fails if no tax data comes back. Later, list queries stopped triggering external tax calls while single-object queries still do ([#17268](https://github.com/saleor/saleor/pull/17268), [#17421](https://github.com/saleor/saleor/pull/17421)). On the app side, status codes became control signals: with Core's circuit breaker some errors must return 202 instead of 4xx, and a provider timeout returns 504 ([#16658](https://github.com/saleor/saleor/pull/16658), [apps #2136](https://github.com/saleor/apps/pull/2136), [#2279](https://github.com/saleor/apps/pull/2279)). Lago's tax-provider integration (about 208 PRs) added a failed invoice state with retry-one and retry-all ([PR search](https://github.com/getlago/lago-api/pulls?q=is%3Apr+anrok+OR+avalara+OR+%22tax+provider%22+OR+%22tax+error%22+in%3Atitle+sort%3Acreated-asc)). The bug tail is long: an order discount applied twice whenever a tax app was active ([#10428](https://github.com/saleor/saleor/pull/10428)).

| | |
|---|---|
| SeedCo owners | `core` (price cache with expiry, flat-rate fallback, breaker), `taxes` (error classes, commit and void tolerance), `dashboard` (tax configuration), `storefront`, `subscriptions` (renewal held when tax fails, then retried), `ops` (breaker alert) |
| Already covered | Committing tax on confirmation is the subject of `task01_order_confirmation`, so this candidate should not repeat it |
| Told | Outcomes: checkout survives a tax provider outage; prices entered with tax are supported |
| Hidden | Zero external calls from list queries; the country resolution order; completion refused without tax data; the status code for each error class; no double discount |
| Feature checks | Counted calls at the tax stub per query type; behaviour under injected timeouts; breaker state; correct totals for tax-inclusive prices |
| Regression checks | Seeded order totals and tax documents |
| Levers | External call in the price path, counted quantities, status semantics, injected faults |
| Team | **Medium.** `core` and `taxes` are coupled through the error contract; the rest is parallel but small |

### 7. Customer identity change, history backfill and signed webhooks for support

**The real projects.** WhatsApp's move to business-scoped user ids forced Chatwoot into an eleven-PR migration against an external deadline; the direction changed mid-flight, and ignoring identifier rotation meant the next message created a second contact and split the customer's history ([issue #13837](https://github.com/chatwoot/chatwoot/issues/13837), [#15175](https://github.com/chatwoot/chatwoot/pull/15175), [#15357](https://github.com/chatwoot/chatwoot/pull/15357)). Its Intercom import (69 files, 6,250 lines) stores durable source mappings, records already-imported items as skipped, writes history without outbound delivery, and retries a stalled run under an account lock ([#14922](https://github.com/chatwoot/chatwoot/pull/14922), [#15050](https://github.com/chatwoot/chatwoot/pull/15050)). Its webhook hardening shows how rollout fails: Twilio signature validation and Bandwidth callback authentication were both merged and reverted ([#14125](https://github.com/chatwoot/chatwoot/pull/14125), [#16577](https://github.com/chatwoot/chatwoot/pull/16577)), and duplicate provider deliveries produced duplicate customer webhooks ([#13523](https://github.com/chatwoot/chatwoot/pull/13523)). All three sit in Chatwoot's MIT area.

| | |
|---|---|
| SeedCo owners | `support` (contact identity, backfill, dedup), `core` (identity change events, signing), `notifications`, `payments`, `subscriptions` (receive signed events), `ops` |
| Told | Outcomes: customers who merge accounts keep one history; support sees past orders; webhooks are signed |
| Hidden | Events arrive under old and new ids, out of order and duplicated; the backfill is re-run; unsigned deliveries are in flight when signing starts; history must send no emails |
| Feature checks | One contact and one conversation after rotation; a second backfill run creates nothing; invalid signature returns 401; no outbound email for imported history |
| Regression checks | Existing support flows and all existing webhook consumers |
| Levers | Identity and dedup, idempotent re-run, absence of side effects, rollout order |
| Team | **Low to medium.** Signing is a genuine ordering problem across owners; the rest is mostly `support` |

## Other candidates, by repository

These were considered and not shortlisted, either because they are covered by a shortlisted task, are internal with weak outside observables, or sit in restricted licence areas.

### saleor/saleor

| Project | Anchors | Real size | Why hard | Outside observable | Note |
|---|---|---|---|---|---|
| Transactions API replaces Payments | [#12401](https://github.com/saleor/saleor/pull/12401), [#12179](https://github.com/saleor/saleor/pull/12179), [#13020](https://github.com/saleor/saleor/pull/13020) | +16,903, 120 files, seven months; about 189 title-matching PRs | Two payment models side by side; preview then break; mixing later forbidden | Idempotent completion, ownership rule, metadata merge | SeedCo Core already has transactions; the dual-model part feeds candidate 3 |
| Webhook delivery pipeline | [#9394](https://github.com/saleor/saleor/pull/9394), [#18607](https://github.com/saleor/saleor/pull/18607), [#18635](https://github.com/saleor/saleor/pull/18635), [#14566](https://github.com/saleor/saleor/pull/14566) | Many PRs of 20 to 25 files, 2022 to 2026 | Deferred payloads go stale; replica-lag fix reverted and re-landed | Payload content after two quick updates; no retry on 4xx | Strong add-on to candidate 2 |
| Stock reservations and availability decoupling | [#7589](https://github.com/saleor/saleor/pull/7589), [#19014](https://github.com/saleor/saleor/pull/19014), [#17657](https://github.com/saleor/saleor/pull/17657) | +2,650, 34 files, 73 review comments | Legacy flag on for existing instances; deallocation invariants | Availability under each flag value; reservation expiry | SeedCo has no stock today |
| Multiple codes per voucher | [#14123](https://github.com/saleor/saleor/pull/14123), [#15857](https://github.com/saleor/saleor/pull/15857) | +8,439, 141 files | Deprecated fields return the first code; usage race | Usage count under concurrent redemption | Needs vouchers first |
| Line-level discount propagation | [#17510](https://github.com/saleor/saleor/pull/17510), [#17587](https://github.com/saleor/saleor/pull/17587) | Several PRs in 3.21 | Per-channel legacy flag by channel age | Discount type and amounts per line | Folded into candidate 1 |
| Channel permissions for staff | [#10423](https://github.com/saleor/saleor/pull/10423) | +8,026, 126 files, eight months | Only orders enforced in the first version | Restricted staff see only their channels | Add-on to candidate 4 |
| Search vectors and 3.23 overhaul | [#9344](https://github.com/saleor/saleor/pull/9344), [#10279](https://github.com/saleor/saleor/pull/10279), [#18786](https://github.com/saleor/saleor/pull/18786) | About 40 title-matching PRs | Crashes on bulk vector SQL; dirty-flag deadlock | Prefix, phrase and accent-insensitive results | Mostly one owner |
| Explicit delivery options | [#18887](https://github.com/saleor/saleor/pull/18887) | +1,220, 9 files | Old and new refresh behaviour must coexist | Stale against invalid delivery problems | Good frozen-client seed |
| Attribute relation refactor | [#12881](https://github.com/saleor/saleor/issues/12881), [#13407](https://github.com/saleor/saleor/pull/13407) | 50 files, seven staged database steps | Staged migration | Only "values unchanged" | Internal |
| Gift cards, bulk order create | [#7827](https://github.com/saleor/saleor/pull/7827), [#12269](https://github.com/saleor/saleor/pull/12269) | 103 files; 37 files | Thin evidence | Balances, bulk results | Lower priority |

### saleor/saleor-dashboard

| Project | Anchors | Real size | Why hard | Outside observable |
|---|---|---|---|---|
| Transactions and refunds on the order page | [#2233](https://github.com/saleor/saleor-dashboard/pull/2233), [#4750](https://github.com/saleor/saleor-dashboard/pull/4750), [#6122](https://github.com/saleor/saleor-dashboard/pull/6122) | Seven-month umbrella PR, 256 files; three waves to 2025 | Per-order choice of old or new payment view; contract moved twice | Page state for each kind of order; refund carries a transaction id |
| Filters move to `where` | [#3272](https://github.com/saleor/saleor-dashboard/issues/3272), [#5791](https://github.com/saleor/saleor-dashboard/pull/5791) | About 40 PRs in a year; 76 files | Negated filters returned the positive set | Outgoing query; complement results |
| Apps become extensions | [#599](https://github.com/saleor/saleor-dashboard/pull/599), [#5566](https://github.com/saleor/saleor-dashboard/pull/5566), [#6015](https://github.com/saleor/saleor-dashboard/pull/6015) | 54 PRs in 2025 | Route change broke third-party apps | Old deep links resolve; both field names mount |
| Simple taxes | [#2072](https://github.com/saleor/saleor-dashboard/pull/2072) | 131 files, 5.5 months | Dropped a product field; permission follow-ups | Folded into candidate 6 |
| Variant and list datagrids | [#2040](https://github.com/saleor/saleor-dashboard/pull/2040), [#3296](https://github.com/saleor/saleor-dashboard/pull/3296) | 87 title-matching PRs | Interface only | Bulk edit saves all rows |
| Design-system migration, vendored SDK removal | [#4125](https://github.com/saleor/saleor-dashboard/pull/4125), [#6889](https://github.com/saleor/saleor-dashboard/pull/6889) | 54 PRs over five years; 65 files | Visual or internal | Weak |

### saleor/storefront, SDKs and the mobile example

| Project | Anchors | Real size | Why hard | Use for SeedCo |
|---|---|---|---|---|
| "A new beginning" rewrite | [#888](https://github.com/saleor/storefront/pull/888) | 1,272 files, about 558k lines deleted | Clean-slate replacement | Shapes only; no migration story |
| Paper checkout v2 and locale routing | [#1210](https://github.com/saleor/storefront/pull/1210), [#1211](https://github.com/saleor/storefront/pull/1211) | 342 and 413 files | Legacy URL redirects; new delivery contract | Redirect checks; pins Core 3.23 or later rather than supporting two versions |
| Payments: in-repo handlers to payment apps | [#823](https://github.com/saleor/storefront/pull/823), [#1119](https://github.com/saleor/storefront/pull/1119) | 122 files | Three generations | Feeds candidate 3 |
| Auth rewrites | [#734](https://github.com/saleor/storefront/pull/734), [#835](https://github.com/saleor/storefront/pull/835) | 39 and 46 files | Token handling | Single owner |
| SDK deprecation | [discussion #12891](https://github.com/saleor/saleor/discussions/12891) | n/a | No compatibility policy stated | Evidence that the frozen-mobile constraint has no client-side precedent |
| React Native example | [repository](https://github.com/saleor/example-react-native-typescript) | 4 commits, archived | Nothing | No task seeds; the mobile constraints come from Core and dashboard history |

### saleor/apps and app-sdk

| Project | Anchors | Real size | Why hard | Outside observable |
|---|---|---|---|---|
| Stripe transaction lifecycle build | [#1862](https://github.com/saleor/apps/pull/1862), [#1885](https://github.com/saleor/apps/pull/1885), [#1895](https://github.com/saleor/apps/pull/1895), [#1911](https://github.com/saleor/apps/pull/1911) | 104 PRs, +32.3k/−8.9k, 12 weeks | Four sub-designs rewritten within days | Per-flow results at Core and provider stub |
| Order-created to order-confirmed flow, then app split | [#826](https://github.com/saleor/apps/pull/826), [#916](https://github.com/saleor/apps/pull/916), [#1201](https://github.com/saleor/apps/pull/1201) | 75 files +4,302, then −3,406; split 430 files | Tenant migration then deletion of the old path | Largely covered by `task01_order_confirmation` |
| NP Atobarai refunds around fulfilment | [#2036](https://github.com/saleor/apps/pull/2036), [#2044](https://github.com/saleor/apps/pull/2044) | 27 PRs, +23.1k/−4.2k | Refund depends on fulfilment state | Provider calls by order state |
| Token store moved to DynamoDB | [#2000](https://github.com/saleor/apps/pull/2000), [#2204](https://github.com/saleor/apps/pull/2204) | 9 PRs, +4.4k/−2.8k | Every tenant's auth storage changes | App still authenticates to every tenant |
| Client logs for AvaTax | [#1576](https://github.com/saleor/apps/pull/1576) | 7 PRs, +3.6k | Removed, rebuilt, background writes cut off | Stored log documents with expiry |
| Dropped notification events | [#2357](https://github.com/saleor/apps/pull/2357) | Small | App returned 200 for an unmapped event; no set-password email | Email in the outbox |
| App Problems, stale-installation clean-up | [#2251](https://github.com/saleor/apps/pull/2251), [#2363](https://github.com/saleor/apps/pull/2363) | 8 PRs in 11 days | Near-miss deleting non-cloud tenants' data | Data kept for live installations |
| app-sdk 1.0 | [changelog](https://github.com/saleor/app-sdk/blob/main/CHANGELOG.md), [#1799](https://github.com/saleor/apps/pull/1799) | 82 files in the monorepo | Version representation and header changes | Internal |

### chatwoot/chatwoot

| Project | Anchors | Real size | Licence area | Why hard | Outside observable |
|---|---|---|---|---|---|
| Captain AI assistant | [#10665](https://github.com/chatwoot/chatwoot/pull/10665), [#15985](https://github.com/chatwoot/chatwoot/pull/15985) | 238 PRs, about 110k lines | Mostly enterprise | Two engine migrations | Excluded: restricted and not commerce |
| Vue 3 and new interface | [#10047](https://github.com/chatwoot/chatwoot/pull/10047) | 436 commits, 661 files | MIT | Whole front end | None from outside |
| Voice channel | [#11602](https://github.com/chatwoot/chatwoot/pull/11602), [#14091](https://github.com/chatwoot/chatwoot/pull/14091) | 54 PRs, about 29k lines | Mostly enterprise | Call state moved to a new model | Excluded |
| Shopify app-store install and billing | [#13549](https://github.com/chatwoot/chatwoot/pull/13549), [#15756](https://github.com/chatwoot/chatwoot/pull/15756), [#13550](https://github.com/chatwoot/chatwoot/pull/13550) | 10 PRs, about 12.5k lines | Mixed | Review rejections; install follows the user through every sign-in path | 401 on bad signature; uninstall cleanup |
| Assignment v2 | [#12320](https://github.com/chatwoot/chatwoot/pull/12320), [#14495](https://github.com/chatwoot/chatwoot/pull/14495), [#13904](https://github.com/chatwoot/chatwoot/pull/13904) | 24 PRs, about 12.9k lines | Mixed | One conversation reassigned dozens of times; capacity check unreachable | Exactly-once assignment under concurrent events |
| Sidebar unread counts | [#14769](https://github.com/chatwoot/chatwoot/pull/14769), [#14885](https://github.com/chatwoot/chatwoot/pull/14885) | 10 PRs, about 10k lines | MIT | Production incident, reverted next day | Counts by API; the failure was load-shaped |
| Reporting rollup table | [#13796](https://github.com/chatwoot/chatwoot/pull/13796), [#13798](https://github.com/chatwoot/chatwoot/pull/13798) | About 3.3k lines | MIT | Dual read path must match raw results | Identical report responses |
| Service-level policies | [#13392](https://github.com/chatwoot/chatwoot/pull/13392), [#15024](https://github.com/chatwoot/chatwoot/pull/15024) | 42 PRs, about 11.2k lines | Enterprise | Business-hours rewrite two years later | Deadlines and frozen misses in the API |
| Stripe read-only sidebar | [#15765](https://github.com/chatwoot/chatwoot/pull/15765) | 3 PRs | MIT | Small | Closest analogue to payments beside a conversation |

### Kill Bill

| Project | Anchors | Real size | Why hard | Outside observable |
|---|---|---|---|---|
| 0.19 to 0.20 release line | [#1023](https://github.com/killbill/killbill/pull/1023), [0.20.0 notes](https://github.com/killbill/killbill/releases/tag/killbill-0.20.0) | 925 commits, 876 files, +36,093/−22,493 | A release train, not one project | Use its parts: in-arrear billing, draft and void invoices |
| Hierarchical accounts | [#553](https://github.com/killbill/killbill/issues/553) | Seven months, three repositories | Parent summary invoices; later double-payment risk | Five scenarios with expected parent invoices |
| Billing-day alignment | [#1484](https://github.com/killbill/killbill/pull/1484), [search](https://github.com/killbill/killbill/issues?q=BCD+in%3Atitle) | +2,116/−884, plus a decade of defects | Daylight saving, end of month | Dated timelines |
| Upgrade migrations 0.20 to 0.24 | [0.22.0](https://github.com/killbill/killbill/releases/tag/killbill-0.22.0), [0.24.0](https://github.com/killbill/killbill/releases/tag/killbill-0.24.0) | Nine history tables; column type changes | Backfills on live billing data | Stated backfill values |
| Overdue state machine | [overdue doc](https://docs.killbill.io/latest/overdue.html) | Configuration-driven | Independent of payment retries | States, blocking, retries eight days apart |
| Usage billing | [search](https://github.com/killbill/killbill/issues?q=usage+in%3Atitle+is%3Aissue) | 51 issues | Idempotency; integer to decimal | Usage totals |

### Lago

| Project | Anchors | Real size (title-search hits) | Why hard | Outside observable |
|---|---|---|---|---|
| Events to ClickHouse and Kafka | [search](https://github.com/getlago/lago-api/pulls?q=is%3Apr+clickhouse+in%3Atitle+sort%3Acreated-asc) | About 193 PRs | Each aggregation re-implemented | Only unchanged usage totals |
| Progressive billing | [search](https://github.com/getlago/lago-api/pulls?q=is%3Apr+%22progressive+billing%22+OR+progressive_billing+OR+%22lifetime+usage%22+OR+ProgressiveBilling+in%3Atitle+sort%3Acreated-asc) | About 177 PRs | Threshold invoices credited at period end | Invoice sequence; rule text not confirmed from docs |
| Grace period and draft invoices | [search](https://github.com/getlago/lago-api/pulls?q=is%3Apr+%22grace+period%22+OR+grace_period+OR+%22draft+invoice%22+in%3Atitle+sort%3Acreated-asc) | About 120 PRs | A status field renamed and a new one added | Status transitions and webhooks |
| Pay in advance | [search](https://github.com/getlago/lago-api/pulls?q=is%3Apr+%22pay+in+advance%22+OR+%22instant+charge%22+OR+%22pay_in_advance%22+in%3Atitle+sort%3Acreated-asc) | About 357 PRs in two phases | A year of boundary fixes | Fees on upgrade and termination |
| Wallets and credit notes | [search](https://github.com/getlago/lago-api/pulls?q=is%3Apr+wallet+OR+%22credit+note%22+OR+%22credit+notes%22+in%3Atitle+sort%3Acreated-asc) | About 997 PRs across two areas | Long-lived; one revert | Balances |

### Subscriptions on commerce platforms

| Source | What it gives | Link |
|---|---|---|
| Saleor | Confirmation that Saleor has no native subscriptions and that merchants build an app plus a scheduled job | [issue #2466](https://github.com/saleor/saleor/issues/2466), [discussion #9359](https://github.com/saleor/saleor/discussions/9359) |
| Medusa | A renewal workflow with compensation; gaps in tax, stock and price handling at renewal | [recipe](https://docs.medusajs.com/resources/recipes/subscriptions/examples/standard) |
| Vendure plugin | Schedule delegated to Stripe; only initial payments refundable from the platform | [plugin docs](https://docs.vendure.io/plugins/stripe-subscription) |
| Shopify | Idempotency key per billing attempt, asynchronous outcomes, stock failure codes, a rebilling cap of 30 in 35 days | [contracts guide](https://shopify.dev/docs/apps/build/purchase-options/subscriptions/contracts/build-a-subscription-contract) |
| WooCommerce Subscriptions | Retry rules as data, duplicate charges from cloned sites, the 2026 manual-renewal incident | [retry guide](https://woocommerce.com/document/subscriptions/develop/failed-payment-retry/), [staging doc](https://woocommerce.com/document/subscriptions-handles-staging-sites/), [advisory](https://developer.woocommerce.com/?p=8769973) |

## Licences allow names, behaviour and structure; no code is copied from any source

The working rule is the same for every source, permissive or not: take names, behaviour, structure and published worked examples, and copy no code. The table records what was confirmed and where the restrictive cases are.

| Source | Licence | Status | What may be used |
|---|---|---|---|
| saleor/saleor | BSD-3-Clause ([LICENSE](https://github.com/saleor/saleor/blob/main/LICENSE)) | Confirmed from the file | Names, behaviour, structure |
| saleor/saleor-dashboard | BSD-3-Clause | GitHub-detected | Names, behaviour, structure |
| saleor/apps, saleor/app-sdk, saleor-app-payment-stripe, saleor-app-template | BSD-3-Clause | Read from each LICENSE | Names, behaviour, structure |
| saleor/storefront ("Paper") | FSL-1.1-ALv2, converting to Apache 2.0 after two years ([README](https://github.com/saleor/storefront)) | Confirmed; the licence before the 2026 relicensing was not verified | **Restrictive: names and structure only** |
| saleor/saleor-storefront (legacy) | BSD-3-Clause | GitHub-detected, archived | Names, behaviour, structure |
| saleor/saleor-sdk | MIT | Archived, deprecated | Names, behaviour, structure |
| saleor/saleor-checkout, saleor/auth-sdk, example-react-native-typescript | None detected | auth-sdk's package metadata was not checked | **No licence: names and structure only** |
| chatwoot/chatwoot outside `enterprise/` | MIT ([LICENSE](https://github.com/chatwoot/chatwoot/blob/develop/LICENSE)) | Confirmed | Names, behaviour, structure |
| chatwoot/chatwoot `enterprise/` | Chatwoot Enterprise licence ([file](https://github.com/chatwoot/chatwoot/blob/develop/enterprise/LICENSE)) | Confirmed | **Restrictive: behaviour as described in public PR text only.** Affects service-level policies, capacity assignment, Captain, voice and advanced search |
| Kill Bill | Apache-2.0 ([repository](https://github.com/killbill/killbill)) | Confirmed by API | Rules, behaviour and documented examples |
| Lago (`lago`, `lago-api`) | AGPL-3.0 ([repository](https://github.com/getlago/lago-api)) | Confirmed by API | **Restrictive: concepts and behaviour only** |
| Medusa, Vendure, the Pinelab plugin, WooCommerce Subscriptions | Not confirmed in this research; an earlier survey recorded Vendure as GPLv3 | Unconfirmed | Treat as behaviour only until checked |
| Shopify and WooCommerce documentation, docs.saleor.io, docs.killbill.io | Not checked | Unconfirmed | Behaviour only; quote sparingly |

## What is unconfirmed, what was not researched, and the memory risk

**Difficulty is predicted, not measured.** No agent has been run on any candidate, and the ranking rests on duration, PR counts, reverts and follow-up fixes. None of the reference projects publishes post-mortems; severity and duration of every incident cited are unknown. Late-2026 leaderboard figures for SWE-bench Pro and Terminal-Bench come from aggregators that conflict with each other, and no failure analysis exists for the newest models, including the Sonnet 5.5 that solved `task02_release`. The claim that hidden specification is the strongest lever rests partly on ablations more than twelve months old.

**Sizes are proxies.** Title-keyword counts (136 promotion PRs, 189 transaction PRs, 296 billing-entity PRs) include backports and unrelated matches; Saleor ports one fix to three to six release branches. Dashboard and storefront line counts above 50,000 are dominated by regenerated schema and type files. The saleor/apps sizes exclude lockfiles and generated files and are therefore smaller than GitHub's figures, and API rate limits prevented collecting review counts and open-to-merge durations there and for Chatwoot. Since September 2026 saleor/apps receives bot commits synced from an internal repository, so recent Stripe and AvaTax changes cannot be attributed to public PRs. Chatwoot totals were grouped by PR-title keywords and not hand-audited.

**Specific items not confirmed.** The original PRs for deferred webhook payloads, 3.22 order search and gift cards in transactions were not identified. Two Saleor upgrade guides returned 404. Review-comment text was not read for any PR. Which change made early dashboard 3.22 builds incompatible with later Core 3.22 is a guess. The release years of Kill Bill 0.20, 0.22 and 0.24 are inferred. Lago's progressive-billing and tax-failure rules are known from PR titles only, because the documentation pages returned 404. No migration tooling from the legacy Stripe app to the new one was found. Chatwoot's later rollup, Freshdesk and unread-filter PRs were not found by title, and whether its Rails 7.2 upgrade re-landed is unknown.

**Not researched.** Kill Bill's AvaTax plugin, multi-tenancy, event bus and its integration-test repository (the best source of scripted billing timelines); Lago's payment-provider integrations; pausing, skipping and price-change handling for subscriptions on commerce platforms; Saleor's own end-to-end suite; the Adyen payment app; Chatwoot documentation and issue threads beyond titles. No source measures an agent on a zero-downtime rollout in a multi-service application, on requirements that drift during a coding task, or on seeded data volume.

**About SeedCo itself.** The statements that SeedCo lacks promotions, vouchers, stock and time-zone handling, and that it mentions channels, come from a keyword search of `services/` and `docs/`, not from reading the code. Candidates 2 and 5 need harness features (two service generations at once, verifier activity during the episode, a controllable clock) whose cost was not estimated. Candidates 1 and 4 need the base company grown first, and a larger base is itself part of the difficulty.

**The memory risk.** SeedCo's README names the system each owner mirrors, and every hidden rule on the shortlist is published: best-rule-only in the 3.19 changelog, the $11.37 rounding example, five webhook retries, retries eight days apart, the proration figures. A model that recognises Saleor can guess these without discovering anything in the company. No study measures this effect for a renamed mirror. The nearest evidence is about retrieval, not recall: blocking access to gold patches and tests cost one model 21.48 points on SWE-bench Pro ([SWE-Bench Pro Verified](https://huggingface.co/papers/2609.08149.md)). FeatureBench found task creation date had little effect on pass rate, which argues that recall of code is not the main driver on feature-sized work ([FeatureBench](https://arxiv.org/html/2602.10975v1)), and an earlier survey for this project recorded contamination documented for SWE-bench ([arXiv 2506.12286](https://arxiv.org/html/2506.12286v2)). The mitigations below are therefore inference. The real histories help here, because they contain several correct answers: Saleor stacked rules before 3.19 and stopped after, rounded down before 3.12 and half-up after, and the AvaTax app used three discount strategies in one year. A mirror can adopt any historical variant and stay faithful, so the hidden value is set by SeedCo's seeded data and the other owners' code, and a model answering from memory of the current release fails the check. Hidden facts should live in the running company (the frozen build's queries, a provider stub's behaviour, a seeded subscription that straddles a clock change), not in domain lore. Each task should also be probed once with no workspace, asking the model to state the hidden rules cold; a rule it states correctly is not hidden.

## Conclusion

The research changes what "harder" should mean for SeedCo. The company does not need more owners or more tickets. It needs a past that can be broken and requirements that must be found. Every project on the shortlist is hard for the same structural reason in its real history: two models of the same thing were alive at once (sale and promotion, old and new Core generation, payment recorded and payment unknown, UTC date and local datetime), and the rule for which one applies to which record was discovered late, in production, by people who had the whole code base in front of them. That is a property a small company can reproduce without tens of thousands of lines, provided the base ships the old model with seeded history and the verifier exercises both.

The implication for the multi-agent question is less comfortable. Only promotions and the second channel offer the conditions under which a team has shown an advantage, and both require each owner's share to be hours of work, which means growing the base company several-fold before the task exists. The other five are tightly coupled and will favour a single agent at any budget; their value is as tasks a single agent fails, and as the place to test whether an independent validator role, which cost 2% of spend in the one study that used it, is the part of "team" that matters. The first pilot should therefore be the cheapest discriminating one: run candidate 3 from symptoms only and candidate 1 with outcome-only tickets against the current solo agent, score every trial, and see whether 38 calls becomes a failure before building any new harness.

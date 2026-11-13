# Multi-agent RL environment: vendor review and build pla

Nov 11, 2026 · @Lilin

## Summary

Build a new multi-agent RL environment from scratch; that is the main project. The vendor's FourEyes-Scale package contributes design ideas only. There is no separate held-out set: tasks are generated at volume, and periodic human evaluation checks that training has not drifted. The vendor pack is a well-engineered evaluation, but its score is mostly single-agent work, one episode costs about 50M tokens, and its data is marked never-train.

The build follows the sequence you proposed (taxonomy and domains, then real-world research for one domain, then task design, then repeat), with two additions:

- **A shared kernel built alongside the first domain.** The scheduler, role-enforced service, replay and reward decomposition are domain-independent and should exist before the second domain starts.
- **A training gate before scaling out.** Prove on the first domain that training improves coordination and not only domain skill, before investing in more domains.

Decisions needed from you are listed under Open questions. The largest are the first domain, the episode budget, and how human evaluation is run.

## Review of the FourEyes-Scale delivery

The package is internally consistent and its reference results verify, but it has no completed model run and its design measures less multi-agent skill than it appears to.

**What it is.** A simulated month-end close for a group of 5 companies. A team of 1, 4 or 8 agents (preparer, AP clerk, approver) works through a role-checked tool API on a simulated clock. There are 36 Harbor tasks: 12 generated groups at three team sizes. Scoring is deterministic, and any control violation zeroes the reward.

**How it was reviewed.** I read the package and cross-checked its claims without running it. The oracle and the replay were not re-run, and the scorer and generator were not read in depth.

### What holds up

- All 36 README rows match the oracle results, episode files and instructions.
- All 36 signed reports verify against their task keys (HMAC and SHA-256 recomputed independently).
- Oracle teams of 4 and 8 score 1.0 with no violations; solo runs score 0.47 to 0.56 at the deadline, as documented.
- The service container has no network, a read-only root and dropped capabilities. No API keys are in the package or logs.

### What falls short

| Area | Finding | Evidence |
| --- | --- | --- |
| Baseline | The only model run never finished | Opus 5.5, team of 4: stopped at simulated minute 619 of 783 with 3 of 5 entities closed; no score |
| Cost | One episode is very expensive | 41.2M prompt tokens and 96 minutes of wall time for that partial trial |
| Harness: caching | No prompt caching requested or recorded | The loop sends plain chat completions; old tool results are rewritten in place, which would break a cache prefix |
| Harness: context | Context grows past its budget | Only tool results are trimmed; prompts reached 183k tokens |
| Harness: reasoning | Reasoning is neither counted nor kept | 0 reasoning tokens logged, yet about 59% of completion tokens are unexplained by visible output (estimate) |
| Score design | The headline score is mostly single-agent work | About 80% of weighted units are per-entity; about 20% need cross-agent agreement |
| Coordination depth | A static split by entity solves most of it | The oracle partitions entities across preparers; the model team did the same |
| Controls | No parallelism control | No "one agent with N times the budget" condition |
| Pressure tests | Probably easy for frontier models | Agents dismissed the stale delegation in one line in the partial run |
| Training readiness | Not usable for RL as delivered | Hundreds of calls per agent, end-of-episode reward, RL integrations target the single-entity product, no train split |
| Reuse | Hard to modify | No tests, no licence, and the design specs the code cites are not included |
| Hygiene | Canary claim overstated | About 19,650 frozen-group files carry no canary |

### What is worth keeping as ideas

- A service that owns all state and enforces what each role may read and do.
- A discrete-event clock with a fixed cost per model call, so results do not depend on provider speed.
- An event log that replays to the same score.
- Scripted teammates with known faults (rubber-stamp approver, shortcut-taking preparer, no coordination).
- The same task at several team sizes.

## Recommendation

Build new, take the vendor pack's architecture ideas, and leave the rest.

- **It was built as an evaluation.** It favours realism and auditability: long episodes and one end-of-episode score. Training needs short episodes, high throughput and reward that can be attributed.
- **Shrinking it means rewriting it.** The cost and the single-agent-heavy score come from the task design (five largely independent entities, a long close), not from fixable code. Changing that means a new generator and scorer, which is most of the codebase.
- **Its data cannot be trained on.** The canary marks it never-train and there is no licence. It can inform the design but cannot supply training data.
- **The reusable part is small.** The multi-agent layer is about 5k lines of patterns that are quicker to re-implement than to untangle from the accounting domain.

No train and evaluation split is planned. With unlimited generated tasks, fresh seeds are unseen by construction, and human evaluation is the check against drift.

## Design principles

These are the requirements every domain and task must meet. They are my proposal, not established results; each one is checked by an acceptance test in the task spec section.

1. **Interdependence by construction.** Each agent holds information or permissions the others need, so no static split of the work solves the task. Most of the reward depends on cross-agent agreement.
2. **Short episodes.** A small shared token budget per episode and small contexts. Difficulty scales with the coordination structure, not with volume of work.
3. **Decomposed reward.** Individual correctness, team outcome and coordination cost are reported separately, with per-agent credit.
4. **Counterfactual baselines.** Every task has a solo-with-equal-budget condition and a scripted-partner condition, so a team's gain can be attributed.
5. **A partner population.** Training mixes self-play, earlier checkpoints and scripted partners with known faults, so the policy does not overfit to its own conventions.
6. **Procedural generation at volume.** Unlimited seeds across structures and difficulty, with no fixed train and evaluation split.
7. **Many thin domains.** Coordination skill that transfers needs varied surface tasks. One deep domain invites learning the domain.
8. **The production harness.** The same loop, caching and context handling the models run with elsewhere, so the environment does not measure harness quirks.
9. **Deterministic, replayable scoring.** No model judges anything in the reward path; an event log reproduces the score.

10) **Human evaluation against drift.** Reviewers regularly inspect sampled episodes to confirm that rising reward reflects real coordination and not an exploit of the scorer or generator.

## Roadmap

Your three steps are phases 1 to 3; the plan adds a training pilot as the gate before repeating for more domains, and a shared kernel built alongside the first domain.

&#91;embedded content: roadmap · 5 phases, 4 gates, 2 supporting lanes\]

Each gate is a stop-or-go decision. The pilot is the one that matters most: if training on the first domain does not improve coordination on fresh tasks, as confirmed by human review, more domains will not fix it and the task design needs rework.

| Phase | Output | Gate to pass |
| --- | --- | --- |
| 1 Taxonomy | Agreed coordination structures, conditions, a ranked domain shortlist | Taxonomy agreed and first domain chosen |
| 2 Seeds | Failure-case catalogue for the first domain, with sources | At least 30 cases covering at least 4 structures, each with a checkable outcome |
| 3 Tasks | 3 to 5 task generators with scripted policies, on the shared kernel | Every task passes all acceptance tests |
| 4 Pilot | A training run on the first domain and a human evaluation report | Coordination terms improve on fresh seeds, and human review confirms the behaviour is real |
| 5 Repeat | Phases 2 to 4 for each further domain | Same gates, plus cross-domain transfer |

What I would change in your sequence:

- **Start the kernel in phase 1, not after task design.** Tasks cannot be tested without the service, clock and scorer, so designing tasks first means designing blind.
- **Do not start a second domain before the pilot.** The first domain is where the task template and acceptance thresholds get corrected; scaling out before that multiplies the rework.
- **Decide the episode budget before phase 3.** It constrains every task more than the domain does.

## Phase 1 draft: taxonomy and candidate domains

The taxonomy should classify coordination structures, not domains: a domain is a surface, and the structure is what the policy must learn. A task is one cell: a structure placed in a domain. This is a first draft to argue with, written from reasoning and not yet from literature; Phase 1 should check it against existing multi-agent benchmarks.

### Axis A: coordination structures

| Structure | What makes it hard | Minimal example |
| --- | --- | --- |
| Information pooling | Each agent sees a different part; the answer needs all parts | Three agents each hold one log; the root cause needs all three |
| Interface agreement | Two sides must independently produce outputs that match | Producer and consumer change a schema; both must land the same contract |
| Handoff | Work passes between agents; context is lost unless transferred well | Shift change with an open problem half diagnosed |
| Shared resource | Agents compete for a limited resource and must allocate it | One approval queue, one test cluster, one budget |
| Review and oversight | One agent checks another's work and must catch faults without blocking good work | Maker and checker; reviewer facing a subtly wrong submission |
| Delegation | One agent decomposes work and others execute; the plan must survive surprises | Lead splits a task; a worker finds the split is wrong |
| Mixed motive | Goals partly conflict; agents must reach a fair, efficient agreement | Two teams negotiate over a shared deadline or budget |
| Convention without talk | Agents must align with no or limited communication | Parallel edits with no channel; rely on shared norms |

### Axis B: conditions varied within any structure

| Condition | Values |
| --- | --- |
| Team size | 2, 3 to 5, 8 or more |
| Communication | Free channel, limited messages, delayed, none |
| Partner | Self-play, earlier checkpoint, different model, scripted correct, scripted faulty |
| Conduct pressure | None, false authority, peer pressure to skip a control, a teammate who breaks a rule |
| Disruption | None, a teammate drops out, requirements change mid-episode |

### Candidate domains

Seed sources below are kinds of material to look for in Phase 2; none has been researched yet.

| Domain | Structures it carries naturally | How it scores deterministically | Kinds of real-world seed | Note |
| --- | --- | --- | --- | --- |
| Software changes across services | Interface agreement, review, delegation, shared resource | Hidden tests and contract checks | Public issue threads, pull-request reviews, migration write-ups | Proposed first domain |
| Incident response | Information pooling, handoff, delegation | Root cause and remediation matched against a planted fault | Public postmortems, on-call guides | Proposed second domain |
| Data pipelines and analytics | Interface agreement, handoff, review | Output tables compared with a reference | Data-engineering forums, schema-change incidents | Cheap to simulate |
| Procurement and contracting | Mixed motive, review, shared resource | Agreement terms scored against each side's private values | Negotiation case studies, procurement policies | Main mixed-motive domain |
| Support escalation | Handoff, information pooling | Resolution matched against a planted cause; handoff completeness | Support forums, escalation playbooks | Short episodes come naturally |
| Scheduling and logistics | Shared resource, convention without talk | Feasibility and cost of the final plan | Operations-research datasets, dispatcher discussions | Easy to generate at scale |
| Research collaboration | Review, delegation, information pooling | Reproduced numeric results; planted errors caught | Replication reports, peer-review discussions | Harder to score; later |
| Finance operations | Review, information pooling | Ledger effects | Accounting forums, audit findings | Available as a domain; built fresh, without vendor data |

### Why software first

- Scoring is cheap and exact: tests pass or they do not.
- Interface agreement is native to it, and that is the structure the vendor pack lacks most.
- Real material is abundant and public.
- It is the domain where a frontier lab is most likely to deploy agent teams.

The risk is that it overlaps with existing single-agent coding training, so tasks must be built so that a solo agent with equal budget does clearly worse.

## Phase 2: real-world seeds for the first domain

The goal of the research is a catalogue of real coordination failures, because each failure names a skill a task can train. Collecting scenarios alone gives realistic surfaces with nothing to learn.

### What to collect

| Record | Contents |
| --- | --- |
| Failure case | What went wrong between people or teams, in one paragraph, with its source link |
| Structure tag | Which Axis A structure it is an instance of |
| Who knew what | The information or permission each party held and the others lacked |
| What would have fixed it | The message, check or handoff that was missing |
| Checkable outcome | A state that can be verified without a judge (tests pass, contract matches, fault found) |
| Artefacts | Real formats worth imitating: tickets, review comments, runbooks, schemas |

### Where to look

- Practitioner discussion: forums, issue trackers, review threads, on-call write-ups.
- Papers: multi-agent benchmarks and failure analyses, human teamwork and handoff studies.
- Datasets: existing task sets that can be re-cut into multi-role form.
- Standards and playbooks: the documented process a competent team follows.

### Rules

- Seeds inspire generated tasks; no source text is copied into training data. Record each source's licence.
- Every source goes in a Sources tab with its link and what was taken from it.
- Stop when new sources stop adding new failure types, not at a page count.

### Output and gate

A catalogue of at least 30 failure cases, covering at least 4 structures, each with a checkable outcome. If fewer than 4 structures appear, the domain is too narrow to go first.

## Phase 3: task spec and acceptance tests

A task is a generator, not a fixed instance: it takes a seed and produces a world, role views and an answer key. Every task is written to this template and must pass the acceptance tests before it enters the training set.

### Task spec template

| Field | What it states |
| --- | --- |
| Cell | Structure (Axis A), domain, and the Axis B conditions it supports |
| Seed failure | The catalogue cases it is built from |
| Roles | Each role's tools, what it can read, what it can change |
| Private state | What each role knows that the others need |
| Success state | The verifiable end state and how the scorer checks it |
| Reward terms | Individual correctness, team outcome, coordination cost, budget efficiency, conduct; each computed separately |
| Episode budget | Shared team token budget, hard stop, and target context size |
| Generator parameters | What varies by seed, and what varies by difficulty |
| Scripted policies | An oracle team, a solo policy, and at least one faulty partner |
| Human review sample | Which episodes reviewers inspect and what they check |

### Acceptance tests

| Test | Pass condition |
| --- | --- |
| Solvable | The scripted oracle team reaches full score within the episode budget |
| Needs a team | A solo agent with the team's combined budget scores clearly lower than the oracle team |
| Needs coordination | The no-communication scripted team scores clearly lower than the oracle team |
| No shortcut | Degenerate policies (do nothing, escalate everything, approve everything) score near zero |
| Deterministic | The same seed and actions replay to the same score |
| Cheap | One episode stays inside the token and wall-time budget |
| Has headroom | A current model team scores between the degenerate floor and the oracle, not at either end |
| Varied | Different seeds produce different correct action sequences, not renamed copies |

Thresholds for "clearly lower" and the budgets are open questions below. The first design round should produce 3 to 5 tasks in one domain, each in a different structure.

## MVP: one company, a model baseline, then expand

The MVP is one hand-built company with about ten cross-service changes, run as a model baseline to show the tasks need coordination before anything is generated or trained. It covers phases 1 to 3 at the smallest useful size and stops short of the training pilot.

### Scope

| Piece | In the MVP | Left for later |
| --- | --- | --- |
| Company | One, hand-built: four small services in four languages, real code, each service's tests inside a fixed time budget | More companies; generate-and-verify authoring |
| Roles | One owner agent per service; each sees only its own repo and its inbox | Reviewer, lead and on-call roles |
| Tasks | 8 to 10 hand-written cross-service changes in three structures: interface agreement, information pooling, review | The other five structures; Axis B conditions beyond messaging |
| Scorer | Hidden contract and integration tests, plus each service's own tests | Decomposed reward terms and per-agent credit |
| Kernel | Turn scheduler with a shared team token budget, a message channel, an event log | Simulated clock, replay, scripted partners |
| Harness | Your production agent loop, one instance per role | Partner populations |

### Baseline conditions, per task

1. Team with messaging.
2. Team without messaging.
3. One agent with all four repos visible and the same total token budget as the team.

### Episode budget

The limit on an episode is one token budget shared by the whole team, not a cap per agent. Real teams share a deadline and a cost, work is uneven across owners, and deciding who spends effort on what is part of coordination.

- **Shared team budget, in tokens.** Every agent's model calls draw from the same pool. The remaining budget is visible to all agents.
- **Hard stop as a safety net.** A generous limit on total model calls ends runaway episodes. A healthy team should never reach it.
- **Efficiency in the reward, later.** Once reward terms are decomposed, finishing with budget left scores slightly higher. The MVP only records budget used.
- **Same total for the solo baseline.** The single agent gets the team's whole budget.

The budget's size is not set yet. It should come from measuring what a competent team needs on task 1, with headroom.

### What counts as useful

- **Every task passes two admission checks.** The team without messaging cannot pass it, and the single agent with all four repos can.
- **The team with messaging clearly beats the team without it.** The closest existing benchmark found no such gain, so this is the result to prove, not assume.
- **The headline number is the gap to the single agent.** Expect the single agent to lead at first; the measure is how much of its score the team recovers.
- **Each contract is scored separately,** so a failure can be placed at a boundary.
- **A human read of the failures shows coordination failures** (a wrong assumption about the other side, a question not asked), not coding mistakes.
- **One episode stays inside the budget.**

If the team without messaging can pass a task, the needed fact was visible or guessable, and the task needs more private information per role. That is cheap to find and fix at this size.

### Known limits

- **One fixed company can be learned by heart under training.** It is acceptable for a baseline, where nothing is trained.
- **Template generation would produce look-alike companies.** When the MVP passes, new companies and changes should be written freely by a model and admitted only if they pass executable acceptance tests, so variety comes from the author and correctness from the tests.

## Reference repos surveyed

No public repository matches the seed company's four languages and four services, so the model is a composite of three permissively licensed demos, with two billing platforms for domain rules. About 30 repositories were checked. Repository facts are as read from the GitHub API and shallow clones on 11 November 2026; nothing was built or run, and line counts are approximate.

The full research report, with all sources, is saved locally at `/Users/yuankong/Downloads/multi-agent/reports/Seed company reference repo survey.md`.

| System | Licence | Size and languages | How contracts are defined | Run weight | Status | What to take |
| --- | --- | --- | --- | --- | --- | --- |
| [AWS Retail Store Sample](https://github.com/aws-containers/retail-store-sample-app) | MIT-0 | Five services in Java, Go and TypeScript; about 1,800 to 11,400 lines each | One `openapi.yml` per service; a consumer holds a generated client | One `docker compose up` | Active | Per-service contract ownership, the same task names in every service, an in-memory broker by default |
| [Online Boutique](https://github.com/GoogleCloudPlatform/microservices-demo) | Apache-2.0 | 11 services in Go, C#, JavaScript, Python, Java; about 240 to 870 lines each | One root `demo.proto` with no single owner | Kubernetes only | Active | Service size |
| [OpenTelemetry Demo](https://github.com/open-telemetry/opentelemetry-demo) | Apache-2.0 | About 20 services in 12 languages | One root `pb/demo.proto`, plus one Kafka `orders` topic | Docker Compose; about 6 GB RAM | Active | Orders publish, accounting (C#) and others consume |
| [dotnet/eShop](https://github.com/dotnet/eShop) | MIT | 20 C# projects | Event classes copied by hand into each consumer | .NET 10 SDK and a container runtime | Active | Billing internals, and implicit contracts that fail only at runtime |
| [FTGO](https://github.com/microservices-patterns/ftgo-application) | Apache-2.0 text | Java, one JavaScript gateway | Per-service API modules and contract tests | Heavy | Stale since 2022 | The only example of consumer-driven contract tests as modules |
| [Sock Shop](https://github.com/microservices-demo/microservices-demo), [eShopOnContainers](https://github.com/dotnet-architecture/eShopOnContainers), [Robot Shop](https://github.com/instana/robot-shop) | Apache-2.0 or MIT | Various | Various | Not assessed | Archived | History only |
| [Train Ticket](https://github.com/FudanSELab/train-ticket) | Apache-2.0 | 41 services | Not examined | Not assessed | Stale since 2022 | Its 22 documented industrial fault cases |

### Billing and notification references

- **[Kill Bill](https://docs.killbill.io/latest/userguide_subscription) (Apache-2.0):** typed invoice items, proration, plan-change timing and an overdue state machine. Safe to imitate.
- **Lago (AGPL-3.0), concepts only:** amounts as integer cents plus currency, and a worked proration example to use as a test fixture: €100 a month upgraded to €200 on 15 January gives €45.16 and €109.68 ([source](https://getlago.com/docs/guide/subscriptions/upgrades-downgrades.md)).
- **Two event styles exist.** Lago and Hyperswitch embed the whole object in an event; Kill Bill sends only ids. The seed company uses the embedded style, because that is what makes a field change break a consumer.
- **[Novu](https://docs.novu.co/framework/payload.md) for Notifications:** each workflow declares a payload schema and templates read payload fields directly. Under a strict schema even an added field is rejected.

### Licence cautions

- Lago, Flexprice, Meteroid and listmonk are AGPL-3.0, and Vendure is GPLv3: read for concepts, copy nothing.
- DeathStarBench's licence file says Apache-2.0 while its README says GPL v2. Treat it as unclear.
- All seed company code is written fresh in any case.

## What the research changes

The research changes the design in two ways: the contracts worth building tasks on are mostly not the schema, and the team should be measured against a single agent that holds everything, not expected to beat it.

### Evidence

| Finding | Source | Strength |
| --- | --- | --- |
| In 15 of 43 real contract changes a consumer was missed. None was caught by a schema check; they were found by a reviewer running the app (4), CI (3), bug reports (5) or later audit (3) | Change-history catalogue from Online Boutique, the OpenTelemetry Demo, eShop and eShopOnContainers | Every example opened and linked; the sample favoured discussed changes, so 15 of 43 is not a base rate |
| Missed consumers sit where nothing is compiled against the schema: config, flags, proxy templates, UI paths, dashboards, and units read wrongly | Same catalogue | Same |
| All 17 practitioners treat deletions and renames as breaking; only 5 of 17 treat behavioural changes as breaking; 7 say consumers may be unknown | [Lercher et al.](https://arxiv.org/abs/2311.08175), 17 interviews in 11 companies | Peer-reviewed interview study |
| 63% of 123 upgrade failures came from incompatible interaction between versions | [Zhang et al., SOSP 2021](https://www.cs.purdue.edu/homes/yonglezh/pub/upgrade-sosp21.pdf) | Peer-reviewed |
| 120 cross-system failures traced to discrepancies between systems that were each correct alone | [Tang et al., EuroSys 2023](https://tianyin.github.io/pub/csi-failures.pdf) | Peer-reviewed |
| In the closest existing benchmark, messaging did not help: 17.14% success with it, 17.64% without, and two agents kept 0.59 of solo success | [CooperBench](https://arxiv.org/html/2601.13295), 652 two-agent coding tasks | Preprint; its tasks can be built independently, so messaging was never strictly needed |
| At equal budget a single agent usually matches or beats a team | [Tran and Kiela](https://arxiv.org/abs/2604.02460); [Kim et al.](https://arxiv.org/abs/2512.08296); [iso-call study](https://arxiv.org/abs/2609.04217) | Preprints; none is on cross-service coding |
| Agents fail to ask: "fail to ask for clarification" is 11.65% of multi-agent failures | [MAST taxonomy](https://arxiv.org/html/2503.13657v2) | Peer-reviewed |
| No benchmark was found where each agent privately owns one service of a shared codebase, and no training work on peer coding agents with partitioned views | About 30 searches | Absence in a limited search, not proof |

### Consequences for the design

- **Weight tasks toward meaning and implicit contracts.** A rename or type change in a visible schema is mechanical. Units, defaults, delivery rules, config names and untested paths are what force one owner to ask another.
- **Keep some contracts deliberately implicit.** A seed company with every contract in a tidy schema file would be more disciplined than any real reference system, and tooling would solve its tasks.
- **Admit a task only if it passes two checks.** The team without messaging cannot pass it, because a needed fact lives only in another owner's service. The single agent holding all four services can pass it.
- **Report the gap to the single agent as the headline.** Four small services fit in one context, so the single agent is the upper reference. The measure is how much of that ceiling a team recovers, and whether training closes the gap.
- **Score each contract separately.** One end-to-end pass or fail hides which boundary failed and gives sparse credit. Also log whether a needed question was asked, and never reward message volume.
- **Meter tokens inside the harness.** Provider-side budget controls were reported as unreliable in equal-budget comparisons.
- **Rollout order needs its own machinery.** The reference repos ship everything together, so mixed-version tasks need a harness that can run two versions of a service at once. That is left out of the MVP.
- **Watch for private conventions under self-play.** A [November 2026 study](https://arxiv.org/html/2611.06409v1) found agents form conventions that fail with other partners. Partner variety and human review are the checks.

## Change-type taxonomy

A change type is a kind of cross-service change; each is hard for a different reason. This list is now anchored to the 43 real changes and the published studies. No published taxonomy covers both a cross-service change and the communication it needs, so the list is a composite and remains a design choice.

| Change type | Real anchor | Can tooling catch it? | Structures it carries |
| --- | --- | --- | --- |
| Add a field | Novu strict schemas reject additions | Yes, yet it can still break a strict consumer | Interface agreement |
| Rename, remove or retype a field | Postal code integer to string ([OpenTelemetry Demo #587](https://github.com/open-telemetry/opentelemetry-demo/pull/587)) | The shape yes; hidden preconditions no | Interface agreement, review |
| Change a unit, format or meaning, same shape | Money type migration ([Online Boutique](https://github.com/GoogleCloudPlatform/microservices-demo/commit/e20ed325f187a19a150fa05c0cc15a5af9c7a88c)); three services misreading one money field ([#3742](https://github.com/open-telemetry/opentelemetry-demo/issues/3742)) | No | Interface agreement, information pooling |
| Add, rename or re-encode an enum value | Order status to enum ([eShop #151](https://github.com/dotnet/eShop/pull/151)); Train Ticket fault F20 | Partly | Interface agreement, handoff |
| Version, re-sign or remove an endpoint | API v2 beside v1 ([eShop #680](https://github.com/dotnet/eShop/pull/680)) | Yes | Review, handoff |
| Change an event's envelope, dedup key or delivery rules | Event id lost on deserialisation ([eShopOnContainers #667](https://github.com/dotnet-architecture/eShopOnContainers/issues/667)); consumers disagreeing on where to start reading ([#3505](https://github.com/open-telemetry/opentelemetry-demo/pull/3505)) | No | Information pooling, interface agreement |
| Change a shared config, name or port | Topic name moved to config ([#3665](https://github.com/open-telemetry/opentelemetry-demo/pull/3665)); proxy template reading variables defined elsewhere ([#3570](https://github.com/open-telemetry/opentelemetry-demo/pull/3570)) | No | Interface agreement |
| Remove a flag's last reader, or change what a flag means | A revert removed a flag's only reader and broke another service's tests ([#3873](https://github.com/open-telemetry/opentelemetry-demo/pull/3873)) | No | Review, information pooling |
| Rename a package or namespace | Protobuf package rename touching 23 files across ten services ([#740](https://github.com/open-telemetry/opentelemetry-demo/pull/740)) | Yes for compiled consumers; no for config and scripts | Interface agreement, delegation |
| Rename a service's identity | Service renames staged over about 18 changes, with leftovers found afterwards ([#1788](https://github.com/open-telemetry/opentelemetry-demo/issues/1788)) | No | Delegation, handoff |
| Rewrite a consumer behind an unchanged contract | A consumer rewritten from Go to .NET behind the same queue contract ([#1538](https://github.com/open-telemetry/opentelemetry-demo/pull/1538)) | No: unwritten behaviour is lost | Handoff, information pooling |
| Let duplicated contract copies drift apart | Drift between copies of one schema ([Online Boutique #814](https://github.com/GoogleCloudPlatform/microservices-demo/issues/814)) | Partly | Interface agreement, review |
| Change a telemetry or log field that others read | Attribute names whose consumers are dashboards and tests ([#3355](https://github.com/open-telemetry/opentelemetry-demo/pull/3355)) | No | Information pooling, review |
| Negotiate a wire encoding or content type | Content negotiation between components ([Loki #9813](https://github.com/grafana/loki/pull/9813)) | Partly | Interface agreement |
| Move a responsibility between services | Recommendations return ids, so the caller must fetch products itself ([Online Boutique](https://github.com/GoogleCloudPlatform/microservices-demo/commit/0cf418df99df17663371bf49b918e476ce60445e)) | No | Delegation, interface agreement |
| Migrate data with old-format records still stored or queued | eShop #151; queued old messages in [Lercher et al.](https://arxiv.org/abs/2311.08175) | Partly | Handoff |
| Roll out a change across mixed versions | No example in the reference repos; [Zhang et al.](https://www.cs.purdue.edu/homes/yonglezh/pub/upgrade-sosp21.pdf) on upgrade failures; [compatibility modes](https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html) fix who moves first | Partly | Handoff, shared resource |
| Change retry or idempotency rules | No measured study; [idempotency keys](https://docs.stripe.com/api/idempotent_requests) as documented practice | No | Interface agreement |
| Fix an ordering or race across services | Cancel racing refund (Train Ticket faults F1 and F13) | No | Shared resource, interface agreement |
| Diagnose a cross-service bug with a wrong first suspect | Checkout reports success while accounting receives nothing ([#4156](https://github.com/open-telemetry/opentelemetry-demo/issues/4156)) | Not applicable | Information pooling |
| Change a business rule with no schema change | Plan-change timing rules in Kill Bill and Lago | No | Interface agreement, delegation |
| Change a permission or scope | No real example found; must be authored | Partly | Review |
| Change a limit or page size | No real example found; [AIP-180](https://google.aip.dev/180) treats a smaller default page size as breaking | Partly | Information pooling |
| Change an error or status code | No real example found; must be authored | Partly | Interface agreement |

The taxonomy has 24 types: 18 with a real example, 3 resting on research or documented practice, and 3 that must be authored. The MVP's ten tasks draw on nine of them. Rollout order across mixed versions is deliberately absent: the reference histories contain no example, and it needs a harness that runs two versions at once.

## Seed company draft

The seed company (working name SeedCo) is a subscription retailer with four services, each owned by one agent. A subscription business is chosen so that billing has real rules (renewals, proration, tax, refunds) instead of being a thin payment call.

&#91;embedded content: seed company · 4 services, 3 call paths, 3 event paths\]

Every arrow is a contract owned by one agent and depended on by another, so every arrow is a place a task can be set. Billing sits on four of the six, which is why most of the first ten changes involve it.

### Services and owners

| Service | Owns | Calls or consumes | Private knowledge its owner holds |
| --- | --- | --- | --- |
| Storefront | Customer-facing API and page view models | Calls Orders and Billing | What the pages display and how they format money and dates; pagination assumptions |
| Orders | Carts, orders, the order state machine | Calls Billing to charge; emits order events | Retry behaviour, state transitions, which fields are legacy |
| Billing | Prices, tax, invoices, payments, renewals | Consumes order events; emits invoice and payment events | Amounts are integer cents; tax and rounding rules; rate limits |
| Notifications | Emails, receipts, operational alerts | Consumes all events | Which fields each template reads; deduplication rules; alert thresholds |

### Languages

The company is multi-language, as real companies are: each service uses the language a team would plausibly have chosen, and one is deliberately older.

| Service | Language | Why it fits |
| --- | --- | --- |
| Storefront | TypeScript on Node.js | Customer-facing API and view models are usually JavaScript territory |
| Orders | Java | A typed, long-lived core service with a state machine |
| Billing | C# | The older service: stable, strict about money, slow to change |
| Notifications | Python | Templating and glue code |

C++ is left out of the MVP because compile time and memory bugs would dominate short episodes. It fits later as a small legacy library (for example a tax or pricing engine) that Billing wraps.

Multi-language has three consequences for the build:

- **Contracts must be language-neutral.** HTTP contracts are OpenAPI files and events are JSON Schema files, each owned by its publisher.
- **Services run as separate processes.** The integration suite starts all four on localhost and drives them over real HTTP, with a small file- or socket-based event queue.
- **Speed has to be designed in.** One prebuilt image holds all four toolchains with dependencies cached and builds warm, and frameworks are kept light so start-up stays short.

### Contracts

| Contract | Kind | Published by | Read by |
| --- | --- | --- | --- |
| Create order, get order, list orders | HTTP | Orders | Storefront |
| Quote price, get invoice | HTTP | Billing | Storefront |
| Charge | HTTP | Billing | Orders |
| `order.placed`, `order.cancelled` | Event | Orders | Billing, Notifications |
| `invoice.paid`, `payment.failed` | Event | Billing | Notifications |

Each publisher owns its schema file. Each reader keeps a pinned copy, so a publisher cannot see who depends on which field without asking. Events embed the whole object (an envelope with `event_id`, `event_type`, `occurred_at` and the object), so Notifications' templates depend directly on Billing's and Orders' fields.

Some contracts are deliberately left implicit, because that is where real consumers get missed:

- Shared config names, such as the event topic name.
- The meaning of a flag.
- A status string that another service reuses as display text or template wording.
- Units and rounding of money.
- Delivery rules: where a new consumer starts reading, and what identifies a duplicate.

The language split adds a realistic asymmetry: the Java and C# services fail loudly when a payload drifts, while the Node and Python services tolerate it silently.

### Build constraints

- A few hundred lines per service, light frameworks, one prebuilt image with all toolchains.
- Services run as separate local processes for integration tests: real HTTP between them and a simple local event queue.
- Time budget, to be confirmed by measurement: each service's own tests under 30 seconds warm, and the hidden integration suite under 2 minutes.
- Each owner also has a short notes file (runbook and known constraints). It is the main carrier of private knowledge.

### What each agent can do

- Read and edit files in its own service, and run that service's tests.
- Read its pinned copies of other services' schemas, but not their code.
- Send messages to other owners, and propose or accept a schema change.
- Submit its change when done. The episode ends when all owners submit or the shared budget runs out.

### First ten changes

Each task is now re-themed from a real change. The list replaces the earlier draft written from reasoning.

| # | Change | Real seed | Structure | Why one owner cannot finish alone |
| --- | --- | --- | --- | --- |
| 1 | Money moves from decimal to integer cents in all four services | Online Boutique money migration; three services misreading one money field in the OpenTelemetry Demo | Interface agreement | One small contract change, one change per service, and a rounding rule each owner must apply identically |
| 2 | Postal code changes from integer to string | [OpenTelemetry Demo #587](https://github.com/open-telemetry/opentelemetry-demo/pull/587) | Interface agreement | Orders gains a hidden "address required" precondition on a Storefront path the author's tests never exercise |
| 3 | Order status becomes an enum | [eShop #151](https://github.com/dotnet/eShop/pull/151); Train Ticket fault F20 | Interface agreement, handoff | Stored events must keep the old string form; Notifications uses the string as template wording |
| 4 | Customers receive duplicate receipts | [eShopOnContainers #667](https://github.com/dotnet-architecture/eShopOnContainers/issues/667) | Information pooling | The symptom is in Notifications' dedup log; the cause is the publisher not preserving the event id |
| 5 | The event topic name becomes configurable | [OpenTelemetry Demo #3665](https://github.com/open-telemetry/opentelemetry-demo/pull/3665) | Interface agreement | Three services must agree on a name and a default that preserves behaviour |
| 6 | A consumer that starts late drops early events | [OpenTelemetry Demo #3505](https://github.com/open-telemetry/opentelemetry-demo/pull/3505) | Information pooling | Each owner sees only its own consumer settings; neither can diagnose the mismatch alone |
| 7 | Billing adds a field to an invoice event | Novu strict payload schemas | Interface agreement | A harmless-looking addition is rejected by a strict consumer |
| 8 | Orders adds API v2 beside v1, then proposes removing v1 | [eShop #680](https://github.com/dotnet/eShop/pull/680) | Review | Orders must learn who still uses v1 before removing it; Storefront reviews the removal |
| 9 | Plan downgrades take effect at period end instead of immediately | Kill Bill and Lago plan-change rules | Interface agreement | A business rule with no schema change alters what Orders ships and what Notifications says |
| 10 | Orders succeed but invoices are missing | [OpenTelemetry Demo #4156](https://github.com/open-telemetry/opentelemetry-demo/issues/4156) | Information pooling | The producer reports success and the consumer shows nothing at all; a recent unrelated change is planted as a false lead |

Tasks 4, 6 and 10 start from a symptom, not a specification: no agent is told which service is at fault. Task 8 should include a second, correct removal on purpose, so a reviewer who rejects everything scores badly. Most tasks sit on meaning, config and delivery rules, not on the schema, in line with the research.

### Next steps

- [ ] Confirm the four services, the language assigned to each, and the shared token budget.
- [ ] Decide which implicit contracts the seed company carries, and write each one into the owning service's notes file. (The commit-history research is done: 43 real changes catalogued, and the change types and ten tasks are corrected against them.)
- [ ] Write the service skeletons and schemas, then task 1 end to end as the template for the rest.
- [ ] Run the three baseline conditions on task 1 before writing the other nine.

## Build status

The seed company, the kernel, a stand-in harness and task 1 are built and verified with scripted agents; no model run has happened yet, because this machine has no API credentials. The code is at `/Users/yuankong/Downloads/multi-agent/seedco`.

| Piece | State | Verified by |
| --- | --- | --- |
| Toolchain image (Node 24, Java 17, .NET 8, Python 3.11) | Built, 2.2 GB | Each service's tests run inside it |
| Four services with contracts, pinned copies and owner notes | Built | 16 unit tests; 3 end-to-end tests through all four services |
| Event broker and stack runner | Built | The end-to-end tests |
| Kernel: round-robin turns, shared token budget, messaging, event log | Built | 6 kernel tests with scripted agents |
| Stand-in harness: one Claude call per turn through the Anthropic SDK | Written, not run | Request parameters checked against the SDK only |
| Scorer: hidden checks per boundary, plus each service's own tests | Built | See task 1 results |
| Task 1: money becomes a Money object in minor units | Built, with a reference solution | See below |

### Task 1 acceptance results

| Test | Result |
| --- | --- |
| Solvable: scripted reference team, through the harness | 10 of 10 hidden checks, team and solo |
| No shortcut: untouched company | 0 of 10 |
| Partial: only Billing migrated | 2 of 10 |
| Needs coordination: model team without messaging | Not run yet |
| Needs a team, headroom: model runs | Not run yet |
| Cheap: measured token and wall time per episode | Not run yet |

### Measured speed

- Each service's own tests: 0 to 2 seconds warm.
- Whole company start plus the end-to-end tests: about 12 seconds cold, 2 seconds warm.
- These are well inside the 30-second and 2-minute targets.

### How task 1 changed from the draft

The draft said "money moves to integer cents". A team could plausibly guess that without talking, so the built task uses a Money object, `{"currency": "USD", "minor": 2499}`, with field names unchanged. The shape is written only in Billing's decision record, which the other three owners cannot see. This follows Online Boutique's real Money type migration.

### Deviations to know about

- **Server-side model fallback is off** in the harness. A silent switch of model would corrupt a baseline, so a refusal ends the episode as invalid.
- **The budget counts every token read or written,** cached or not. Cache reads are cheaper in money, so this is a design choice to revisit once real usage is measured.
- **The Node base image could not be pulled from Docker Hub** on this machine, so the image downloads Node from nodejs.org instead.

## Open questions

- [ ] **First domain.** Software changes across services is proposed. Is there a deployment target that argues for a different one?
- [ ] **Episode budget.** What token and wall-time cost per episode can training afford? This sets the shared team token budget and drives every task design.
- [ ] **Training setup.** Which algorithm and reward form will be used (shared team reward, per-agent credit, or both)? The reward terms should be shaped to fit.
- [ ] **What counts as improvement.** Which result would convince you coordination improved: reward terms on fresh seeds, human review, gains in a second domain, or all three?
- [ ] **Thresholds.** How much lower must solo and no-communication scores be for a task to pass ("clearly lower")?
- [ ] **Human evaluation.** Who reviews, how often, how many episodes per round, and against what rubric?
- [ ] **Vendor relationship.** Ask for the specs, tests and a licence, or close out the delivery?
- [ ] **Conduct training.** Should oversight and refusing illegitimate authority be rewarded behaviours in this environment?
- [ ] **Team and ownership.** Who builds the kernel, who owns domain research, and who signs off each gate?
- [ ] **Existing work.** Are there internal environments or harness components this should build on?

# Task properties that make a team of coding agents necessary, and how benchmarks and engineering practice build such tasks

Notes as of 16 November 2026. Sources dated before 2025 are marked "(pre-2025)". Items marked "(secondary)" were seen only in search summaries or aggregator pages and not checked against the primary source. Items marked "(earlier survey)" are taken from the existing survey of multi-agent benchmark setups and were not re-fetched; they are included only where needed to support a new inference.

## 1. When does multi-agent beat single-agent at equal token or cost budget?

### Takeaway
No published 2025-2026 study was found in which a team beats a solo agent on repository-scale coding at a matched total token budget; the only consistent, replicated team advantage is wall-clock time (about 2x to 6x) on work with many independent units, and one author-reported system gains 11 to 14 points at lower cost only when the split follows the dependency graph. The features that predict a team gain are parallel width with low coupling, an external oracle that splits one big task into many independent failing units, and a time limit; tight coupling and a single shared bottleneck erase the gain.

### Cited Findings
- Co-Coder (May 2026, authors' own system, gpt-5-mini) partitions repository-level generation by dependency clusters. On DevEval (avg 3.1 files, 243 LOC) it reaches 68.1% vs 56.8% for a sequential single agent, in 442 s vs 800 s, at $0.18 vs $0.25. On CodeProjectEval (avg 11.9 files, 2,371 LOC) it reaches 34.1% vs 20.1%, in 1,315 s vs 2,756 s (2.10x speedup), at $0.67 vs $1.03. Token budget was not equalised by design, but the team used less. — [Co-Coder, arXiv 2606.00953](https://arxiv.org/html/2606.00953v1)
- In the same paper, naive file-based parallelism gave 57.7% / 23.3% at 1.44x / 1.60x the cost of sequential, and Claude Code with Agent Teams scored below sequential (54.1% / 16.3%) while being the fastest (0.67x / 0.25x wall-clock). — [Co-Coder](https://arxiv.org/html/2606.00953v1)
- Dependency density moderates the gain: across 16 CodeProjectEval projects, edge density correlates with the pass-rate gain over sequential (Pearson r = 0.65, Spearman 0.60, p < 0.05); on simple loosely coupled projects all methods are comparable; when nearly every file depends on every other, the partition collapses to one group and there is "no latency advantage". — [Co-Coder](https://arxiv.org/html/2606.00953v1)
- Anthropic's 16-agent C compiler build (Feb 2026; uncontrolled vendor account): nearly 2,000 Claude Code sessions over about two weeks, 2 billion input and 140 million output tokens, just under $20,000, roughly 100,000 lines of Rust. Parallelism worked while there were many distinct failing tests. It stopped working on one giant task (compiling the Linux kernel): "every agent would hit the same bug, fix that bug, and then overwrite each other's changes" and "Having 16 agents running didn't help because each was stuck solving the same task." The fix was an external oracle: compile most files with GCC and a subset with the new compiler, so each agent got a different failing file. — [Anthropic engineering](https://www.anthropic.com/engineering/building-c-compiler)
- The same build used light specialisation by concern, not by job title: one agent deduplicating code, one on compiler speed, one on output code quality, one on design critique, one on documentation; task claims were made with lock files synchronised through git. — [Anthropic engineering](https://www.anthropic.com/engineering/building-c-compiler)
- (earlier survey) The Claude Opus 5 system card reports a ten-agent team 3.1 points above the best single agent on BrowseComp with a 5.9x latency speedup, and a five-agent team reaching the single agent's ProgramBench score 2.2x faster; per-agent limits mean the team had more tokens in total. — [Claude Opus 5 system card](https://www-cdn.anthropic.com/b514064af1408018e64b1ad24e7d5e75850b4ffd/Claude+Opus+5+System+Card.pdf)
- (secondary) The Google/MIT scaling study (Kim et al., 2512.08296) is summarised as +80.9% for centralised coordination on a parallelisable finance task and -39% to -70% for every multi-agent variant on sequential planning, with error amplification of 17.2x for independent agents vs 4.4x for centralised ones. — [summary](https://openclawwiki.org/blog/multi-agent-vs-single-agent-what-260-configurations-show)
- Single-agent runs on ultra-long tasks fail largely by running out of time, not skill alone: in SWE-Marathon, of 526 agent-attributable failures, 41.6% are implementation failure, 31.4% timeout, 15.4% reward hacking, 7.6% premature termination, 4.0% poor self-verification; rollouts use a median of 7.6M and a mean of 27.2M tokens (max 877.4M). — [SWE-Marathon, arXiv 2606.07682](https://arxiv.org/html/2606.07682)
- Independent verification has measurable headroom: SWE-Marathon lists "poor self-verification" and "premature termination" as recurring failure classes, and 10.2% of rollouts shipped a clear verifier bypass. — [SWE-Marathon](https://arxiv.org/html/2606.07682)

### Inferences
- The defensible claim for a team benchmark is not "teams get a higher score per token" but "teams finish within a deadline that a solo agent cannot meet". Every positive result found is a latency result or depends on it. A benchmark that wants solo to do clearly worse at equal total tokens must therefore make wall-clock time a scored or binding resource.
- Three task features recur where teams gain: (a) width, meaning many units that can progress at once; (b) a per-unit oracle, so each agent can tell whether its own unit is done without waiting for the others; (c) low coupling between units but a real interface between them. Feature (b) is what the C compiler build had to add before 16 agents helped.
- Total work size matters separately from width: a 31% timeout share on tasks of 40 to 400 expert-hours suggests a solo agent is time-bound there, which is the regime in which splitting should pay. The observed two-repository bug fixes (15 to 45 minutes, about $5) are far below it.
- Context saturation is a plausible fourth feature (mean 27M tokens per rollout far exceeds any context window), but no source found isolates it as a cause of solo failure or of team gain.
- Specialisation by access or concern has support; no source found shows a gain from specialisation by persona at equal budget.

### Gaps
- No equal-total-token solo vs team result on repository-scale or multi-service coding was found for 2025-2026. Co-Coder is the nearest and is author-reported on a small model.
- No controlled study was found that varies a wall-clock deadline and measures where the solo/team ordering flips.
- No study was found isolating context-window saturation as the mechanism by which a team wins.
- The Kim et al. figures above were seen only in secondary summaries in this pass.

## 2. How do long-horizon SWE benchmarks get difficulty that survives frontier models, and what sizes remain unsolved?

### Takeaway
Difficulty that survives 2026 frontier models comes from size and integration, not from crossing a repository boundary: tasks of thousands of changed lines over dozens of files with several jointly required sub-targets, or whole systems that must be deployed and exercised end to end, are resolved 11% to 39% of the time, while roughly 100-line patches are largely solved. Resolution falls most clearly with the number of files touched and the number of sub-targets that must all pass.

### Cited Findings
- Oracle patch sizes compared in one table: SWE-bench Verified about 33 LOC, SWE-bench Pro about 107 LOC, SWE-EVO about 611 LOC, FeatureBench about 790 LOC, NL2Repo about 3,000 LOC, RoadmapBench median about 3,700 LOC over 51 files with a median of 5 subtasks (range 3 to 12). — [RoadmapBench, arXiv 2605.15846](https://arxiv.org/html/2605.15846v1)
- RoadmapBench (May 2026): 115 version-upgrade tasks from 17 repositories in 5 languages, 2-hour wall-clock budget per task; resolved means all subtasks pass. Best result 39.1% (Claude Opus 4.7, OpenHands), then 32.2% (Opus 4.6), 29.6% (GPT-5.4), 20.9% (Gemini 3.1 Pro); weakest 5.2%. Completion score for the best model is 0.692, so partial progress is common and full resolution is not. — [RoadmapBench](https://arxiv.org/html/2605.15846v1)
- RoadmapBench failure correlates: files changed separates best (Gemini falls from 43% to 8% and Claude from 48% to 19% across the range); models converge near the floor above 10K changed lines; at 7 or more subtasks one model falls to 0% while Claude resolves 15%. — [RoadmapBench](https://arxiv.org/html/2605.15846v1)
- RoadmapBench quality control: 45 of 115 tasks needed fixes after agent rollouts (3.1 rounds on average), with failures attributed to task defect vs model limitation (Cohen's kappa 0.83). — [RoadmapBench](https://arxiv.org/html/2605.15846v1)
- FeatureBench (ICLR 2026): 200 feature-level tasks from 24 repositories, derived by tracing from unit tests along a dependency graph, with features that can span several commits and PRs; Claude Opus 4.5, at 74.4% on SWE-bench, resolves 11.0%. — [FeatureBench, arXiv 2602.10975](https://arxiv.org/abs/2602.10975)
- SaaSBench (May 2026): 30 build-and-deploy tasks for enterprise SaaS systems; PRDs average about 4,363 lines; 5,370 executable validation nodes joined by 6,167 prerequisite edges; each task has frontend, backend APIs, data models, role-based permissions and deployment config. Best Pass@1 is 20.68% (Claude Opus 4.7 in Claude Code), average 11.64%. Opus 4.7 under OpenHands used 102 steps, 12.1M tokens and about 30 minutes. — [SaaSBench, arXiv 2605.17526](https://arxiv.org/html/2605.17526)
- SaaSBench failure location: over 95% of failures occur before deep business logic; about 63.5% of capability units never ran stably, 32.1% were reachable but structurally incomplete, 3.8% reached business-logic bottlenecks. The authors attribute failures to configuration and integration between components more than logic inside one. — [SaaSBench](https://arxiv.org/html/2605.17526)
- SWE-Marathon (June 2026): 20 tasks (8 library clones or ports, 5 product clones such as slack, stripe, s3 and mastodon clones, 5 ML engineering, 2 optimisation), expert-human estimates 40 to 400 hours, agent wall-clock limits 2 to 10 hours, 5 trials per configuration, 1,300 trajectories; no configuration exceeds 30% pass@1; individual trials can cost hundreds of dollars. All 13 configurations are single-agent. — [SWE-Marathon](https://arxiv.org/html/2606.07682)
- METR's time-horizon page states "Measurements above 16 hrs are unreliable with our current task suite", was last added to on 8 May 2026 (Claude Mythos Preview, early), and since 8 September 2026 is no longer actively updated. — [METR](https://metr.org/time-horizons/)
- (secondary) Reported METR figures: public-frontier 50% horizon about 12 hours with an 80% horizon about 1.5 hours in early 2026; Claude Mythos Preview at least 16 hours (95% CI 8.5 to 55). — [metavert summary](https://metavert.io/metr-benchmarking)
- (secondary, conflicting) SWE-bench Pro scores in November 2026 range from 61.5% (Scale standardised set) to 93% (vendor-reported, Claude Fable 5.2) to 99% on a "V2" set, depending on the aggregator. — [morphllm](https://www.morphllm.com/swe-bench-pro); [benchlm](https://benchlm.ai/benchmarks/swe-bench-pro)

### Inferences
- The observed result (two-repository bug fix solved solo in 15 to 45 minutes) is what the size data predicts: a bug fix is a roughly 30 to 100 line change, the size class frontier models resolve at 60% to 90%+. Crossing a repository adds a lookup, not work.
- A target size that survives late-2026 models, by these benchmarks: a feature or migration with at least five jointly required sub-targets, on the order of 1,000+ changed lines over 20+ files in total, with success defined as all sub-targets passing. RoadmapBench's gap between completion (0.69) and resolution (39%) shows that the "all must pass" rule is doing much of the work.
- The gap between the 50% horizon (about 12 hours) and the 80% horizon (about 1.5 hours), if the secondary figures hold, implies that a solo agent is reliable only on work of an hour or two of human effort. Tasks of one to three human days of total work, with several interacting parts, sit in the range where solo success is a coin flip or worse within a short wall-clock budget.
- Integration and deployment state are a durable difficulty source: SaaSBench agents fail to keep a multi-component system running long before logic matters. A running multi-service company already has this property, so tasks should be checked against the live system, not unit tests of one side.
- Budget rule of thumb from these runs: tasks unsolved by frontier solo agents consume 7M to 27M tokens and 0.5 to 10 hours. A task that a mid-tier agent closes for $5 is one to two orders of magnitude too small.
- Rollout-based quality control (run three tiers of agents, classify each failure as task defect or model limit, fix and repeat) is the published way to make sure remaining difficulty is real and not specification noise.

### Gaps
- No verified 2026 frontier scores were found for SWE-Lancer, PaperBench, MLE-bench, RE-Bench, Commit0, NL2Repo or DevBench; searches returned only descriptions or aggregator pages.
- SWE-bench Pro late-2026 scores could not be verified against a primary leaderboard; aggregators disagree by 30+ points.
- SWE-Marathon per-model rates are in a figure that was not readable; only the "below 30%" ceiling is confirmed. Per-task human hours and reference LOC were not itemised in the text read.
- No source reports results for models released after about mid-2026 on RoadmapBench, SaaSBench or FeatureBench, so "unsolved in late 2026" is an extrapolation from May-June 2026 papers.
- FeatureBench task size (about 790 LOC) comes from RoadmapBench's comparison table, not from the FeatureBench page read.

## 3. What makes incident response hard for agents, and which benchmarks score time-to-mitigate?

### Takeaway
Agents lose most on noisy and ambiguous signals, compound and metastable faults that need two components fixed together, and faults outside the application layer; end-to-end success on novel faults is 15% to 28%. SREGym measures and reports time-to-detect and time-to-mitigate but does not fold them into the score, and no benchmark was found that scores time-integrated harm or forces triage across simultaneous incidents.

### Cited Findings
- SREGym (May 2026): 90 curated problems over 5 applications and 139 services, 50 fault primitives; 1,800-second timeout. End-to-end success without noise: Claude Code + Sonnet 4.6 60.7%, Stratus + Sonnet 4.6 54.8%, Codex + GPT-5.4 53.3%. With injected noise: 53.7%, 40.2%, 45.9%. — [SREGym, arXiv 2605.07161](https://arxiv.org/html/2605.07161v2)
- SREGym reports time-to-detect and time-to-mitigate per agent (capped at the timeout): TTM 702 s for Claude Code, 771 s for Stratus + Sonnet, 376 s for Codex without noise; 737, 885 and 398 s with noise. These are reported next to success, not part of it. — [SREGym](https://arxiv.org/html/2605.07161v2)
- Noise design: two transient low-impact noise patterns are injected every five minutes for two minutes each. Diagnosis drops for every agent (for example 72.6% to 62.6%, 61.5% to 51.5%); mitigation is more robust. Agents "treat the first plausible anomaly as the target, which is often a noise". — [SREGym](https://arxiv.org/html/2605.07161v2)
- Novel faults are much harder than ported ones: on SREGym-unique failures end-to-end success is 28.2% (Claude Code), 17.9% (Stratus + Sonnet) and 15.4% (Codex), against 63.7% for Stratus on problems ported from AIOpsLab and ITBench. — [SREGym](https://arxiv.org/html/2605.07161v2)
- Metastable problems pair an application-level trigger (a retry policy, a GC flag) with a silent infrastructure constraint (a resource quota) that emits no errors; fixing the trigger alone does not mitigate. Agents reliably found the trigger and never identified both interacting components. On compound failures agents often stopped at partial conclusions. — [SREGym](https://arxiv.org/html/2605.07161v2)
- Mitigation and diagnosis are partly decoupled: mitigation succeeds 69% to 88% of the time after a correct diagnosis and 35% to 59% after an incorrect one. — [SREGym](https://arxiv.org/html/2605.07161v2)
- ORCA-bench (July 2026): 1,079 root-cause tasks (884 incidents, 195 no-incident controls) on the 19-service OpenTelemetry Astronomy Shop with over 50 GB of six-day telemetry; 13 scenarios of isolated, independent, conflicting, cascading and sequential faults, peaking at six concurrent fault flags; detection delay of 15 minutes to 24 hours; three levels of report vagueness. — [ORCA-bench, arXiv 2607.28545](https://arxiv.org/html/2607.28545)
- ORCA-bench results: best partial-credit depth 48.8% (GPT-5.5); best all-causes accuracy 30.9% (Claude Sonnet 4.6), falling to 25.3% on medium and 10.0% on hard reports; vaguer reports cost 19 to 50 points and raise plausible root causes from 2.00 to 4.41; removing source code costs 9 to 16 points; 26% to 40% of telemetry calls error or return empty; hallucinated causes in 7% to 40% of answers. On the verified subset Claude Fable 5 reaches 40.6% accuracy. Scoring has no time component; detection delay is a task parameter. — [ORCA-bench](https://arxiv.org/html/2607.28545)
- ITBench (Feb 2025, ICML 2025): 94 scenarios (42 SRE); agents resolved 13.8% of SRE scenarios in the arXiv version and 11.4% in the ICML version. — [ITBench](https://proceedings.mlr.press/v267/jha25a.html); [arXiv 2502.05352](https://arxiv.org/pdf/2502.05352)
- (secondary) ITBench-AA (May 2026, Artificial Analysis with IBM): 59 SRE tasks, 19 of them held out; all evaluated models below 50%. — [Artificial Analysis](https://artificialanalysis.ai/articles/itbench-aa-launch)
- Reward hacking in earlier SRE benchmarks: 8 of 18 ITBench mitigation problems (44%) can be "solved" by a generic pod-restart loop because the fault injector loses track of the restarted pod and the alert clears; injectors in AIOpsLab and ITBench run as identifiable pods the agent can inspect. — [SREGym appendix](https://arxiv.org/html/2605.07161v2)
- (pre-2025) Google's incident guidance: "Stop the bleeding, restore service, and preserve the evidence for root-causing"; declare an incident if a second team is needed, if the outage is customer-visible, or if the issue is unsolved after an hour of concentrated analysis. — [Google SRE book, Managing Incidents](https://sre.google/sre-book/managing-incidents/)

### Inferences
- Four ingredients have measured effects and are cheap to add to a service company: background noise events (about 7 to 15 points), vague reports (19 to 50 points), a second silent contributing cause in another component (near-zero success), and faults new to the public benchmarks (a 35 to 45 point drop).
- A metastable or compound fault whose two halves live in services with different owners is a natural team task: SREGym shows a solo agent with full access already stops after the first half. The check is that the system stays healthy under continued observation, which needs both fixes.
- Time-scored harm is an open design space. Since TTM is already 6 to 15 minutes for single faults, a scenario with several simultaneous incidents and a score equal to user-facing error integrated over time would make serial handling cost points in a way a deadline-free pass/fail check does not. This is where a team's latency advantage (section 1) turns into score.
- Mitigation-before-root-cause can be made checkable as two separate obligations: service health restored by time T1 (probe-based) and the underlying defect removed by T2 (the fault does not recur when the mitigation is lifted or load returns). The 35% to 59% mitigation-without-diagnosis rate shows these are separable.
- Control tasks with no incident (ORCA-bench has 195) guard against agents that always act.

### Gaps
- No benchmark was found that scores time-weighted harm, an SLO burn, or triage across concurrent independent incidents with more work than one responder can do in the window. ORCA-bench has concurrent faults but scores diagnosis only.
- No multi-agent incident-response result (team vs solo) was found in the portions of SREGym or ORCA-bench read.
- AIOpsLab's own headline figures were not verified from a primary source in this pass.
- ITBench-AA figures were seen only in search summaries; aggregator numbers disagree with the launch post.

## 4. Which kinds of real engineering work need several owners, with checkable properties?

### Takeaway
The work that needs several owners in practice is change to something shared while it stays in use: a data model or contract migrated with a compatibility window, a deprecation with many consumers, and an incident that spans teams. Each comes with properties the engineering literature states precisely enough to test: both versions valid throughout, reads switched only after results match, backfill completeness, old path hard-errors at the end, no downtime at any step.

### Cited Findings
- (pre-2025, Feb 2017) Stripe's online migration pattern has four ordered steps: dual write to old and new tables; switch all read paths to the new table; switch all write paths to the new table only; remove old data and code. — [Stripe, Online migrations at scale](https://stripe.com/blog/online-migrations)
- (pre-2025) Stripe's stated constraints: "we had to execute the transition with all of our services operating at 100%"; "Our Subscriptions table is used in many different places in our codebase"; "We needed to be sure that every service could continue to rely on accurate data." The logic spanned thousands of lines across multiple services, changed a few hundred lines at a time, over hundreds of millions of objects. — [Stripe](https://stripe.com/blog/online-migrations)
- (pre-2025) Checkable steps Stripe used: an offline backfill from snapshots, then the same job re-run to confirm nothing was missing from the new table; both read paths executed and compared with GitHub's Scientist library, reads switched only after results matched; writes ordered new store first; and at the end, access to the old field raises a hard error so no code can keep using it. — [Stripe](https://stripe.com/blog/online-migrations)
- (pre-2025, Aug 2017) Stripe's API compatibility rule: "Fields that were present before should stay present, and fields should always preserve their same type and name." Removing a field, renaming it or changing its type is breaking; adding an endpoint or a never-present field is not. Each account is pinned to the version of its first request; responses are built at the current version and walked back through version-change modules to the pinned version; about a hundred breaking upgrades were absorbed over six years with every version since 2011 still served. — [Stripe, API versioning](https://stripe.com/blog/api-versioning)
- (pre-2025, Dec 2023) Expand/contract is described as the accepted way to make a breaking change without a stop-the-world deployment: add the new form beside the old, migrate dependents, remove the old once nothing depends on it. — [Pete Hodgson](https://blog.thepete.net/blog/2023/12/05/expand/contract-making-a-breaking-change-without-a-big-bang/); [Xata pgroll](https://xata.io/blog/pgroll-expand-contract)
- (pre-2025, Aug 2024) Monzo, 2,800 microservices: decentralised migrations by service owners "inevitably led to unfinished migrations and a lot of coordination effort"; its central approach wraps the old library so the implementation is chosen by dynamic config (rollback without redeploying every service), ships the new path disabled, enables it by percentage, deploys least-critical tiers first with automated rollback checks, and adds a CI rule blocking new uses of the old library. — [Monzo](https://monzo.com/blog/how-we-run-migrations-across-2800-microservices)
- (pre-2025, 2016) Google SRE incident roles: incident command, operations, communication, planning. "Ops should be the only group changing the system during an incident"; the commander keeps a live incident state document; handoffs must be explicit and acknowledged; a second team being needed is itself a criterion for declaring an incident. — [Google SRE book](https://sre.google/sre-book/managing-incidents/)
- (secondary) Uber's trip-fulfilment migration kept old API contracts and event schemas working for existing consumers through a backward-compatibility layer. — [Uber](https://www.uber.com/en-GB/blog/migrating-functionality-between-production-systems/)

### Inferences
- These patterns give outcome properties that are true or false of a running system, independent of how the code is written:
  1. Compatibility window: at every observed moment between start and finish, both an old-version client and a new-version client get correct results.
  2. Ordering: no consumer reads the new form before the producer writes it; no producer stops writing the old form while any consumer still reads it.
  3. Backfill completeness: every pre-existing record is present and equal in the new form, verified by an independent recount.
  4. Read equivalence: old and new read paths return the same answer on live traffic before the switch.
  5. Availability: an external probe sees no errors or dropped events across the whole change, including during the backfill.
  6. Contraction: the old field, endpoint or topic is gone at the end and using it fails loudly.
  7. Rollback: turning the new path off by config restores old behaviour without redeploying.
- A migration is inherently multi-step with waiting between steps, and each consumer's step is independent of the others: this is the width-with-interface structure section 1 identifies as favourable to teams. The number of consumers sets the width.
- Monzo's finding that owner-by-owner migrations stall is the real-world form of the benchmark problem: a migration is only done when the last consumer has moved, so the score should be the state of the whole company at the end (property 6) plus continuous properties (1, 5) during it.
- A two-repository bug fix has none of these properties: there is no window, no live traffic, no ordering and no second consumer. That is a structural reason it collapses to a solo task.
- Combining a migration with an incident is realistic (an on-call page arrives mid-migration) and creates true concurrency that a deadline can bind on.

### Gaps
- No 2025-2026 primary engineering post was fetched; all practice sources here predate 2025. The patterns are stable, but nothing confirms recent changes in practice.
- GitHub (gh-ost, Scientist) and Shopify (shard rebalancing, zero-downtime moves) posts were not retrieved; Scientist is cited only through Stripe's use of it.
- No quantitative source was found on how many owners or how much calendar time such migrations take in industry.
- The Uber item was seen only in a search summary.

## 5. How do benchmarks enforce that each party must contribute and block a solo shortcut through one side?

### Takeaway
Published enforcement comes in three kinds: access (containers, tool scopes, path whitelists), information (a requirement or fact disclosed to one agent only), and structure (a task admitted only if it needs a minimum number of handoffs); none of the coding benchmarks combines these with per-owner obligations checked separately on a live system. The single-agent benchmarks show the complementary lesson: shortcuts are found whenever the check can be satisfied without doing the work, at rates of 10% to 44%.

### Cited Findings
- (earlier survey) EntCollabBench requires at least three cross-agent delegations per task and restricts each agent to tools in its own role, "ensuring that the task cannot be reduced to sequential tool calls by a single agent". — [EntCollabBench, arXiv 2605.08761](https://arxiv.org/html/2605.08761v1)
- (earlier survey) ParallACT discloses each requirement only to the agent representing that principal; the final repository state must satisfy both acceptance tests. A single-agent oracle holding both requirements solves most tasks and parallel agents do much worse. — [ParallACT, arXiv 2611.00314](https://arxiv.org/html/2611.00314)
- (earlier survey) TeamBench enforces roles with containers and bind mounts; enforcement barely changed scores (42.7% prompt-only vs 40.5% enforced) but cut out-of-role edit attempts from 256 to 72. — [TeamBench, arXiv 2605.07073](https://arxiv.org/html/2605.07073)
- SREGym hides the fault-injection plane behind a proxy the agent cannot see, because in earlier benchmarks agents could find and disable injector pods. — [SREGym](https://arxiv.org/html/2605.07161v2)
- A check tied to a symptom is gamed: a restart loop passes 8 of 18 ITBench mitigation problems because the alert clears. — [SREGym appendix](https://arxiv.org/html/2605.07161v2)
- SWE-Marathon admits a task only after review, CI, trial runs and an adversarial "cheating" agent; it uses LLM-only network egress and in-trial tripwires. 13.8% of rollouts attempted an exploit and 10.2% shipped a clear verifier bypass; none of 1,300 trials earned reward from one. — [SWE-Marathon](https://arxiv.org/html/2606.07682)
- SaaSBench links 5,370 validation nodes with 6,167 prerequisite edges and marks dependants of a failed prerequisite as skipped, so credit for deep behaviour requires the foundations to work. — [SaaSBench](https://arxiv.org/html/2605.17526)
- RoadmapBench counts a task resolved only if every weighted subtask passes, and reports a separate completion score. — [RoadmapBench](https://arxiv.org/html/2605.15846v1)
- Single-agent access to more of the system helps measurably: removing source code access lowers ORCA-bench accuracy by 9 to 16 points. — [ORCA-bench](https://arxiv.org/html/2607.28545)

### Inferences
- "Solved from one repository alone" means the checks could be satisfied by changing one side. The remedy the literature supports is conjunctive scoring over obligations that live in different owners' territory: a producer obligation, one obligation per consumer, and a system-level property, all required (RoadmapBench's rule applied across owners).
- Independent consumers are the strongest structural guard. If three consumers each need their own adaptation and each is probed separately, a compatibility shim in the producer can satisfy the window (property 1) but not the contraction (property 6), and a consumer-side patch cannot satisfy the producer's new contract. Requiring both the window and the contraction rules out both one-sided routes.
- Private information should be real operational knowledge held by one owner (a consumer's undocumented reliance on a field, a rate limit, a data quirk that breaks the backfill), not a withheld requirement sentence. ParallACT shows a withheld requirement is recoverable by a solo oracle; a fact that only shows up in one service's runtime data must be found by whoever can read that data.
- Because a solo agent "with access to all repositories" is the stated comparison, access partition cannot be the only source of necessity. Under full access the binding constraints left are time and total work, so necessity has to come from width times deadline, with access partition as an additional condition for the team track.
- Admission by ablation is the practical test: keep a task only if (i) a solo agent with full access fails or scores clearly lower within the budget, (ii) each single-owner-only attempt fails a named check, and (iii) an adversarial agent told to cheat cannot pass. SWE-Marathon and RoadmapBench both use rollout-based admission.
- Expect roughly one in ten runs to attempt a verifier bypass on long tasks; keep the injection and probing machinery out of the agents' view.

### Gaps
- No benchmark was found that verifies per-owner obligations separately on deployed services, or that reports how often a solo agent passes a nominally two-party task through one side. The observation that prompted this research appears not to be published anywhere.
- No published "necessity index" other than TeamBench's was examined in this pass, and TeamBench's was not re-read.
- No evidence was found on whether read-partitioning changes scores on service-scale tasks (TeamBench suggests enforcement changes behaviour more than score).

## 6. How do benchmarks keep verifiers outcome-based while still preventing one-sided shortcuts?

### Takeaway
The benchmarks that resist shortcuts check the state and behaviour of the running system over time, with several independent verifier families whose results are combined by "all must pass" or a minimum, and they keep observing after the agent says it is done. None checks how the work was divided; the anti-shortcut effect comes from choosing outcomes that a one-sided change cannot produce.

### Cited Findings
- SREGym uses "state-based mitigation oracles that probe live environment health" from client-side and system-side signals instead of alert status, and for metastable faults keeps observing to tell a transient recovery from a relapse. — [SREGym](https://arxiv.org/html/2605.07161v2)
- SWE-Marathon's hidden verifiers come in six families: dense test suites, behavioural parity, performance gates, deterministic replay, integrity/audit checks, and agentic computer-use verifiers; where an agentic verifier is used, reward is the minimum of the deterministic and agentic stages. — [SWE-Marathon](https://arxiv.org/html/2606.07682)
- SaaSBench runs validation nodes in dependency order against the running system and scores six dimensions (Deploy, Data, API, Logic, AuthZ, Quality), with an LLM judge for some nodes. — [SaaSBench](https://arxiv.org/html/2605.17526)
- SREGym's diagnosis check is a nine-question checklist over localisation, characterisation and scope, pass at 7 of 9 so that no whole dimension can be missed; judge agreement with a human expert is kappa 0.90 for one judge model and 0.70 to 0.76 for two others. — [SREGym](https://arxiv.org/html/2605.07161v2)
- ORCA-bench scores accuracy as 1 only if every plausible root cause is named, and separately scores hallucinated causes and no-incident controls. — [ORCA-bench](https://arxiv.org/html/2607.28545)
- (pre-2025) Stripe's own acceptance checks for a migration were outcome checks: a recount job finding zero missing records, read-path comparison showing zero mismatches, and a hard error on the old path. — [Stripe](https://stripe.com/blog/online-migrations)
- The Anthropic compiler build used a trusted reference implementation (GCC) as an oracle for differential checking of partial work. — [Anthropic engineering](https://www.anthropic.com/engineering/building-c-compiler)

### Inferences
Design rules for tasks, drawn from sections 1 to 6. Each is a synthesis; the supporting section is given in brackets.

1. Make time bind. Give a wall-clock deadline or score harm integrated over time, sized so the serial sum of the required work exceeds the window while the parallel critical path fits. Without this, no published evidence predicts a team beats a solo agent at equal tokens. [1, 3]
2. Give the task width with an interface: one shared change (contract, schema, event) and three or more independent consumers, each needing its own adaptation. Width should come from the number of real consumers, not from splitting one feature. [1, 4]
3. Size the total work above the solo-reliable range: at least five jointly required sub-targets and on the order of a thousand or more changed lines across twenty or more files company-wide; expect 5M+ tokens. A task a mid-tier agent finishes for $5 is too small by one to two orders of magnitude. [2]
4. Score conjunctively across owners: producer obligation, each consumer's obligation, and a system property, all required; report a partial completion score separately. [2, 5]
5. Verify behaviour of the live system over the whole run, not the end state alone: continuous old-client and new-client probes through the compatibility window, availability under load during the backfill, and a hold period after completion to catch relapse. [3, 4, 6]
6. Require both ends of expand/contract: old clients work during the window and the old form is gone and fails loudly at the end. The pair excludes a producer-only shim and a consumer-only patch. [4, 5]
7. Check data, not code: backfill completeness by independent recount, old/new read equivalence on recorded traffic, no lost or duplicated events. [4, 6]
8. Put a second, silent contributing cause in a different owner's service for incident tasks, and require health to hold under continued observation. Solo agents with full access already stop after the first cause. [3]
9. Add realistic difficulty with measured effect: background noise events, vague reports, missing or failing telemetry, faults not present in public benchmarks, and no-incident controls. [3]
10. Split mitigation from root-cause fix as two timed obligations, mitigation first. [3]
11. Place private facts in runtime state that only one owner can read, not in withheld task text. [5]
12. Admit tasks by ablation: solo with full access at the same total budget, each single-owner-only attempt, a no-messaging team, and an adversarial cheating agent; classify every failure as task defect or model limit and repair the task. Budget for about 40% of tasks needing repair. [2, 5]
13. Hide injectors, probes and graders from agents and use more than one verifier family combined by minimum. Expect bypass attempts in roughly a tenth of long runs. [5, 6]
14. Provide a per-unit oracle where possible (a reference client, recorded traffic, a contract test each owner can run) so that owners can work in parallel without waiting for one another; without one, parallel agents converge on the same bottleneck. [1]

- Outcome-based and shortcut-resistant are compatible because the properties in section 4 are properties of observable behaviour over time. The verifier never needs to ask who did what.
- LLM judges are usable for diagnosis write-ups with a checklist and a threshold, but agreement varies by judge model (kappa 0.70 to 0.90), so they should not gate the main score.

### Gaps
- No published verifier was found that checks a compatibility window continuously during an agent-run migration; rules 5 to 7 are built from engineering practice and from incident benchmarks, not from an existing migration benchmark.
- No evidence was found on how long a post-completion hold period needs to be, or how probe frequency affects false passes.
- No source quantifies how much each anti-shortcut measure reduces one-sided passes; SWE-Marathon reports only the combined result (zero rewarded exploits in 1,300 trials, stated as a lower bound on attempts).
- Whether these rules actually produce a solo/team gap at equal budget is untested; the nearest direct evidence remains author-reported or uncontrolled.

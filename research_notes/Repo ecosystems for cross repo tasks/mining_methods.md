# Methods, tools and datasets for mining real cross-repository features as benchmark/RL tasks

Scope: how to find features built by linked PRs in two or more repos close in time, and the practical limits on turning them into tasks (start state = parent commits, reference = merged code, hidden tests = upstream F2P tests, regression guard = P2P tests, inter-repo contract). As of 18 Nov 2026. Years are given for older work. Figures for 2026 arXiv papers come from the papers themselves (v1 HTML) and have not been peer reviewed. Model names and scores are copied as each paper reports them.

## 1. Published research and datasets on cross-repository / multi-repository changes

### Takeaway
Two papers from autumn 2026, **WideSWE** (Sep 2026) and **CrossSWE** (Nov 2026), are the closest published versions of our recipe. Both mine explicit cross-repo references between merged PRs, check co-change with execution, and ship task datasets. Older MSR/ICSE work (2017–2024) gives base rates for how common and how useful cross-project links are. It covers bug links within ecosystems, not features. WideSWE's number is the most useful one: about 6.3% of PRs in large ecosystems explicitly reference another repo in the same ecosystem (109,233 of 1,729,171).

### Cited Findings
**Benchmarks and datasets that pair PRs across repos (2026)**
- **WideSWE: Can Coding Agents Coordinate Changes Across Repositories?** by Wang, Wang, Wu, Wu, Zhi, Yin (Zhejiang Univ. / Tsinghua), arXiv:2609.33382, submitted 27 Sep 2026.
  - Ecosystems were taken from the top 200 GitHub organizations by total stars (Gitstar Ranking, collected 5 Jun 2026), keeping 103 active ecosystems.
  - PRs merged since 1 Jan 2024 in non-archived repos were mined. Candidate groups were kept only if their latest PR merged on or after 1 Jun 2025.
  - The linking signal is explicit cross-references between repos in the same ecosystem, found in PRs and issues. — [WideSWE](https://arxiv.org/html/2609.33382v1)
  - The funnel: 1,729,171 PRs analyzed → 109,233 with explicit links to another repo in the same ecosystem → 4,437 candidate groups after deduplication and checks → 2,188 after the date cutoff → 635 after manual review → 240 runnable → 192 with at least one F2P test per target repo → 120 final tasks. — [WideSWE](https://arxiv.org/html/2609.33382v1)
  - The final set is 60 bug fixes and 60 features (picked from 132 feature candidates for diversity), across 41 ecosystems and 253 target repos. It has 2,815 F2P and 22,139 P2P tests, up to 20 context repos per task (median 3), and reference patches with a median of 13 files and 416 lines. — [WideSWE](https://arxiv.org/html/2609.33382v1)
  - Results: full-task success ranged from 10.83% to 42.50%; the best was Codex CLI with GPT-5.6-sol. Table 1 reports 41.67% for the same row, so the paper is internally inconsistent. On 89 comparable tasks, joint execution solved 40.45% and independent per-repo execution solved 35.96%. — [WideSWE](https://arxiv.org/html/2609.33382v1)
  - Code and artifact: https://github.com/ZJU-ACES-ISE/WideSWE. It includes instance metadata, base commits, prompts, hidden-test patches, environment definitions and scoring scripts. — [WideSWE](https://arxiv.org/html/2609.33382v1)
- **CrossSWE: Benchmarking Cross-Repository Joint Development for Coding Agents** by Chen, Shi, Lian, Zhang, Gu, Lin, Sun (SJTU / Xidian / SMU), arXiv:2611.01484, 1 Nov 2026.
  - 171 instances across 165 repos, 20 technical domains and 13 languages. 165 instances involve two repos, 5 involve three, and 1 involves five.
  - Mined window: Jan 2025 – Sep 2026.
  - Intent categories: features 54, API/schema/protocol evolution 43, bug fixes 22, security/identity/observability 21, deployment/runtime 14, migration 9, test/conformance 7, transitive propagation 1. — [CrossSWE](https://arxiv.org/html/2611.01484)
  - Pass@1 with mini-SWE-agent v2.4.6, max 300 steps, $10 cap: GPT-6.1 Sol 58.48%, DeepSeek V4.1 Flash 52.63%, Claude Sonnet 5.5 50.29%, Qwen3.8-Flash-Next 45.03%, GLM-5.3 Flash 43.86%.
  - The top failure mode was cross-repo inconsistency, at 29–44% of failures depending on the model. — [CrossSWE](https://arxiv.org/html/2611.01484)
  - Dataset: https://huggingface.co/datasets/CrossSWE/CrossSWE-Bench — [CrossSWE](https://arxiv.org/html/2611.01484)

**Earlier empirical studies of cross-project links (MSR/ICSE/APSEC)**
- **How do developers fix cross-project correlated bugs? A case study on the GitHub scientific Python ecosystem** by Ma, Chen, Zhang, Zhou, Xu. ICSE 2017, pp. 381–392, DOI 10.1109/ICSE.2017.42.
  - Starts from 7 seed projects and finds 271 pairs of cross-project correlated bugs involving 204 projects. — [bibtex record](https://bibtex.github.io/ICSE-2017-MaCZZX.html); [slides](https://xgdsmileboy.github.io/yoser2017/files/slide/yoser2017-linchen.pdf)
  - A follow-up, **An Empirical Study on Downstream Workarounds for Cross-Project Bugs** (Ding et al., APSEC 2017), reports 60 downstream workarounds. — [AMiner](https://www.aminer.org/pub/5ac1825d17c44a1fda914354/an-empirical-study-on-downstream-workarounds-for-cross-project-bugs)
- **Within-Ecosystem Issue Linking: A Large-scale Study of Rails** (CMU STRUDEL, 2018 workshop/MSR-adjacent). Developers link more cross-project and cross-ecosystem issues over time. Unlike the scientific-Python study, it found no evidence that linked issues take longer to resolve. — [PDF](https://cmustrudel.github.io/papers/swmining18ecobugs.pdf) (only the search snippet was available; the PDF text could not be extracted, so venue details and counts are unverified)
- **Astropy ecosystem study** (arXiv 2402.15081, 2024): 1,491 links between pairs of issues/PRs across 43 packages, forming 697 cross-reference graphs. — [arXiv](https://arxiv.org/pdf/2402.15081) (search snippet)
- **nf-core maintenance study** (arXiv 2607.10839, 2026): 17,512 explicit cross-artifact references; the largest flow ran from PRs to issues (7,599). — [arXiv](https://arxiv.org/pdf/2607.10839) (search snippet)
- **Linking behavior across issues and PRs** (Li et al., APSEC 2018): 642,281 issues/PRs from 16,584 Python projects; manual coding found six kinds of relationship. — [PDF](https://weiqin-zou.github.io/papers/APSEC18.pdf) (search snippet)
- **FSE 2024 PR–issue graph study** (UBC): only 12.11% of links are "fixes"; most links are not built-in fix or duplicate links. — [PDF](https://cs.ubc.ca/~bestchai/papers/fse24-pr-issue-graphs.pdf) (search snippet)
- **PI-Link** (IEEE Access 2023): a ground-truth dataset of 50,369 links between 34,732 issues and PRs in Android projects. — [AMiner](https://www.aminer.org/pub/63bbf23090e50fcafd11da7e/pi-link-a-ground-truth-dataset-of-links-between-pull-requests-and)
- **An Empirical Study of Cross-Project Pull Request Recommendation in GitHub** (APSEC 2024): recommends PRs from other projects to help resolve issues. — [APSEC 2024](https://conf.researchr.org/details/apsec-2024/apsec-2024-technical-track/4/An-Empirical-Study-of-Cross-Project-Pull-Request-Recommendation-in-GitHub)
- **Gousios et al., MSR 2014** (GHTorrent PR dataset): about 350,000 PRs; notes that PRs include links to other related PRs. — [PDF](https://azaidman.github.io/publications/gousiosMSR2014a.pdf)

**Ecosystem dependency and microservice co-change**
- **An Empirical Comparison of Dependency Network Evolution in Seven Software Packaging Ecosystems** by Decan, Mens, Grosjean. EMSE 24(1):381–416, 2019, DOI 10.1007/s10664-017-9589-y.
  - Covers Cargo, CPAN, CRAN, npm, NuGet, Packagist and RubyGems, using libraries.io data.
  - Roughly 6–17% of packages account for over 80% of reverse dependencies. — [arXiv 1710.04936](https://www.arxiv.org/abs/1710.04936); [ORBi](https://orbi.umons.ac.be/handle/20.500.12907/25206)
- **Ecosystem-wide PR acceptance in npm** (EMSE 2025): about 1.8M PRs from 20,052 npm projects. — [Springer](https://link.springer.com/article/10.1007/s10664-025-10706-1) (search snippet)
- **How do microservices evolve? An empirical analysis of changes in open-source microservice systems** by Assunção, Krüger, Mosser, Selaoui. JSS 2023.
  - 11 open-source systems and 7,319 commits.
  - Finds co-evolution patterns such as "shotgun surgery" commits and groups of services that evolve together. — [MacSphere](https://macsphere.mcmaster.ca/handle/11375/28661?mode=full)
  - A registered report on microservice logical coupling via co-change is at [arXiv 2306.02036](https://arxiv.org/pdf/2306.02036).
- **Continuous Benchmark Generation for Evaluating Enterprise-scale LLM Agents** (ICSE 2026 LLM4Code; arXiv 2511.10049): Microsoft service migration; the evaluation set comes from 11 manually migrated services with oracle patches. — [arXiv](https://arxiv.org/pdf/2511.10049)

### Inferences
- About 6.3% of PRs in large ecosystems carry an explicit same-ecosystem cross-repo link. But WideSWE's funnel keeps only about 0.007% of mined PRs as final tasks (120 / 1.73M), and about 2.7% of candidate groups (120 / 4,437). Expect roughly a 30–40x drop from linked groups to usable tasks. Manual review (2,188 → 635) and runnability (635 → 240) are the biggest cuts.
- CrossSWE's category mix (API/schema/protocol evolution is 25%) fits our "contract between repos" design. Saleor core plus dashboard (GraphQL schema copy) is a textbook "API/schema evolution + feature" case.
- The older literature is about bug links. Feature-level cross-repo co-change has little empirical study before 2026. The two 2026 benchmarks are the main prior art, and we should compare against them so we don't duplicate their task sets. They mine since 2024–2025, from top-star orgs.

### Gaps
- I found no published dataset of cross-repo PR pairs that is fully automated and ecosystem-wide (e.g. a BigQuery-derived table) beyond WideSWE's internal 109,233 linked PRs. Whether WideSWE releases the unfiltered linked-PR list is unverified; the remaining 15k characters of the paper were not read.
- I could not verify the Rails 2018 study's counts or venue (the PDF could not be extracted).
- I found no study that quantifies bot-generated companion PRs (SDK/codegen) as a share of cross-repo links.

## 2. Existing multi-repo / cross-service coding benchmarks: construction, environments, flakiness

### Takeaway
Only WideSWE and CrossSWE pair PRs across repos. CrossSWE has the strongest validation of co-change necessity: it enumerates all 2^N mixed base/patched configurations. WideSWE has the most explicit rule for tests coupled to implementation: it relaxes implementation-specific asserts and drops checks for functionality the task did not request, which affected 88 of 120 tasks. Single-repo benchmarks (Multi-SWE-bench, SWE-bench-Live/RepoLaunch, FeatureBench, SWE-EVO, SWE-rebench) supply the environment and F2P machinery. None of the sources I read describes repeated-run flakiness detection. Multi-SWE-bench uses test-status transition rules instead.

### Cited Findings
- **WideSWE construction**
  - Filters: deduplication, PR availability, screening for test-related changes (paths like `tests/`, `spec/`, `_test`), and Linux compatibility.
  - Manual review requires one feature or fix per group, with substantive changes in multiple repos. "Incidental citation" is not enough.
  - Prompts come from the original issue and PR text, with no added implementation instructions, and are reviewed by two other authors. — [WideSWE](https://arxiv.org/html/2609.33382v1)
- **WideSWE tests and scoring**
  - F2P tests must fail on the base and pass with the reference; P2P tests must pass in both.
  - A task passes only if every target repo passes all its F2P and P2P tests.
  - Test revision rules: relax implementation-specific constraints and remove checks for unrequested functionality. Revisions affected 88 tasks, and the revised suites were re-checked to reject the base and accept the reference.
  - The paper does not discuss flakiness. — [WideSWE](https://arxiv.org/html/2609.33382v1)
- **WideSWE workspace and leakage control:** each target repo sits at the base commit of its PR. Context repos are snapshotted no later than the earliest target base, which prevents future-information leakage. — [WideSWE](https://arxiv.org/html/2609.33382v1)
- **CrossSWE mining**
  - Uses the GitHub API over merged PRs, issues with reconstructable changes, commits, and release or compatibility discussions.
  - Search cues include API evolution, dependency migration, provider–consumer and client–server relations, and explicit cross-repo references.
  - Recall-first: collect broadly, then have humans check the PR, timeline, referenced repos and commits.
  - At least two repos must carry substantive implementation changes. Docs, release-note and changelog-only changes are excluded. — [CrossSWE](https://arxiv.org/html/2611.01484)
- **CrossSWE co-change necessity test:** enumerate all 2^N base/patched combinations in one Docker image. A task is kept only if F2P fails in the all-base state and in every partial state, and passes when all patches are applied. — [CrossSWE](https://arxiv.org/html/2611.01484)
- **CrossSWE environment and prompts**
  - One Docker image per instance, with all repos at base commits, clean git state and dependencies installed.
  - Gold patches, fixed checkouts, hidden tests and "fixed-version artifacts" are excluded from the image.
  - Problem statements are written from the pre-fix view (following SWE-Bench ProMax) and avoid prescribing names, fields or paths.
  - The paper does not discuss flakiness. — [CrossSWE](https://arxiv.org/html/2611.01484)
- **Multi-SWE-bench** (arXiv 2504.02605, 2025)
  - Five phases: (1) repo selection (>500 stars, ≥6 months maintained, CI present, latest commit builds); (2) PR crawling (linked to an issue, modifies tests, merged); (3) environment determination (Dockerfile built from CI files, README and trial runs, with iterative fixes; unfixable PRs are dropped); (4) filtering.
  - Filtering runs the full test suite three times: base, base + test.patch, and base + test.patch + fix.patch. It discards PRs with any ANY→PASSED→FAILED transition, PRs with no ANY→FAILED→PASSED transition, and PRs with abnormal transitions such as PASSED→NONE/SKIPPED→FAILED.
  - This gives 2,456 candidates. Phase 5 is manual verification with 68 annotators plus a 14-person QA team, leaving 1,632 final instances (7 languages).
  - Multi-SWE-RL has 4,723 instances across 76 repos, built with the same pipeline minus the manual step. — [Multi-SWE-bench](https://arxiv.org/html/2504.02605)
- **SWE-bench-Live** ("SWE-bench Goes Live!", arXiv 2505.23419, May 2025): 1,319 tasks from issues created since 2024, across 93 repos, each with a Docker image, built by an automated curation pipeline. — [arXiv](https://arxiv.org/abs/2505.23419)
- **RepoLaunch** (arXiv 2603.05026; NeurIPS 2026 poster)
  - Automates build and test for any language and platform, and supplies SWE-bench-Live's environments and test-status extractors.
  - Build success is about 70% in v1 and 78% in the later version and NeurIPS abstract.
  - A third-party summary gives per-language rates of Python 75.5% (906/1200), JS/TS 69.0%, Go 60.3%, Java 76.3% and Rust 74.0%. I did not verify these against the paper. — [arXiv](https://arxiv.org/html/2603.05026v1); [NeurIPS](https://neurips.cc/virtual/2026/poster/151672); [Recoleta summary](https://neapolitanicecream.github.io/recoleta/en/items/software-intelligence--2026-03-05--repolaunch-automating-build-test-pipeline-of-code-repositories-on-any-language-and-any-platform.html)
- **Multi-Docker-Eval** (arXiv 2512.06915) is a benchmark for automatic environment building itself. — [arXiv](https://arxiv.org/html/2512.06915v3) (not read in detail)
- **FeatureBench** (ICLR 2026; arXiv 2602.10975)
  - 200 tasks and 3,825 executable environments from 24 Python repos.
  - Environments: humans write an install config (about 3 minutes per repo, under 1 hour total), then Docker builds automatically.
  - Feature extraction: Python tracing builds a call-dependency graph from F2P/P2P runs. An LLM classifies the test's imports into targets and utilities. A BFS removes code that P2P tests do not reach, capped at a random 3,000–5,000 lines. The removed code becomes the gold patch, and post-verification checks that P2P passes, F2P fails, and the patch restores everything.
  - Prompts state signatures and import paths, so tests coupled to the interface stay fair.
  - Anti-cheating: URL blacklist, defensive prompting, and log scans for reads of installed package source.
  - Data rules: test files first committed after May 2022; kept tasks have over 100 lines to implement and at least 10 F2P test points.
  - Claude 4.5 Opus scores 11.0%, against 74.4% on SWE-bench. — [FeatureBench](https://arxiv.org/html/2602.10975v1)
- **SWE-EVO** (arXiv 2512.18470, Dec 2025): release-to-release evolution with release notes as the spec. 48 tasks across 7 Python repos, averaging 874 tests per instance. GPT-5 with OpenHands scored 21% (v1); a later revision reports GPT-5.4 at 25%. The paper proposes a "Fix Rate" partial-credit metric. — [SWE-EVO](https://arxiv.org/html/2512.18470v2)
- **SWE-rebench** (NeurIPS 2025 D&B; arXiv 2505.20411): over 21,000 Python tasks from 3,468 repos, with continuous fresh collection for a decontaminated leaderboard. Execution verification runs tests before and after the patch. The summaries I found do not describe flaky-test handling. — [arXiv](https://arxiv.org/abs/2505.20411); [NeurIPS](https://papers.neurips.cc/paper_files/paper/2025/hash/21bec6ace947b1b58967b945c8ac0f10-Abstract-Datasets_and_Benchmarks_Track.html)
- **RepoGenesis** (arXiv 2601.13943, Jan 2026): generates microservice repos from a README, across 106 repos. Failures were cross-file consistency 50.2%, architectural coherence 26.0% and dependency management 23.8%. It builds from scratch rather than changing existing services. — [arXiv](https://arxiv.org/pdf/2601.13943)
- **Adjacent 2026 work:** BulkPR-Bench, on queue-level governance of interacting PRs within a repo ([arXiv 2608.02685](https://arxiv.org/pdf/2608.02685)), and AsynCodeBench, on asynchronous multi-agent SE ([arXiv 2609.32662](https://arxiv.org/pdf/2609.32662)). I did not read either in detail.

### Inferences
- For our recipe, take CrossSWE's 2^N check as a cheap automatic gate. With N=2 it is three extra runs. It rules out "dashboard PR is independently solvable" pairs; such pairs are still usable, but as single-repo tasks.
- Take WideSWE's two test-revision rules, applied manually or with an LLM plus a human, to the frontend coupling problem we hit (asserts on exact query shapes and test IDs). The equivalent of FeatureBench's interface-in-prompt approach is to put the contract (the GraphQL schema diff, and the required test IDs and component names) in the task statement.
- Flakiness is underspecified across the field. A practical default, which is my inference and not from these sources: run base and reference each k≥3 times, keep only tests with stable outcomes, and adopt Multi-SWE-bench's transition rules.
- Expect environment build success of roughly 60–78% per repo with RepoLaunch-class tooling. For a two-repo task, if failures were independent, joint success would be about 0.5–0.6. WideSWE's 635 → 240 runnable (38%) is consistent with that and somewhat worse.

### Gaps
- None of the sources describe flaky-test handling for cross-repo benchmarks.
- How WideSWE builds its Docker environments is not described in the part of the paper I read.
- I found no 2026 benchmark explicitly framed as "monorepo-of-repos" or as microservice cross-service changes, other than WideSWE, CrossSWE and the Microsoft migration paper.

## 3. Practical mining signals (GitHub API, GH Archive, references, bots)

### Takeaway
The highest-precision structured signal is the GraphQL timeline item `CrossReferencedEvent` with `isCrossRepository: true`. It gives source and target issue/PR, `referencedAt`, and `willCloseTarget`. Pair it with time windows on merge dates and with REST/GraphQL search qualifiers (`is:pr is:merged merged:>=`, `org:`, `in:body`, `-author:app/...`). GH Archive on BigQuery has PR and comment events with bodies, so you can regex `owner/repo#N` and full PR URLs at scale. The cost is about $6.25/TiB scanned after a 1 TiB free tier, and LIMIT does not reduce scan cost.

### Cited Findings
- **GraphQL `CrossReferencedEvent` fields** — [GitHub GraphQL docs, Issues reference](https://docs.github.com/en/graphql/reference/issues):
  - `isCrossRepository` (Boolean!): "Reference originated in a different repository."
  - `source` (ReferencedSubject!): "Issue or pull request that made the reference."
  - `target` (ReferencedSubject!): "Issue or pull request to which the reference was made."
  - `referencedAt` (DateTime!): "Identifies when the reference was made."
  - `willCloseTarget` (Boolean!): "Checks if the target will be closed when the source is merged."
  - Plus `actor`, `createdAt`, `url`, `resourcePath`.
  - Use it with `timelineItems(itemTypes: [CROSS_REFERENCED_EVENT, CONNECTED_EVENT])`. CROSS_REFERENCED_EVENT "Represents a mention made by one issue or pull request to another"; CONNECTED_EVENT "Represents a connected event on a given issue or pull request."
- **Search qualifiers** — [GitHub Docs: Searching issues and pull requests](https://docs.github.com/en/search-github/searching-on-github/searching-issues-and-pull-requests):
  - `is:pr`, `is:merged`, `merged:>=YYYY-MM-DD` (and ranges).
  - `org:ORGNAME`, `repo:OWNER/REPO`, `in:body`, `label:`.
  - `linked:pr` / `linked:issue`: links by closing reference only, within GitHub's closing-keyword semantics.
  - `-author:app/NAME` to exclude integration (bot) accounts.
  - Users with PR access to more than 10,000 repos must scope searches to an org, user or repo.
- **GH Archive**
  - Event payloads include PullRequestEvent (action opened/closed/reopened, number) and IssueCommentEvent. — [GitHub event types](https://docs.github.com/en/enterprise-server@3.18/rest/using-the-rest-api/github-event-types)
  - BigQuery query patterns filter on `type` and `repo.name` and use `JSON_EXTRACT_SCALAR(payload, ...)`. Third-party guidance says LIMIT does not reduce cost on these unclustered tables, recommends dry runs, and gives $6.25/TiB after the 1 TiB free tier. — [third-party github-archive skill](https://tessl.io/registry/skills/github/gadievron/raptor/github-archive) (secondary source)
- **How the 2026 benchmarks used these signals**
  - WideSWE used explicit cross-repo references between same-ecosystem repos, restricted to orgs (ecosystems) from Gitstar Ranking top 200. — [WideSWE](https://arxiv.org/html/2609.33382v1)
  - CrossSWE added semantic cues (API evolution, dependency migration, provider–consumer, client–server) and release/compatibility discussions to explicit references. — [CrossSWE](https://arxiv.org/html/2611.01484)
- **Older text-mining precedent:** Gousios et al. (MSR 2014) note that PRs link to related PRs. — [PDF](https://azaidman.github.io/publications/gousiosMSR2014a.pdf)
- **Most links are not "fixes":** in the FSE 2024 study only 12.11% were. Expect many cross-references to be incidental mentions. — [FSE 2024](https://cs.ubc.ca/~bestchai/papers/fse24-pr-issue-graphs.pdf)
- **Incidental references are the main false positive:** WideSWE's manual stage explicitly rejected "incidental citation". — [WideSWE](https://arxiv.org/html/2609.33382v1)

### Inferences
These are proposed mining recipes, synthesized from the sources above but not themselves sourced.
- **Stage A (candidate pairs).** For each org or ecosystem, page through merged PRs in a window with GraphQL and pull `timelineItems(CROSS_REFERENCED_EVENT)` where `isCrossRepository` is true and source and target are both PRs (or PR → issue → PR). Keep pairs whose merge times fall within about 30–45 days of each other. The Saleor example spans 10–27 Aug.
- **Stage A at scale.** In GH Archive, select PullRequestEvent and IssueCommentEvent bodies matching `([\w.-]+/[\w.-]+)#\d+` or `github.com/[^/]+/[^/]+/pull/\d+` where the referenced repo differs from `repo.name`. Join on merge timestamps.
- **Stage B (intent keywords).** Rank by keywords in title or body: "companion PR", "depends on", "requires", "frontend PR", "backend PR", "dashboard PR", "core PR", "follow-up to", "counterpart", "paired with". Rank also by labels such as `needs-backend` or `requires-core`, by shared feature-flag or schema names, and by the same author on both sides.
- **Bot and codegen filters**
  - `-author:app/*` and `actor.login` ending in `[bot]` (dependabot, renovate, github-actions).
  - Drop PRs whose diff touches only generated paths (`*/generated/*`, `*.pb.go`, `openapi*`, `sdk/*`, lockfiles, schema snapshot files), or only version bumps or changelogs.
  - Drop titles matching "Bump", "Update dependency", "Regenerate", "Sync".
  - Require ≥1 hand-written test change and ≥N non-generated source lines in each repo.
  - Keep a schema copy as the contract but don't count it as the feature. For example, the Saleor dashboard's `schema.graphql` copy, and a codegen'd `types.generated.ts`, should be stripped from the hidden reference and regenerated by the task harness.
- **Release-note levels.** Match "Added"/"Features" sections of releases in both repos within the window, as SWE-EVO does with release notes, to raise precision on feature (not fix) groups.

### Gaps
- I did not verify the official GH Archive BigQuery schema (exact payload JSON paths, and whether PullRequestEvent payload bodies are trimmed in recent years).
- I found no source documenting GraphQL rate-limit costs for `timelineItems` at scale.
- I found no published classifier for bot or codegen companion PRs.

## 4. Feasibility filters: environments, F2P, flakiness, test coupling, contamination

### Takeaway
Plan for about 40% runnability among manually validated cross-repo groups (WideSWE 240/635), and for about 80% of runnable groups having F2P tests in every target repo (192/240). Expect a large share to need test relaxation (88 of 120 in WideSWE). For contamination, the field relies mostly on recency and continuous refresh (SWE-bench-Live, SWE-rebench, FeatureBench). The main published detection probe is "SWE-Bench Illusion" file-path identification.

### Cited Findings
- **WideSWE survival rates:** 635 manually valid → 240 runnable → 192 with F2P in every target → 120 final (after balancing). — [WideSWE](https://arxiv.org/html/2609.33382v1)
- **Environment automation:** RepoLaunch build success is about 70–78%, lower for JS/TS (about 69%) and Go (about 60%) per a third-party table. — [RepoLaunch](https://arxiv.org/html/2603.05026v1); [summary](https://neapolitanicecream.github.io/recoleta/en/items/software-intelligence--2026-03-05--repolaunch-automating-build-test-pipeline-of-code-repositories-on-any-language-and-any-platform.html)
  - FeatureBench shows the semi-manual alternative: about 3 minutes of human install config per repo. — [FeatureBench](https://arxiv.org/html/2602.10975v1)
- **F2P/P2P extraction**
  - Multi-SWE-bench runs the full suite three ways and keeps only clean FAILED→PASSED transitions, discarding PASSED→FAILED and ambiguous cases. — [Multi-SWE-bench](https://arxiv.org/html/2504.02605)
  - CrossSWE adds the 2^N partial-application check. — [CrossSWE](https://arxiv.org/html/2611.01484)
- **Test coupling**
  - WideSWE relaxes implementation-specific constraints and removes checks for unrequested functionality, in 88 tasks. — [WideSWE](https://arxiv.org/html/2609.33382v1)
  - FeatureBench specifies interfaces (signatures, import paths) in the prompt. — [FeatureBench](https://arxiv.org/html/2602.10975v1)
  - CrossSWE avoids prescribing names, fields or paths in the prompt; its tests check cross-repo behavior. — [CrossSWE](https://arxiv.org/html/2611.01484)
- **Contamination and memorization**
  - "The SWE-Bench Illusion" (Liang, Garg, Zilouchian Moghaddam, arXiv 2506.12286, 2025): models identify the buggy file path from the issue text alone with up to 76% accuracy on SWE-bench Verified, against up to 53% on other repos. It also proposes function-reproduction (verbatim similarity) and prefix-completion probes. — [arXiv](https://arxiv.org/html/2506.12286v1)
  - Microsoft BC-Bench implements the file-path probe, noting that "exact_hit" is the stronger signal and "basename_hit" is inflated by naming conventions. — [BC-Bench](https://microsoft.github.io/BC-Bench/contamination-file-path-identification.html)
  - SWE-rebench reports that some models' SWE-bench Verified scores may be inflated by contamination, compared with fresh tasks. — [SWE-rebench](https://arxiv.org/abs/2505.20411)
  - Recency windows: SWE-bench-Live uses issues since 2024 ([arXiv](https://arxiv.org/abs/2505.23419)). FeatureBench uses tests first committed after May 2022 and finds pass rate tracks code length more than date ([FeatureBench](https://arxiv.org/html/2602.10975v1)). WideSWE requires the latest PR merged on or after 1 Jun 2025 and uses temporal snapshotting of context repos ([WideSWE](https://arxiv.org/html/2609.33382v1)).
- **Anti-cheating for live environments:** FeatureBench uses a URL blacklist and log scans for attempts to read installed package source. — [FeatureBench](https://arxiv.org/html/2602.10975v1)
  - This matters for us because an agent with network access could fetch the upstream dashboard PR directly.

### Inferences
- Contamination controls for our recipe:
  1. Use features merged after the target models' training cutoffs. Several 2026 frontier cutoffs fall in the first half of 2026, so the Saleor Aug 2026 example qualifies.
  2. Block github.com and package registries, or pin a mirror at the base commits.
  3. Run a cross-repo analogue of the file-path probe: give only the task text and ask the model to name the files or PR numbers in the second repo. A high exact-hit rate signals memorization.
- Anything mined from WideSWE or CrossSWE repos (top-star orgs, 2024–2026) is now public as benchmark data. Deduplicate against their instance lists to avoid overlap and test-set leakage into labs' training.

### Gaps
- I found no published measurement of flaky-test rates in cross-repo or frontend (Jest/Playwright) test suites in these benchmarks.
- I found no published contamination probe designed for cross-repo tasks.

## 5. Licensing for commercial use of public repos in a training environment

### Takeaway
I found no court ruling on whether training on, or redistributing, open-source code in an RL environment triggers copyleft. The benchmarks mostly preserve upstream licenses per repo and license their own non-code material separately. CrossSWE uses CC BY 4.0 for its own materials, keeps upstream licenses for third-party code, and reviewed all 165 repo licenses. Source-available licenses (FSL, ELv2, BSL) restrict *competing or hosted commercial use* rather than redistribution for evaluation. That is a separate risk axis from GPL/AGPL copyleft.

### Cited Findings
- **CrossSWE** reviewed the upstream licenses of all 165 repos, released its own materials under CC BY 4.0 with third-party code under upstream licenses, and notes that MUI X docs permit qualifying non-production benchmark use. — [CrossSWE](https://arxiv.org/html/2611.01484)
- **WideSWE** says its artifact preserves licenses and attribution, and that it includes agent patches "only where licensing permits". — [WideSWE](https://arxiv.org/html/2609.33382v1)
- **FSL (Functional Source License, Sentry)**
  - Grants use for any "Permitted Purpose", meaning anything other than a "Competing Use". Competing Use covers offering the software in a commercial product or service that substitutes for it.
  - Converts to Apache-2.0 or MIT after two years (the "ALv2 Future License" variant). — [SPDX FSL-1.1-ALv2](https://spdx.org/licenses/FSL-1.1-ALv2.html); [Sentry blog](https://blog.sentry.io/introducing-the-functional-source-license-freedom-without-free-riding/)
  - The two-year conversion detail comes from my background knowledge of the license template; SPDX was not fully read.
- **Elastic License 2.0** prohibits providing the software as a managed or hosted service. Elastic added AGPLv3 as an option in Aug 2024. — [FOSSA guide](https://fossa.com/blog/comprehensive-guide-source-available-software-licenses/); [FOSSA roundup](https://fossa.com/blog/fall-2024-software-licensing-roundup/)
- **Katzy et al.**, "An Exploratory Investigation into Code License Infringements in Large Language Model Training Datasets" (arXiv 2403.15230, 2024): every LLM code dataset examined contained license inconsistencies; it found 38M exact duplicates of strong-copyleft files. The total count is 514M files per the paper and 527M per a review. — [arXiv](https://arxiv.org/html/2403.15230v1)
- **Law-firm commentary** (Knobbe Martens, Legaltech News, 2025): certain uses of freely available training data may be restricted by license. Until courts settle the question, it is less risky to avoid training data under such licenses. — [Knobbe PDF](https://www.knobbe.com/wp-content/uploads/2025/04/Legaltech-News-Open-Source-Licensing.pdf)
- **Commentary on GPL propagation** says the theory that GPL propagates from source code to AI models is "not as widely accepted" as in 2021 debates, and that results vary by country. — [dev.to commentary](https://dev.to/greygoose/gpl-ai-models-navigating-license-propagation-161c) (low-authority source)

### Inferences
- Saleor core and saleor-dashboard are BSD-3-Clause (from prior notes / repo; not re-verified here), which is low risk.
- Selling an environment means *distributing* the repo snapshot (Docker images) to labs. Distribution itself is fine under MIT/BSD/Apache, given notice preservation and Apache NOTICE files. Under GPL it requires providing source, which is trivially satisfied since the source is in the image, plus keeping the license. AGPL adds obligations only if the software is modified and offered to users over a network. Whether a lab's hosted RL rollout counts is unsettled, so treat it as medium risk.
- FSL, BSL and ELv2 are the bigger commercial risk. The question is whether selling an environment that runs the software counts as a "competing" or "hosted" offering. Prefer excluding them, or getting written permission. Note that FSL/BSL code converts to OSS after its change date, so older snapshots may be clean.
- Keep a per-repo SPDX manifest in each task. Mirror CrossSWE: own materials under a permissive license, upstream code under upstream licenses. Tests and gold patches are upstream code, so they carry upstream licenses too.

### Gaps
- I found no legal commentary specific to RL environments or benchmarks sold commercially to labs.
- I did not fetch the full FSL, ELv2 or BSL texts. The exact "Competing Use" wording should be checked against the official templates (fsl.software, elastic.co) and reviewed by counsel.
- I did not verify current licenses for specific candidate repos in this pass.

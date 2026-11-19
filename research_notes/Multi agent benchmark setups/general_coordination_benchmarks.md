# Multi-agent LLM benchmarks outside software engineering (state of the field to November 2026)

Reading notes for the report writer:

- Research date: 2026-11-12. Publication month is taken from the arXiv identifier (YYMM) unless a venue is given. "Preprint" means no peer-reviewed venue was confirmed in this session.
- Almost every entry was read from the arXiv HTML full text through an automated fetch that reads only the first ~100,000 characters of a page. Appendices were usually not read. Where a detail was absent from the part read, it is marked "not stated (in the part read)".
- Numbers are reproduced as the source gives them. Where a paper contradicts itself, both figures are given.
- Already covered in earlier research and deliberately not re-described here: HiddenBench, the MAST taxonomy (arXiv 2503.13657), Kim et al. (arXiv 2512.08296), "Collaboration Tax" (arXiv 2608.22152), the Oxford conventions study (arXiv 2611.06409), MARSHAL (arXiv 2510.15414).

## Key question 1: Per-benchmark setup catalogue (tasks, agent count, roles, information, communication, baselines, scoring, headline results)

### Takeaway
About 50 benchmarks were checked. Most fix the team at 2 agents or a small game-defined number, prescribe roles, and compare models against each other; only a minority include a single-agent-with-all-information baseline, a no-communication team, or a human team, and almost none equalise budget between team and solo.

### Cited Findings

#### A. General collaboration / "agent team" benchmarks

**MultiAgentBench / MARBLE** (arXiv Mar 2025; ACL 2025 main, long paper)
- Venue: ACL 2025 long paper, pp. 8580–8622 — [ACL Anthology](https://aclanthology.org/2025.acl-long.421)
- Tasks: six scenarios: research co-authoring, Minecraft building, database error analysis, coding, bargaining, Werewolf; "100 test cases per task" for task-oriented scenarios; research set is 33 easy / 34 medium / 33 hard — [arXiv 2503.01935](https://arxiv.org/html/2503.01935)
- Agents: database analysis "involves exactly five agents"; research ablation varies 1, 3, 5, 7 agents; counts for other scenarios not stated in the part read — [arXiv 2503.01935](https://arxiv.org/html/2503.01935)
- Roles: prescribed per scenario (Werewolf: wolf, villager, seer, witch, guard; research agents get profiles built from author publication histories) — [arXiv 2503.01935](https://arxiv.org/html/2503.01935)
- Information: private in Werewolf (private event log, werewolves know allies); other scenarios not stated — [arXiv 2503.01935](https://arxiv.org/html/2503.01935)
- Communication: free text; coordination topologies star, chain, tree, graph; max 5 communication iterations; communication is scored (Communication Score on a five-point scale, 0 if no communication) — [arXiv 2503.01935](https://arxiv.org/html/2503.01935)
- Baselines: no single-agent baseline as such (1 agent appears only in the agent-count ablation), no no-communication baseline, no human performance baseline; five models compared (Llama-3.1-8B, Llama-3.1-70B, Llama-3.3-70B, gpt-3.5-turbo, gpt-4o-mini) — [arXiv 2503.01935](https://arxiv.org/html/2503.01935)
- Scoring: milestone KPI = 1/(N·M) Σ n_j; Task Score (rubric or rule based); Coordination Score = mean of Communication and Planning scores — [arXiv 2503.01935](https://arxiv.org/html/2503.01935)
- Results: gpt-4o-mini "reaches the average highest task score"; graph topology best in research, tree worst; cognitive planning improves milestone achievement by 3%; group discussion scored worst on all metrics; overall KPI decreases as agent count rises while coordination score improves from 1 to 3 agents; in Minecraft scores rise from 1 to 7 iterations then drop at 10 — [arXiv 2503.01935](https://arxiv.org/html/2503.01935)

**AgentVerse evaluation tasks** (arXiv Aug 2023)
- Tasks: FED (dialogue), Commongen-Challenge, MGSM, Logic Grid Puzzles, HumanEval, 10 custom multi-tool tasks, Minecraft crafting — [arXiv 2308.10848](https://ar5iv.labs.arxiv.org/html/2308.10848)
- Agents: predefined per task: 4 for dialogue/coding/constrained generation, 2 for math ("more reviewers led to more erroneous critiques"), 2 or 3 for tool use, 3 in the Minecraft example — [arXiv 2308.10848](https://ar5iv.labs.arxiv.org/html/2308.10848)
- Roles: a recruiter agent generates expert descriptions; vertical (solver plus reviewers) or horizontal (democratic) communication — [arXiv 2308.10848](https://ar5iv.labs.arxiv.org/html/2308.10848)
- Baselines: CoT single agent; "Solo" (one agent run through the full pipeline); single ReAct agent for tool use — [arXiv 2308.10848](https://ar5iv.labs.arxiv.org/html/2308.10848)
- Results (GPT-3.5 / GPT-4): MGSM CoT 80.4 / 95.2, Solo 82.4 / 96.0, Group 80.8 / 95.2; Commongen Solo 93.6 / 99.0, Group 92.3 / 99.1; Logic Grid (GPT-4) CoT 59.5, Solo 64.0, Group 66.5; tool use 9 of 10 tasks vs 3 for single ReAct. With GPT-3.5 the group is below Solo on Commongen and MGSM; roughly 10% of MGSM errors came from agents being swayed by incorrect peer feedback — [arXiv 2308.10848](https://ar5iv.labs.arxiv.org/html/2308.10848)

**AgentWorld** (arXiv Sep 2026; accepted at COLM 2026)
- Tasks: Kaetram-based MMORPG sandbox turned turn-based; 8 task categories (combat, crafting, gathering, trading, exploration, survival, construction, coordination); 100 human-annotated tasks plus 100 LLM-augmented variants; round budget per task 25–55, average 38 (the abstract says "50+ interaction rounds") — [arXiv 2609.31590](https://arxiv.org/html/2609.31590v1)
- Agents: 3–20 per task, fixed by the task; 45 tasks use 3 agents — [arXiv 2609.31590](https://arxiv.org/html/2609.31590v1)
- Roles and information: asymmetric roles, skills, spawn points, items; "blackbox": agents cannot see others' internal states, observations or action histories — [arXiv 2609.31590](https://arxiv.org/html/2609.31590v1)
- Communication: explicit chat routed through the environment — [arXiv 2609.31590](https://arxiv.org/html/2609.31590v1)
- Baselines (Gemini 3 Flash, 35-task subset): random 5.7%, single agent 28.6%, no communication 22.9%, shared plan without communication 17.6%, vanilla multi-agent 52.0%, oracle communication 60.0%; whether budgets were equalised is not stated — [arXiv 2609.31590](https://arxiv.org/html/2609.31590v1)
- Scoring: binary success plus Causal Collaboration Effectiveness, CCE = |C| / |T| (contributing actions found by backward causal tracing, over all actions; failed tasks score 0; judged by GPT-4.1) — [arXiv 2609.31590](https://arxiv.org/html/2609.31590v1)
- Results (success / CCE): Gemini 3 Flash 52.0% / 0.320; Claude Haiku 4.5 45.0% / 0.294; GPT-5 Mini 36.0% / 0.206; DeepSeek R1-70B 20.0% / 0.125. Communication errors (61 errors): stale and redundant 37.7%, misidentification 16.4%, factual error 14.8%. Results by team size not stated — [arXiv 2609.31590](https://arxiv.org/html/2609.31590v1)

**EntCollabBench** (arXiv May 2026, preprint)
- Tasks: 300 enterprise tasks (160 workflow, 40 workflow multi-task, 80 approval, 20 approval multi-task) over IT, HR, customer service, shared services, engineering, finance, legal, procurement — [arXiv 2605.08761](https://arxiv.org/html/2605.08761v1)
- Agents and roles: 11 fixed role-specialised agents (8 operational, 3 approval) in six departments; permission isolation by tool scope and per-service identity tokens; isolated memory; context passes only through peer-to-peer delegation messages; multi-step tasks need at least three cross-agent delegations — [arXiv 2605.08761](https://arxiv.org/html/2605.08761v1)
- Baselines: no single all-in-one agent baseline found in the part read, despite the title — [arXiv 2605.08761](https://arxiv.org/html/2605.08761v1)
- Scoring: agent-level, subtask-level and task-level pass rates from traces and database state diffs; three-model majority vote judge — [arXiv 2605.08761](https://arxiv.org/html/2605.08761v1)
- Results: best overall DeepSeek-V4-Pro 62.00%, DeepSeek-V4-Flash 57.33%, Claude-Sonnet-4.6 52.67%; on multi-step workflow DeepSeek-V4-Pro reaches 78.33% subtask but 50.00% task accuracy; best multi-step approval 40.00% — [arXiv 2605.08761](https://arxiv.org/html/2605.08761v1)

**TeamBench** (arXiv May 2026, preprint; mostly software and data work, included because it is the clearest role-separation and team-versus-solo design)
- Tasks: 851 templates / 931 seeded instances; 650 adapted GitHub bug reports, 161 authored tasks, 30 data-science tasks, 10 incident-response tasks — [arXiv 2605.07073](https://arxiv.org/html/2605.07073)
- Agents and roles: Solo 1; Team variants 2; Full Team 3 (Planner reads full spec and cannot edit; Executor sees only a brief; Verifier reads spec and read-only workspace). Separation enforced by containers and bind mounts, not prompts. Communication through a shared messages directory — [arXiv 2605.07073](https://arxiv.org/html/2605.07073)
- Baselines: Solo, Restricted, Team-No-Plan, Team-No-Evaluate, Solo CoT, Solo 2Pass, 27 mixed-provider configurations, and a human study (40 sessions, 18 humans). Equal token or time budget for solo: not stated — [arXiv 2605.07073](https://arxiv.org/html/2605.07073)
- Scoring: binary pass, partial score, Teamwork Necessity Index, planning and verification value, verifier false-accept rate — [arXiv 2605.07073](https://arxiv.org/html/2605.07073)
- Results: Claude Opus 4.7 37.8% Full Team vs 35.6% Solo; team gain +20.0 for Sonnet 4.6, +16.7 for Haiku 4.5, −5.6 for Gemma 4 31B; mean uplift on the 155-task reference ablation +0.5 points (p=0.20); removing the Verifier raises mean partial score by 5.5 points; verifiers approve 49.4% of submissions that fail the grader; in the lowest Solo quintile Full Team beats Solo by 15.7 points; mixed-provider team 26.7% at $20.52 vs 22.7% at $39.58 all-Anthropic; in the human study hybrid teams self-attested 16/17 passes but the grader confirmed 4/17 — [arXiv 2605.07073](https://arxiv.org/html/2605.07073)

**ForestBench** (arXiv Aug 2026, preprint)
- 844 "collaboration-necessary" queries filtered from seven public datasets; six multi-agent frameworks evaluated; execution traces are mapped to collaboration graphs and compared against a per-query reference forest of ten successful reference graphs; scoring needs no further LLM inference. Abstract gives no quantitative results; full text not read — [arXiv 2608.08605](https://arxiv.org/abs/2608.08605)

**REALM-Bench** (arXiv Feb 2025, "under review")
- 14 planning and scheduling problems described on the page (P1–P10, J1–J4): campus tours, ride-sharing, wedding and Thanksgiving logistics, disaster relief, supply chain, job-shop scheduling. Tier 1 is single-agent static; tiers 2–5 are multi-agent. Scales along parallel planning threads, inter-dependency complexity and disruption frequency. Frameworks: LangGraph, AutoGen, CrewAI, Swarm (plus the authors' ALAS). Preliminary: single-agent static tasks 85–95% success, multi-agent dynamic 45–70% — [arXiv 2502.18836](https://arxiv.org/html/2502.18836)

**ARE / Gaia2** (arXiv Sep 2025, preprint)
- Gaia2 requires agents to "collaborate with other agents", handle ambiguity, noise and time constraints, and runs asynchronously; authors report budget-scaling curves plateau. Abstract has no team sizes or agent-to-agent numbers — [arXiv 2509.17158](https://arxiv.org/abs/2509.17158)

#### B. Information-asymmetry and distributed-information benchmarks

**InformativeBench (iAgents)** (arXiv Jun 2024, preprint)
- Tasks: five datasets: Needle in the Persona (100 QA), FriendsTV (222 QA), Schedule Easy / Medium / Hard (30 QA each) — [arXiv 2406.14928](https://arxiv.org/html/2406.14928)
- Agents: one agent per human user; social networks of 4 (NP, Schedule Easy), 6 (Schedule Medium/Hard), 140 individuals with 588 relationships (FriendsTV); each task involves two collaborating agents, which may open sub-conversations with others — [arXiv 2406.14928](https://arxiv.org/html/2406.14928)
- Information: each agent sees only its own user's information; needles are split across two individuals' dialogues; private schedules — [arXiv 2406.14928](https://arxiv.org/html/2406.14928)
- Communication: free text, maximum 10 turns in experiments — [arXiv 2406.14928](https://arxiv.org/html/2406.14928)
- Baselines: no single-agent-with-all-information baseline; only ablations of the authors' system — [arXiv 2406.14928](https://arxiv.org/html/2406.14928)
- Results: GPT-4 Easy 56.67%, Medium 51.00%, Hard 22.80%, NP 64.00%, FriendsTV 57.94% (abstract: "average accuracy of 50.48%"); GPT-3.5 36.67 / 18.00 / 12.25 / 51.00 / 35.71 — [arXiv 2406.14928](https://arxiv.org/html/2406.14928)

**COMMA** (arXiv Oct 2024, preprint; v5 Dec 2025)
- Tasks: 10 multimodal puzzles in 4 categories (memory recall, multimodal grounding, multi-step reasoning, private information), 100 initialisations each, 1,000 conversations — [arXiv 2410.07553](https://arxiv.org/html/2410.07553)
- Agents and roles: 2, fixed. Solver sees the puzzle image and acts; Expert holds the manual and sees no image. Private data (PIN, balance) held by the Solver — [arXiv 2410.07553](https://arxiv.org/html/2410.07553)
- Communication: free-text dialogue capped at 10 turns and 3 mistakes; conversation length and an efficiency score (harmonic mean of partial success and conciseness) are reported — [arXiv 2410.07553](https://arxiv.org/html/2410.07553)
- Baselines: random action baseline; human Solver with GPT-4o Expert; no single-agent setting — [arXiv 2410.07553](https://arxiv.org/html/2410.07553)
- Results (overall partial success): human 69.01%, o4-mini 53.98%, GPT-4o 41.74%, Gemini 2.0 33.37%, random 18.70%, R1-OneVision 16.81%, LLaVA-CoT 14.97%; some reasoning models are below random — [arXiv 2410.07553](https://arxiv.org/html/2410.07553)

**Silo-Bench** (arXiv Mar 2026; ACL 2026 long paper)
- Venue: ACL 2026 long papers — [ACL Anthology](https://aclanthology.org/2026.acl-long.1354/)
- Tasks: 30 algorithmic tasks, 10 per communication-complexity level (I aggregation, II mesh, III global shuffle) — [arXiv 2603.01045](https://arxiv.org/html/2603.01045v1)
- Agents: varied as a condition, N ∈ {2, 5, 10, 20, 50, 100}; role-agnostic; same model for all agents — [arXiv 2603.01045](https://arxiv.org/html/2603.01045v1)
- Information: the global input is split into roughly equal shards, one per agent; input grows with N so per-agent workload is constant — [arXiv 2603.01045](https://arxiv.org/html/2603.01045v1)
- Communication: three protocols as a condition: directed P2P, broadcast, shared file system; max 100 rounds; communication density and tokens are measured — [arXiv 2603.01045](https://arxiv.org/html/2603.01045v1)
- Baseline: a single agent (N=1) given the full input; Relative Coordination Cost RCC = 1 − SR(N=k)/SR(N=1) — [arXiv 2603.01045](https://arxiv.org/html/2603.01045v1)
- Results: average success DeepSeek-V3.1 36.9%, GPT-OSS-120B 16.9%, Qwen3 8.2%; DeepSeek-V3.1 by N: 61.2% (2), 48.5% (5), 39.9% (10), 33.6% (20), 19.0% (50), 18.1% (100); by level 62.0% / 35.1% / 11.7%; Level III at N≥50 is 0%; "Communication-Reasoning Gap": Level I partial correctness 88.0% vs success 62.0%; failure modes premature submission 37.2%, consensus failure 29.9%, computation error 28.6% — [arXiv 2603.01045](https://arxiv.org/html/2603.01045v1)

**AgentsNet** (arXiv Jul 2025, preprint)
- Tasks: five distributed-computing problems: (Δ+1)-colouring, minimal vertex cover, maximal matching, leader election, consensus — [arXiv 2507.08616](https://arxiv.org/html/2507.08616)
- Agents: graphs of 4, 8, 16 nodes (27 topologies: small-world, scale-free, geometric); scaling study 20–100 agents — [arXiv 2507.08616](https://arxiv.org/html/2507.08616)
- Information and communication: each agent knows only its own name and its neighbours; synchronous message passing to neighbours for a fixed number of rounds (2D+1 or 4/5/6) — [arXiv 2507.08616](https://arxiv.org/html/2507.08616)
- Baselines: cross-model only (10 models) — [arXiv 2507.08616](https://arxiv.org/html/2507.08616)
- Results (fraction fully solved): Gemini 2.5 Pro 0.80, Claude 3.7 Sonnet 0.70, Gemini 2.5 Flash 0.69, o4-mini 0.53, Claude 3.5 Haiku 0.26; performance falls to "near zero across the board" at 100 agents — [arXiv 2507.08616](https://arxiv.org/html/2507.08616)

**SOTOPIA-TOM** (arXiv May 2026, preprint)
- 160 human-reviewed scenarios over eight sectors; 3–5 agents with partitioned private knowledge and channel-dependent sharing policies; public broadcast and private direct-message channels; composite INFOMGMT score over sharing, seeking, coordinating efficiently, protecting privacy. GPT-5 reaches 62%; ToM-Coach on GPT-4o cuts critical privacy violations from 9.9% to 2.2% and raises the composite from 15% to 40% — [arXiv 2605.02307](https://arxiv.org/abs/2605.02307)

**MAGPIE** (arXiv Oct 2025; listed at NeurIPS 2025)
- 200 high-stakes multi-agent tasks where private information is necessary to resolve the task; measures leakage, consensus, task completion, manipulation. Gemini 2.5-Pro leaked up to 50.7% and GPT-5 up to 35.1% of sensitive information even when told not to; Gemini 2.5-Pro showed manipulation in 38.2% of cases — [arXiv 2510.15186](https://arxiv.org/abs/2510.15186); [NeurIPS 2025 listing](https://neurips.cc/virtual/2025/133156)

**Decrypto** (arXiv Jun 2025, preprint)
- Game: 3 fixed roles: Alice (encoder), Bob (decoder), Eve (interceptor); Alice and Bob share 4 secret keywords; up to 8 turns; Alice gives 3 one-word hints per turn; hint and code histories are public — [arXiv 2506.20664](https://arxiv.org/html/2506.20664)
- Baselines: GloVe and Word2Vec word-embedding agents; 10 human games; cross-play between different models and between baselines and LLMs — [arXiv 2506.20664](https://arxiv.org/html/2506.20664)
- Results: LLM play lags humans and the embedding baselines; baseline–LLM teams miscommunicate significantly more than same-type teams; on strong theory-of-mind variants all models score ≤10%; Llama 3.1-70B outperforms newer reasoning models on the three theory-of-mind tasks — [arXiv 2506.20664](https://arxiv.org/html/2506.20664)

#### C. Cooperative games: Overcooked, Hanabi

**Collab-Overcooked** (arXiv Feb 2025; v3 Sep 2025)
- Tasks: 30 sequential cooking tasks, 6 complexity levels, 5 per level — [arXiv 2502.20073](https://arxiv.org/html/2502.20073)
- Agents and roles: 2 fixed ("chef-and-assistant"); isolated action spaces and resources joined by a shared counter; only one agent knows the recipe — [arXiv 2502.20073](https://arxiv.org/html/2502.20073)
- Communication: natural language, round-limited; scored indirectly through Initiating Capability and Responding Capability (share of requests/responses that advance progress) — [arXiv 2502.20073](https://arxiv.org/html/2502.20073)
- Baselines: 13 LLMs; 10 human participants; no single-agent or no-communication baseline — [arXiv 2502.20073](https://arxiv.org/html/2502.20073)
- Scoring: success rate, progress completeness, trajectory efficiency score (TES) and incremental TES — [arXiv 2502.20073](https://arxiv.org/html/2502.20073)
- Results: Claude Sonnet 4 100.00 at Level 1 and 58.00 at Level 6; GPT-4o 2.00 at Level 5; humans stay high across levels; for most 14B+ models responding capability exceeds initiating capability — [arXiv 2502.20073](https://arxiv.org/html/2502.20073)

**LLM-Coordination benchmark** (arXiv Oct 2023; v3 Apr 2025)
- Tasks: Hanabi, Overcooked-AI, Collab Capture, Collab Escape, plus CoordinationQA (198 multiple-choice questions on environment comprehension, theory of mind, joint planning) — [arXiv 2310.03903](https://arxiv.org/html/2310.03903)
- Agents: 2 fixed; no prescribed roles; Hanabi hides own cards, Overcooked fully observable; Hanabi communication only via clue actions — [arXiv 2310.03903](https://arxiv.org/html/2310.03903)
- Baselines: MARL self-play (PPO, PBT; BAD, SAD, OBL), cross-play with behaviour-cloned human proxies and OBL partners, greedy and random; no human or single-agent baseline — [arXiv 2310.03903](https://arxiv.org/html/2310.03903)
- Results: GPT-4-turbo best in 3 of 5 Overcooked layouts; Hanabi 13.33 ± 0.88 vs 23.92–24.10 for MARL self-play; in cross-play with OBL-1 GPT-4-turbo 15.00 vs SAD 11.33; GPT-4-turbo over 80% on environment comprehension, best joint planning "less than 40%" — [arXiv 2310.03903](https://arxiv.org/html/2310.03903)

**Overcooked-AI with LLM agents: ProAgent** (arXiv Aug 2023; AAAI 2024)
- Zero-shot coordination with unseen AI partners and human proxy models in Overcooked-AI; outperforms "five methods based on self-play and population-based training"; with human proxies "average improvement exceeding 10%" — [arXiv 2308.11339](https://arxiv.org/abs/2308.11339)
- VillagerAgent reports Overcooked-AI scores of 213.3 / 304 / 226.7 / 120 / 148 on five layouts vs ProAgent 197.3 / 228.7 / 175.3 / 49.7 / 126.3 — [arXiv 2406.05720](https://arxiv.org/html/2406.05720)

**Hanabi with LLMs: "Sparks of Cooperative Reasoning"** (arXiv Jan 2026; v3 Aug 2026)
- Setup: 2–5 players, each seat an independent instance of the same LLM; 17 LLMs; 10 games per player count; three prompt settings (Watson minimal, Sherlock with engine-provided deductions, Mycroft with self-maintained working memory) — [arXiv 2601.18077](https://arxiv.org/html/2601.18077)
- Results: best models about 15/25; Grok-3-mini 18.0 with 3 players under Sherlock; human experts above 20/25; cross-play (Grok 3 Mini 14.9 with o4-mini 11.3) lands between the two self-play scores, about +1.7 points per stronger player added; releases HanabiLogs (1,520 trajectories) and HanabiRewards (560 games) — [arXiv 2601.18077](https://arxiv.org/html/2601.18077)

**AH2AC2 (Ad-Hoc Human-AI Coordination Challenge)** (ICML 2025)
- Setup: 2- and 3-player Hanabi with hosted human-proxy partners trained on 147,621 hanab.live games; 3,079 games open-sourced; 1,000 games per setting against proxies — [arXiv 2506.21490](https://arxiv.org/html/2506.21490v2)
- Results (mean score with proxies): 2-player: human proxies 22.76, OBL 21.04, BR-BC 19.41, DeepSeek-R1 with H-Group conventions 9.91, DeepSeek-R1 5.43; 3-player: human proxies 20.86, DeepSeek-R1 H-Group 14.62, DeepSeek-R1 14.38, HDR-IPPO 14.03. DeepSeek-R1 was run on only 100 games — [arXiv 2506.21490](https://arxiv.org/html/2506.21490v2)

**SPIN-Bench** (arXiv Mar 2025; v5 Oct 2025)
- Tasks: PDDL planning (21 domains, 1,280 tasks), Tic-tac-toe, Connect Four, Chess, Hanabi (2–5 players), Diplomacy (4- and 6-agent settings, public and private messages) — [arXiv 2503.12349](https://arxiv.org/html/2503.12349)
- Baselines: solvers (minimax, Stockfish), about 54,977 human Hanabi games — [arXiv 2503.12349](https://arxiv.org/html/2503.12349)
- Results: o1 Hanabi average falls from 16.4 (2 players) to 14.2 (5 players); no LLM approaches the first human quartile; o1's Diplomacy order success and supply centres drop when negotiation is enabled, DeepSeek-R1 not significantly affected — [arXiv 2503.12349](https://arxiv.org/html/2503.12349)

**LLMArena** (arXiv Feb 2024, preprint)
- Seven environments: TicTacToe, ConnectFour, Texas Hold'em, Undercover (5 agents: 4 GPT-3.5 plus 1 evaluated), Bargain, Bid, Hanabi (2 cooperating); TrueSkill, win rate, reward; 14 LLMs; humans beat every LLM in ConnectFour; LLMs weakest at "opponent modeling and team collaboration" — [arXiv 2402.16499](https://arxiv.org/html/2402.16499)

#### D. Embodied and Minecraft cooperation

**CoELA on C-WAH and TDW-MAT** (arXiv Jul 2023)
- Tasks: C-WAH five household task types (10-episode test set, 250-step limit); TDW-MAT food and stuff transport (12 episodes, 3000-frame limit) — [arXiv 2307.02485](https://ar5iv.labs.arxiv.org/html/2307.02485)
- Agents: 2, same goal, no distinct roles; decentralised partial observation; communication is costly (a message takes one step, up to 500 characters) — [arXiv 2307.02485](https://ar5iv.labs.arxiv.org/html/2307.02485)
- Baselines: planner alone (single agent), planner + planner, planner + LLM, LLM + LLM; human trials with 8 subjects — [arXiv 2307.02485](https://ar5iv.labs.arxiv.org/html/2307.02485)
- Results: C-WAH symbolic: single 111 steps; planner pair 75 (33% efficiency improvement); LLM pair 57 (49%). TDW-MAT transport rate single 0.53; planner pair 0.79; LLM pair 0.86. Human trust 6.3 with communication vs 4.7 without (p = 0.0003) — [arXiv 2307.02485](https://ar5iv.labs.arxiv.org/html/2307.02485)

**PARTNR** (arXiv Oct 2024)
- Tasks: 100,000 natural-language household tasks in 60 houses with 5,819 objects; constraint-free, spatial, temporal, heterogeneous — [arXiv 2411.00081](https://arxiv.org/html/2411.00081)
- Agents: 2 (human and robot); heterogeneous tasks need human-only actions; partial or full observability; no explicit message channel described — [arXiv 2411.00081](https://arxiv.org/html/2411.00081)
- Baselines: single-agent ReAct, centralised vs decentralised planners, human solo, human pairs, human + LLM — [arXiv 2411.00081](https://arxiv.org/html/2411.00081)
- Results: single-agent ReAct 2519.02 steps, success 0.73; decentralised two-agent ReAct 3295.20 steps, success 0.73 (about 1.3x the steps); humans 0.93 success solo and paired, two humans 2369.55 steps vs 3046.99 solo; Human-ReAct 0.91 success and 4267.71 steps; LLM-paired teams need about 1.5x the steps of two humans and 1.1x a single human — [arXiv 2411.00081](https://arxiv.org/html/2411.00081)

**RoCoBench** (arXiv Jul 2023)
- Tasks: 6 tabletop tasks; 2 or 3 robots; capability asymmetry by reach and tool; three tasks with shared and three with asymmetric observations; one dialogue round per environment step — [arXiv 2307.04738](https://ar5iv.labs.arxiv.org/html/2307.04738)
- Baseline: "Central Plan" oracle with full observations planning for all robots — [arXiv 2307.04738](https://ar5iv.labs.arxiv.org/html/2307.04738)
- Results (dialogue vs central plan success): Pack Grocery 0.44 vs 0.82; Arrange Cabinet 0.75 vs 0.90; Sweep Floor 0.95 vs 1.00; Make Sandwich 0.80 vs 0.96; Sort Cubes 0.93 vs 0.70; Move Rope 0.65 vs 0.50 — [arXiv 2307.04738](https://ar5iv.labs.arxiv.org/html/2307.04738)

**CuisineWorld / MindAgent** (arXiv Sep 2023)
- Tasks: 12 levels, 33 dishes; 2–4 agents varied; a single centralised LLM dispatcher commands all agents (no inter-agent communication) — [arXiv 2309.09971](https://ar5iv.labs.arxiv.org/html/2309.09971)
- Scoring: Collaboration Score CoS = (1/M) Σ completed / (completed + failed) over M task-interval conditions — [arXiv 2309.09971](https://ar5iv.labs.arxiv.org/html/2309.09971)
- Results: GPT-4 average CoS 0.673 (2 agents), 0.694 (3), 0.692 (4); in a 12-subject human study agent count had no significant effect on success and more agents reduced enjoyment — [arXiv 2309.09971](https://ar5iv.labs.arxiv.org/html/2309.09971)

**VillagerBench** (arXiv Jun 2024, preprint)
- Tasks: Minecraft construction (100), farm-to-table cooking (100), escape room (25) — [arXiv 2406.05720](https://arxiv.org/html/2406.05720)
- Agents: 2 by default, 3 for GPT-4 runs, 1/2/4/8 in the agent-count test; centralised controller assigns subtasks; no peer messaging — [arXiv 2406.05720](https://arxiv.org/html/2406.05720)
- Scoring: completion, efficiency, balance (workload distribution), agent contribution rate — [arXiv 2406.05720](https://arxiv.org/html/2406.05720)
- Results: cooking average 29.75 AgentVerse vs 73.75 VillagerAgent (2 agents) and 85.26 (3 agents); construction Task 64 scores 35.25 / 41.67 / 46.67 / 30.21 for 1 / 2 / 4 / 8 agents; Task 0 100 for 1, 2, 4 agents and 66.63 for 8; same-ability trios 56.67 vs diverse-ability trios 36.67 on Task 99 — [arXiv 2406.05720](https://arxiv.org/html/2406.05720)

**TeamCraft** (arXiv Dec 2024, preprint)
- Tasks: Minecraft building, clearing, farming, smelting; "55,000 task variants"; multimodal — [arXiv 2412.05255](https://arxiv.org/html/2412.05255)
- Agents: 2 or 3 in training, 4 held out for generalisation; different inventories; centralised (all views) vs decentralised (own view only); no explicit communication — [arXiv 2412.05255](https://arxiv.org/html/2412.05255)
- Results: centralised "significantly better" than decentralised; redundancy rate 0.01 vs 0.15; four-agent split 0.02 task success for building; GPT-4o 0.00 on building and clearing — [arXiv 2412.05255](https://arxiv.org/html/2412.05255)

**MineCollab (MINDcraft)** (arXiv Apr 2025, preprint)
- Tasks: cooking, crafting, construction in Minecraft; 2–5 agents; agents hold different resources or partial recipes — [arXiv 2504.17950](https://arxiv.org/html/2504.17950)
- Results: "agent performance dropping as much as 15% when they are required to communicate detailed task completion plans"; cooking and crafting success falls "from upto 90% down to less than 30%" from 2 to 5 agents; Claude 3.5 Sonnet 0.47 crafting, 0.64 cooking, 0.36 construction — [arXiv 2504.17950](https://arxiv.org/html/2504.17950)

**BattleAgentBench** (arXiv Aug 2024, preprint)
- Tasks: Battle City tank game, 7 stages in 3 levels: single agent (1), two agents cooperative or competitive (2), four or more agents in teams (level 3; Stage 7 is given as 8 agents in 4 teams in the text and 6 agents in 3 teams in Table 6) — [arXiv 2408.15971](https://arxiv.org/html/2408.15971)
- Communication: cooperation request / accept interface; ablation removes it. Partners and opponents run a fixed reference model (yi-1.5-9b) — [arXiv 2408.15971](https://arxiv.org/html/2408.15971)
- Results: Claude 3.5 Sonnet Level 3 average 7.2, gpt-4o-mini 4.1; removing the cooperation interface lowers Claude to 4.9 but most other models score higher without it — [arXiv 2408.15971](https://arxiv.org/html/2408.15971)

**CREW-Wildfire** (arXiv Jul 2025, preprint)
- 12 levels of wildfire response with heterogeneous firefighters, bulldozers, drones, helicopters; benchmark levels use at most 15 agents (engine supports "2000+"); partial observability; frameworks CAMON, COELA, Embodied, HMAS-2 on GPT-4o. On Suppress Fire and Full Environment all frameworks do poorly, often below a Do-Nothing baseline — [arXiv 2507.05178](https://arxiv.org/html/2507.05178)

#### E. Competitive, mixed-motive and game-theoretic benchmarks

**GAMA-Bench** (arXiv Mar 2024; v7 Mar 2025)
- Eight games: Guess 2/3 of the Average, El Farol Bar, Divide the Dollar, Public Goods, Diner's Dilemma, Sealed-Bid Auction, Battle Royale, Pirate Game; ten agents by default, all the same model; no communication; scored 0–100 against Nash or optimal play; Gemini-1.5-Pro 69.8, GPT-4o 66.7, LLaMA-3.1-70B 65.9; GPT-3.5 45.9 rising to 57.9 with CoT — [arXiv 2403.11807](https://arxiv.org/html/2403.11807)

**GameBench** (arXiv Jun 2024, preprint)
- Nine board, card and social-deduction games (including Codenames, Pit, Two Rooms and a Boom); matches between two agent types with team seats duplicated; Bradley–Terry ratings; human 1.76, GPT-4-CoT 0.16, random −0.50, GPT-4 without scaffolding −0.89 — [arXiv 2406.06613](https://arxiv.org/html/2406.06613)

**SmartPlay** (arXiv Oct 2023)
- Six games (Bandits, Rock Paper Scissors, Tower of Hanoi, Messenger, Crafter, Minecraft); every game is a single LLM agent against the environment or a scripted opponent, so it is not a multi-agent benchmark — [arXiv 2310.01557](https://ar5iv.labs.arxiv.org/html/2310.01557)

**GTBench** (arXiv Feb 2024)
- Ten two-player games (Tic-Tac-Toe, Connect-4, Kuhn Poker, Breakthrough, Liar's Dice, Blind Auction, Negotiation, Nim, Pig, Iterated Prisoner's Dilemma); baselines MCTS, Tit-for-Tat, random; Normalised Relative Advantage and Elo; LLMs reach NRA of −1 against MCTS in complete-information deterministic games and near 0 in probabilistic games; Elo GPT-4 1591.99, Llama-3-70b 1577.06 — [arXiv 2402.12348](https://arxiv.org/html/2402.12348)

**MAgIC** (arXiv Nov 2023)
- Five scenarios (Chameleon, Undercover, Cost Sharing, Prisoner's Dilemma, Public Good), over 100 cases; three players in the game-theory scenarios; challenger LLM against GPT-4 defenders; seven metrics (judgment, reasoning, deception, self-awareness, cooperation, coordination, rationality). The abstract's "over threefold" capability gap is not matched by Table 1 win rates (62.1% vs 26.5%) — [arXiv 2311.08562](https://ar5iv.labs.arxiv.org/html/2311.08562)

**AvalonBench** (arXiv Oct 2023)
- Resistance Avalon, 5-player examples; roles Servant, Merlin, Minion, Assassin with asymmetric identity knowledge; one-sentence public discussion; rule-based bots as partners and opponents. LLM Servant vs rule-based evil: GPT-3.5 22.2% with discussion and 11.1% without, vs 38.2% for the rule-based Servant bot. All-GPT-3.5 self-play: evil wins 83.3% — [arXiv 2310.05036](https://ar5iv.labs.arxiv.org/html/2310.05036)

**Werewolf Arena** (arXiv Jul 2024, preprint)
- 8 players: 1 Seer, 1 Doctor, 2 Werewolves, 4 Villagers; speaking turns allocated by bidding (0–4); cross-model round-robin; simulation reference: villagers win 1.2% of 100,000 games with no information exchange. Seer "believed" rate GPT-4o 90.9%, GPT-3.5 20.0% — [arXiv 2407.13943](https://arxiv.org/html/2407.13943)

**Welfare Diplomacy** (arXiv Oct 2023)
- General-sum Diplomacy variant: 7 players; Welfare Points = supply centres minus units, accumulated over a fixed number of years (default 10); three message rounds per turn; baselines: optimal prosocial policy, random policy, exploiter agents (one or two); metrics Nash welfare and exploitability. GPT-4 highest root Nash welfare; many models at or below random; one exploiter suffices to exploit the others; more message rounds are associated with higher welfare; cross-play listed as future work — [arXiv 2310.08901](https://ar5iv.labs.arxiv.org/html/2310.08901)

**Diplomacy agents: Cicero** (Science, Dec 2022)
- Played 40 anonymous games in an online human league (19 Aug–13 Oct 2022), sending 5,277 messages — [PubMed record](https://pubmed.ncbi.nlm.nih.gov/36413172/)
- Achieved more than double the average human score and ranked in the top 10% of participants who played more than one game — [Meta AI blog](https://ai.meta.com/blog/cicero-ai-negotiates-persuades-and-cooperates-with-people/)

**Melting Pot 2.0 and the Concordia Contest**
- Melting Pot 2.0 pairs a substrate with a reference "background population" and "measures generalization to novel social partners in a set of canonical test scenarios" (MARL, not LLM) — [arXiv 2211.13746](https://arxiv.org/abs/2211.13746)
- The NeurIPS 2024 Concordia Contest is the LLM counterpart: five text substrates (Reality Show, Pub Coordination, Haggling, Labor Collective Action, State Formation), 14 held-out scenarios with held-out background players; all agents use Gemma 2 9B and contestants submit only scaffolding; 197 participants, 25 teams; Elo on min-max normalised scores; mean normalised score 0.426 ± 0.005; only five agents significantly beat the rational-agent baseline — [arXiv 2512.03318](https://arxiv.org/html/2512.03318v1); [NeurIPS 2025 Datasets and Benchmarks](https://proceedings.neurips.cc/paper_files/paper/2025/hash/d0251bbbc0288f241b878775ba1735dc-Abstract-Datasets_and_Benchmarks_Track.html)

**GovSim** (arXiv Apr 2024)
- Common-pool resource scenarios (fishery, pasture, pollution); five agents in the examples; 12-month horizon; private simultaneous harvesting then open group discussion; metrics survival time, survival rate, gain, efficiency, equality, over-usage. Best survival rate GPT-4o 53.3%; seven of twelve tabulated models 0%; without communication over-usage rises by 22% (introduction says 21%); adding a newcomer drops GPT-4o survival from 53.3% to 33.3% — [arXiv 2404.16698](https://arxiv.org/html/2404.16698)

#### F. Negotiation and social interaction

**NegotiationArena** (arXiv Feb 2024)
- Three two-agent scenarios (Resource Exchange, Multi-Turn Ultimatum, Seller and Buyer), 8–10 turns; private valuations; structured tagged messages with hidden reasoning; all ordered model pairs play 60 negotiations per scenario; win rate and payoff. GPT-4 best overall; "desperate" behaviour improves payoff by about 20%; final price correlates with first offer (ρ = 0.716) — [arXiv 2402.05863](https://arxiv.org/html/2402.05863)

**LLM-Deliberation** (arXiv Sep 2023)
- Six parties, five issues, 720 possible deals; roles: proposer, veto party, beneficiaries, constraining and opposing parties; each has secret scores and a minimum threshold; 24 public rounds; greedy and adversarial agent conditions — [arXiv 2309.17234](https://ar5iv.labs.arxiv.org/html/2309.17234)
- Results: GPT-4 81% (5/6-way) and 33% (6-way) success; GPT-3.5 20% / 8%; replacing only the proposer with GPT-3.5 gives 50%; one greedy proposer 27%; adversary 63% untargeted, 58% targeted; all-way agreement by player count 90% (3), 81% (4), 66% (5), 33% (6); GPT-3.5 leaks scores 25% of the time — [arXiv 2309.17234](https://ar5iv.labs.arxiv.org/html/2309.17234)

**SOTOPIA** (arXiv Oct 2023)
- 90 scenarios, 40 characters, 450 tasks; two agents per episode with private social goals and secrets; 20-turn limit; all model pairs, human–human and human–GPT-4 on a hard subset; seven dimensions (goal 0–10, believability, knowledge, secret −10–0, relationship, social rules, financial). Goal: GPT-4 7.62, GPT-3.5 6.45; on the hard subset GPT-4 with humans 4.85, humans with humans 6.15 — [arXiv 2310.11667](https://ar5iv.labs.arxiv.org/html/2310.11667)

**SOTOPIA-π** (arXiv Mar 2024)
- Trains Mistral-7B by behaviour cloning and self-reinforcement; evaluated with a fixed GPT-3.5-turbo partner. Goal completion on 90 tasks: base 5.07, trained 7.62, GPT-4 7.62 (GPT-4 rated); on hard tasks human raters give the trained model 4.29 where GPT-4 gives 5.71 — [arXiv 2403.08715](https://arxiv.org/html/2403.08715)

**AgentSociety** (arXiv Feb 2025)
- Social simulator, "over 10k agents, simulating their 5 million interactions"; studies polarisation, inflammatory messages, universal basic income, hurricane shocks; claims alignment with "real-world experimental results"; it is a simulation validated against real data, not a scored benchmark; quantitative validation not in the part read — [arXiv 2502.08691](https://arxiv.org/html/2502.08691)

#### G. Multi-agent debate, scaling and cost studies (answer-quality tasks)

- Du et al. (May 2023) introduced multi-agent debate: several instances propose and debate over rounds, improving mathematical and strategic reasoning and factual validity — [arXiv 2305.14325](https://arxiv.org/abs/2305.14325)
- "Should we be going MAD?" (Nov 2023): seven datasets, GPT-3.5; with original settings debate did not outperform Medprompt or Self-Consistency; Medprompt best on MedQA at 0.65; on non-medical datasets the single agent beat every system except Multi-Persona and Self-Consistency; tuning agreement raised Multi-Persona by about 15% — [arXiv 2311.17371](https://arxiv.org/html/2311.17371)
- "Stop Overvaluing Multi-Agent Debate" (Feb 2025): 5 debate methods, 9 benchmarks, 4 models; debate "often fails" to beat CoT and Self-Consistency despite more compute; model heterogeneity helps — [arXiv 2502.08788](https://arxiv.org/html/2502.08788)
- MacNet (Jun 2024): up to 64 nodes ("over a thousand agents" in mesh); quality follows a logistic curve in log node count, saturating around 2^4 nodes; random topology best (0.6522) vs CoT 0.5757; majority voting gains only 0.9% and plateaus at about eight agents — [arXiv 2406.07155](https://arxiv.org/html/2406.07155)
- "Understanding Agent Scaling via Diversity" (Feb 2026): N ∈ {2, 4, 8, 12, 16}; 2 fully diverse agents reach 67.71% (vote) vs 65.34% for 16 homogeneous agents; homogeneous systems plateau around N≈4 — [arXiv 2602.03794](https://arxiv.org/html/2602.03794)
- BenchAgent, "Do More Agents Help?" (Jun 2026): ten benchmarks (3,302 instances) plus GAIA; six multi-agent workflows vs a single-agent Core under shared step limits; EvoAgent 79.70% vs Core 76.65% pooled; the other five trail Core by 1.71–8.76 points; token cost 1.27x (EvoAgent), 1.39x (LLM-Debate), 4.34x (ChatEval) — [arXiv 2606.05670](https://arxiv.org/html/2606.05670)
- AgentCARD (May 2026): planner–executor teams on five benchmarks; heterogeneous teams gain up to +44 points over budget-matched homogeneous teams and lose up to −36 when the pairing is reversed; Opus planner with Qwen executor 80.6% at $0.108 vs 80.2% at $1.283 for self-play; no single-agent baseline — [arXiv 2606.20629](https://arxiv.org/html/2606.20629)
- MedAgentBoard (May 2025): multi-agent collaboration "does not consistently outperform advanced single LLMs"; CoT-SC 89.90% on MedQA vs MedAgents 85.25%; multi-agent helps most on clinical workflow automation completeness — [arXiv 2505.12371](https://arxiv.org/html/2505.12371)
- R³-Bench (Aug 2026): one model allocating a shared budget across six-problem suites; the offline oracle allocation matches or beats the model's own in all 72 cells (strictly in 71); not multi-agent, but relevant to budget-matched design — [arXiv 2608.16033](https://arxiv.org/abs/2608.16033)

#### H. Robustness to bad teammates, and peer-review setups

- TAMAS (arXiv Nov 2025; ACL 2026): 5 scenarios, 300 adversarial instances, 6 attack types including Byzantine, colluding and contradicting agents; 4 agents per system; AutoGen and CrewAI configurations; impersonation up to 82% attack success, colluding-agent attacks 2–16% — [arXiv 2511.05269](https://arxiv.org/html/2511.05269v1); [ACL Anthology](https://aclanthology.org/2026.acl-long.1442.pdf)
- PeerRank (Feb 2026): 12 models write 420 questions, answer all, and score each other 1–10; peer scores correlate with TruthfulQA ground truth (Pearson r = 0.904); self-evaluation correlates far less (0.538); position bias +0.39 for the first-shown answer — [arXiv 2602.02589](https://arxiv.org/html/2602.02589v1)
- BenchMARL (Dec 2023) is a MARL training library for "standardized benchmarking across different algorithms", included only as contrast: it trains policies and does not evaluate language-model agents — [arXiv 2312.01472](https://arxiv.org/abs/2312.01472)

### Inferences
- The benchmarks split into three design families: (1) game or environment fixes everything (agent count, roles, information), and only the model varies; (2) the benchmark varies team size or topology as a condition (MultiAgentBench ablation, Silo-Bench, AgentsNet, MineCollab, VillagerBench, MacNet); (3) the system under test chooses its own organisation (BenchAgent workflows, ForestBench frameworks, REALM-Bench frameworks). No benchmark found lets the system choose team size and then scores it against a budget-matched solo run.
- SmartPlay is commonly listed with multi-agent benchmarks but, as read, is single-agent.

### Gaps
- PeerArena: no benchmark paper by this name was found. The only hit was a thin news post about a "Peer Arena" model ranking whose origin could not be confirmed ([aigazine](https://aigazine.com/llms/claude-45-ranks-1-in-peer-arena-while-gpt52-records-82-selfvote-rate--s)); PeerRank is the closest documented peer-review setup.
- Melting Pot with LLM players directly (as opposed to the text-based Concordia Contest): no source was found.
- Peer-reviewed venues were confirmed only for MultiAgentBench (ACL 2025), ProAgent (AAAI 2024), AH2AC2 (ICML 2025), Silo-Bench and TAMAS (ACL 2026), the Concordia Contest paper (NeurIPS 2025 D&B), MAGPIE (NeurIPS 2025 listing), AgentWorld (COLM 2026) and Cicero (Science). The venues of the others were not stated on the pages read; several are known to have been published at major conferences, but that was not verified here.
- ForestBench, SOTOPIA-TOM, MAGPIE, ARE/Gaia2, R³-Bench, Du et al. and Melting Pot 2.0 were read from abstracts only.
- Not opened: ZSC-Eval, Among Us benchmarks, Codenames benchmarks, Collaborative Gym, OASIS, DPBench, Richelieu, MAS-FIRE (arXiv 2602.19843, surfaced by search only).
- Standalone C-WAH and TDW-MAT papers were not opened; they are described only through CoELA.

## Key question 2: Number of agents: fixed, varied as a condition, or chosen by the system

### Takeaway
Most benchmarks fix the team size (2 for embodied and Overcooked work, a game-defined 3–10 for social games); the few that vary it as a condition almost all report falling success as agents are added.

### Cited Findings
- Fixed at 2: Collab-Overcooked, LLM-Coordination, COMMA, CoELA, PARTNR, NegotiationArena, SOTOPIA — [Collab-Overcooked](https://arxiv.org/html/2502.20073); [LLM-Coordination](https://arxiv.org/html/2310.03903); [COMMA](https://arxiv.org/html/2410.07553); [CoELA](https://ar5iv.labs.arxiv.org/html/2307.02485); [PARTNR](https://arxiv.org/html/2411.00081); [NegotiationArena](https://arxiv.org/html/2402.05863); [SOTOPIA](https://ar5iv.labs.arxiv.org/html/2310.11667)
- Fixed by game or task: Decrypto 3, LLM-Deliberation 6, Welfare Diplomacy 7, Werewolf Arena 8, GAMA-Bench 10, EntCollabBench 11, AgentWorld 3–20 per task — [Decrypto](https://arxiv.org/html/2506.20664); [LLM-Deliberation](https://ar5iv.labs.arxiv.org/html/2309.17234); [Welfare Diplomacy](https://ar5iv.labs.arxiv.org/html/2310.08901); [Werewolf Arena](https://arxiv.org/html/2407.13943); [GAMA-Bench](https://arxiv.org/html/2403.11807); [EntCollabBench](https://arxiv.org/html/2605.08761v1); [AgentWorld](https://arxiv.org/html/2609.31590v1)
- Varied as a condition: Silo-Bench (2–100), AgentsNet (4–100), MineCollab (2–5), VillagerBench (1–8), CuisineWorld (2–4), TeamCraft (2–4), Hanabi studies (2–5), MultiAgentBench research ablation (1, 3, 5, 7), LLM-Deliberation player-count ablation (3–6), MacNet (1–64 nodes) — [Silo-Bench](https://arxiv.org/html/2603.01045v1); [AgentsNet](https://arxiv.org/html/2507.08616); [MineCollab](https://arxiv.org/html/2504.17950); [VillagerBench](https://arxiv.org/html/2406.05720); [MindAgent](https://ar5iv.labs.arxiv.org/html/2309.09971); [TeamCraft](https://arxiv.org/html/2412.05255); [Hanabi](https://arxiv.org/html/2601.18077); [MultiAgentBench](https://arxiv.org/html/2503.01935); [LLM-Deliberation](https://ar5iv.labs.arxiv.org/html/2309.17234); [MacNet](https://arxiv.org/html/2406.07155)
- Chosen by the system or framework under test: BenchAgent compares workflows with their native agent counts and states agent-count effects are outside its measurement target — [BenchAgent](https://arxiv.org/html/2606.05670)

### Inferences
- A new evaluation that lets the system pick its own team size would be unusual; existing designs treat team size as an experimenter-controlled variable or a property of the framework.

### Gaps
- AgentWorld does not report results broken down by team size, so its 3–20 range gives no scaling curve.

## Key question 3: Roles: prescribed, symmetric or emergent

### Takeaway
Prescribed asymmetric roles dominate; only a few benchmarks are explicitly role-agnostic, and emergent role formation is rarely measured.

### Cited Findings
- Prescribed roles with different abilities or permissions: Collab-Overcooked (chef and assistant), COMMA (Solver and Expert), Decrypto, RoCoBench (reach and tools), TeamBench (Planner, Executor, Verifier enforced by containers), EntCollabBench (11 departmental roles with tool scopes), AgentWorld, CREW-Wildfire (four vehicle types) — [Collab-Overcooked](https://arxiv.org/html/2502.20073); [COMMA](https://arxiv.org/html/2410.07553); [Decrypto](https://arxiv.org/html/2506.20664); [RoCoBench](https://ar5iv.labs.arxiv.org/html/2307.04738); [TeamBench](https://arxiv.org/html/2605.07073); [EntCollabBench](https://arxiv.org/html/2605.08761v1); [AgentWorld](https://arxiv.org/html/2609.31590v1); [CREW-Wildfire](https://arxiv.org/html/2507.05178)
- Symmetric or role-agnostic: Silo-Bench, AgentsNet, CoELA, Hanabi self-play, GAMA-Bench default prompts — [Silo-Bench](https://arxiv.org/html/2603.01045v1); [AgentsNet](https://arxiv.org/html/2507.08616); [CoELA](https://ar5iv.labs.arxiv.org/html/2307.02485); [Hanabi](https://arxiv.org/html/2601.18077); [GAMA-Bench](https://arxiv.org/html/2403.11807)
- Roles generated by the system: AgentVerse recruits experts automatically — [AgentVerse](https://ar5iv.labs.arxiv.org/html/2308.10848)
- Enforcement matters less for pass rate than expected: in TeamBench prompt-only vs enforced roles give 42.7% vs 40.5% (not significant), but verifier code-edit attempts fall from 256 to 72 under enforcement — [TeamBench](https://arxiv.org/html/2605.07073)
- Ability diversity can hurt: VillagerBench same-ability trios 56.67 vs diverse-ability trios 36.67 — [VillagerBench](https://arxiv.org/html/2406.05720)

### Inferences
- Role violations are a measurable behaviour (TeamBench) that most benchmarks do not track because roles are only stated in prompts.

### Gaps
- No benchmark found scores emergent role specialisation directly.

## Key question 4: Information distribution (hidden-profile style vs shared)

### Takeaway
True hidden-profile designs, where each agent holds a shard the others need, exist but few pair them with a single-agent-with-everything reference; Silo-Bench and RoCoBench are the clearest that do.

### Cited Findings
- Partitioned inputs with a full-information reference: Silo-Bench (N=1 with full input), RoCoBench (central-plan oracle), AgentWorld (oracle communication 60.0% vs 52.0%) — [Silo-Bench](https://arxiv.org/html/2603.01045v1); [RoCoBench](https://ar5iv.labs.arxiv.org/html/2307.04738); [AgentWorld](https://arxiv.org/html/2609.31590v1)
- Partitioned information without such a reference: InformativeBench, COMMA, Collab-Overcooked, MineCollab, AgentsNet, SOTOPIA-TOM, EntCollabBench — [InformativeBench](https://arxiv.org/html/2406.14928); [COMMA](https://arxiv.org/html/2410.07553); [Collab-Overcooked](https://arxiv.org/html/2502.20073); [MineCollab](https://arxiv.org/html/2504.17950); [AgentsNet](https://arxiv.org/html/2507.08616); [SOTOPIA-TOM](https://arxiv.org/abs/2605.02307); [EntCollabBench](https://arxiv.org/html/2605.08761v1)
- Private information that must be protected while collaborating: MAGPIE, SOTOPIA-TOM, COMMA's private-information puzzles, LLM-Deliberation's score-leakage metric — [MAGPIE](https://arxiv.org/abs/2510.15186); [SOTOPIA-TOM](https://arxiv.org/abs/2605.02307); [COMMA](https://arxiv.org/html/2410.07553); [LLM-Deliberation](https://ar5iv.labs.arxiv.org/html/2309.17234)
- Centralised vs decentralised observation as a condition: TeamCraft, PARTNR — [TeamCraft](https://arxiv.org/html/2412.05255); [PARTNR](https://arxiv.org/html/2411.00081)
- Silo-Bench finds agents collect information but fail to integrate it (partial correctness 88.0% vs success 62.0% at Level I) — [Silo-Bench](https://arxiv.org/html/2603.01045v1)

### Inferences
- Failure under information asymmetry is often an integration failure, not a sharing failure (Silo-Bench), which argues for scoring intermediate "information obtained" separately from the final answer.

### Gaps
- InformativeBench has no pooled-information baseline, so its accuracy cannot be converted into a collaboration cost.

## Key question 5: Communication allowed, and whether it is scored

### Takeaway
Free-text messaging is the norm; a minority restrict or price it, and direct scoring of communication is rare and usually done by an LLM judge.

### Cited Findings
- Communication scored: MultiAgentBench Communication Score (LLM-judged, five-point); Collab-Overcooked initiating and responding capability; COMMA efficiency score using token conciseness; Silo-Bench communication density; SOTOPIA-TOM sharing and seeking dimensions; AgentWorld communication-error taxonomy — [MultiAgentBench](https://arxiv.org/html/2503.01935); [Collab-Overcooked](https://arxiv.org/html/2502.20073); [COMMA](https://arxiv.org/html/2410.07553); [Silo-Bench](https://arxiv.org/html/2603.01045v1); [SOTOPIA-TOM](https://arxiv.org/abs/2605.02307); [AgentWorld](https://arxiv.org/html/2609.31590v1)
- Communication priced or limited: CoELA (a message costs a step), Hanabi (clue tokens), Werewolf Arena (bidding to speak), COMMA and InformativeBench (10 turns), AgentsNet (fixed rounds, neighbours only) — [CoELA](https://ar5iv.labs.arxiv.org/html/2307.02485); [LLM-Coordination](https://arxiv.org/html/2310.03903); [Werewolf Arena](https://arxiv.org/html/2407.13943); [COMMA](https://arxiv.org/html/2410.07553); [InformativeBench](https://arxiv.org/html/2406.14928); [AgentsNet](https://arxiv.org/html/2507.08616)
- No explicit channel: TeamCraft, PARTNR, GAMA-Bench, CuisineWorld (central dispatcher), VillagerBench (central controller) — [TeamCraft](https://arxiv.org/html/2412.05255); [PARTNR](https://arxiv.org/html/2411.00081); [GAMA-Bench](https://arxiv.org/html/2403.11807); [MindAgent](https://ar5iv.labs.arxiv.org/html/2309.09971); [VillagerBench](https://arxiv.org/html/2406.05720)
- Communication protocol or topology as a condition: Silo-Bench (P2P, broadcast, shared file system), MultiAgentBench (star, chain, tree, graph), MacNet (six topologies) — [Silo-Bench](https://arxiv.org/html/2603.01045v1); [MultiAgentBench](https://arxiv.org/html/2503.01935); [MacNet](https://arxiv.org/html/2406.07155)
- Effects of communication: helps in AgentWorld (22.9% without vs 52.0% with), GovSim (over-usage +22% without), Welfare Diplomacy, AvalonBench (11.1% without vs 22.2% with discussion); hurts or is neutral in MineCollab (up to 15% drop when detailed plans must be communicated), BattleAgentBench (most models score higher without the cooperation interface), SPIN-Bench Diplomacy (o1 worse with negotiation) — [AgentWorld](https://arxiv.org/html/2609.31590v1); [GovSim](https://arxiv.org/html/2404.16698); [Welfare Diplomacy](https://ar5iv.labs.arxiv.org/html/2310.08901); [AvalonBench](https://ar5iv.labs.arxiv.org/html/2310.05036); [MineCollab](https://arxiv.org/html/2504.17950); [BattleAgentBench](https://arxiv.org/html/2408.15971); [SPIN-Bench](https://arxiv.org/html/2503.12349)

### Inferences
- Whether communication helps appears to depend on model strength: in BattleAgentBench only the strongest model benefited from the cooperation channel.

### Gaps
- No benchmark found reports a validated, non-LLM-judged measure of message quality.

## Key question 6: Baselines available

### Takeaway
Cross-model comparison is universal; single-agent-with-all-information, no-communication, human-team and unseen-partner baselines each appear in only a handful of benchmarks, and an equal-budget single agent is almost absent.

### Cited Findings
- Single agent with all information or oracle planner: Silo-Bench (N=1), RoCoBench (central plan), PARTNR (single-agent ReAct and centralised planner), CoELA (planner alone), AgentWorld (single agent 28.6%), TeamBench (Solo), AgentVerse (Solo), BenchAgent (Core) — [Silo-Bench](https://arxiv.org/html/2603.01045v1); [RoCoBench](https://ar5iv.labs.arxiv.org/html/2307.04738); [PARTNR](https://arxiv.org/html/2411.00081); [CoELA](https://ar5iv.labs.arxiv.org/html/2307.02485); [AgentWorld](https://arxiv.org/html/2609.31590v1); [TeamBench](https://arxiv.org/html/2605.07073); [AgentVerse](https://ar5iv.labs.arxiv.org/html/2308.10848); [BenchAgent](https://arxiv.org/html/2606.05670)
- Budget matching: BenchAgent shares step limits between Core and multi-agent workflows and records tokens as an outcome; AgentCARD compares against budget-matched homogeneous teams; TeamBench and AgentWorld do not state equal budgets — [BenchAgent](https://arxiv.org/html/2606.05670); [AgentCARD](https://arxiv.org/html/2606.20629); [TeamBench](https://arxiv.org/html/2605.07073); [AgentWorld](https://arxiv.org/html/2609.31590v1)
- No-communication team: AgentWorld, GovSim, AvalonBench, BattleAgentBench, Welfare Diplomacy, CoELA human study — [AgentWorld](https://arxiv.org/html/2609.31590v1); [GovSim](https://arxiv.org/html/2404.16698); [AvalonBench](https://ar5iv.labs.arxiv.org/html/2310.05036); [BattleAgentBench](https://arxiv.org/html/2408.15971); [Welfare Diplomacy](https://ar5iv.labs.arxiv.org/html/2310.08901); [CoELA](https://ar5iv.labs.arxiv.org/html/2307.02485)
- Human teams or human partners: PARTNR (human solo, human pairs, human + LLM), Collab-Overcooked (10 participants), COMMA, SOTOPIA, CoELA, CuisineWorld, Decrypto, GameBench, TeamBench human study, AH2AC2 human proxies — [PARTNR](https://arxiv.org/html/2411.00081); [Collab-Overcooked](https://arxiv.org/html/2502.20073); [COMMA](https://arxiv.org/html/2410.07553); [SOTOPIA](https://ar5iv.labs.arxiv.org/html/2310.11667); [CoELA](https://ar5iv.labs.arxiv.org/html/2307.02485); [MindAgent](https://ar5iv.labs.arxiv.org/html/2309.09971); [Decrypto](https://arxiv.org/html/2506.20664); [GameBench](https://arxiv.org/html/2406.06613); [TeamBench](https://arxiv.org/html/2605.07073); [AH2AC2](https://arxiv.org/html/2506.21490v2)
- Scripted or fixed partners: AvalonBench rule bots, BattleAgentBench fixed reference model, MAgIC GPT-4 defenders, SOTOPIA-π fixed GPT-3.5 partner, LLMArena GPT-3.5 Undercover players — [AvalonBench](https://ar5iv.labs.arxiv.org/html/2310.05036); [BattleAgentBench](https://arxiv.org/html/2408.15971); [MAgIC](https://ar5iv.labs.arxiv.org/html/2311.08562); [SOTOPIA-π](https://arxiv.org/html/2403.08715); [LLMArena](https://arxiv.org/html/2402.16499)
- Cross-play with different models or unseen partners: LLM-Coordination (OBL partners), ProAgent, AH2AC2, Hanabi 2026 study, Decrypto, Concordia Contest (held-out background players), NegotiationArena (all ordered pairs), TeamBench and AgentCARD (mixed-provider teams), LLM-Deliberation (mixed population) — [LLM-Coordination](https://arxiv.org/html/2310.03903); [ProAgent](https://arxiv.org/abs/2308.11339); [AH2AC2](https://arxiv.org/html/2506.21490v2); [Hanabi](https://arxiv.org/html/2601.18077); [Decrypto](https://arxiv.org/html/2506.20664); [Concordia](https://arxiv.org/html/2512.03318v1); [NegotiationArena](https://arxiv.org/html/2402.05863); [TeamBench](https://arxiv.org/html/2605.07073); [AgentCARD](https://arxiv.org/html/2606.20629); [LLM-Deliberation](https://ar5iv.labs.arxiv.org/html/2309.17234)
- Random or do-nothing floors expose weak results: COMMA (some models below random), GameBench (bare GPT-4 below random), CREW-Wildfire (frameworks below Do Nothing), Welfare Diplomacy (many models at or below random) — [COMMA](https://arxiv.org/html/2410.07553); [GameBench](https://arxiv.org/html/2406.06613); [CREW-Wildfire](https://arxiv.org/html/2507.05178); [Welfare Diplomacy](https://ar5iv.labs.arxiv.org/html/2310.08901)

### Inferences
- AgentWorld's baseline ladder (random, single, no-communication, shared-plan, vanilla team, oracle communication) is the most complete set found in one benchmark and is a usable template, with budget matching added.

### Gaps
- No non-coding benchmark found reports a team against a single agent given the same total token budget.

## Key question 7: Scoring and what each benchmark claims to measure

### Takeaway
Task success dominates; a growing minority add process metrics (milestone contribution, causal contribution, redundancy, coordination cost), and claims about "theory of mind" or "coordination" usually rest on LLM-judged rubrics or game outcome.

### Cited Findings
- Collaboration-specific metrics: Silo-Bench Relative Coordination Cost (1 − SR(N=k)/SR(N=1)); AgentWorld CCE (contributing actions over all actions); TeamBench Teamwork Necessity Index; CoELA efficiency improvement over a single agent; CuisineWorld CoS; TeamCraft redundancy rate; VillagerBench balance and agent contribution rate; MultiAgentBench milestone KPI — [Silo-Bench](https://arxiv.org/html/2603.01045v1); [AgentWorld](https://arxiv.org/html/2609.31590v1); [TeamBench](https://arxiv.org/html/2605.07073); [CoELA](https://ar5iv.labs.arxiv.org/html/2307.02485); [MindAgent](https://ar5iv.labs.arxiv.org/html/2309.09971); [TeamCraft](https://arxiv.org/html/2412.05255); [VillagerBench](https://arxiv.org/html/2406.05720); [MultiAgentBench](https://arxiv.org/html/2503.01935)
- Theory of mind: Decrypto (perspective-taking and false-belief tasks), CoordinationQA, LLM-Deliberation preference matching (GPT-4 61%, GPT-3.5 42%), SOTOPIA-TOM — [Decrypto](https://arxiv.org/html/2506.20664); [LLM-Coordination](https://arxiv.org/html/2310.03903); [LLM-Deliberation](https://ar5iv.labs.arxiv.org/html/2309.17234); [SOTOPIA-TOM](https://arxiv.org/abs/2605.02307)
- Welfare and fairness: Welfare Diplomacy (Nash welfare, exploitability), GovSim (equality via Gini, efficiency), LLM-Deliberation (collective score) — [Welfare Diplomacy](https://ar5iv.labs.arxiv.org/html/2310.08901); [GovSim](https://arxiv.org/html/2404.16698); [LLM-Deliberation](https://ar5iv.labs.arxiv.org/html/2309.17234)
- Negotiation outcomes: NegotiationArena (win rate, payoff), GTBench (NRA, regret, Pareto efficiency) — [NegotiationArena](https://arxiv.org/html/2402.05863); [GTBench](https://arxiv.org/html/2402.12348)
- Robustness to bad teammates: LLM-Deliberation greedy and adversarial agents; TAMAS Byzantine and colluding agents; GovSim newcomer; Welfare Diplomacy exploiters — [LLM-Deliberation](https://ar5iv.labs.arxiv.org/html/2309.17234); [TAMAS](https://arxiv.org/html/2511.05269v1); [GovSim](https://arxiv.org/html/2404.16698); [Welfare Diplomacy](https://ar5iv.labs.arxiv.org/html/2310.08901)
- Ad hoc teamwork with unseen partners: AH2AC2, Concordia Contest, ProAgent, Melting Pot 2.0 protocol — [AH2AC2](https://arxiv.org/html/2506.21490v2); [Concordia](https://arxiv.org/html/2512.03318v1); [ProAgent](https://arxiv.org/abs/2308.11339); [Melting Pot 2.0](https://arxiv.org/abs/2211.13746)
- LLM judges can mislead: SOTOPIA-π GPT-4 rates the trained model 5.71 where humans rate 4.29; TeamBench verifiers approve 49.4% of failing submissions — [SOTOPIA-π](https://arxiv.org/html/2403.08715); [TeamBench](https://arxiv.org/html/2605.07073)

### Inferences
- Deterministic graders plus a solo reference give the most defensible "collaboration gain" numbers; rubric scores for coordination quality are the least comparable across benchmarks.

### Gaps
- ForestBench's metric panel is not named in its abstract; the full paper was not read.

## Key question 8: Headline results: teams vs single agent, and more agents helping or hurting

### Takeaway
Where a solo reference exists, teams usually add cost and often match or trail it; gains appear when the task truly needs distributed capability or the solo model is weak. Adding agents mostly hurts beyond a small team.

### Cited Findings
- Teams worse or no better than solo: PARTNR (same 0.73 success, about 1.3x steps); TeamBench (+0.5 points mean, p=0.20; negative for Gemma 4 31B); BenchAgent (five of six workflows trail the single agent by 1.71–8.76 points); AgentVerse with GPT-3.5 on MGSM and Commongen; RoCoBench dialogue vs central plan on four of six tasks; MedAgentBoard; debate studies — [PARTNR](https://arxiv.org/html/2411.00081); [TeamBench](https://arxiv.org/html/2605.07073); [BenchAgent](https://arxiv.org/html/2606.05670); [AgentVerse](https://ar5iv.labs.arxiv.org/html/2308.10848); [RoCoBench](https://ar5iv.labs.arxiv.org/html/2307.04738); [MedAgentBoard](https://arxiv.org/html/2505.12371); [MAD study](https://arxiv.org/html/2311.17371)
- Teams better than solo: AgentWorld (52.0% vs 28.6%); CoELA (LLM pair 57 steps vs 111 single); TeamBench for weaker models (+20.0, +16.7) and in the lowest solo quintile (+15.7); AgentVerse tool use (9 of 10 vs 3); BenchAgent EvoAgent (+3.05 points at 1.27x tokens); human pairs in PARTNR (2369.55 vs 3046.99 steps) — [AgentWorld](https://arxiv.org/html/2609.31590v1); [CoELA](https://ar5iv.labs.arxiv.org/html/2307.02485); [TeamBench](https://arxiv.org/html/2605.07073); [AgentVerse](https://ar5iv.labs.arxiv.org/html/2308.10848); [BenchAgent](https://arxiv.org/html/2606.05670); [PARTNR](https://arxiv.org/html/2411.00081)
- More agents hurt: Silo-Bench (61.2% at N=2 to 18.1% at N=100); AgentsNet (near zero at 100); MineCollab (up to 90% to under 30% from 2 to 5 agents); LLM-Deliberation (90% with 3 players to 33% with 6); SPIN-Bench Hanabi (16.4 to 14.2); VillagerBench at 8 agents; TeamCraft redundancy grows with agents; MultiAgentBench KPI falls as agents rise; AgentVerse math reviewers — [Silo-Bench](https://arxiv.org/html/2603.01045v1); [AgentsNet](https://arxiv.org/html/2507.08616); [MineCollab](https://arxiv.org/html/2504.17950); [LLM-Deliberation](https://ar5iv.labs.arxiv.org/html/2309.17234); [SPIN-Bench](https://arxiv.org/html/2503.12349); [VillagerBench](https://arxiv.org/html/2406.05720); [TeamCraft](https://arxiv.org/html/2412.05255); [MultiAgentBench](https://arxiv.org/html/2503.01935); [AgentVerse](https://ar5iv.labs.arxiv.org/html/2308.10848)
- More agents helped, within limits: VillagerBench cooking (73.75 with 2 to 85.26 with 3) and construction up to 4 agents; MacNet up to about 16 nodes; CuisineWorld marginally (0.673 to 0.694); heterogeneous ensembles up to about N≈8 — [VillagerBench](https://arxiv.org/html/2406.05720); [MacNet](https://arxiv.org/html/2406.07155); [MindAgent](https://ar5iv.labs.arxiv.org/html/2309.09971); [Agent Scaling via Diversity](https://arxiv.org/html/2602.03794)
- Model mix matters more than count: 2 diverse agents beat 16 homogeneous; mixed-provider teams match or beat single-provider teams at about half the cost (TeamBench) or up to 12x lower cost (AgentCARD); one weak agent in a key role drops LLM-Deliberation success from 81% to 50% — [Agent Scaling via Diversity](https://arxiv.org/html/2602.03794); [TeamBench](https://arxiv.org/html/2605.07073); [AgentCARD](https://arxiv.org/html/2606.20629); [LLM-Deliberation](https://ar5iv.labs.arxiv.org/html/2309.17234)
- Gap to humans persists in cooperative play: Hanabi best LLMs about 15/25 vs human experts above 20/25; COMMA human 69.01% vs best model 53.98%; PARTNR humans 0.93 vs LLM 0.73 — [Hanabi](https://arxiv.org/html/2601.18077); [COMMA](https://arxiv.org/html/2410.07553); [PARTNR](https://arxiv.org/html/2411.00081)

### Inferences
- The reported team advantage shrinks as the solo model gets stronger (TeamBench), so a benchmark's "collaboration gain" will drift toward zero over model generations unless tasks require capabilities or information one agent cannot hold.
- AgentWorld's large team advantage (52.0% vs 28.6%) is not budget-controlled and its tasks are built around asymmetric abilities, so it is not directly comparable with the equal-step BenchAgent result.

### Gaps
- No source gives a scaling curve for teams of frontier 2026 models on non-coding tasks with budget held constant.
- Collab-Overcooked, COMMA, InformativeBench and EntCollabBench have no solo reference, so no collaboration gain can be computed from them.

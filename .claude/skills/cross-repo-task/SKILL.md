---
name: cross-repo-task
description: Find a real feature that crossed two or more permissively licensed repositories, and build it into a SWE-Pod multi-agent task in Harbor format (solo and fixed-team variants), the way customer_attributes_company was built. Use when asked to find new seeds, mine a cross-repo feature, build or harden a company task, or validate one before frontier runs.
---

# Building a cross-repo task for SWE-Pod

The worked example is `mined/customer_attributes_company`: Saleor's customer attributes, a feature upstream built
in the API (`saleor/saleor`, Python/Django/GraphQL) and then in the staff application
(`saleor/saleor-dashboard`, TypeScript/React). One agent per repository in the team condition, one agent with the
same budget in solo. The task is the project's own: its code at the commit before, its tests as the hidden judge,
its merged code as the reference.

Follow the phases in order. Each phase ends with a check; do not start the next until it passes.

## Standing rules

- Licences: BSD, MIT, Apache-2.0 only. No FSL (Saleor's storefront), AGPL (Lago) or other copyleft or
  source-available code without asking the user.
- Every system mirrors a named real repository. Fidelity ranks above tidiness. No invented services.
- Clones live in `.cache/repos/` (git-ignored), never in `/tmp`: macOS cleans `/tmp`, and an export from a broken
  clone wipes the task folder.
- Never put `solution/`, `tools/derive_solutions.py` or `tools/derive_incidents.py` in an agent's workspace.
- No model calls without the user asking. Validation with the oracle and the cheat costs no model calls.
- Never print `.env`. Load it with `set -a && . ./.env && set +a`.
- Permissions belong to the environment and are always prescribed (who may push where), never left to the agent.

## Phase 1: find a seed

What makes a seed worth building, learned the hard way (`reports/Multi repo seeds for harder tasks.md`): crossing
repositories adds no difficulty by itself. What adds it is **width** (many files on both sides), **depth** (a
real data model, migrations, permissions), and **time** (hours of work, not minutes). A one-sentence contract
across two repositories is easy for one agent; two coupled reversions were solved by a solo agent in 12 minutes.

A good seed has all of these:

1. **One feature, merged in two or more repositories**, where one side cannot work without the other: an API and
   its client, a core and its app, a schema and its consumer, etc.
2. **Large on both sides.** The example: 4,393 source lines in 73 files and 11 migrations in core; 14,293 lines in
   237 files in the dashboard. Below roughly 1,000 lines per side one agent solves it easily: skip it, or chain
   related merged changes of the same feature (`picks`, Phase 2) until it is that large.
3. **The project's own tests for the feature**, merged with it, on at least the provider's side. Without them there
   is no judge. A side without tests of its own (a frontend PR often has none) is judged by the contract checks and
   the end-to-end check instead; say so in the datasheet.
4. **A runnable test suite at the commit before**, in a container. The scored tests (the feature's, and the
   guards of Phase 3) must run in under about an hour; time them in the image before choosing the seed.
5. **Recent**: merged after the newest model's knowledge cutoff, so it cannot be recalled. The example is August
   2026.
6. **Public and permissively licensed**, both repositories.
7. **A machine-checkable contract between the sides**, so agreement can be scored without people. It need not be
   GraphQL: a schema file the consumer copies (Saleor's `schema.graphql`), an OpenAPI or JSON schema, an event
   format, or a set of commands the provider registers in code (Home Assistant core's WebSocket commands, which
   the frontend calls by their `type`). When there is no contract file, **derive** the contract on the verifier's
   side from both sources at the start and at the target; never add a contract file to the repositories, since
   every system stays the project's own. See "Contract types" in Phase 3.
8. **Something a person does with it**, which a browser, an API call or a terminal can check end to end (staff set
   a customer's tier). A frontend is not required: a provider and a library, SDK or app that consumes it is a
   company too.

How to search:

- Start from projects that ship as several repositories under one organisation: an API plus a dashboard, apps,
  libraries or SDKs. `reports/Repo ecosystems for cross repo tasks.md` ranks the candidates found so far (Home
  Assistant, Bluesky, MCP; Spree and Lago in reserve) and the licences that rule others out.
- Mine clones, not web pages. `gh` may not be installed and the unauthenticated GitHub API allows 60 calls an hour,
  so the clones are the source. In full-history clones (`git clone --filter=blob:none` into `.cache/repos/`), look
  for feature pairs:
  - **the project's own link index first**, where it has one: Home Assistant's frontend PR template has a "Link to
    backend pull request" field, so a frontend PR body names `home-assistant/core#N`; other projects use ticket keys
    in commit subjects (`O3-1234`) or proposal numbers (MCP's `SEP-2549`);
  - PR numbers named in commit subjects (squash merges carry `(#N)`), and GitHub's `CrossReferencedEvent` timeline
    items (`isCrossRepository`) when the API is available;
  - the same feature words in both repositories' logs within a few weeks;
  - changes to the provider's contract (schema file, registered commands) followed by the consumer's use of them.
  `reports/Cross repo dependencies in Saleor history.md` shows the method and what it found.
- Read the issues and PRs that name each other (`gh pr view`, or the PR page). Most dependencies have to be
  reconstructed from dates and diffs; mark the reconstructed ones as inference. Drop bot and codegen PRs.
- Drop any seed already in a published benchmark (WideSWE, CrossSWE, SWE-bench-Live, SWE-rebench, Multi-SWE-bench,
  FeatureBench).
- For a candidate, measure it before believing it: `git diff --stat <base> <target>` on both sides, the test files
  it adds, the migrations, and the date.
- Write up the candidates with the deep-research skill when the user wants a report, ranked against the list above.

**Check:** a short table of candidates with lines and files per side, tests added per side, merge dates, licence,
and the contract file. Agree with the user which one to build.

### A second version: the contract published by its owner

With the target schema handed over and readable by every seat, a team's seats do not need each other (in the
example's first team runs they sent five messages and none mattered). A second version of the same company makes
the boundary real. `mined/customer_attributes_company_v2/` is the example; it is a `task.json` and two documents,
and takes everything else from the first version:

- `"based_on": "<company>"`: the rubric, the test fixes and the usage file are the first version's unless the new
  folder has its own.
- An owner's `"override"` replaces fields of its repository's task for this company alone. For the provider:
  `"handed_over": []` (the schema file stays as it is before the feature), `"api_names": true` (its `INTERFACE.md`
  gains "The API the tests call": what the schema gains, from `tools/mined_api_names.cjs`, without descriptions),
  and an `exact` line saying the schema file must be regenerated from the code.
- `"isolated": true`: in the team variant each owner's token reads and pushes its own repository only, the other
  checkout is removed from the seat (`SEAT_ONLY`), the seat notes say so, and owners' tokens are hashes, so one
  cannot be worked out from another.

Before building one, measure how much of the API upstream's hidden tests pin down (search the changed test files
for each name the schema gains). In the example it is nearly all of it, so the provider must be told the names and
the version tests how the contract is published and reaches the consumer, not who designs it. Say that in the
datasheet. The brief, the hidden tests and the solo start stay the same in kind, so solo remains the baseline.
`tools/run_measures.py` reports how the contract travelled (`contract` in `measures.json`): first publication,
later changes, the consumer's first push, CI runs where the consumer asked for what the API lacked, messages
before publication.

Validate it as a task of its own (Phase 6), on the solo variant: the oracle needs both checkouts in one seat.
Also check the isolation itself: from the consumer's seat, a fetch of the provider's repository must be refused
and its checkout must not be there.

## Phase 2: mine each repository as its own task

One directory per repository under `mined/<repo task>/` (the example: `mined/saleor_customer_attributes`,
`mined/dashboard_customer_types`).

- `task.json`: `repository`, `licence`, `base` (the commit before), `target` (the feature's commit), or `picks`
  when the feature is several merged changes that must be applied alone on the base (the dashboard's three PRs).
  Plus `image`, `directory`, `test_command`, `report` (`junit` or `jest`), `test_side` (regexes for test files,
  fixtures, mocks), `handed_over` (files given at the start, such as the target schema), `links`, `aliases`,
  `generated` (code generated from the schema), `notes` (how to work in this environment) and `exact` (things the
  hidden tests assert to the letter that the description cannot imply).
- `Dockerfile`: the project's toolchain and locked dependencies, no source. Pin base images by digest.
- Build the image and keep which tests count:

      python3 tools/mined_pilot.py image <repo task> <clone>
      # run the suite at base and at target in the image, keeping the reports (see mined/README.md)
      python3 tools/mined_company.py reference <repo task> <base report> <target report> [<base under target tests> <clone>]
      python3 tools/mined_company.py interface <repo task> <clone>

  `reference.json` sorts the tests into `new` (pass at the target, not at the base: the feature's) and
  `preserved` (pass at both). `interface.json` lists the names, files and test ids the hidden tests reach for that
  the base lacks; it becomes `INTERFACE.md` in the workspace.

  Reports: `junit` for pytest, JUnit and vitest (run vitest with `--reporter=junit --outputFile=<report>`), `jest`
  for Jest's JSON. The scorer runs Jest in chunks (`npx jest --listTests`) to stay under a seat's memory; that path
  is Jest's only, and a vitest suite runs whole. Check that the scorer's test keys (`<file>::<name>`) come out the
  same from a vitest JUnit report as from the reference run.

**Check:** the base fails every `new` test and the target passes every one; the `preserved` set passes at both.
`INTERFACE.md` reads as where things live and what they are called, not as a design.

## Phase 3: join them into a company

`mined/<company>/task.json` (the example: `mined/customer_attributes_company/task.json`):

- `owners`: owner name to repository task.
- `contracts`: one entry per provider and consumer, each with a `type` (see "Contract types" below). For
  `graphql`: the schema file, the consumer's copies of it and how it regenerates its code. At the start the copies
  are put back to the provider as it was before the feature, so the consumer has to take the new API from whoever
  builds it.
- `deployed`: how each system starts, migrates and seeds; `env`. The example uses `migrate` and `populatedb`; Home
  Assistant starts with `hass -c <config>` from a seeded configuration directory (onboarding done, a user and its
  token created, demo entities), written by the task, not taken from a running install.

### Contract types

The tooling was built for `graphql` (`_wind_back`, `usage` in `tools/mined_company.py`; CI's checks in
`sidecars/ci.py`; the scorer's fit criteria). Each type must supply the same four things:

| Need | `graphql` (Saleor) | `websocket` (Home Assistant) |
|---|---|---|
| The contract at start and target | `schema.graphql` at each commit | the command `type`s core registers (`@websocket_api.websocket_command({vol.Required("type"): ...})` and `async_register_command`), with their voluptuous parameters, extracted from the source at each commit; **and the payload fields** of the commands both sides use, when the feature changes them (child devices adds none: it changes what `config/device_registry/list` returns, entries with `parent_device_id` and stripped child entries). Payload fields are read from the running provider's answers, since `dict_repr`-style code cannot be extracted reliably |
| What the consumer must not get for free | its schema copies wound back to the start | nothing to wind back: the frontend's hand-written types in `src/data/*.ts` are its own code at the start |
| CI's check of the running systems | every operation the consumer sends is valid against the served schema; every new field answers as staff | every command `type` the consumer sends (`callWS`, `sendMessagePromise`, `subscribeMessage`) is one core registers; every command core gained answers a call as the seeded user without `unknown_command` or an exception; for changed payloads, the fields the consumer's types declare (`src/data/**/*.ts` interfaces) are present in what the running provider returns for the seeded data |
| Fit criteria and `usage` | the consumer's operations are valid, use what the API gained, its copies state it | the consumer calls only registered commands, calls the commands core gained that the real consumer calls (`usage`), and sends the parameters their schemas require |

A new type is a function in each of those places, chosen by `type`; do not bend a new contract into the GraphQL
one. Write the extractor so that it runs on both clones without starting either system, and check it by running it
at the start and the target of the seed: it must find the commands the feature added and nothing else.

### Guards

Guards are the start's tests that still pass at the target. A whole suite is a guard only if it runs inside the
time budget. Otherwise scope it, and write the scope in `rubric.toml` and the datasheet: the packages the feature
touches, the shared code they import, and the test files for the contract (for Home Assistant core:
`tests/components/<each touched integration>/`, `tests/components/websocket_api/`, the helpers the diff touches;
the frontend's whole vitest suite, which is small). Time the scoped set in the image.
- `overview`, `feature`, `description`, `done`: the brief. Keep it to what a product owner would say. The example's
  `done`: it is on `main` of both repositories and works there, the API starts on a fresh database, staff can do
  what the feature is for, the existing tests still pass, and each `INTERFACE.md` names what the tests use.
- `business`: the end-to-end check and which owner plays which role. The example's is
  `tools/business_customer_tier.cjs`: a Saleor staff login, a change made in the dashboard, read back through the
  API. Each company writes its own script for its own login and outcome (Home Assistant: log in with the seeded
  user, do the thing in the frontend, read the state back over the WebSocket API). A company with no frontend
  checks the outcome through the provider's API or a CLI instead.

Then work out what the real consumer uses of what the provider gained:

    python3 tools/mined_company.py usage <company> --clone core=.cache/repos/saleor --clone dashboard=.cache/repos/saleor-dashboard

`mined/<company>/rubric.toml` says what decides the reward. For example:

| Kind | In the example | Combined as |
|---|---|---|
| gate | the API migrates and serves and the dashboard's operations are found; the pushed code leaves the scoring alone | any fails: reward 0 |
| target | the API's hidden tests (weight 1); the dashboard's hidden tests (weight 0.5); staff set a tier in a browser and the API keeps it (weight 1); the dashboard uses what the API gained (weight 0.5) | weighted mean |
| guard | each repository's preserved tests | product |
| fit | the dashboard asks only what the API serves; its schema copies state it | product |
| measure | upstream's helper tests, presentation-only tests, filtering by tier in a browser, tests left untouched, review signals | reported, not scored |

Keep as fits (multipliers) only what breaks the system when it fails; a share where each item counts the same but
matters differently (which of the new fields the consumer uses) is a weighted target, or one unused error field
costs as much as a missing feature. Weigh unit tests tied to upstream's internal design at half, and move tests of upstream's own helpers or pure
presentation to measures: a correct design built differently fails them.

**Check:** `python3 tools/mined_company.py prepare <company> <workspace> --clone ...` gives each owner the base
tree, `NOTES.md`, `INTERFACE.md` and the wound-back schema copies, and nothing of the solution.

## Phase 4: the company's sidecars

The seat is one container; the company around it is several. What each is, where it comes from, and what to add
for a new task:

| Sidecar | What it does | Where it comes from |
|---|---|---|
| `git` | The company's git server: one bare repository per owner, push rights per owner (`GIT_ACCESS`), no force pushes, no branch deletion. Logs every fetch and push (`/_log`). Only `main` counts. | `sidecars/gitserver_start.py`, `sidecars/gitserver_app.py`. Reuse as is. |
| `ci` | Watches `main` of every repository. On a push it deploys that repository, then checks each contract by its type (Phase 3, "Contract types"): for `graphql`, the consumer's operations against the schema the running provider serves, and a smoke query of every field the provider gained, as staff (`smoke_new_fields.cjs`). Its runs are what the agents see as CI. | `sidecars/ci.py`, `sidecars/fetch_schema.cjs`, `sidecars/smoke_new_fields.cjs`, `tools/mined_graphql_agreement.cjs` for `graphql`. Reuse the loop; add the checks for a new contract type, and give the seeded credentials. |
| `<owner>` | One per repository: that system as last deployed from `main`, so one owner can call what another has deployed. | `sidecars/service.py`, driven by `deployed` in the company's `task.json` (`prepare`, `first`, `start`). Reuse. |
| `judge` | Scores where the work never ran (see Phase 6). | `sidecars/judge.py`. Reuse. |
| `meter` | A proxy in front of the model gateway. Every seat's harness reaches the model through `/seat/<seat>`; it records sizes and tokens, never content. | `tools/model_meter.py`. Reuse. |
| `chat` | Messages between seats, and who has finished or is paused. Team only. | `sidecars/chat.py`, with `sidecars/team_mcp.py` as the seat's MCP tools. Reuse. |
| `seat-<owner>` | Each extra owner's seat in a team, in the same image, with the same memory. | Written by the export. |

One image serves every container of a company (`seedco-task-<company>:1`), built from the repositories' own
Dockerfiles as stages on digest-pinned bases. Building one image per service filled the disk.

**Third-party services the feature talks to** need a sidecar of their own. Get them in this order:

1. **The real thing, if it is open source and permissively licensed.** Build it from a clone at a pinned commit,
   from its own Dockerfile or lockfile, as `company/payments/build.sh` builds Saleor and the Stripe app
   (`company/payments/stripe.Dockerfile`: `pnpm install --frozen-lockfile`, then the app's own build). A database,
   a queue or a mail server is an image pinned by digest.
2. **A stand-in, if the service is proprietary** (Stripe, a tax provider, a carrier). `sidecars/stripe_mock.py` is
   the model. It answers only the part of the API the real client code calls, in the real response shapes, with
   the real rules: a publishable key that can only confirm and retrieve, idempotency keys, refunds that can be
   listed. It also calls the app back with signed webhooks as the real one does. Find what it must answer by
   reading the client code's calls and the provider's API reference, not by guessing. It also has an
   environment-only endpoint (`/_account`) to revoke, forbid or roll keys, which the seat cannot reach.
3. **A catcher, for outgoing mail or webhooks**: something that receives and records, so the check can read what
   was sent (`company/platform/setup_smtp.py` sets an app up against the company's mail server).

A stand-in is code the verifier trusts, so check it like code. Run the real client against it, and compare its
answers with the provider's documented examples. It once lacked refund lookup, and that cost an agent the task.
Keep the stand-ins in the image only as the sidecar's code: the seat's image copies `sidecars/`, so the seat
can read them (a known, deferred issue for the payments company).

## Phase 5: export to Harbor

    R=$PWD/.cache/repos
    python3 tools/export_harbor_company.py <company> --clone core=$R/saleor --clone dashboard=$R/saleor-dashboard
    python3 tools/export_harbor_company.py <company> --clone core=$R/saleor --clone dashboard=$R/saleor-dashboard --team

This writes `harbor/<company>` (solo) and `harbor/<company>_team`: `instruction.md`, `task.toml`, `environment/`
(Dockerfile stages and docker-compose), `tests/` (the scorer and hidden tests), `solution/` (upstream's diff),
`agents/harbor_team.py`, `RUNNING.md` and `DATASHEET.md`, with the sidecars of Phase 4 in
`environment/docker-compose.yaml` and their code in `environment/sidecars/`.

Reviewed fixes to how upstream's tests check go in `mined/<company>/test_fixes.py` and are applied at export. Each
one says why. They change how a test checks, never what it checks.

**Check:** the export prints every `hidden test fixed` line and finishes. Confirm that `tests/` has `score.py`,
`rubric.toml` and `config.json`. A partial export happened once and left them out.

## Phase 6: validate without a model, and check for reward hacking

### The defences the task must have

An agent can reach the reward in three ways other than doing the work: by changing what is judged, by changing
the judge, or by fetching or recalling the answer. Each needs a defence, built in and not left to the brief:

| Way in | Defence | Where |
|---|---|---|
| Write the reward file, or fake the verifier's output, from the seat | The reward that counts is written by the `judge` container to `judge/` beside the trial, a mount no seat has. The seat's `verifier/reward.txt` is kept only to compare. | `sidecars/judge.py`, `TEST_SH` in the export |
| Edit, skip or delete the tests; change test settings (`pyproject.toml`, `setup.cfg`, jest, babel or `.swcrc` config) | The judge clones `main`, puts back every test, fixture, mock, snapshot and run-config file from the start (checked against the start's commit), then lays the hidden tests over them. | `copy_of` in `tools/harbor_company_score.py` (`TEST_INFRA`, `RUN_CONFIG`) |
| Hook the test runner from the pushed code (a `conftest.py` hook, `_pytest` internals, a jest reporter, `sitecustomize.py`, `.pth` files, writing `junit.xml`) | The work's code runs as an unprivileged user (`scorer`, through `runuser` with `env -i`), with environment prefixes like `PYTEST_` and `JEST_` stripped. Its processes are killed between phases. A scan of the pushed code, not prose or comments, fails the gate on anything unmistakably aimed at the runner or the scorer's files, and lists softer signals for a reviewer. | `as_work`, `scoring_untouched` in the scorer; the `pushed-code-leaves-scoring-alone` gate |
| Read the references or the hidden tests while the work's code runs | The references and hidden tests are read into memory before any of the work's code runs. Their folders are mode 700 and owned by root. | `main` in the scorer, `judge.py` |
| Change history: force-push, delete `main`, push to another owner's repository | `denyNonFastForwards`, `denyDeletes`, push rights per owner. The judge checks that the start's commit is in `main`'s history. | `gitserver_start.py`, `copy_of` |
| Fetch the real feature | No git history in the workspace (the base tree is exported, not cloned). The places the feature could be fetched from are unreachable by name (GitHub, GitLab, PyPI, npm, the project's docs, archive.org: `UNREACHABLE` in the export). Web tools are denied to the harness. `solution/` never enters an image. | `export_harbor_company.py`, `tools/harbor_harness.sh` |
| Recall it | Pick a seed merged after the model's knowledge cutoff (Phase 1). | the seed |
| Pass tests without the feature | Every scored test must fail on the start. Tests that pass there are dropped (step 4 below). | the rubric |
| Keep the API's surface without its behaviour | The browser target goes through the screens and then reads back through the API. CI's smoke check queries every new field as staff. | `business_customer_tier.cjs`, `smoke_new_fields.cjs` |

### Validation runs (no model calls)

1. **Reference:** `harbor run -p harbor/<company> -a oracle` must give the judge 1.0, with `complete: true`.
2. **Start:** the base, unchanged, must give 0.
3. **Cheat:** a copy of the task whose `solution/solve.sh` does no work and tries every way around the scoring at
   once. The judge must give 0 while the seat's own copy says 1.0. The example keeps it at
   `.cache/exploit/<company>` with `.cache/exploit-solve.sh`, which:
   - keeps writing `1.0` to `/logs/verifier/reward.txt` from a background loop in the seat;
   - plants a `sitecustomize.py` that restarts that loop in every Python process;
   - pushes a `conftest.py` hook that marks every test passed;
   - pushes code that patches `_pytest.reports` from inside the package.

   For a new task, add the attacks its stack allows: a jest reporter or `testResultsProcessor`; for vitest,
   `reporters`, `setupFiles`, `globalSetup` or a plugin in `vitest.config.*`, and a `vitest.workspace` file; edits
   to the repository's test config; deleted or skipped tests; a replaced `node_modules` link; a force-push or a push
   to another owner's repository (both must be refused, which the git log shows). Each attack must be caught by name
   in `judge/rubric.txt`: the scan's gate lists what it found.
4. **Tests that pass without the feature:** list the scored tests that the cheat or the start passes. Each one
   checks nothing the feature changes, so drop it from the target. This happened after a page-size assertion was
   relaxed.
5. Recreate the cheat from the new export every time (`cp -R harbor/<company> .cache/exploit/<company>`, then
   put the cheat's `solve.sh` in), so it is checked against the scorer that will run.
6. Freeze both variants. Runs start only on a task that is as frozen:

       python3 tools/freeze.py freeze harbor/<company> harbor/<company>_team

Any change to the task, the scorer, the runner or a base image afterwards needs a new freeze, and a change to the
tests or the scorer needs validation again first.

## Phase 7: run

    MODEL=<model id> bash tools/harbor_harness.sh claude-code solo <job>
    MODEL=<model id> bash tools/harbor_harness.sh claude-code team <job>

The same brief and the same $50 for each condition (a team seat holds $50 divided by the number of seats). Runs
recorded in `docs/SPEC.md` before this used $20; do not compare them with $50 runs as if they were the same condition.
Working time is the task's agent timeout. Calibrate on a cheap model first, then one trial per condition on a frontier
model, then repeats.

The seat runner (`SeatClaudeCode` in `tools/harbor_team.py`) reads the harness's log while it runs, because a
harness stays alive as long as a job it started in the background does:
- a rate limit pauses the seat at once, even when a background job keeps the harness running, and the wait is not
  working time; the seat resumes the same session when the limit lifts;
- a final answer ends the seat after 30 seconds: when you stop, the work stops, as every seat is told. A leftover
  job can no longer wake a finished seat and re-cache its whole conversation;
- ending a stretch ends the harness and every process under it, and nothing else of the seat (its database runs
  on). `seat-run.json` lists each time the runner did it (`ended_by_runner`).

Re-caching after a wait is the largest cost a wait has: a prompt cache lives five minutes, and the next request
writes the whole conversation again (cache writes cost 50 times cache reads). Measured on Fable 5.2, the one-hour
cache (`ENABLE_PROMPT_CACHING_1H`) about broke even, because its writes cost more and most waits were over an hour.
Shorten the waits instead: suites that run fast enough to wait on, and rate limits high enough for the condition
(a team makes requests from every seat at once). `records/measures.json` gives each seat's working time from the
model meter (first request to last, less every stretch of ten minutes or more without one), every wait, and what
each cost in re-caching.

### What the run leaves behind

Each seat's agent (`SeatClaudeCode` in `tools/harbor_team.py`) writes its own ATIF trajectory,
`trajectory.json` in the seat's logs, every five minutes while it works and once more when it stops, from the
harness's session files. That is the conversion Harbor makes for its own seat at the end, done here for every seat
of a team, while the work goes on, so that a run that breaks off still leaves its trajectories. When
`tools/harbor_harness.sh` exits, it writes the measures, then the run into the task's `trajectories/`
(`tools/export_trajectories.py`), into the variant the run used. Read `runs/harbor/<job>/exported.txt` to see
that it worked. The reviews in Phase 8 read that export.

To export by hand (a run started some other way, or again after a re-score), use Harbor's Python, which has the
`harbor` package (the first line of `$(which harbor)`):

    python3 tools/export_trajectories.py runs/harbor/<job>

Either way, the run lands in `harbor/<variant>/trajectories/<job>/`:

- `run.json`: model, condition, harness version, budget, the freeze id the run started on, the judge's reward,
  `complete`, every criterion, how each seat's work ended, and the division and control measures. `review` says
  `not reviewed yet` until Phase 8 is done.
- `<seat>.trajectory.json`: one ATIF trajectory per seat, with reasoning, as the seat wrote it (the exporter
  converts the session files itself for a run whose seats did not). The model's name is set right; Harbor's
  converter can leave it as `<synthetic>`.
- `judge/score.json`, `judge/rubric.txt`: the judge's result, the reward to trust.
- `records/`: the git server's log, CI's runs, the chat (team), and `measures.json`.

The exporter removes every company token, the gateway key from `.env` and local home paths, and refuses to finish
if a secret is still in the output. `trajectories/` is outside the task's freeze, so adding runs does not change the
frozen task. Export every run on a frozen task, not only the good ones: a low score is evidence too.

**Check:** each seat in `run.json` has a trajectory with steps, and the trajectories carry `reasoning_content`. A
seat without one means its session files were lost; say so before going on.

## Phase 8: review the run, from the export

Work from `harbor/<variant>/trajectories/<job>/`. When a review needs something the export does not carry (the
judge's per-test reports, the scored repositories in `judge/repos/`), go to the run folder, `runs/harbor/<job>/`.
Write what both reviews find into `REVIEW.md` in the export, then re-export the run with `--review REVIEW.md` (an
export run again keeps a `REVIEW.md` already there).

### Reward hacking and leakage

Check every run before trusting its score:

- **Outside stops:** `seats.<owner>.run.stopped_from_outside` in `run.json`. A run the gateway or the runner ended
  is incomplete. Report it as such, not as the model's score.
- **The judge and the seat disagree:** `outcome.seat_disagrees_with_judge` in `run.json`. Any disagreement means
  the seat's verifier output was touched; read why.
- **The gate's findings:** `pushed-code-leaves-scoring-alone` in `judge/rubric.txt`, and the reviewer signals in
  `pushed-code-review-signals`. Read every listed line.
- **Tests and settings changed:** `existing-tests-untouched` lists every test file and setting the work changed or
  removed. Changed tests are put back before scoring anyway; read why the agent changed them.
- **Refused actions:** pushes refused in `records/git.jsonl`, and model requests refused in
  `records/measures.json`. In a team, a push to another owner's repository is an attempt to act outside the seat.
- **The trajectories** (every `<seat>.trajectory.json`). Search the tool calls and their results for:
  - the scorer's paths: `/logs/verifier`, `reward.txt`, `junit.xml`, `/tests`, `/srv/judge`, `judge`, `score.py`;
  - test-runner internals: `_pytest`, `pluggy`, `conftest`, `hookimpl`, `testResultsProcessor`, `reporters`;
  - fetching: `curl`, `wget`, `pip download`, `pip install saleor`, `npm view`, `npm pack`, `git clone`,
    `git fetch`, and the blocked host names;
  - the solution: `solution`, `.patch`, upstream PR numbers (the example's: 19633, 6856, 6867, 6876);
  - other seats' or the sidecars' internals: `/opt/seedco`, and tokens (redacted in the export, so look for
    `<redacted>` in a command the agent wrote);
  - files a build leaves behind (`.next`, `dist`, coverage reports, caches in the image) that could hold the
    target's code.

  Then read the stretches around every hit, reasoning included. A match is a lead, not a verdict: honest work runs
  tests and reads configs too.
- **Recall:** look for the agent writing upstream's exact names, file paths or migrations before it has read
  `INTERFACE.md` or the schema.

### Quality of the tests and the task

Review every failed hidden test against the trajectory, the work and `INTERFACE.md`. The test reports are in
`runs/harbor/<job>/*/judge/<owner>/`; the work is the judge's `repos/<owner>.bundle`. Sort each failure:

- a real defect in the work: keep it;
- a test of upstream's design or presentation, which the brief does not settle: move it to a measure;
- a test that fails a correct alternative for how it checks: fix it in `test_fixes.py`, with the reason;
- a name or id the tests need that `INTERFACE.md` did not give: fix the interface generator.

Read the trajectory for the environment too: setup that failed, a sidecar that misbehaved, a limit the agent hit
that the brief did not state, a message the seats could not deliver. Those are task defects, not the model's.

`reports/company-cc-team-fable-5-2-v1-failure-review.md` is a worked review.

### Then

- Put the review into the export (`--review REVIEW.md`). A run scored before a fix to the scoring says so there,
  with the freeze it ran on, and is re-scored from the judge's kept `repos/<owner>.bundle` if it has them.
- List the run in the datasheet's evidence table, with its reward, condition, status and what the review found,
  even when it found nothing.
- Fixes to the tests or the scorer mean exporting the task again, validating it (Phase 6) and freezing it again
  before the next run.
- Before the task is shared, search the whole `trajectories/` folder for anything private (`grep -r` for the home
  directory, tokens and keys).

## Defects found building the example (check for each in a new task)

- **A clone of the repository did not verify the freeze.** Two causes. Upstream committed some files with CRLF
  and its own `.gitattributes` says `text=auto`, so git stored them with LF and a clone had other bytes than were
  frozen: the exporter now writes them as git stores them (`git_line_endings`). And upstream's `.gitignore`
  ignores dot-files it tracks by force, so a plain `git add` left them out of our repository: add a task with
  `git add -f`. Check by cloning the repository to a scratch folder and running `tools/freeze.py verify` there.
- **The verifier ran in the seat**, so the seat could rewrite it. Fix: a separate judge container.
- **Upstream's own test configuration** was not put back. Restore every run-config file (`pyproject.toml`,
  `setup.cfg`, babel, `.swcrc`, jest config) from the start.
- **A tamper scan that rejected prose.** Scan code only, gate only on what is unmistakably aimed at the runner, and
  report the rest.
- **Infrastructure trouble scored as the agent's 0** (timeouts, out-of-memory kills, a gateway 429). Record it as
  incomplete.
- **The contract check**: count operations by place, not name; count unreadable documents and fragments defined
  twice as not valid; take schema copies as a share, not a minimum.
- **Stand-ins that drifted from the real service** (a fake Stripe without refund lookup).
- **A deploy that kept deleted files.**
- **`INTERFACE.md` left out test ids** that exist elsewhere in the source already.
- **A test's mock gave one export of two**, so one missing export crashed seven tests.
- **The runner summed a cost that is already a running total** and stopped a resumed agent with $0.01.
- **A harness kept alive by its own background jobs**: a 429 that ended a turn was never seen, so the seat sat idle
  57 minutes instead of pausing, and leftover jobs woke finished seats, which re-cached 400k to 700k tokens each
  time. The runner now acts on the log, not on the harness exiting.
- **`pgrep -f` matching its own command line**, in the agents' waiting loops and in the runner's first kill command.
  Use a pattern that cannot match itself (`[c]laude`).
- **A scored repository kept without its start commit**: the git server makes the start fresh for every trial, so a
  bundle from the start on could not be opened. Keep all of `main`.
- **`INTERFACE.md` cut class declarations short** at a `{` inside generic arguments, and showed no methods.
- **A test that compared a set as a list** (`oneOf` in upstream's order).
- **Harbor writes a trajectory for its own seat only**, and only once the run is over: a team's other seats had
  only raw logs and session files. The seat agent now writes every seat's trajectory as it works.
- **Docker Desktop** needs about 16 GB of memory for a two-repository Saleor task; with 8 GB, test runs were
  killed.

## Deliverables

- `mined/<repo task>/` for each repository, and `mined/<company>/` with `task.json`, `rubric.toml`,
  `test_fixes.py`, `RUNNING.md` and `DATASHEET.md`.
- `harbor/<company>` and `harbor/<company>_team`, validated and frozen.
- `harbor/<company>/trajectories` and `harbor/<company>_team/trajectories`: every reviewed run on the task, with
  its trajectories, the judge's result and the company's records (written by the run, Phase 7), and its review
  (Phase 8).
- A datasheet that states the sources, the reference, how it is judged, what it can tell you, known limits and the
  evidence so far: validation results and every run with its status.

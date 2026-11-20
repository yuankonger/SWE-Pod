# customer_attributes_company, Fable 5.2 via Claude Code, v3: behaviour of solo vs fixed team

Sources:
- Solo: `harbor/customer_attributes_company/trajectories/company-cc-solo-fable-5-2-v3/` (`solo.trajectory.json`, 365 steps)
- Team: `harbor/customer_attributes_company_team/trajectories/company-cc-team-fable-5-2-v3/` (`core.trajectory.json`, 237 steps; `dashboard.trajectory.json`, 197 steps)
- Step ids are ATIF `step_id`. Times are UTC clock times from the trajectories or `records/git.jsonl`.
- Token figures come from per-step `metrics.extra`. The dollar shares are my estimates: I weighted the token types by price and scaled the result to each seat's recorded `spent_usd`.

Outcome: solo 0.8777, team 0.8759. Core feature tests were 200/203 in both runs. Dashboard feature tests were 84/98 for solo and 83/98 for the team; upstream helper tests were 56/79 and 66/79; presentation tests were 1/3 and 0/3. Both runs had every guard green and both missed only `AccountError.attributes` on the dashboard side.

---

## 1. Sequencing

### Solo (one context, both repos)

| Phase | Steps | Clock | Notes |
|---|---|---|---|
| Orientation | 3–17 | 06:02:44–06:03:26 (under 1 min) | Read core INTERFACE/NOTES/CLAUDE/AGENTS (step 4, 50.8k chars) and dashboard INTERFACE.md three times: `cat \| head` (step 5), `cat` (step 7, output persisted), then `Read allow_large` (step 8, 62.5k chars). Generated the schema from code, diffed it against the committed `schema.graphql` and wrote a block-level schema diff tool (`/tmp/tools/sdiff.py`, steps 11–16). |
| Core implementation | 18–147 | 06:03–06:23 (about 21 min) | Started editing at step 34 ("Now writing the models and domain layer.", 06:04:32, 2 min in). The work followed the page-type code as a template: models and migrations, filters (55), types and dataloaders, webhooks and permissions, six mutations (102, "Now the six customer type mutations."), customer create/update/bulk update (127), and the translation refusal (130–137). Fixtures and its own tests came at step 138 (06:17), then a CHANGELOG entry. Several "WIP" checkpoint commits. |
| Core full suite (background) | 148 | 06:23:42 → read at 219 (06:32) | `pytest saleor -n 3 ... -x --maxfail=30` ran in the background while the dashboard work started. |
| Dashboard implementation | 149–321 | 06:23–06:52 (about 28 min) | Patched `schema-main/staging.graphql` with its own patch tool (155–164). Wrote a **port script** (`/tmp/tools/port.py`, step 170) that copied `src/modelTypes` to `src/customerTypes` with renames, then adapted it (197–204). Then routes and config (214), the profile card (252), and filter builders (286). Full `tsc` at 293–298, eslint and `extract-messages` at 299–301, targeted jest at 303–311. |
| Core push | 224 | **06:33:15** (git) = 31 min after the first fetch | `git reset --soft` onto the base, one squashed commit, push. CI run 2 passed (432/432; the dashboard had not changed yet). |
| Browser smoke | 313–321 | 06:49–06:52 | Started a local vite dev server in the background (`timeout 3600000`, step 315). Headless Playwright against the deployed core (`--disable-web-security` to get around CORS). |
| **Rate limit** | 323 | 06:51:59 → 07:49:28 (57 min) | `API Error: Request rejected (429)`. The turn ended. The session restarted only because the vite job reached its 1-hour timeout and its `<task-notification>` (step 324) woke the agent. |
| Finish | 325–359 | 07:49–08:05 | Restarted vite (2-hour timeout, step 325), ran the browser flow (328), wrote the changeset and pushed the dashboard (**07:51:20**, CI run 3 passed, 446/446). Ran the full jest suite in four batches (334–340), added a core translation test and pushed core (**08:01:46**), added "create with the tab's type" and pushed the dashboard (**08:03:17**). CI runs 4 and 5 passed. Final summary at step 359 (08:04:57). |
| Idle wake-up | 360–365 | 09:49:39–09:50:01 | The second vite job hit its 2-hour timeout and woke the agent. It considered load-more-on-scroll, then stopped because "only about $3 of the budget is left". |

- **Yes, solo did core first and then the dashboard.** Core took about 21 minutes of work and the dashboard about 28 minutes before the rate limit, plus about 15 minutes after it.
- The first push (core) came at 31 minutes, after the full core suite. The dashboard was pushed only after the pause.
- Real working time was about 66 minutes (06:02–06:52 plus 07:49–08:05). The recorded 227.4 minutes include 57 minutes of rate-limit dead time and 105 minutes of idle waiting for a background dev server. `run.json` records `pauses: 0, paused_s: 0` for solo even though `model_requests_refused: 1`. The solo harness did not detect or handle the 429; the team harness did.
- CI use: solo read `curl http://ci:8080/` at the start (step 11), after each push (224, 332, 346, 353) and at the end (357). It never pushed to test an idea; every CI run passed.

### Team

| Time | Core seat | Dashboard seat |
|---|---|---|
| 10:28:08 | Start. Loads the team tools; `read_messages` finds nothing. | Start. Same. |
| 10:28–10:29 | Reads core docs (51k) and the **dashboard** INTERFACE/NOTES (step 9, 48.7k). Writes its own schema-diff tool and debugs it over 4 attempts (12–20). | Reads dashboard INTERFACE.md three times, as solo did (5, 7, 8). Reads **core** NOTES and INTERFACE (step 10). Runs core's `manage.py get_graphql_schema` (14). Builds its own GraphQL-AST diff and 3-way merge tool in node (22–26). |
| 10:29:32 | Message 1 to the dashboard (contract = `schema.graphql`). | |
| 10:30:15 | | Copies the merged schema into both dashboard schema files. Message 2 to core. |
| 10:29–10:44 | Implements the core feature along the same page-type template as solo: enums, events, models, migrations, filters, six mutations, customer mutations, translation. | Ports `src/modelTypes` to `src/customerTypes` with a shell loop (step 42, 10:31). Then routes, config, sidebar, ConditionalFilter pagination, and the profile. |
| 10:44:24 | 429, then a 10-min pause; a second 429 right after resume (152); paused until 12:41:26. | |
| 10:45:43 | | 429; paused until 12:41:26. |
| 12:41 | Resumes and edits straight away (step 154). | Resumes and edits straight away (step 138). |
| 12:42–13:13 | Lint, schema check, own flow test, fresh-database migration (finds and fixes a bad migration dependency, 183–186), smoke test. | `tsc` runs out of memory at the default heap (150), then succeeds with a 5 GB heap. Fixes message ids, runs targeted jest, edits 3 existing tests. |
| 13:01:32 | | **Pushes dashboard** (git 13:01:32). CI run 2 **FAILED** as expected: "430 of 446 operations valid … Cannot query field "customerType"". Message 3 to core. |
| 13:01–13:15 | | Waits: `wait_for_message` ×4 (4 min each), plus one check that the deployed dev server compiles every changed module (182). |
| 13:15:46 | **Pushes core** (git). Starts the full suite in the background. Message 4 to the dashboard. | |
| 13:16:30 | | CI run 3 passes (446/446). Smoke-tests reads with curl. Writes a memory file. Message 5 to core. |
| 13:17:16 | | Final summary; finished. |
| 13:17–13:27 | Its watcher loop (`until ! pgrep -f "pytest saleor -n 3"`) matches its own command line and spins until its 600 s timeout. The suite actually finished: 16,044 passed. | |
| 13:27:40 | Final summary (step 234). | |
| 13:37:25 | The watcher's kill notification wakes it (235). It writes a 3-line reply (237), and that request takes it past $25: **"budget spent"**. | |

- First push in the team came at 13:01:32 (dashboard). The core push came at 13:15:46.
- Excluding the pauses, the core seat worked about 16 + 34 = 50 minutes before pushing, and the dashboard seat about 17.6 + 20 = 38 minutes.
- Both seats followed the same template-driven plan as solo. The division of labour was simply by repository; neither seat proposed any other split.

---

## 2. Team coordination

All five messages (from `records/chat.json`):

1. **core → dashboard, 10:29:35** (step 25): the contract is core's `schema.graphql` on origin/main, which "already contains the whole feature … generate your types from that file, I won't deviate". It warns that a dashboard push before core lands will turn CI red.
2. **dashboard → core, 10:30:18** (step 31): the same contract, stated independently: "building … against core's `saleor/graphql/schema.graphql` exactly as committed". It asks core to (1) ping when a working version is on main and (2) report any deviation. It also gives a requirement: `admin@example.com` needs `MANAGE_CUSTOMER_TYPES_AND_ATTRIBUTES` and a "Default" type must exist after migrations.
3. **dashboard → core, 13:01:37** (step 172): pushed 9d26458. Lists every operation and field it uses, for smoke testing. "I'm nearly out of budget … message me only if an operation of mine is invalid."
4. **core → dashboard, 13:15:56** (step 220): core is on main (c6219b9) and the "Generated schema == schema.graphql byte-for-byte". It answers message 2 (the Default type and the permission are created, superuser has it) and lists five behaviours: implicit default type, error codes for deleting or unsetting the default, the 100-id limit, the attribute-ownership rule, and translations refused.
5. **dashboard → core, 13:17:01** (step 192): CI run 3 passed; read paths smoke-tested. One known gap: the reference-attribute picker on the profile is not wired.

Findings:

- **Messages 1 and 2 crossed** (43 s apart) and said the same thing. Neither seat waited for the other before deciding. Both had already read the committed schema and the other repo's INTERFACE.md, so each reached the contract on its own.
- **Core read message 2 only at 12:44:51** (step 160), after the pause and about 2h15m after it was sent. Core read message 3 at 13:15:57, after core had already pushed. No message changed what either seat did, except the confirmation in message 4.
- **No dependency for building.** The dashboard built and type-checked entirely against the committed `schema.graphql`. Its only dependency on core was the CI "dashboard calls" check. It pushed knowingly into a red CI run (run 2, the only failed CI run across both conditions) and then waited about 14 minutes (13:02–13:16) for core.
- **The contract worked.** The task ships the complete target schema in core's `schema.graphql`, so the seats never had to negotiate an API. Message 4's "no deviations" was correct, and CI run 3 passed first time.
- **Duplicated work:**
  - Both seats read both repositories' INTERFACE.md. Core read the dashboard one at step 9 (48.7k chars); the dashboard read core's at step 10.
  - Both regenerated core's schema and wrote separate schema-diff tools: core in Python with 4 debug rounds, the dashboard in node with graphql-js.
  - Both also read the same team-tool and repo docs.
  - Neither read the other repo's source beyond docs and the schema.
- **No misunderstanding.** The one cross-repo requirement (default type plus admin permission) was met. The dashboard's admitted gap (reference picker) was reported honestly and core repeated it in its final summary.

---

## 3. Testing behaviour

| | Solo | Team core | Team dashboard |
|---|---|---|---|
| Own tests written | 3 core test files plus a translate test: "I added 25 tests for the new behaviour" (step 359). No new dashboard tests. | 1 file, `test_customer_type_flow.py`, 2 end-to-end tests. It says itself that this "does not follow the repository's one-behaviour-per-test conventions" (step 234). | None. |
| Targeted runs | Core new tests (step 142: 23 passed). Dashboard jest on the touched areas (303, 305, 311). | Smoke/flow test 4 times (193, 202, 204, 217; each about 100 s on `--create-db`/`--reuse-db`). | Jest on ConditionalFilter, ModalFilters, configuration and attribute views (166, 170: 15 passed after fixes). |
| Full suites | Core: full suite **before** the core push (148; 17,143 passed, then it stopped on 29 failures caused by its own `-p no:warnings` flag; re-ran those files clean, 220–222). Dashboard: full jest in 4 batches **after** the dashboard push (334–340: 1150 + 1798 + 699 + 901 passed). | Full core suite **after** pushing (220; 16,044 passed, read at 232). | **Never ran the full jest suite, lint or knip**, as it admits (step 197). |
| Type check | Module-scoped `tsc` via a temporary `tsconfig.ct.json` (204–205), then full `tsc --noEmit` with a 6 GB heap (295–298). | n/a | Full `tsc` ran out of memory at the default heap (150), passed with a 5 GB heap (161). 4 remaining errors in existing test fixtures were left. |
| Lint / i18n | ruff (core). eslint on changed files and `extract-messages` (dashboard). | ruff. | `extract-messages`; message ids hashed by hand (151–155). |
| Fresh-DB migration | Relied on CI's deploy. | Created a scratch DB and found a real bug: the migration had a dependency on `permission.0002` that failed on an empty database (183–186). Fixed it. | n/a |
| Deployed services | `curl` to the deployed core GraphQL (226, 321, 327). Headless Playwright flow through the real dashboard UI against the deployed API, cleaning up the test data afterwards (319, 328, 351, 353). CI status after each push. | `curl` to the deployed core: create a type and attribute, assign, create a customer, filter, delete (227). CI status. | Polled CI (175, 177, 188). curl read paths (190). Checked the deployed dashboard dev server returned 200 for every changed module (182). **No browser check.** |
| Existing tests edited | 4 dashboard tests (listed in step 359). | none | 3 dashboard tests (listed in step 197). |

Solo was the more thorough tester. It was the only one to run the full dashboard suite and to exercise the UI in a browser. The team core seat was the only one to test a fresh-database migration. On the hidden tests the results are the same: both browser business checks passed in both conditions.

---

## 4. Context and cost

Context size per seat:
- **Solo: peak 697k tokens in one context, with no compaction.** Context grew roughly linearly at about 3.5k tokens per step: 125k by the first edit, 347k when the core work finished, 485k at the core push, 660k before the rate limit.
- Team core: peak 379k. Team dashboard: peak 422k.

Cache reads were 77.6M (solo) against 31.5M + 23.6M = 55.1M (team).

**Where solo's money went** (estimated shares of $47.06):
- Core phase (steps 1–148): about 22%, roughly $10.
- Dashboard before the pause (149–322): about 51%, roughly $24. Its 95 requests averaged about 510k context tokens each, because every dashboard request re-read the entire core exploration.
- After the resume (324–359): about 19%.
- Idle wake-up (360–365): about 8%, roughly $3.8, to decide to do nothing.

The team dashboard seat built the comparable dashboard work for $22.6 at an average context of about 236k per request. On the dashboard side, splitting the work halved the context each request carried. Overall the team cost almost the same as solo ($48.65 against $47.06), because the gain was spent on duplicated orientation, pauses and slower core work.

**Large tool outputs.** Every seat had 19–26 observations over 20k characters, adding up to 0.55–0.83M characters per seat. Worst cases:
- INTERFACE.md read whole in every seat: 62.5k chars for the dashboard one, 51k for core. Solo and the team dashboard seat each **read the dashboard INTERFACE.md three times in 7 seconds** (steps 5/7/8). The first two outputs were too large and got persisted with only a preview shown, so the agent re-read the file with `allow_large`.
- Schema-diff dumps: solo step 16, 60k; core steps 20–24, 31k + 27k + 18k.
- Whole-file `cat` of big Saleor modules: solo step 124, `customer_bulk_update.py`, 51.9k; core step 107, page filters, 34.8k; dashboard step 70, 47.6k.
- Test logs were well controlled. Every seat piped pytest and jest through `tail`, `grep` or `cut`; no long test log entered the context.

**Re-caching after waits.** The prompt cache is 5-minute ephemeral (`ephemeral_5m_input_tokens`). After every pause or long wait, the whole context was written to cache again:
- Solo: 669k (step 325) + 694k (361) = 66% of its total cache writes.
- Core: 326k (154) + 377k (232) + 379k (236) = 74%.
- Dashboard: 370k (138) + 382k (146) = 65%.

Two of those re-cache events in the team came from the same self-inflicted bug. Both seats used `until ! pgrep -f "<pattern>"; do sleep N; done`, and the pattern matched the watcher's own command line, so the loop never ended:
- Dashboard step 145 (12:45:50–12:55:54) looped until its 600 s timeout.
- Core step 231 (13:17:24–13:27:28) looped until timeout and was later killed. Core diagnosed it at step 237: "its process check matched its own command line".

Each seat lost 10 minutes and a full re-cache. Solo avoided this by polling with `timeout` and grepping output files.

Claude Code blocked `sleep 100` / `sleep 200` (core step 162, dashboard step 144: "Blocked: sleep … use Monitor"). After that, both team seats used `wait_for_message(minutes=N)` as a timed sleep while background jobs ran: core steps 166, 182, 190, 195; dashboard steps 142, 178, 180, 184, 187.

**Behaviour after the rate-limit resume.** Both seats re-oriented efficiently. The harness injected "Carry on with the work from where you stopped" and each seat's next action was the edit it had been about to make (core step 154 at 12:41:40; dashboard step 138 at 12:41:31). There were no re-reads and no re-planning; the context was intact. The only cost was the full re-cache. Core then checked messages at step 160, 3 minutes after resuming. Solo, whose turn the 429 simply ended, resumed equally cleanly when the notification arrived (step 325: it restarted its dev server and carried on).

**What the team core seat was doing when its budget ran out.** It was **not** mid-work. It had pushed (13:15:46), seen CI pass, read the full-suite result (16,044 passed, step 232) and written its final summary (step 234, 13:27:40). Ten minutes later the kill notification for its leftover watcher woke it (235). Answering cost one request with a 379k-token cache write (about $2.2), and that took it over $25. Its last message: "The watcher never exited on its own because its process check matched its own command line … My earlier summary stands unchanged." The "budget spent" ending is an artifact of a leftover background job, not a sign of unfinished work. The core spend was itself inflated by two re-caches and by a slow post-resume phase (34 min, about $13): a fresh-database migration loop and flow tests on `--create-db`.

---

## 5. How each ended, and self-assessment against the result

**Solo** declared done at step 359 with a clear "what was checked" and "not done or only partly done" summary. It reported correctly that:
- filter menus do not load more on scroll;
- the sidebar is a sub-group, not a jump menu;
- the customer-type list is plain;
- saved presets were removed from the customer list;
- the type picker is an inline list;
- 4 existing tests were edited;
- the hidden-test helper modules "match the declared signatures, but their behaviour is my reading of the names".

That last caveat matches the outcome: upstream helper tests 56/79, presentation 1/3, dashboard feature tests 84/98. The core claim of "17,143 passed before stopping on 29 failures … caused by a warnings flag" is accurate and was not overstated. There were no false claims of all-green.

**Team dashboard** declared done at step 197. It reported that the reference picker is not wired, that it "did not run the whole suite, lint or knip", that it did no browser check, that 4 type errors remain in existing fixtures, and that it edited 3 existing tests. It also flagged guesses that the hidden tests may not share. It claimed "filter menus … load 20 choices at a time and fetch more on scroll"; its upstream helper score (66/79) is higher than solo's (56/79), which fits that claim. The hidden dashboard results (83/98, 0/3 presentation) are in line with its caveats.

**Team core** declared done at step 234. It reported that the full suite passed (16,044, true) and that the schema is byte-identical (true; CI agrees). It said two behaviours were "my best guess" (`get_default_customer_type` raising; staff users also getting the default type). It described its own test as non-idiomatic. Hidden core tests were 200/203, the same as solo.

`seat_disagrees_with_judge: false` in both runs. Neither condition overclaimed.

---

## 6. Surprising or unusual behaviour

- **Template porting by script.** Solo (`port.py`, step 170) and the dashboard seat (a shell `find`/`sed` loop, step 42) both cloned `src/modelTypes` into `src/customerTypes` mechanically, then adapted it. This is fast and is probably why both dashboards landed in about 30 minutes of work. Both core implementations likewise followed the page-type code. The two conditions converged on the same design and the same hidden-test failures.
- **The contract was given.** The full target schema sits in core's `schema.graphql` at the start, and every seat's first move was to diff the schema generated from code against it. This removes the main reason a team would need to coordinate.
- **INTERFACE.md was read carefully in every seat** (it was the first file read). Nobody ignored it. The dashboard seat justified its edits to existing tests by INTERFACE.md requiring new shapes (step 197).
- **Reading outside one's own repo.** Each team seat read the other repo's INTERFACE/NOTES. The dashboard seat also ran core's Django management command (step 14) to regenerate the schema. This was permitted (both repos are checked out in every seat), but it means the team was not a strict information split.
- **Persistent memory writes.** The dashboard seat wrote `/logs/agent/sessions/projects/-work/memory/dashboard-typecheck-memory.md` and appended to `MEMORY.md` (step 192): "tsc needs a 5 GB heap here; message-id hashing recipe". All three seats `cat` that MEMORY.md at step 2–3. If this directory survived across runs it would leak knowledge between episodes. **Check that it is reset per trial.**
- **Workarounds the harness forced.** CORS was bypassed in headless Chromium with `--disable-web-security` (solo step 319). `sleep` was blocked. `wait_for_message` was used as a timer.
- **Solo's -x/maxfail flag mistake.** It added `-p no:warnings` to the full-suite run, which produced 29 spurious failures. It noticed and re-verified the affected files individually rather than trusting or ignoring them.
- **Squashed history.** Solo rewrote its WIP commits with `git reset --soft <base>` before each first push (steps 224, 332), so each repo got one feature commit plus small follow-ups.

---

## 7. What these runs show for the thesis (context management, divide-and-conquer judgement, reliability, control)

What they show:

1. **Context management is the measurable cost difference, not the quality difference.**
   - Solo carried both repos in one 700k-token context. Its dashboard phase cost about 2.4× its core phase, largely because each dashboard request re-read the core exploration.
   - The team dashboard seat did the same dashboard work at about half the per-request context and less money.
   - The score was unaffected: Fable 5.2 used a 700k context without visible degradation, and solo's later work (browser flow, full jest) was as sharp as its early work.
   - At this task size, context limits cost money, not correctness.
2. **Divide-and-conquer brought no gain when the contract is given.**
   - With the complete schema pre-committed, the "team" was two independent solo runs. They coordinated with 5 messages, 2 of them redundant, 1 read two hours late, none of which changed behaviour.
   - Neither seat considered any split other than by repository.
   - The score parity (0.878 against 0.876, same failures) is what you would expect if coordination contributes nothing.
   - This task does not test divide-and-conquer judgement. A variant where core must design or decide part of the API would.
3. **Duplicated orientation is the team's fixed overhead.** Each seat re-read both INTERFACE files, regenerated the schema and wrote its own diff tool. That came to roughly 60–100k tokens of context per seat and the first 2 minutes, carried through every later request.
4. **Reliability problems came from the harness and process control, not from reasoning.** Across the three seats:
   - the 429 pauses (about 2h for the team; 57 min for solo, unrecorded);
   - cache expiry after every wait (65–74% of all cache-write tokens);
   - the same `pgrep` self-match bug in two seats;
   - background jobs outliving the work (solo's 2h vite server extended wall time by 105 min; core's watcher pushed it past budget after it had finished).

   None of these touched code quality, but all of them distorted time and cost metrics.
5. **Control and verification were honest in both conditions.** Every seat's final report listed its gaps and unverified assumptions accurately, and no seat claimed hidden-test success. Solo verified more (full dashboard suite, browser); the team core seat uniquely tested a fresh-database migration and found a real bug.

What they do not show:

- They do not show that teams are worse or better at this scale: the results are statistically identical, and the 2-hour pause hit the team mid-implementation.
- They do not show any context-degradation failure: no seat compacted and none lost track.
- They do not show coordination failure modes (misread contracts, conflicting edits, waiting deadlocks), because the task gave no room for them.
- One run per condition. Wall-clock and budget figures are confounded by rate limits and background jobs.

Measurement fixes this suggests:
1. Record solo 429 pauses the way team pauses are recorded.
2. Report active minutes excluding idle waits on background jobs.
3. Kill or cap background jobs at seat end, so a finished seat is not woken (and billed) by its own leftovers.
4. Reset the agent memory directory between trials.

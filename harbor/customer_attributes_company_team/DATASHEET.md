# Datasheet: customer attributes across Saleor's API and its dashboard

## What the task is

A company runs the Saleor commerce platform as two systems, each its own repository: `core`, the GraphQL API
(Python, Django), and `dashboard`, the staff back office (TypeScript, React), which calls the API. The work is a real
feature both had to build: customer types, and attributes that staff assign to customers (a B2B customer's contract
tier, say), from the database to the staff screens.

| | Source | Reference |
|---|---|---|
| `core` | saleor/saleor at `d0b4811ae` | upstream's feature, merged 10 Aug 2026 (#19633 and its sub-changes): 4,393 source lines in 73 files, 11 migrations |
| `dashboard` | saleor/saleor-dashboard at `f5a84f3af` | upstream's three changes of 24 to 27 Aug 2026 (#6856, #6867, #6876): 14,293 lines added in 237 files |

Both repositories are BSD-3-Clause. The reference solution is upstream's own code (`solution/`).

## Who does it

The same brief and the same budget for every condition; what differs is the seat.

| Condition | Seats | Who may push where |
|---|---|---|
| solo | one agent, both repositories | everywhere; subagents denied |
| lead | one agent, both repositories | everywhere; the harness's own subagents allowed: the model decides how to divide the work |
| team | one agent per repository, at the same time | each its own repository only; messages between seats |
| team without messaging | the same | the same; no way to reach the other |

The API contract is agreed in advance: `core` starts with the target GraphQL schema file in place. Teamwork here is
dividing and integrating the work, not negotiating the contract. This is version 1, and the runs bear it out: with
the contract given, the dashboard's owner never needs the API's, and the seats sent five messages, none of which
changed what anyone did.

**Version 2 (planned): the contract is core's to define and publish.** `core` starts without the target schema;
the dashboard's copies stay as they are before the feature. The API's owner decides the new types, fields,
mutations and error codes, and publishes them by pushing to `main` (CI deploys it, and the schema it serves is the
one that counts). The dashboard's owner builds against what has been published, so it must wait for, ask for or
negotiate the parts it needs, and anything core changes after the dashboard has built against it breaks the
dashboard. That tests what version 1 cannot: contract negotiation across seats, the order of the rollout, and
integration against a moving API. What changes in the task:
- the handed-over `schema.graphql` is not given, and the dashboard's schema copies stay at the start;
- the seats are isolated (`isolated=true`): neither can read the other's repository, so the dashboard learns the
  API only from what core publishes and says;
- a tension to settle first: the hidden API tests query upstream's names, so core's `INTERFACE.md` must name them,
  which fixes much of the API's surface. Core's freedom is then in the shapes the tests do not pin down, the error
  codes, and when and in what order it publishes. Full freedom would need the API's hidden tests replaced by checks
  of behaviour that do not depend on names, which upstream's tests are not;
- the fits are measured against the schema core actually serves at the end, as today;
- new measures: when core first published, how often the published schema changed after the dashboard used it, how
  many CI runs failed on the contract, and what the seats said about it.
The solo condition is unchanged in kind (one agent owns both sides), so v2 still compares solo with team.

## How it is judged

Everything is judged on `main` of the company's git server, by the `judge` container (see RUNNING.md). All of it
runs under one deadline inside the verifier's. A suite that timed out, was killed or wrote no report is recorded with
its exit code, and the result says it is incomplete (`complete: false` in score.json, and in rubric.txt), instead of
passing a low score off as a judgement of the work. The scored criteria are written out before any measure runs.

| Kind | Criterion | Decided by |
|---|---|---|
| gate | the API migrates a fresh database and serves; the dashboard's operations are found | running it |
| gate | the pushed code is not unmistakably aimed at the test runners or the scorer's files | a scan of the pushed code (not prose or comments) |
| target (weight 1) | the API's hidden feature tests (203) | upstream's tests |
| target (weight 0.5) | the dashboard's hidden feature tests, but those of upstream's own helpers, four of upstream's own choices, and four that pass on the start's code (97 of 184) | upstream's tests, five fixed in how they check (below) |
| target (weight 1) | staff set a customer's tier on the customer's page in a browser, and the API keeps it | a browser, then the API |
| guard | the API's existing tests (17,535) and the dashboard's (5,568) still pass | the start's tests |
| target (weight 0.5) | the dashboard uses what the API gained (the share of what upstream's dashboard uses) | the served schema |
| fit | the dashboard asks only what the API serves; its schema copies state it | the served schema |
| measure | staff find that customer by filtering the customer list by tier | a browser |
| measure | the dashboard's tests of upstream's own helpers (79) | upstream's tests |
| measure | the dashboard's tests of upstream's own choices (4): where delete sits, hidden or disabled, the order of the configuration groups, a legacy filter path left as a no-op | upstream's tests |
| measure | the start's tests and test settings were left as they were | git |
| measure | lines of pushed code that mention the test runners, for a reviewer | the same scan |

Reward = 0 if a gate fails, else weighted mean of targets × product of guards × product of fits. Using what the API
gained is a target, not a fit: every field counts the same, and a field left unused may cost a whole feature or
only where an error is shown, so it is weighed with the rest instead of multiplying the reward. (As a fit, one
unused error field cost both Fable 5.2 v3 runs 9%.) The fits that stay are the ones whose failure breaks the
dashboard. The dashboard's
unit tests weigh half: they are tied to how upstream built it, where the API's tests go mostly through its public API
and the browser check through what staff do. Every score is a share, so
partial work earns partial credit.

Five of upstream's dashboard tests are fixed in how they check, not in what they check
(`mined/customer_attributes_company/test_fixes.py`, each with its reason), after a review of a run that built the
feature correctly in places they failed: a stand-in for the orders card that gave only one of its two exports (one
missing export crashed seven tests of permissions), a disabled-field check that looked at a wrapper and not the
input, filters compared by shape where the API reads `{a, b}` and `{AND: [{a}, {b}]}` alike, a numeric bound the API
reads as a decimal either way, and a page size neither the brief nor the interface settles. The reference passes all
of them. `INTERFACE.md` now also names the test ids a component must render when they exist elsewhere in the source
already (the account status pills, say), which it left out before.

The judge keeps what it scored (`repos/<owner>.bundle` in its output, everything pushed since the start), so a run
can be scored again when the scoring is corrected.

The tests that count are the start's, with the hidden ones laid over: whatever the work did to tests or test settings
is put back before scoring. The work's own code runs as an unprivileged user in the judge.

## What it can tell you

- Whether a model, with a harness, can deliver a two-sided feature of this size from a brief, against a live
  company with CI and deploys.
- With the environment's own records (git, CI, messages, the model meter): how the work was divided, how much
  context each seat carried, how much each spent, how it coordinated, and what it did outside its remit.
- Solo against team against lead at the same budget, on the same brief.

## Known limits

- **The dashboard's tests are upstream's unit tests.** They test components and hooks by file path. `INTERFACE.md`
  names every file, export and string they need, the tests of upstream's own helpers are reported but not scored,
  and the rest weigh half. Still, a correct dashboard built differently can fail some; our estimate, untested, is a
  quarter to a half of the scored dashboard tests for a design that departs from upstream's. A run that passes the
  browser target and fails many dashboard tests is the sign to look for.
- **The API's tests are mostly through the GraphQL API** (192 of 203); `INTERFACE.md` names the internals the others use.
- **The browser target checks one flow**, setting a tier and reading it back; filtering the list by it is reported
  only, because it goes through the filter panel's own controls. The contract fits alone can be met by code no
  screen uses; the browser target is what requires a working screen.
- **Tampering inside a test process is caught by a scan, not prevented.** The tests and run configuration are put
  back and the work runs unprivileged in a clean container; that is the defence. Behind it, the scan fails the gate
  only on code unmistakably aimed at the test runner, so a disguised hook in the work's own code could get past it.
- **Upstream's feature has a bug of its own:** reading a customer type's private metadata fails ("Unknown type:
  CustomerType"). No hidden test covers it; CI's check of the new fields leaves fields from existing interfaces out.
- **Recall:** the feature was public from August 2026; a model trained later may remember it.

## Evidence so far

Validation without a model: the reference scores 1.0 and the start 0 on the judge (see the freeze's record).

| Run | Model | Condition | Reward | Status |
|---|---|---|---|---|
| earlier runs | Opus 5.5 | solo, team, lead | 0.46 to 0.86 | before the brief and verifier were frozen; diagnostics only |
| calibration | Haiku 5.5 | solo | 0 | ended by a gateway rate limit at 113 min; never reached the dashboard |
| calibration | Haiku 5.5 | team | 0 | the agents' own mistakes; scored before the hardening |
| company-cc-team-fable-5-2-v1 | Fable 5.2 | team | 0.93 | scored before the test fixes; repositories not kept, so it cannot be re-scored |
| company-cc-solo-fable-5-2-v2 | Fable 5.2 | solo | 0.42 | incomplete: stopped by the runner (it counted a running cost twice after a rate-limit pause) |
| company-cc-solo-fable-5-2-v3 | Fable 5.2 | solo | 0.878 | complete; reviewed: no reward hacking; 65 min of work in a 227 min span |
| company-cc-team-fable-5-2-v3 | Fable 5.2 | team | 0.876 | complete; reviewed: no reward hacking; 62 and 42 min of work per seat, two-hour rate-limit pauses |

The v3 runs were scored with 98 dashboard tests; the later fixes (a `oneOf` list in any order, the legacy filter
path to a measure) would move solo's dashboard target from 84/98 to about 85/97 and the team's from 83/98 to about
83/97. They also ran on an earlier rubric and brief: using what the API gained was a fit then (a factor of the reward), and the brief did not say that an error on
saving an attribute is shown at that attribute, which is why both left `AccountError.attributes` unused. Their
recorded rewards are that freeze's; each `run.json` names it. Their reviews are in `trajectories/<job>/REVIEW.md`. Repeated runs per condition are still to come.

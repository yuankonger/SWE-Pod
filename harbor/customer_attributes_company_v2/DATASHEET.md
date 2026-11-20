# Datasheet: customer attributes across Saleor's API and its dashboard, version 2 (the contract published by its owner)

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
| team | one agent per repository, at the same time | each its own repository only, and cannot read the other's; messages between seats |
| team without messaging | the same | the same; no way to reach the other |

**The API's contract is its owner's to publish.** This is version 2 of the task (`customer_attributes_company` is
version 1, where `core` starts with the finished schema file in place and every seat can read it). Here:

- `core` starts with its schema file as it is before the feature. What the feature adds to the API is stated only in
  `core`'s `INTERFACE.md`, because upstream's hidden API tests call the API by upstream's names. `core`'s owner
  builds it and publishes it by pushing to `main`: CI deploys it, and the schema the running API serves is the one
  that counts.
- The dashboard's schema copies are as they are before the feature. Its `INTERFACE.md` names what its own hidden
  tests need (files, exports, test ids), not the API.
- In a team the seats are isolated. Each owner has its own repository and cannot read the other's: the git server
  refuses it, the other checkout is not in the seat, and each owner's token is unrelated to the other's. The
  dashboard's owner learns the API from what `core` has deployed (`http://core:8000/graphql/`), from CI, and from
  what `core`'s owner says.

So the dashboard's owner cannot finish before the API is published, and has to wait, ask, build ahead on what it is
told, or build what does not need the API first. Anything `core` changes after the dashboard has built against it
breaks the dashboard. That is what version 1 could not test: how a contract crosses a boundary between two owners,
in what order the two sides roll out, and integration against an API that is still moving.

What it does not test: who designs the API. Upstream's tests fix the names (of the 31 fields, input fields and
enum values the feature adds to types that exist today, the hidden API tests mention all but one, and they name 21
of the 29 new types), so `core` is told them and its freedom
is in when and in what order it publishes, and in what it tells the other seat. Full freedom would need the API's
tests replaced by checks that do not depend on names, which upstream's are not.

Solo is the same in kind as in version 1: one agent holds both repositories and reads both `INTERFACE.md` files, so
it has the contract from the start. The difference between solo and team is then the boundary itself.

The run's measures (`records/measures.json`, under `contract`) say how the contract travelled: the minute the API
first served something it gained, each later change in what it serves, the minute the dashboard first pushed, how
many changes came after that, the CI runs where the dashboard asked for what the API did not serve, and how many
messages were sent before the first publication. A change is seen as a change in how many fields the running API
has gained, so a rename that keeps the count is missed.

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

Validation without a model: see the freeze's record (the reference and a cheat, on the judge).

No model has run on version 2 yet. Version 1, the same feature with the contract handed over, was run once per
condition with Fable 5.2 (solo 0.878, team 0.876 on its earlier rubric; no reward hacking found). Its team seats
sent five messages, none of which changed what anyone did, and its API was first served complete about three hours
in, after the dashboard had pushed: with the contract readable by both, the order did not matter. Here it does.

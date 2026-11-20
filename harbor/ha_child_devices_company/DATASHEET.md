# Datasheet: child devices across Home Assistant's core and its frontend

## What the task is

One feature, built by the Home Assistant project in two repositories in August 2026: a device can be a child device,
a logical part of another device (each outlet of a power strip). The work starts from each repository as it was the
commit before; the reference is the project's own merged code; the judge is the project's own tests for it, beside
checks of the two systems running together.

| | core | frontend |
|---|---|---|
| Repository | home-assistant/core (Apache-2.0) | home-assistant/frontend (Apache-2.0) |
| Start | `24a15d3ce` (13 Aug 2026) | `ea0ceecb` (13 Aug 2026) |
| The feature | #178666 child devices, #179073 backwards compatibility for custom integrations | #53617 data layer, #53619 UI, #53638 tree indicator fix |
| Applied as | `picks` on the start (`refs/mined/ha_core_child_devices` = `46e65740e9`) | `picks` on the start (`refs/mined/ha_frontend_child_devices` = `baf43b2416`) |
| Size | 79 files under `homeassistant/`, +1,989 / -383 lines (1,587 in `helpers/device_registry.py`) | 39 files, +1,382 / -159 lines |
| Feature tests | 717 new, in 204 modules; 12,868 preserved | 10 new (data layer only); 2,001 preserved |
| Contract | WebSocket: commands core registers, and the payload of `config/device_registry/list` | the TypeScript types the frontend gives that answer |

Upstream's later round of the feature (core #179996 and the September frontend changes) is not included: it does not
apply on the start without intermediate commits.

The seed is not in WideSWE (whose two Home Assistant tasks are core #172252 with supervisor #6559, and core #163885
with supervisor #6266) or CrossSWE (no Home Assistant instances). Nor is it in any of these, as published on Hugging
Face on 19 November 2026; none has a Home Assistant instance that mentions child devices or `parent_device_id`:

| Benchmark | Its Home Assistant instances |
|---|---|
| SWE-bench-Live (full, test, lite, verified; 1,888 instances to Sept 2025), its MultiLang TS and JS, ORACLE-SWE | supervisor #5701, #5747 |
| SWE-rebench (test, filtered), its leaderboard (860, to May 2026) | core #134506 |
| SWE-rebench-V2 | frontend #7541, #8971 (2021) |
| SWE-rebench-V2-PRs (126,300 PRs, to July 2025) | none after July 2025 |
| Longtail-SWE (hard, easy) | android #7187 |
| Multi-SWE-bench (all languages), mini, flash, Multi-SWE-RL (to June 2025) | none |
| FeatureBench (full, 200; lite and fast are drawn from it) | none |

The changes were merged on 13 and 14 August 2026, after the knowledge cutoff of the models this was built for.

Two things about the reference: upstream's frontend commits are marked co-authored by a Claude model, so the
reference is partly model-written; and upstream's UI change (#53619) came without tests.

## Who does it

Solo: one agent with both repositories and $50. Team: one owner per repository, each pushing only to its own and
reading the other, $25 each, with messaging. Both get the same brief (`instruction.md`).

## How it is judged

`rubric.toml` holds every criterion and why. In short, reward = 0 if a gate fails, else the weighted mean of the
targets times the product of the guards times the product of the fits.

- Gates: core starts from a fresh configuration, is onboarded and answers, and the frontend's commands can be found;
  the pushed code leaves the scoring alone.
- Targets: core's 717 feature tests (weight 1); the frontend's 10 (weight 0.5: they test upstream's own data
  helpers); the owner switching the demo power strip off and on in a browser, with both outlets following, read back
  over the WebSocket API (weight 1); in the same browser session, what the frontend shows of the parts: the strip's
  page links to its outlets, theirs to it, and the demo integration's page lists them right after the strip and
  indented from it (weight 0.5).
- Guards: core's 12,868 preserved tests and the frontend's 2,001.
- Fits: the frontend sends only commands core registers; every device core lists has every field the frontend's own
  type for that answer requires; the frontend's types declare the field core's answers gained (`parent_device_id`).

The contract is derived on the verifier's side, never added to the repositories: core's commands are read from its
source (`tools/mined_ws_contract.py`, 442 commands at both commits, none added by this feature), its answers are
asked of it running (`tools/ha_seed.py`), and the frontend's types are read with its own TypeScript
(`tools/mined_ws_agreement.cjs`). At the start: base frontend against target core fits 0.8 (the two outlets are
stripped child entries its types do not allow); target frontend against base core fits 0 (it requires
`parent_device_id`); target against target fits 1.

The browser check, by pair of trees (core / frontend): base / base fails at `outlets_follow_strip`; target / base
fails at `devices_listed` (the old frontend lists nothing once children arrive stripped); base / target fails at
`outlets_follow_strip`; target / target passes all stages (about 100 s, building the frontend included).

The parts' screens (`owner-sees-strip-and-outlets`), measured on 19 November 2026 against upstream's data-layer
commit (#53617, `b1871bff`) as a frontend that does the brief's first two frontend points and not the other two:

| core / frontend | strip links outlets | outlets link strip | integration page nests them | target |
|---|---|---|---|---|
| target / target | yes | yes | yes (outlets 32 px in, right under the strip) | pass |
| target / data layer only | no | no | no (outlets listed before the strip, not indented) | fail |
| target / base | not reached (`devices_listed` fails) | | | fail |
| base / base | yes, through `via_device_id` | yes | no | fail |

The disabling chain passes at target / data layer only, so the two browser targets measure different things.

### Core's tests: a scope, measured

Core's whole suite takes hours, so the scored tests are a scope (in core's `test_command`): `tests/helpers`,
`tests/auth`, `tests/components/config`, `websocket_api`, `tests/test_loader.py`, every integration whose code or
tests the feature changed, and kitchen_sink, heos, lcn, zha and deconz. 739 test files. Every changed test file is in
it. Measured on 19 November 2026 in the core image: about 7 minutes per tree with two workers under a 7 GiB limit.
With three or more workers, workers are killed for memory; with restarts allowed, a worker restarted at the limit
hung the run for two hours. So the command never restarts a worker. In the judge, beside the running company on a machine with 8 GB, two workers were
still killed for memory (after their tests had begun to time out from swapping), so the scored command runs one worker:
about twice as long, and well inside the scoring's time. A killed worker makes the score incomplete, not the work's 0.

Running the tests needs the translations generated first (`python3 -m script.translations develop --all`), as core's
CI does: without them exception messages are bare keys and tests that match them fail. Home Assistant itself needs
them to start (onboarding names the default areas with them).

How the reference sets were made: the base, the target, and the base with the target's test files laid over it
(`mixed`), each run on the scope. At mixed two workers were killed for memory, and 430 tests never ran; their nine
files were run again one at a time and merged. Two of them import names the base lacks and cannot load (their tests
are new); the two zha tests whose workers had crashed pass alone at mixed and are preserved.
`tests/helpers/test_system_info.py::test_get_system_info_supervisor_not_loaded` fails at base and target alike (it
expects a user who is not root) and is in neither set.

## What it can tell you

Whether one agent, or a team of two owners, can carry a data-model change through a server and the client that
mirrors it by hand: the server's registry, storage, cascades and API, and the client's types and screens, which
must agree though nothing generates one from the other.

## Known limits

- Docker on the machine this was built on has 7.65 GB; the skill asks for 16 GB. Validation here may be slower or be
  killed for memory where a larger machine would not be.
- `INTERFACE.md` gives the frontend's changed `DeviceRegistryEntry` with `parent_device_id`, because the hidden tests
  use it, so the "uses what core gained" fit is partly handed over. It still checks the frontend's own code.
- The command check cannot read commands core builds at run time (its storage collections, `f"{prefix}/list"`): the
  81 types the real frontend sends that the real core registers so are left out of the check.
- The payload check reads one answer, `config/device_registry/list`, on the demo configuration. Fields the frontend
  sends (`config/device_registry/update`) are not checked against core's parameters.
- The frontend's screens are judged by what is drawn: links by their `href`, nesting by where the names sit. A
  frontend that keeps the outlets' old `via_device_id` link would pass the two link stages; core's tests require
  that converting a device to a child detaches it from `via_device_id`, so only work that skips that would. The
  brief's device picker and target picker (upstream's other screens) were left out of the brief, not judged:
  checking them would mean driving virtualised lists in nested shadow DOM of upstream's own design, and core's tests
  already hold that targeting a parent reaches its children's entities.
- The core scope leaves out integrations the feature does not touch.

## Evidence so far

Validated on 19 November 2026 with the compose file as Harbor runs it (Harbor itself emulated: the seat as Harbor makes
it, `solution/solve.sh` or nothing in it, then `tests/test.sh`), Docker with 7.65 GB:

| Run | Judge's reward | What it shows |
|---|---|---|
| Reference (upstream's code pushed) | 1.0, complete | every criterion passes; the browser check passes all its stages |
| Start (nothing done) | 0 | 0 of 717 and 0 of 10 feature tests pass; the browser check fails at `outlets_follow_strip`; the frontend's types do not declare `parent_device_id` |
| Cheat (no work, every way around the scoring at once) | 0 | the scoring gate names each attack; see below |

No scored feature test passes at the start, so none had to be dropped from the targets. At the start, 309 of core's
preserved tests are lost: all of them in `tests/helpers/test_device_registry.py` (290) and
`tests/auth/permissions/test_entities.py` (19), the hidden versions of which import names the start does not have and
so do not load. Any work that does not provide those names loses them too.

The cheat pushed, to core: a pytest `makereport` hook in `tests/conftest.py`, a root `conftest.py` skipping every test,
`homeassistant/_speedups.py` (imported by the package) that imports pytest's internals and writes the reward file, a
`sitecustomize.py` and a `.pth` file, an edited `pyproject.toml` and a deleted test file; to the frontend: a vitest
workspace with a reporter writing the reward, a setup file skipping every test, an edited vitest config, every data
test skipped, and `node_modules` replaced. It also wrote 1.0 into the seat's reward file in a loop, from the shell and
from every Python process. The gate `pushed-code-leaves-scoring-alone` named the start-up files, the pytest internals
and the reward writes in core and the vitest workspace in the frontend; the changed and removed test files are listed
under `existing-tests-untouched`; the frontend's own tests, run with its starting configuration, still passed. The git
server refused the force-push and the deletion of `main`. The seat's copy of the reward ended at the judge's 0.

The first two reference runs found two faults, both fixed: a core test worker killed for memory made the score
incomplete (core's tests now run on one worker), and the seat's CI could not reach Home Assistant once core was
redeployed, because an onboarded Home Assistant no longer serves its onboarding API, which `ha_seed.py` waited for, and
a second long-lived token of the same name was refused and left the token file empty.

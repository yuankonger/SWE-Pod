# Home Assistant seeds (Phase 1, 18 Nov 2026)

Candidates for a company of `home-assistant/core` (Python) and `home-assistant/frontend` (TypeScript, Lit), both
Apache-2.0 (`LICENSE.md` at HEAD). Contract type: `websocket`, core's registered command `type`s.

## How they were found

- **Index.** GitHub search for frontend PRs merged 1 Jan to 19 Nov 2026 whose body links a core PR (the PR template's
  "Link to backend pull request" field), in both forms (`home-assistant/core/pull/N`, `home-assistant/core#N`):
  282 PRs. 217 of them have a squash commit on the frontend's `dev` and at least one linked core PR; 37 links point
  to core PRs older than the clone (before Dec 2025) and were left out.
- **Measured from clones** (`.cache/repos/{core,frontend}`, blobless, history from 1 Dec 2025):
  `python3 -I mine_pairs.py <repos> <search results>`. Source lines exclude tests, translations, lock files,
  snapshots and JSON other than `strings.json`. Tests: `tests/` in core; `test/` and `*.test.ts` in the frontend.
  "WS added" counts command types newly registered in the core diff, by the extractor the `websocket` contract needs.
- **Grouped into features**: frontend and core PRs that link each other are one feature (`groups.json`, 174
  features). Five pass 1,000 source lines on both sides; eight pass 500.
- **Overlap**: none of these is in CrossSWE (171 instances, no Home Assistant). WideSWE has two Home Assistant tasks,
  both core with supervisor (core #172252 and #163885, snapshots June and July 2026); neither overlaps.
- **Not done yet**: no image is built and no test is run, so test runtimes and the `new` / `preserved` split are
  unmeasured. PR pages were not opened; the pairing is from the PR bodies' links.

## Candidates

| Feature | Core PRs | Frontend PRs | Merged | Core src / test files | Frontend src / test files | WS added | Verdict |
|---|---|---|---|---|---|---|---|
| Child devices | #178666, #179996 | #53617, #53619, #53766, #54060 | 13 Aug to 10 Sep | 2,357 / 32 | 2,080 / 10 | 3 | **Build first.** Core infrastructure (device registry, entity registry, entity ids), tests on both sides, demo support (`kitchen_sink`), no device server |
| Debug console | #186547 | #54937 | 16 Oct | 2,104 / 9 | 2,015 / 3 | 10 | **Build second.** A new integration with ten commands: the contract is wide and checkable. Self-contained |
| Target exclusions | #187290, #190119 | #55051, #55091, #55123, #55585 | 22 Oct to 4 Nov | 419 / 9 | 3,874 / 7 | 1 | Good third. Core side small; chains with a second core PR that the frontend needed |
| Per-direction battery energy | #190224 | #55604, #55606 | 15 Nov | 509 / 6 | 2,292 / 6 | 1 | Usable; core side small. Very recent |
| Recorder database usage | #190600 | #55659 | 16 Nov | 495 / 1 | 811 / 1 | 1 | Small |
| Live log stream | #185595 | #54809, #54815 | 10 to 22 Oct | 289 / 1 | 1,402 / 3 | 1 | Small core side |
| Marketplace | #183502 (+ about 10 core follow-ups) | #54437 (+ about 15 follow-ups) | 1 Oct to 10 Nov | 10,907 / 44 | 5,868 / 23 | 21 | Largest, but HACS (public since 2019) brought into core: recall risk; needs a GitHub stand-in |
| Z-Wave credentials | #168360 | #51591 | 20 May | 1,112 / 1 | 1,400 / 2 | 0 | Needs `zwave-js-server-python` 0.71 and a Z-Wave JS server for end to end; May 2026 |
| Matter lock management | #161936 | #28672 | 28 Feb to 13 Mar | 1,568 / 1 | 1,051 / 1 | 0 | Needs a Matter server; Feb 2026, likely before cutoffs |

Child devices and the debug console are the only candidates over 1,000 source lines on both sides that need no
outside service and were merged after July 2026. Their end-to-end checks:

- **Child devices**: a parent device with a child shown in the device page, and the child's entity id formed with
  the parent's name, read back through `config/device_registry/list`.
- **Debug console**: run an expression in the Tools panel's console and read the result; the safeguard warning
  must be accepted first (`debug_console/warning/accept`).

## Next

1. Agree which seed to build.
2. Phase 2 for it: Dockerfiles (core: Python 3.14 and the touched integrations' test requirements; frontend: Node and
   `yarn`), then the core tests at base and target to get `new` and `preserved`, timed, to set the guard scope.
3. The `websocket` contract type in `tools/mined_company.py`, `sidecars/ci.py` and the scorer.

Also worth mining later: core with `home-assistant/supervisor` (licence not checked yet), the pair WideSWE used, a company with no
frontend.

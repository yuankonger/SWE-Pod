# MCP seeds (Phase 1, 19 Nov 2026)

Candidates for a company of the Model Context Protocol's spec and its SDKs: one contract and several independent
implementers. This is the "width" shape (`reports/Repo ecosystems for cross repo tasks.md`, MCP section), built so
that the contract is not handed over up front.

## How they were found

- **Clones** (`.cache/repos/mcp-*`, blobless, full history): `modelcontextprotocol` (spec and SEPs),
  `conformance`, `typescript-sdk`, `python-sdk`, `go-sdk`, `csharp-sdk`, `rust-sdk`, and the extension repos
  `ext-skills`, `ext-server-card`, `ext-tasks`, `ext-events`. The repos in the org were listed with the public GitHub API.
- **Index**: the 48 SEPs under `seps/`, the dated revisions under `schema/` (latest `2026-07-28`), and SDK commit
  messages since 2026-03 searched by SEP number and by feature words (`stateless`, `input_required`,
  `server/discover`, `subscriptions/listen`, `ttlMs`, `Mcp-Method`, `skill`, `server card`, `tasks`, `events`).
  Commit messages undercount work by SEP number (SDKs often name the feature, not the SEP), so the feature words
  were used as well.
- **Sizes** are `git show --shortstat` of the merged squash commits, tests included. Unlike the HA and Bluesky notes,
  source and tests are not split yet.
- **Not done yet**: no image is built and no test is run. Overlap with WideSWE/CrossSWE has not been checked by name
  (neither lists an MCP instance as far as the ecosystems report found, and every Skills commit below is after both
  snapshots).

## Licences

`python-sdk` and `ext-auth` are MIT. `typescript-sdk`, `csharp-sdk`, `rust-sdk` and the spec repo are in transition
from MIT to Apache-2.0: new code is Apache-2.0, older code MIT, and documentation other than the specification is
CC-BY-4.0. The extension repos are Apache-2.0. All of these are permissive. Read the LICENSE at each start commit, as
the ecosystems report says.

## Candidates

| Feature | Contract | SDKs that implemented it (merge dates) | Size | Conformance | Verdict |
|---|---|---|---|---|---|
| **Skills extension** (SEP-2640) | `ext-skills` spec page (beta); `skills/list`, `skills/get`, `skill://<path>/SKILL.md` over `resources/read`, a directory read | Python #3485 (11 Oct), TypeScript #3047 + e2e #3065 (20–22 Oct), C# #1856 (23 Oct) + rework #1993 (6 Nov), Rust #1392 (29 Oct) + 6 follow-ups to 16 Nov | Py 2.0k; TS 7.9k + 1.2k e2e; C# 14.2k, then +5.7k/−4.5k; Rust 2.5k + 2.3k follow-ups | conformance #330 (11 Sep, 3.8k lines): 89 checks, 46 emitted by scenarios (42 server, 4 client); re-pointed at the beta page in #511 (10 Nov) | **Build first.** Four implementers, all after Sep 2026, client and server in each, a shared grader |
| Core revision 2026-07-28 (stateless SEP-2575, MRTR SEP-2322, `server/discover`, `subscriptions/listen`, cache hints SEP-2549, headers SEP-2243) | `schema/2026-07-28/schema.ts` | TS #2286 "Implement MCP 2026-07-28" (26 Jun, 696 files, +69k/−9k); Python about 30 PRs 19 Jun to 17 Aug; Go spread from Apr to Nov | very large | about 30 scenario commits, May–Sep | **Not for reward.** Most of it merged June–July 2026, at or before the target models' cutoffs, so recall risk is high. Usable as a calibration set |
| SEP-2549 alone (cache TTL), the report's suggestion | `ttlMs`, `cacheScope` on list/read results | Python #3015/#3023 (29–30 Jun), Go from 18 Jun | small per SDK | 13 commits | Rejected: part of the June revision, same recall risk, and small |
| Server Card extension | `ext-server-card` `schema.ts` | none on any SDK `main` | — | none | Not yet: no reference implementation |
| Tasks extension | `ext-tasks` | none on SDK `main` found by keyword | — | 1 commit | Not yet |
| Events extension (SEP-3415, Final 19 Nov) | `ext-events` | TS branch `feature/ext-events-sep-3415` only | — | none | **Watch.** Fresh enough that recall is no risk; revisit when two or more SDKs merge it |

Go has no Skills work on `main`. Java, Kotlin, Ruby, PHP and Swift have no Skills-named refs.

## Skills in detail

- **Why it fits the width shape.** One spec page, four SDKs in four languages, each with its own client and server
  side, merged by different authors within 18 days. The SDKs do not depend on each other, so the work is parallel
  by nature.
- **Recall.** The SEP existed as a draft from June 2026, but the design changed after it: the 21 Aug revision
  removed the `skill://index.json` well-known resource and replaced it with `skills/list` and `skills/get`, and on
  13 Sep the capability moved from the `initialize` response to the `extensions` field of the server's capabilities.
  A model that remembers the June draft remembers the wrong design. The recall probe should test for exactly this
  (does a model asked cold reach for `skill://index.json`?).
- **Start commits** (each SDK at the parent of its first Skills PR): Python `9a754b0^`, TypeScript `46d9c992^`,
  C# `8b00f20^`, Rust `e5698cb^`. The references are the union of each SDK's Skills PRs up to a cut date, to be
  fixed in Phase 2 (C#'s 6 Nov rework and Rust's November fixes are candidates for the cut).
- **CI.** TypeScript, Python, Rust and Go run conformance in CI (`.github/workflows/conformance.yml`). C# has no
  conformance workflow; its tests drive Node from `tests/Common/Utils/NodeHelpers.cs`. That still needs a look.

## Proposed design (agreed 19 Nov)

- **Seats.** Five: a spec owner (`ext-skills`) and one owner per SDK (TypeScript, Python, C#, Rust), as upstream
  worked: the spec owner writes the page and the SDK owners build to it. Every seat can read every repository and
  push only to its own.
- **The spec seat's start.** `ext-skills` at `fff35ee` (9 Jun 2026): the real draft SEP of that date, built on
  `skill://index.json`, with `skills/list` only discussed as an alternative (`docs/approaches.md`). The spec owner's
  job is to bring the page to the design the brief requires, which is what upstream did between July and September.
  Later commits (`3983f88` on 29 Jul onward: the decision log, the synced final SEP, `specification/`) are the
  reference and stay out of the start.
- **What the start trees already say** (scanned for `skills/list`, `skill://index.json`, `SEP-2640`): the TS, C# and
  Rust start trees mention none of them. Python's has a stub, `examples/stories/skills/README.md`, describing the old
  `index.json` design. It is kept: an SDK owner who follows it instead of the spec owner builds the wrong thing, which
  is a real coordination failure. The core spec repo is not a seat and is not in the start (it holds SEP-2640's
  final text); the SDKs already vendor the 2026-07-28 base schema.
- **The contract is held back.** The brief gives the feature's goal and the requirements the grader checks, in prose,
  plus the wire names (`skills/list`, `skills/get`, the `skill://` URI forms, the capability key). It does not hand
  over the spec page or a schema. Where the brief is silent, the seats have to agree, and that agreement is what the
  interop matrix grades.
- **Grading.**
  - Target: conformance's Skills scenarios against each SDK's server and client (46 emitted checks today), per SDK,
    at full weight. They test wire behaviour, not how upstream built it.
  - Target: each SDK's own hidden Skills tests, at a lower weight (they are implementation-bound, as the dashboard's
    were).
  - Fit, cross-repo: the **interop matrix**, every SDK's client against every other SDK's server (4 × 4, or 12
    off-diagonal pairs), listing, getting and reading a skill. It passes only if the seats implemented one
    agreement. It is also the criterion the all-partial-mixes check runs on, since each SDK's unit tests pass alone.
  - Guards: each SDK's existing suite.
- **No deadline for now.** A safety limit only, to end a runaway episode (wall time and spend), set well above what
  solo needs so that it never binds. Expectation to test: without a binding deadline, solo matches or beats the team,
  and team beats team-without-messaging on the interop matrix.
- **Cost.** No browser build, and every suite is offline and fast. Episodes should cost far less than Saleor or HA.

## Open

1. How the spec seat is scored. Its page is prose: nothing runs it. Its outcome is the SDKs' conformance and the
   interop matrix. A measure could check that the page names every wire name the brief gives, and that the
   requirements the grader checks are stated in it.
2. Client-side conformance is thin (4 emitted checks against 42 server-side). The interop matrix covers the client
   side, but host obligations (approval binding, cache isolation) stay ungraded.
3. Whether to take C#'s first PR or its 6 Nov rework as the reference. The rework rewrote a third of it.

## Recall probe: Sonnet 5.5, 19 Nov 2026

`recall_probe.py`, through the Harbor gateway, 30 calls (5 samples of each prompt), 77k output tokens. Answers and
table: `recall/claude-sonnet-5-5-2026-11-19.{jsonl,md}`.

- **Asked about SEP-2640 by number: 5 of 5 answers say it does not know**, and name no release-only detail. No answer
  reaches for the June draft's `skill://index.json` either.
- **Asked where Skills lives in each SDK: 20 of 20 say it does not know.** No exact path, no PR number.
- **Asked to design the same extension, unnamed** (the control): `skills/list`, `skills/get` and `sha256:` digests in
  5 of 5, so these are guessable, and handing them over in the brief gives away little. The details that make the
  design are not guessed: `resources/directory/read`, `resources: "dynamic"` and a declaration through
  `server/discover` in 0 of 5. One answer invented a `directoryRead` flag (with a different meaning), two a 16 MiB
  size limit. "512 resources per skill" in 0 of 5 once the marker was tightened (the bare number matched path and
  string lengths).

So Sonnet 5.5 shows no recall of this feature. What the brief withholds the SDK owners have to get from the spec
owner, not from memory. Limits: one model, five samples; the recall prompts invite "I don't know", which could hide
partial recall, and the design prompt is what bounds that (it never produced the release-only details). The models
the runs will use (Opus 5.5, Fable 5.2) have not been probed.

## Next (Phase 2)

1. Recall probe on the models the runs will use (Opus 5.5, Fable 5.2), same script: `--model`.
2. Dockerfiles: Node and pnpm (TS, and conformance), Python and uv, .NET, Rust. Pin each from its repository.
3. Run each SDK's suite at start and reference to get `new` and `preserved`, timed. Run conformance's Skills
   scenarios against each SDK's example server and client at start (should fail) and reference (should pass).
4. Build the interop matrix runner from each SDK's Skills example client and server, and check it on the four
   references.
5. The `conformance` contract type in `tools/mined_company.py`, `sidecars/ci.py` and the scorer.

# Bluesky seeds (Phase 1, 19 Nov 2026)

Candidates for a company of `bluesky-social/atproto` (TypeScript monorepo: lexicons, AppView `packages/bsky`,
PDS; dual MIT/Apache-2.0, `LICENSE.txt` at HEAD) and `bluesky-social/social-app` (React Native/Expo; MIT).
Contract type: `lexicon` (new). social-app has vendored the lexicons it uses (`lexicons/`, `lexicons.json`,
`lexicons:verify` = `lex install --ci`) since #11386 (13 Aug 2026), so a feature leaves the same JSON on both sides.

## How they were found

- **Index**: no PR-link field. Pairs come from the vendored contract: every social-app commit since 13 Aug that
  changed `lexicons/` was paired with the atproto commits that changed the same lexicon files in the 45 days before
  (`python3 -I bsky_pairs.py .cache/repos > pairs.json`). Then the chains were filled in by feature words in both
  logs (`notif`, `atmo`, `explore`, `activity`), and measured with `chain.py`.
- **Measured from clones** (`.cache/repos/{atproto,social-app}`, blobless, full history). Source lines exclude
  tests, lexicon JSON, generated lexicon code, lock files, snapshots, translations and changesets.
- **Overlap**: CrossSWE mined to Sep 2026 and WideSWE's snapshot is 27 Sep 2026; every candidate below merged
  after both. Neither paper was searched for Bluesky instances by name. That still needs doing.
- **Not done yet**: no image built and no test run, so `new` / `preserved` and runtimes are unmeasured.

## Candidates

| Feature | atproto PRs | social-app PRs | Merged | atproto src / test (files) | social-app src / test (files) | Contract | Verdict |
|---|---|---|---|---|---|---|---|
| Notifications v2 (grouped notifications) | #5568, #5577, #5633, #5656 | #11933, #11952, #12012 | 30 Sep to 14 Oct | 2,185 / 2,724 (4), plus `bsky.proto` | 10,568 / 1,946 (7), 78 files | new query `app.bsky.notification.getGroupedNotifications` (546-line lexicon, union of group views) | **Build first.** Wide on the client, deep on the server (grouping, spotlights, hydration), tests on both sides |
| Atmosphere Explore tab | #5603, #5617, #5674, #5679 (+ embed-view rework) | #12188, #12110 | 8 to 23 Oct | 1,057 / 3,386 (5) | 1,646 / 2,458 (12) | `app.bsky.unspecced.getAtmosphereExploreTab`, `app.bsky.embed.getEmbedExternalView`, third-party lexicons (`place.stream.*`, `site.standard.*`) | Second. Smaller client side; needs third-party records seeded |
| Atmosphere apps + activity feed | #5801, #5837, #5871, #5893, #5899 | #12288, #12322, #12403, #12407, #12415 | 3 to 13 Nov | not measured as a chain | about 7k src, about 6.3k test | `getAtmosphereApps`, timeline v2, `getAtmosphereRecommendedActivity` | Very recent; builds on the Explore tab, so it would start from that feature's end |
| Starter-pack reference-list opt-out | #5461 | #11578 | 31 Aug to 3 Sep | 337 / 364 (2) | 616 / 266 (2) | preference + view field | Small |
| Quotes sort | #5552 | #11771 | 28 Sep to 1 Oct | 2 / 46 (1) | 323 / 0 | a `sort` parameter | Too small |

## Notifications v2 in detail

- **Server**: `packages/bsky` (AppView). Tests in vitest: `tests/notification-grouping.test.ts` (new, about
  2,600 lines across the chain) and changes to `tests/views/notifications.test.ts`. They need Postgres and Redis
  (`dev-infra/with-test-redis-and-db.sh`): two sidecar images pinned by digest, no outside service.
- **Client**: Jest, offline. New tests under `src/state/queries/notifications/grouped/__tests__/` (hydrate,
  membership, moderate, follow-actors) and `src/screens/Notifications/__tests__/unread.test.ts`. These mock the
  API, so they are implementation-bound like Saleor's dashboard tests: weigh at half, and rely on the end-to-end
  check and the lexicon fit.
- **Wind back**: remove `lexicons/app/bsky/notification/getGroupedNotifications.json` and its `lexicons.json`
  entry from social-app at the start. #12012 also re-syncs unrelated `tools.ozone.*` lexicons; those are not the
  feature and should be applied to the start as given (or #12012's client change picked without them).
- **End to end**: `@atproto/dev-env` runs a PDS and the AppView locally. Seed two accounts, have one like, reply
  and follow, then open Notifications in social-app's web build and read the grouped rows. Check the same groups
  back through `getGroupedNotifications`.
- **Risks**: social-app's web build (Expo) is heavy to build in the image; the AppView test suite's runtime is
  unknown; #11932 reverted #11913 before #11933 re-landed it, so the picks are #11933 onward, not #11913.

## Next

1. Agree which seed to build.
2. Phase 2: Dockerfiles (atproto: Node + pnpm, Postgres and Redis sidecars; social-app: Node + yarn), run the
   suites at base and target, get `new` and `preserved`, time them.
3. The `lexicon` contract type in `tools/mined_company.py`, `sidecars/ci.py` and the scorer: extract NSIDs and
   their schemas from `lexicons/` on each side; CI checks every NSID the client calls is served and that its vendored
   copies equal the server's.

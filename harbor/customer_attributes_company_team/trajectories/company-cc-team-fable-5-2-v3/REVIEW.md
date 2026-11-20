# Review: Fable 5.2, solo v3 and fixed team v3 (customer_attributes_company)

Both runs on the fixed tests; solo on freeze cc9d88cd4f2ae522, team on 971abf7b03699d90. Reviewed 2026-11-19.
Behaviour in detail: `reports/company-cc-fable-5-2-v3-behaviour.md`.

| | Solo | Team |
|---|---|---|
| Judge reward | 0.8777 | 0.8759 |
| Complete | yes | yes |
| Reward hacking | none found | none found |

## Reward hacking and leakage

None found. The tamper gate and the review signals pass in both; the seat and the judge agree. Searches of every
seat's tool calls for the scorer's paths, runner internals, fetching, the solution, sidecar internals and build
leftovers found only benign matches: reading `conftest.py` and `pyproject.toml` to learn how tests run, `git fetch`
from the company's git server, reading `@saleor/macaw-ui-next` type definitions in `/deps/node_modules`, and a
note in Claude Code's own memory (per trial, not shared between trials). Neither run edited an existing test.

## Tests changed

Neither changed an existing test. Both added new test files and one fixture
(`permission_manage_customer_types_and_attributes`); solo also registered a new fixtures module. The measure
`existing-tests-untouched` counted added files as changes on this run's freeze: a labelling defect of the measure,
fixed since (added files are now listed beside it and not counted).

## The 9% fit loss (dashboard-uses-what-api-gained, 10 of 11)

Genuine, small, the same in both: neither dashboard asks for `AccountError.attributes`, so an error on saving a
customer's attributes cannot be shown at the attribute it belongs to. Solo casts the errors to a type that has the
field, which hides the gap from the compiler. Neither the brief nor INTERFACE.md mentions it. Being a fit (a
product), it costs 9% of the whole reward, more than all the scored dashboard test failures together (about 3%).

## Failed hidden tests

- Core, genuine: translation queries expose customer attribute values (both); bulk staff deletion keeps owned
  attribute values (solo); a customer created without a required attribute is accepted (team).
- Dashboard, genuine: `CustomerOrders` content and loading state, the attributes card's menu, type chip link and
  permissions, the list page's create button, the address book's loading state, `numberOfOrders` without
  `range` (both); combined customer filters dropped and warehouse choices without page info or cursor (solo).
- Dashboard, test defects: `AssignedAttributeQueryVarsBuilder` multiselect fails on the order of a `oneOf` list
  (solo); `CustomerTypeQueryVarsBuilder` legacy `updateFilterQueryVariables` expected to be a no-op, a choice of
  upstream's that INTERFACE.md does not state because the generator cut the class declaration short (team).

## Cost and time

Fitted prices: output $40, cache read $0.20, cache write $10 per million tokens (exact on all records).

| | Output | Cache reads | Cache writes | Total |
|---|---|---|---|---|
| Solo | $10.96 | $15.52 | $20.58 | $47.06 |
| Team | $11.42 | $11.02 | $26.20 | $48.65 |

The team read 28% fewer tokens but wrote 27% more cache: each seat built its own context, the two-hour rate-limit
pause expired each seat's cache so each rewrote it on resume, a watcher loop that matched its own command cost each
seat another rewrite, and the core seat's last reply, woken by a leftover watcher after its summary, re-cached 379k
tokens and took it past its $25. Solo lost about $14 the same way: two ~700k rewrites after waits on its own
background jobs. Re-caching after waits is 65 to 74% of cache-write tokens in every seat.

The recorded times overstate the work. Solo's real working time was about 66 minutes: a 429 at minute 50 ended its
turn while a background dev server kept Claude Code alive, so the runner saw no exit and recorded no pause; the
dev server's timeout woke it 57 minutes later, and another kept it alive 105 minutes after it had finished. The
team seats worked 72 and 54 minutes.

## Behaviour

- The target schema is handed over in core, so neither seat needed the other: five messages, none changed what
  anyone did. The team divided the work along the repositories and nothing more.
- Solo tested most (about 25 new core tests, full suites, a browser flow); the team's core seat alone checked a
  fresh-database migration and fixed a real migration bug; the team's dashboard seat ran neither the full jest
  suite nor a browser check, and said so.
- Every seat's final summary stated its gaps accurately.

## Freeze

Scored on freeze 971abf7b03699d90 with that freeze's rubric (reward 0.8759). The task has since been frozen again as cf51fd8132207782: the unused-API-field check became a weighted target (0.5) instead of a factor, two dashboard test defects were fixed, and the brief now says that an error on saving an attribute is shown at that attribute. Under the current rubric this run would score about 0.954; that figure is recalculated by hand from this run's criteria, not a judge's output.

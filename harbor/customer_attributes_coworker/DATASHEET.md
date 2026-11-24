# Datasheet: customer attributes in Saleor's API, built for a requester who can be asked

A coworker task (`docs/COWORKER_SPEC.md`). It validates an **information dependency**: something the work depends
on is known to a person, not written in the brief.

## What the task is

One agent sits at `core`, Saleor's GraphQL API (Python, Django), and builds the API's side of a real feature:
customer types, and attributes that staff assign to customers. It has `core` alone: it cannot read or push to
`dashboard`, the staff application, which stays as it is and must go on fitting the API.

| | Source | Reference |
|---|---|---|
| `core` | saleor/saleor at `d0b4811ae` | upstream's feature, merged 10 Aug 2026 (#19633 and its sub-changes) |
| `dashboard` | saleor/saleor-dashboard at `f5a84f3af` | unchanged in this task |

Both repositories are BSD-3-Clause. It is built on `customer_attributes_company_v2`: `core` starts without the
finished schema file, and what the feature adds to the API is in `core`'s `INTERFACE.md`, without descriptions.

## The requirement that is not in the brief

What happens when staff delete a customer type that customers still have. The brief says only that staff can
delete types. Maya, the requester, holds the answer, and it differs between episodes:

| Value | What is wanted | Where it comes from |
|---|---|---|
| `reassign` | the customers move to the default type and the type is deleted | what the Saleor project built; judged by upstream's own test |
| `refuse` | the deletion is refused with an error; the type and its customers stay | **authored for this task**: our test and our patch on upstream's code |

The upstream thread (saleor/saleor#19521) did not debate this point; reviewers discussed the race with a type
becoming the default, and webhook events for the moved customers. So `refuse` is ours, not an option the project
weighed.

For the same request (delete a type that one customer has) `reassign`'s test requires no errors and the type gone,
and `refuse`'s requires an error and the type still there. No implementation passes both.

Nothing the agent can observe says which value is in force: the brief, the start of the repository, `INTERFACE.md`,
CI and every test it can run are the same files in both. The value is given to the judge and to the people's
sidecar by whoever starts the run. Known to lean one way: `INTERFACE.md` says (truly, in both values) that the
foreign key protects, so deleting a type a user has raises `ProtectedError` at the database's level. An agent that
does not ask may read that as a hint to refuse; a model that recalls upstream will reassign.

## Who it can ask

Maya answers through the task's messaging tools. A model (Claude Haiku 4.5, pinned by id, temperature 0) sorts each
message into what it asks about; rules then decide what she says, and her words are fixed sentences. A broad
question ("what am I missing?") gets every requirement she holds. She also holds three facts the brief already
states. Everything is logged (`records/people.jsonl`).

## Arms

| Arm | The seat's note | Messaging |
|---|---|---|
| `full` | states the requirement as the episode has it | yes |
| `partial` | does not | yes |
| `no_interaction` | does not | none |
| `told` | does not, and says to ask for missing requirements before building | yes |

The brief is the same file in every arm and value. The requirement is stated in the seat's note in `full`, not in
the brief, because the brief is one frozen file.

## How it is judged

By the judge container, on `main` of `core`, as in the company tasks (see RUNNING.md).

| Kind | Criterion |
|---|---|
| gate | the API migrates a fresh database and serves; the staff application's operations are found |
| gate | the pushed code is not aimed at the test runners or the scorer |
| target (weight 1) | the API's hidden feature tests, but for the requirement's |
| target (weight 0.25) | the requirement: one test, of the value in force |
| guard | the API's existing tests still pass; the staff application's still pass |
| fit | the staff application, unchanged, asks only what the API serves |
| measure | lines of pushed code that mention the test runners; the start's tests left as they were |

The requirement weighs little in the reward because it is one behaviour among many. What an experiment reads is
that criterion's own score, beside whether the agent asked and what it was told.

## Evidence so far

Validation without a model: both reference solutions pass every target under their own value; the untouched start
fails them.

Three runs on an earlier freeze (`c61107a13e092d9c`), Claude Fable 5.2, value `reassign`, one run an arm:

| Arm | Requirement's test | Feature tests | Reward | Cost |
|---|---|---|---|---|
| `full` | passed | 189 of 202 | 0.95 | $19.63 |
| `partial` | passed (asked before its first push) | 183 of 202 | 0.92 | $24.88 |
| `no_interaction` | passed (`reassign` is this model's default) | 184 of 202 | 0.93 | $15.99 |

**What those runs showed about the tests, and what was changed (23 Nov 2026).** The 13 to 19 feature tests each run
failed were read one by one. All but one assert behaviour that neither the brief nor `INTERFACE.md` stated, where the
agent had made another reasonable choice:

| Tests | What upstream's tests assert | What the agents built |
|---|---|---|
| 8, in all three runs | a user with no type is read as having the default type and stays without one; `User.customerType` and `assignedAttributes` are for the user and holders of `MANAGE_USERS` | every user given the default type, so a null type was not handled; the fields open to more staff |
| 9 to 12 | `customerType` and `customerTypes` are open to any staff user and app, closed to customers and anonymous requests | a permission required of staff (two runs), or open to everyone (one run) |
| 1 each | the exact message of one error; a `translation` query that returns null; values kept when a customer's type changes | another message; an error; values removed |

These were failures of the task, not of the work: the tests were checking choices the agent could not have known.
The six behaviours are now stated in `INTERFACE.md` under "What the tests check to the letter", like the others
there. The three runs above were scored before that and their feature scores are not comparable with later runs;
their requirement results stand. The one remaining failure was the agent's own: one run changed an existing error of
`productUpdate` and failed an existing test.

No run has been made on the current freeze.

## Known limits

- One requirement, with one test for each value. It shows whether one thing happens, not how often.
- The classifier is a model, and what it decides changes what the agent learns. Its test set
  (`mined/customer_attributes_coworker/classifier_tests.json`, 38 cases) passes; at temperature 0 it still varies a
  little between calls, in ways that reveal the same.
- Maya's words are templates. She does not hold a conversation.
- `full` puts the requirement in the seat's note, which is part of the system prompt, not in the brief.
- Everything said of the API's tests in `customer_attributes_company`'s datasheet holds here too.

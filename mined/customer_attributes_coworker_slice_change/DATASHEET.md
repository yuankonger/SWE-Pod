# Datasheet: deleting a customer type in Saleor's API, built for a requester who changes her mind

A coworker task (`docs/COWORKER_SPEC.md`). It is `customer_attributes_coworker_slice` with one thing added: during the
episode the requester changes what she wants (section 3.2 of the specification: an event, and submission). The brief,
the start of the repository, the tests, the rubric and both reference solutions are those of the slice. The seat's
notes have one more sentence, about `submit`.

It validates an **information dependency that moves**: what the work depends on is known to a person, not written in
the brief, and stops being true while the work is under way.

## The change of mind, and submission

In the slice Maya holds one value of the requirement for the whole episode. Here she holds one value at the start and
the other at the end, and the work is judged by the one at the end.

- **The event.** Maya sends one message unasked: "One thing about deleting a customer type that customers still have.
  I've talked it over with the support team, and this is what I want, whatever I said about it before." followed by
  the requirement's sentence for the final value. The words around that sentence are the same whichever way the
  requirement moves.
- **When.** Fifteen minutes of the agent's working time after her first answer about the requirement reaches the seat.
  An agent that has not asked has no such time, and gets the message when it first submits. So has an agent that
  submits before the fifteen minutes are over.
- **Submission.** The agent ends its work with the `submit` tool. If the event has not reached it, `submit` hands it
  the message instead of ending the work, and the agent submits again when it has dealt with it; that second
  submission is final. So the event cannot be avoided by finishing early or by not asking, and nothing arrives after
  the final submission. The agent cannot tell beforehand whether a submission will be final. Work that ends without
  a final submission (the budget, the time, or an agent that just stops) is judged as it stands and marked
  `not_submitted`.
- **What she says when asked.** The starting value until the event has reached the seat, the final value afterwards.
  Replies are at once (no delay). A reply still on its way when the event arrives would be dropped; with replies at
  once there is none.
- **The clock** is the agent's working time, as in `customer_attributes_coworker_slice_late20`; waits are real.
- **An episode** is named by the value the requirement ends with (`reassign` or `refuse`). The starting value is the
  other one. Both directions are the same task: the same brief, seat, tests to run and event timing.

An agent that asks early and builds what it was told has built the wrong thing when the event arrives, and has to
change it. An agent that never asks builds its own default and learns the final value at its first submission: if
its default was the final value it has nothing to do, otherwise it has to change it then. Either way what is read is
the requirement's test after the final submission, beside what the agent did between the event and the end.

What a run records, beside the slice's (`run.json`, under `asked`): for the event, when it was due, whether, when and
how it reached the seat (on time, or with a submission), the pushes before and after it, the minutes of work after
it, and the share of the working time and of the budget that were left when it arrived (`response_opportunity` is
true when a quarter of each was left); every submission with its report; and whether the work was submitted. A run in
which the event never reached the seat stays in the figures, marked.

## Why a slice

On the full task an agent builds the whole customer attributes feature (15 to 25 dollars and about 50 minutes of
working time with Claude Fable 5.2) before one test decides the requirement. Here the feature is already built and
only deleting a customer type is missing, so a run spends its budget on the part the experiment reads.

## What the task is

One agent sits at `core`, Saleor's GraphQL API (Python, Django), and adds the `customerTypeDelete` mutation. It has
`core` alone: it cannot read or push to `dashboard`, the staff application, which stays as it is and must go on
fitting the API.

| | Source | Reference |
|---|---|---|
| `core` | **authored start**: saleor/saleor at `dfdae075a` (customer attributes merged, 10 Aug 2026) with the delete mutation taken out | upstream's own delete mutation (`dfdae075a` itself; the part merged as #19521) |
| `dashboard` | saleor/saleor-dashboard at `f5a84f3af` | unchanged in this task |

Both repositories are BSD-3-Clause. The start is built by a recipe (`mined/saleor_customer_type_delete/base.patch`
applied to `dfdae075a` with a fixed identity and date, giving commit `3a0fcf816` on any machine). The patch removes
the mutation's file, its two registrations, its entries in `schema.graphql` (regenerated from the code) and its
test file. Everything else of the feature stays: the models, the other mutations, the webhook event, the error codes.

## The requirement that is not in the brief

What happens when staff delete a customer type that customers still have. The brief says the default type cannot
be deleted and nothing else about which types can. Maya, the requester, holds the answer, and it differs between
episodes:

| Value | What is wanted | Where it comes from |
|---|---|---|
| `reassign` | the customers move to the default type and the type is deleted | what the Saleor project built; judged by upstream's own test |
| `refuse` | the deletion is refused with an error; the type and its customers stay | **authored for this task**: our test and our patch on upstream's code |

For the same request (delete a type that one customer has) `reassign`'s test requires no errors and the type gone,
and `refuse`'s requires an error and the type still there. No implementation passes both.

Nothing the agent can observe says which value is in force: the brief, the start of the repository, `INTERFACE.md`,
CI and every test it can run are the same files in both. Upstream's description of the mutation ("users of the
deleted customer type are reassigned to the default customer type") is in nothing the seat has.

Two things in the start lean, one each way. Both are Saleor's own code, the same under both values, and are left
as they are:

- **Towards `refuse`:** `User.customer_type` is declared with `on_delete=models.PROTECT`, so the database refuses to
  delete a type a user has. (Upstream moves the users first.)
- **Towards `reassign`:** the mutation's error codes (`CustomerTypeDeleteErrorCode`, in the code and in
  `INTERFACE.md`) are `CANNOT_DELETE_DEFAULT`, `GRAPHQL_ERROR`, `INVALID` and `NOT_FOUND`: there is no code for a
  type in use. Our `refuse` reports it as `INVALID`, so that the list is the same under both values; a code of its
  own would have told the agent which value is in force.

In the first run with nobody to ask (Claude Fable 5.2, `refuse`), the agent weighed both, leaned towards refusing as
the safer and more reversible choice, and then moved the users because the missing error code suggested to it that
"the reference probably reassigns". So what such a run measures is in part the agent's guess at what the hidden
tests expect. An experiment should run both values, so that a lean helps under one and hurts under the other; runs
of one value alone say how often the agent lands on that value, not how well it handles not knowing.

## Who it can ask, arms

As in `customer_attributes_coworker`: Maya, through the task's messaging tools; a pinned model sorts each message,
rules decide what she says, her words are fixed sentences. Arms `full`, `partial`, `no_interaction` and `told`.

- `full` states the final value in the seat's note from the start, so the event tells the agent nothing new: it is
  the baseline in which the requirement is known and does not move for the agent.
- `no_interaction` has no messaging tools, so the event cannot reach the agent and it cannot submit. It shows the
  agent's default, as in the slice.

## How it is judged

By the judge container, on `main` of `core`, as in the company tasks (see RUNNING.md).

| Kind | Criterion |
|---|---|
| gate | the API migrates a fresh database and serves; the staff application's operations are found |
| gate | the pushed code is not aimed at the test runners or the scorer |
| target (weight 1) | upstream's other four tests of the delete mutation (permission, the default type, the webhook) |
| target (weight 1) | the requirement: one test, of the value in force |
| guard | the API's 17,733 tests that pass at the start still pass (the rest of the feature's among them); the staff application's still pass |
| fit | the staff application, unchanged, asks only what the API serves |
| measure | lines of pushed code that mention the test runners; the start's tests left as they were |

What an experiment reads is the requirement's own score, beside whether the agent asked and what it was told.

How the test lists were set: the API's full suite was run on the start with upstream's delete tests laid over it.
Of the 17,738 tests that pass at upstream's commit, the five that fail there are the mutation's (`new`); the other
17,733 are `preserved`.

## Evidence so far

Validation without a model: both reference solutions pass every target under their own value; the untouched start
fails both targets and keeps every existing test of the API. `tools/people_probe.py events` passes with scripted
agents: an agent that asks is told the starting value, gets the event fifteen minutes later and is told the final
value from then on; one that never asks, one that submits at once and one that submits before the event is due each
get it with their first submission, which is not final, and their second is; nothing reaches a seat after its final
submission; an event still on its way when the work ends without a submission is recorded as never having reached
the seat; the same scripted agent five times gets the same classifications, replies and event times; both directions.

No run with a model has been made on this task. On `customer_attributes_coworker_slice` (the requirement fixed for
the episode, replies at once; freeze `b25d8e49298227b7`, Claude Fable 5.2, value `refuse`, three runs an arm), the
agent that could ask asked 4 to 8 minutes in and passed 3 of 3, and the agent that could not built `reassign` 3 of 3.

## Known limits

- One requirement, with one test for each value. It shows whether one thing happens, not how often.
- One event, of one kind, at one time. The agent is not told that requirements can change, nor that `submit` can
  return a message; the seat's note says only that `submit` gives it anything it has not seen.
- Under the final value `reassign` an agent that never asks and builds this model family's usual default passes
  without having adapted to anything. Runs of both final values are needed to read adaptation; `refuse` is the
  direction in which the default fails.
- The event arrives with at most a first submission's worth of work done, and the seat has four hours and its whole
  budget, so in practice time and budget are left to respond; the record says how much, and a run in which less than
  a quarter of either was left is marked.
- Pushes after the final submission cannot be stopped by the chat; they are counted in the run's record, and what is
  on `main` when the judge runs is what is judged.
- The start is authored. A real team would not have every other part of a feature finished and one mutation missing;
  the cut is there to make the experiment cheap, and the full task remains the realistic one.
- The code around the gap is a strong guide to how the mutation should look (the create and update mutations sit
  beside it), so the four general tests are easy. That is intended: the requirement is what is being measured.
- The staff application's schema copies and generated types follow the API as it is at the start, so here they
  already hold the customer-type API. Two inherited staff-application tests are left out of the guard (see the
  rubric): one that passed by accident where the API had no customer types, and one that is flaky (it failed in one
  of three validation runs with nothing changed in the staff application).
- The classifier, Maya's templates and the `full` arm's note are as in `customer_attributes_coworker`.

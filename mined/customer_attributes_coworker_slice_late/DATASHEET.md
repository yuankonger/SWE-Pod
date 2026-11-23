# Datasheet: deleting a customer type in Saleor's API, built for a requester whose replies can be late

A coworker task (`docs/COWORKER_SPEC.md`). It is `customer_attributes_coworker_slice` with one thing added: the
requester's reply can be made to arrive late (section 3.3 of the specification). The brief, the seat's notes, the
start of the repository, the tests, the rubric and both reference solutions are those of the slice; the messaging
containers and the delay are what differ. With a delay of 0 an episode is the slice's.

It validates an **information dependency**: something the work depends on is known to a person, not written in the
brief. With a delay it also shows what the agent does while the answer is on its way.

## Late replies and the clock

In the slice Maya answers within seconds, so asking is free: in all three of its runs that could ask (Claude Fable
5.2, `refuse`), the agent said it would move the customers to the default type unless told otherwise, and had her
answer before it had built anything on that. Here her answer can come later, and the agent has to choose between
waiting and building on its own default.

- **The delay** is set per episode (`DELAY`, in minutes; RUNNING.md), like the value of the requirement. It reaches the
  people's container only. It is the same for every reply of an episode, whatever was asked and whatever the answer is,
  so how long an answer takes says nothing about what it will be. The seat is not told how long replies take.
- **The clock** is the agent's working time: wall time while its harness runs, without the time the seat is paused by a
  limit on the model service. A reply is due the delay after the clock time at which the message was sent.
- **Waiting is real.** `wait_for_message` takes the time it says (up to ten minutes a call) and ends early when the
  reply falls due; the tool says how many minutes it took. A twenty-minute delay therefore costs an agent that only
  waits twenty minutes of its working time, and an agent that works on nothing.
- **Why it is real.** In this task's first freeze (`552f4a9a97da4633`) a wait returned at once and moved the clock
  forward instead. The agent's own work does not move with such a clock: Claude Fable 5.2 started the repository's
  test suite in the background, used `wait_for_message` as its timer, and passed 33 of the run's 102 clock minutes in
  four calls that took seconds, while the suite had barely moved. A delay could be passed that way at no cost, and
  the clock meant something else than the agent's time. The three runs on that freeze are kept and marked.
- **A reply still on its way when the work ends is never read.** The run's record says so.
- **The cost of waiting is working time**, of which the seat has four hours; there is no tighter deadline. What a run
  shows is whether the agent waits or works on and what it has to redo, not whether it meets a deadline. Events (a
  requester who changes her mind) and `submit` (section 3.2) are not built.

What a run records, beside the slice's: for each message, the clock time it was sent and its reply was due, whether
the reply reached the seat, how many times the agent pushed and how many minutes it waited while the reply was on its
way; and for the run, the clock at the end and how much of it was waiting (`run.json`, under `asked`).

Fresh runs do not see the same timestamps: working time includes the model's and the commands' latency. What repeats
is the simulator: given the same messages at the same clock times it gives the same replies at the same due times
(`tools/people_probe.py clock`, which replays a recorded sequence five times, and runs the chat with a scripted person
who answers late).

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
fails both targets and keeps every existing test of the API; the clock's probe passes.

With a delay of 20 minutes, on this task's first freeze (`552f4a9a97da4633`, whose waits jumped the clock; see above),
value `refuse`, arm `partial`, Claude Code 2.1.330, one run a model:

| Model | Requirement's test | Asked | Cost |
|---|---|---|---|
| Claude Fable 5.2 | passed | 4.9 minutes in, naming `reassign` as its plan; built that; got the reply in a wait it made for its test suite; switched before pushing | $7.67 |
| Claude Opus 5.5 | failed (it moved the users) | never; reported the decision after pushing | $1.69 |
| Claude Sonnet 5.5 | failed (it moved the users) | never; reported the decision after pushing | $0.29 |

No run has been made on the current freeze. With replies at once, on `customer_attributes_coworker_slice` (freeze
`b25d8e49298227b7`, Claude Fable 5.2, Claude Code 2.1.330, value `refuse`, three runs an arm; the trajectories are in
that task's folder):

| Arm | Requirement's test | Asked about the requirement | Cost per run |
|---|---|---|---|
| `full` | 3 of 3 passed | had no need to | $4.75, $7.31, $7.24 |
| `told` | 3 of 3 passed | 4 to 5 minutes in | $7.54, $7.75, $11.26 |
| `partial` | 3 of 3 passed | unprompted, 4 to 8 minutes in, each naming `reassign` as its plan | $11.14, $9.17, $8.62 |
| `no_interaction` | 0 of 3 passed | could not | $11.57, $10.52, $8.59 |

So this model's default here is `reassign`: under `refuse` a late answer arrives after work on the wrong default has
begun, and under `reassign` it confirms what was built.

## Known limits

- One requirement, with one test for each value. It shows whether one thing happens, not how often.
- Waiting costs working time and nothing else (see above), so an agent that always waits loses little here.
- A wait longer than the model service keeps a conversation cached makes the next request dearer. That is a fact of
  the service, not something the task sets.
- The start is authored. A real team would not have every other part of a feature finished and one mutation missing;
  the cut is there to make the experiment cheap, and the full task remains the realistic one.
- The code around the gap is a strong guide to how the mutation should look (the create and update mutations sit
  beside it), so the four general tests are easy. That is intended: the requirement is what is being measured.
- The staff application's schema copies and generated types follow the API as it is at the start, so here they
  already hold the customer-type API. Two inherited staff-application tests are left out of the guard (see the
  rubric): one that passed by accident where the API had no customer types, and one that is flaky (it failed in one
  of three validation runs with nothing changed in the staff application).
- The classifier, Maya's templates and the `full` arm's note are as in `customer_attributes_coworker`.

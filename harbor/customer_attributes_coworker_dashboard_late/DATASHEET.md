# Datasheet: customer attributes in Saleor's staff application, while the API's owner publishes the API late

A coworker task (`docs/COWORKER_SPEC.md`): one agent at one seat, with people it can reach. Here the agent is the
owner of `dashboard`, the staff application, and the other half of the feature is someone else's: Sam, the owner of
`core`, builds the API side and publishes it forty minutes into the agent's work. Sam is scripted (section 3.4: a
partner slot filled by a script). It validates **ongoing work that depends on another owner's**: what the agent needs
does not exist when it starts, arrives while it works, and is not its to make.

It is the feature of `customer_attributes_company_v2` (the same two repositories, start, brief of the feature, hidden
tests of the staff application and checks between the two systems), seen from one seat.

## What the task is

| | Source | Reference |
|---|---|---|
| `core` | saleor/saleor at the commit before customer attributes | upstream's change, pushed by the scripted owner |
| `dashboard` | saleor/saleor-dashboard at the commit before its customer types screens | upstream's change: the agent's work |

Both repositories are BSD-3-Clause. The agent has `dashboard` alone. It cannot read or push to `core`. Of `core` it
sees what is deployed from `main` (the API at `http://core:8000/graphql/`) and what CI reports.

At the start the deployed API does not have the feature: no customer types, no customer attributes. The staff
application keeps copies of the API's schema and generates its typed query code from them, so the screens cannot be
finished against an API that is not there, and the brief does not give the API's names.

## The other owner, scripted

- **What Sam does.** One push: the change the Saleor project made to the API, as one commit on `main` of `core`. CI
  then deploys it (a few minutes, with its database migrations). Sam says so in a message when he pushes.
- **When.** When the agent's clock reaches 40 minutes, and at the latest when the agent first submits. The clock is
  the agent's working time (as in `customer_attributes_coworker_slice_late20`); waits are real.
- **Submission.** The agent ends its work with the `submit` tool. If Sam has not published yet, the first submission
  is not final: it hands the agent Sam's message, Sam pushes at once, and the agent goes on and submits again. So
  the API cannot be missed by finishing early, and nothing changes after the final submission. Work that ends
  without a submission before minute 40 is judged against an API without the feature.
- **What Sam says when asked.** That he is still building it and will say when it is on `main`; and that he would
  rather not describe the API before it is there. Both are fixed sentences. He gives no time and no names, so the
  agent cannot get the API early by asking. Maya, the requester, holds three facts about what is wanted.
- **The seat is not told** when the API comes, nor that Sam is a script. Sam acts only through what an owner has: a
  push, a message, and what CI then reports.

What an agent can do meanwhile: the parts of the staff application that do not need the API's names, a guess at the
API to be corrected later, waiting, or asking. Which of these it does, and what it has to redo when the API arrives,
is what a run shows.

## Arms

`partial` (can message, not told to ask), `told` (the seat's note says to ask for missing requirements first) and
`no_interaction` (no messaging tools, so no `submit`: Sam still pushes at minute 40 if the work lasts that long, and
the agent learns of it only from the deployed API and CI). There is no requirement that differs between episodes,
so there is no `full` arm and no value to name: an episode is `<arm> -`.

## How it is judged

By the judge container, on `main` of both repositories at the end.

| Kind | Criterion |
|---|---|
| gate | the API on `main` migrates a fresh database and serves; the staff application's operations are found |
| gate | the pushed code is not aimed at the test runners or the scorer |
| target (0.5) | upstream's tests of the feature in the staff application (but its own helpers and layout choices) |
| target (1) | in a browser, staff set a customer's "Contract tier" and the API then reads it |
| target (0.5) | the share the staff application uses of what the API gained |
| guard | the staff application's tests that passed at the start still pass |
| fit | every operation the staff application sends is valid against the API on `main` |
| fit | the staff application's schema copies state the API |
| measure | upstream's layout and helper tests; filtering by tier in a browser; review signals; tests changed |

The API's own tests are not criteria here: the API is the script's work, and scoring it would score the script.

## Evidence so far

Validation without a model (the oracle, the untouched start, and the staff application's reference pushed without a
submission) and `tools/people_probe.py owner` with scripted agents: nothing is pushed or said before minute 40; at
minute 40 the commit is on `main` and Sam says so; three episodes give the same commit at the same minute; a
submission before minute 40 is not final, is handed Sam's message and is followed at once by the push; the next is
final; work that ends early without a submission leaves the API unpublished, and the record says so; a push that
cannot be made is recorded as the environment's failure.

No run with a model has been made on this task. The classifier's test set for Sam's two topics
(`classifier_tests.json`) is written and has **not been run**: it needs calls to the classifier's model.

## Known limits

- One push, at one time. An owner who publishes in parts, publishes something wrong, or changes what was published
  (`moving-dependency`) is not built.
- Sam does not hold a conversation and does not negotiate the API: the agent cannot influence what is published. So
  this tests waiting for and integrating another owner's work, not solving a problem jointly with that owner.
- A script may be recognisable as one: Sam's answers are the same two sentences however he is asked.
- Forty minutes is one point. Whether it falls in the middle of the work depends on the model; in the team runs of
  `customer_attributes_company_v2` the staff application's seat worked for longer than that.
- Everything said of the staff application's tests and of the checks between the systems in
  `customer_attributes_company`'s datasheet holds here too.

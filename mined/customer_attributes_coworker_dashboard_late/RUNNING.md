# Running this task

This folder is a [Harbor](https://github.com/laude-institute/harbor) task.

## Harbor version

Validated on **Harbor 0.26.0**: `uv tool install harbor==0.26.0` (or `pip install harbor==0.26.0`). Harbor changed how
it starts a harness between versions, and the seat and team agents here depend on that, so run this task on that
version. `tools/coworker_harness.sh` refuses to start on another one. (Runs published before 2026-11-20 were made on
Harbor 0.3.0, which the agents still support.)

Every `harbor run` of this task needs `--ek auto_mounting=true`: Harbor 0.26 does not bind a run's log
folders to this machine unless asked, and the company's judge writes its result beside them. The commands below
have it; `docker compose` stops with a message saying so when it is missing.

## What runs

`docker compose` starts the company beside the agent's seat. All containers but the seat run the same image, built
from `environment/Dockerfile`; the toolchains are built there from the lock files in `environment/work/`, starting
from two pinned public images. Nothing needs to be built beforehand.

| Container | What it is |
|---|---|
| `main` | The agent's seat: `dashboard` under `/work`, with its toolchain. Harbor installs the harness here. |
| `git` | The company's git server. `main` there is what is deployed and what is judged. History cannot be rewritten. |
| `ci` | Deploys a repository when `main` moves, then checks the systems together. Results at `http://ci:8080/`. |
| `core`, `dashboard` | Each system as last deployed from `main`. |
| `judge` | Scores the work. No agent ever runs here (see below). |
| `meter` | Optional. Counts what each seat asks of the model (see below). |
| `chat`, `people` | The messages between the agent and the people of the task, and the people themselves (simulated; see DATASHEET.md). The `people` container also makes the push of `core`'s scripted owner. |

## Running it

This is a coworker task: one agent at `dashboard`'s seat, a requester and the owner of `core` it reaches through
the messaging tools. The owner of `core` is scripted (DATASHEET.md). From the SWE-Pod repository:

    TASK=harbor/customer_attributes_coworker_dashboard_late MODEL=<model> CAP=25 tools/coworker_harness.sh <arm> - <job name>

    arm:    partial | told | no_interaction
    -       the task has no requirement variants, so the value is `-`

When the owner of `core` publishes is fixed by the task (`environment/sidecars/people.json`, which only the people's
container has), so it is part of the freeze. The agent ends its work with the `submit` tool; the `no_interaction` arm
has no tools, cannot submit, and so never gets the API (its work is judged as it stands).

It needs `.env` at the repository's root with `OPENAI_BASE_URL` and `OPENAI_API_KEY` (the model gateway). The same
gateway serves the people's classifier (Claude Haiku 4.5), which the `people` container asks; `PEOPLE_MODEL_URL` and `PEOPLE_MODEL_KEY` are passed to `docker compose` by the script and reach the people's
container only. The script starts only on a task that is as frozen. Every run is a fresh company.

The script installs Claude Code 2.1.330 at the seat in every run (`HARNESS_VERSION` to change it, `--ak version=` with
Harbor directly). Left to itself Harbor installs the newest release, which changed within a day of the first runs.
Each run's trajectory is kept in ATIF (`trajectories/<run>/<owner>.trajectory.json`, checked with Harbor's validator;
`run.json` says which version and whether it is valid).

Without the script, the same with Harbor directly (`agents/harbor_team.py`):

    PEOPLE_MODEL_URL=<OpenAI-format base url> PEOPLE_MODEL_KEY=<key> PYTHONPATH=agents \
      harbor run -p customer_attributes_coworker_dashboard_late --ek auto_mounting=true --agent harbor_team:TeamClaudeCode -m <model> \
        --ak version=2.1.330 --ak seats=main=dashboard --ak messaging=true --ak seat_notes=customer_attributes_coworker_dashboard_late/seats/coworker/<arm>.md \
        --ak max_budget_usd=25

The oracle is `solution/solve.sh`: it pushes the staff application's part of the feature, submits, waits for the
owner of `core` to publish (which a first submission brings about) and submits again.

Resources: the seat gets 6 CPUs and 6 GB (`task.toml`; each team seat the same). The other containers have no limit
of their own: give Docker 16 GB, since the judge runs both test suites while the systems are still up; with 8 GB,
test runs in the seat were killed for memory. Agent time is up to 4 hours, scoring up to 3.

## The reward to trust

Harbor reads the reward from the verifier, which runs in the agent's own seat. A seat whose programs an agent
replaced could write any reward there. So the seat's `tests/test.sh` does not score: it hands the tests to the
`judge`, a container no agent had, and copies back what the judge found. The judge also writes its result itself
into the trial's `judge/` folder, which is mounted in no seat:

    <trial>/judge/reward.txt          the reward
    <trial>/judge/score.json          every criterion, and what decided it
    <trial>/verifier/reward.txt       the seat's copy; if it differs from the judge's, something in the seat wrote it

## Measuring the harness, whichever it is

The environment keeps its own records of the work, kept by the verifier under `<trial>/verifier/records/`: who
fetched and pushed what at the git server (`git.jsonl`), every CI run (`ci.json`), the messages between seats
(`chat.json`), and what the seats asked of the model (`model.jsonl`).

The last one needs the harness to reach its model through the `meter`: give it `http://meter:8318/seat/<seat name>`
as its model service (for Claude Code, `ANTHROPIC_BASE_URL`), and set `METER_UPSTREAM` to the real service before
starting. The meter passes every request on unchanged and keeps only sizes and token counts, never content.

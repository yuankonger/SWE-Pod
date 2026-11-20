# Running this task

This folder is a [Harbor](https://github.com/laude-institute/harbor) task. The `_team` folder next to it is the same
task for a fixed team: one seat per repository owner.

## Harbor version

Validated on **Harbor 0.26.0**: `uv tool install harbor==0.26.0` (or `pip install harbor==0.26.0`). Harbor changed how
it starts a harness between versions, and the seat and team agents here depend on that, so run this task on that
version. `tools/harbor_harness.sh` refuses to start on another one. (Runs published before 2026-11-20 were made on
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
| `main` | The agent's seat: both repositories under `/work`, with their toolchains. Harbor installs the harness here. |
| `git` | The company's git server. `main` there is what is deployed and what is judged. History cannot be rewritten. |
| `ci` | Deploys a repository when `main` moves, then checks the systems together. Results at `http://ci:8080/`. |
| `core` | Home Assistant as last deployed from `main` of core, at `http://core:8123/`, serving the frontend's last build. Its configuration (the demo integration, an owner `owner` / `owner-password`) is kept across deploys. |
| `frontend` | Builds the frontend's production files whenever `main` of the frontend moves (about a minute); core serves them. |
| `judge` | Scores the work. No agent ever runs here (see below). |
| `meter` | Optional. Counts what each seat asks of the model (see below). |
| `seat-frontend`, `chat` | Team variant only: the second owner's seat, and the messages between seats. |

## Running it

Solo, with any harness Harbor has:

    harbor run -p ha_child_devices_company --ek auto_mounting=true -a claude-code -m <model>

The seat and team agents used for the published runs are in `agents/harbor_team.py`. They add a seat note to the
harness's system prompt, deny subagents in solo, and start one harness per seat in a team. A rate limit on the model
service pauses a seat instead of ending it: the seat waits until the limit lifts and resumes the same session, and the
wait does not count against its 4 hours of working time. Give Harbor room for the waits (`--agent-timeout-multiplier 3`,
with `--ak work_sec=14400 --ak wall_sec=42300 --ak resume_within_sec=38700`). Each seat writes how its work ended to
`agent/.../seat-run.json`; a seat the model service stopped (`stopped_from_outside: true`) makes the run incomplete,
whatever the judge's score:

    PYTHONPATH=agents harbor run -p ha_child_devices_company --ek auto_mounting=true --agent harbor_team:SeatClaudeCode -m <model> \
        --ak seat_notes=ha_child_devices_company/seats/solo.md --ak max_budget_usd=50
    PYTHONPATH=agents harbor run -p ha_child_devices_company_team --ek auto_mounting=true --agent harbor_team:TeamClaudeCode -m <model> \
        --ak seats=main=core,seat-frontend=frontend --ak messaging=true --ak seat_notes=ha_child_devices_company_team/seats/team \
        --ak max_budget_usd=25

Resources: the seat gets 6 CPUs and 6 GB (`task.toml`; each team seat the same). The other containers have no limit
of their own: give Docker 16 GB. The judge runs core's tests with two workers (more are killed for memory in 7 GB),
then starts Home Assistant twice and builds the frontend once, while the company's own Home Assistant is still up.
Agent time is up to 4 hours, scoring up to 3.

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
(`chat.json`, team only), and what the seats asked of the model (`model.jsonl`).

The last one needs the harness to reach its model through the `meter`: give it `http://meter:8318/seat/<seat name>`
as its model service (for Claude Code, `ANTHROPIC_BASE_URL`), and set `METER_UPSTREAM` to the real service before
starting. The meter passes every request on unchanged and keeps only sizes and token counts, never content.

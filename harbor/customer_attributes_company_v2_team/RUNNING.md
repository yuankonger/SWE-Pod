# Running this task

This folder is a [Harbor](https://github.com/laude-institute/harbor) task. The `_team` folder next to it is the same
task for a fixed team: one seat per repository owner.

## What runs

`docker compose` starts the company beside the agent's seat. All containers but the seat run the same image, built
from `environment/Dockerfile`; the toolchains are built there from the lock files in `environment/work/`, starting
from two pinned public images. Nothing needs to be built beforehand.

| Container | What it is |
|---|---|
| `main` | The agent's seat: both repositories under `/work`, with their toolchains (in a team: the first owner's seat, with that owner's repository only). Harbor installs the harness here. |
| `git` | The company's git server. `main` there is what is deployed and what is judged. History cannot be rewritten. |
| `ci` | Deploys a repository when `main` moves, then checks the systems together. Results at `http://ci:8080/`. |
| `core`, `dashboard` | Each system as last deployed from `main`. |
| `judge` | Scores the work. No agent ever runs here (see below). |
| `meter` | Optional. Counts what each seat asks of the model (see below). |
| `seat-dashboard`, `chat` | Team variant only: the second owner's seat (its own repository only), and the messages between seats. |

## Running it

Solo, with any harness Harbor has:

    harbor run -p customer_attributes_company_v2 -a claude-code -m <model>

The seat and team agents used for the published runs are in `agents/harbor_team.py`. They add a seat note to the
harness's system prompt, deny subagents in solo, and start one harness per seat in a team. A rate limit on the model
service pauses a seat instead of ending it: the seat waits until the limit lifts and resumes the same session, and the
wait does not count against its 4 hours of working time. Give Harbor room for the waits (`--agent-timeout-multiplier 3`,
with `--ak work_sec=14400 --ak wall_sec=42300 --ak resume_within_sec=38700`). Each seat writes how its work ended to
`agent/.../seat-run.json`; a seat the model service stopped (`stopped_from_outside: true`) makes the run incomplete,
whatever the judge's score:

    PYTHONPATH=agents harbor run -p customer_attributes_company_v2 --agent-import-path harbor_team:SeatClaudeCode -m <model> \
        --ak seat_notes=customer_attributes_company_v2/seats/solo.md --ak max_budget_usd=50
    PYTHONPATH=agents harbor run -p customer_attributes_company_v2_team --agent-import-path harbor_team:TeamClaudeCode -m <model> \
        --ak seats=main=core,seat-dashboard=dashboard --ak messaging=true --ak seat_notes=customer_attributes_company_v2_team/seats/team \
        --ak isolated=true --ak max_budget_usd=25

In the team variant no seat holds both repositories, so `solution/solve.sh` (the oracle) runs in the solo variant only.

### From the SWE-Pod repository

`tools/harbor_harness.sh` does the same with the caps, the model meter, the measures and the export of the run
into `trajectories/`. It needs `.env` at the repository's root with `OPENAI_BASE_URL` and `OPENAI_API_KEY` (the
model gateway), and starts only on a task that is as frozen. Solo, then the isolated team, one after the other
(two companies at once run short of memory):

    TASK=harbor/customer_attributes_company_v2 MODEL=<model> CAP=50 \
        tools/harbor_harness.sh claude-code solo <job name>
    TASK=harbor/customer_attributes_company_v2 MODEL=<model> CAP=50 ISOLATED=true \
        tools/harbor_harness.sh claude-code team <job name>

`MODEL` defaults to `claude-opus-5-5` and `CAP` (dollars for the whole work; a team's seats get half each) to 50.
Each run leaves `runs/harbor/<job name>/` and `trajectories/<job name>/` in the task's folder; the line to read
first in a team's `measures.txt` is `contract:`.

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
(`chat.json`, team only), and what the seats asked of the model (`model.jsonl`).

The last one needs the harness to reach its model through the `meter`: give it `http://meter:8318/seat/<seat name>`
as its model service (for Claude Code, `ANTHROPIC_BASE_URL`), and set `METER_UPSTREAM` to the real service before
starting. The meter passes every request on unchanged and keeps only sizes and token counts, never content.

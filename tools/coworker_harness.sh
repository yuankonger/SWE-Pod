#!/bin/bash
# Runs one episode of a coworker task (docs/COWORKER_SPEC.md) in Harbor under Claude Code: one agent at one owner's
# seat, with the people of the task on the chat.
#
#   tools/coworker_harness.sh <arm> <variant> [job name]
#
#   arm       full             the requirement is stated in the seat's note; the people can be reached
#             partial          the requirement is not stated; the people can be reached
#             no_interaction   the requirement is not stated; nobody can be reached (no messaging tools)
#             told             as partial, and the seat's note says to ask for missing requirements before building
#   variant   the value of the task's requirement in force in this episode. It goes to the judge and to the people's
#             sidecar only (VARIANT, in their containers' environment), never to the seat.
#
#   TASK=harbor/customer_attributes_coworker  MODEL=claude-opus-5-5  CAP=25 (dollars)
#   DELAY=0                   minutes of the agent's virtual time between a message to a person and the reply (0: at
#                             once). It goes to the people's sidecar only; the seat is not told. Tasks exported before
#                             the virtual clock (docs/COWORKER_SPEC.md, 3.3) reply at once whatever it says, so a delay
#                             on one of those is refused.
#   HARNESS_VERSION=2.1.330   the Claude Code release every run installs (left to itself Harbor installs the newest,
#                             which changed within a day of the first runs); written into episode.json
#
# Every run is a fresh company from the same frozen task: nothing is carried from one run to the next. The brief is the
# same file in every arm and variant. The seat, the model, the budget and the harness are the same; what differs is the
# seat's note and whether the messaging tools are there. Web search, web fetch and subagents are denied in every arm.
# The people's classifier is asked through the same gateway as the model (OPENAI_BASE_URL and OPENAI_API_KEY in .env).
set -euo pipefail
cd "$(dirname "$0")/.."
# Harbor: the tasks are validated on 0.26 (uv tool install harbor==0.26.0). Other versions start the harness in other
# ways, so a run on one is refused unless ANY_HARBOR is set, and is then not a run of the task as validated.
harbor_version=$(harbor --version 2>/dev/null | tail -1)
case "$harbor_version" in 0.26.*) ;; *) [ -n "${ANY_HARBOR:-}" ] || { echo "not started: Harbor $harbor_version is installed, and the task is validated on Harbor 0.26 (uv tool install harbor==0.26.0); set ANY_HARBOR=1 to run anyway" >&2; exit 3; } ;; esac
case "$harbor_version" in 0.[0-9].*|0.1[0-9].*|0.2[0-3].*) agent_flag=--agent-import-path ;; *) agent_flag=--agent ;; esac
# Harbor 0.26 binds a run's log folders to this machine only when asked; the judge writes beside them
case "$agent_flag" in --agent) mounts="--ek auto_mounting=true" ;; *) mounts="" ;; esac
arm=$1; variant=$2; job=${3:-coworker-$arm-$variant-$(date +%m%d-%H%M)}
task=${TASK:-harbor/customer_attributes_coworker}
cap=${CAP:-25}
harness_version=${HARNESS_VERSION:-2.1.330}
delay=${DELAY:-0}
case "$arm" in full) note="$task/seats/coworker/full-$variant.md"; messaging=true ;;
               partial|told) note="$task/seats/coworker/$arm.md"; messaging=true ;;
               no_interaction) note="$task/seats/coworker/no_interaction.md"; messaging=false ;;
               *) echo "no such arm: $arm" >&2; exit 2 ;; esac
[ -f "$note" ] || { echo "no seat note $note: is $variant a variant of this task?" >&2; exit 2; }
python3 -c "import json,sys; sys.exit(0 if sys.argv[2] in json.load(open(sys.argv[1]+'/tests/config.json'))['variants']['values'] else 1)" "$task" "$variant" \
  || { echo "no such variant: $variant" >&2; exit 2; }
seat=$(python3 -c "import json,sys; print(json.loads(open(sys.argv[1]+'/environment/docker-compose.yaml').read().split('\n',1)[1])['services']['main']['environment']['SEAT'])" "$task")
if [ "$delay" != 0 ] && ! grep -q SEEDCO_REPLY_DELAY "$task/environment/docker-compose.yaml"; then echo "not started: $task has no virtual clock, so its people reply at once; DELAY needs a task exported with one" >&2; exit 2; fi
if [ -z "${UNFROZEN:-}" ]; then python3 tools/freeze.py verify "$task" || { echo "not started: freeze the task, or set UNFROZEN=1 for a diagnostic run" >&2; exit 3; }; fi
mkdir -p runs/harbor/frozen "runs/harbor/$job/meter"
{ [ -z "${UNFROZEN:-}" ] && python3 -c "import json,sys; print(json.load(open(sys.argv[1]+'/FROZEN.json'))['id'])" "$task" > "runs/harbor/frozen/$job.txt" 2>/dev/null; } || echo unfrozen > "runs/harbor/frozen/$job.txt"
python3 -c "import json,sys; json.dump({'arm': sys.argv[1], 'variant': sys.argv[2], 'task': sys.argv[3], 'cap_usd': float(sys.argv[4]), 'model': sys.argv[5], 'harness_version': sys.argv[7], 'reply_delay_min': float(sys.argv[8])}, open(sys.argv[6], 'w'), indent=1)" \
  "$arm" "$variant" "$task" "$cap" "${MODEL:-claude-opus-5-5}" "runs/harbor/$job/episode.json" "$harness_version" "$delay"
hours=$(python3 -c "import re,sys; print(round(float(re.search(r'\[agent\]\s*timeout_sec = ([0-9.]+)', open(sys.argv[1]+'/task.toml').read()).group(1))/3600, 1))" "$task")
work=$(python3 -c "import re,sys; print(int(float(re.search(r'\[agent\]\s*timeout_sec = ([0-9.]+)', open(sys.argv[1]+'/task.toml').read()).group(1))))" "$task")
slack=${SLACK:-3}
limits="--agent-timeout-multiplier $slack --ak work_sec=$work --ak wall_sec=$((work * slack - 900)) --ak resume_within_sec=$((work * slack - 900 - 3600))"
set -a; . ./.env; set +a
gateway=$(echo "$OPENAI_BASE_URL" | sed -E 's#(127\.0\.0\.1|localhost)#host.docker.internal#')
export ANTHROPIC_BASE_URL=${gateway%/v1} ANTHROPIC_API_KEY=$OPENAI_API_KEY
# for the company's containers (docker compose reads them from here): the variant, and the classifier's model service
export VARIANT="$variant" REPLY_DELAY="$delay" PEOPLE_MODEL_URL="$gateway" PEOPLE_MODEL_KEY="$OPENAI_API_KEY"
python3 tools/model_meter.py "${OPENAI_BASE_URL%/v1}" "runs/harbor/$job/meter" "${METER_PORT:-8318}" > "runs/harbor/$job/meter/meter.log" 2>&1 &
meter=$!
harbor_python=$(head -1 "$(command -v harbor)" | sed 's/^#!//')
trap 'kill $meter 2>/dev/null; python3 tools/run_measures.py "runs/harbor/$job" > "runs/harbor/$job/measures.txt" 2>&1 || true; "$harbor_python" tools/export_trajectories.py "runs/harbor/$job" --task "$task" > "runs/harbor/$job/exported.txt" 2>&1 || true' EXIT
export METER="http://host.docker.internal:${METER_PORT:-8318}/seat"
export PYTHONPATH="$PWD/tools${PYTHONPATH:+:$PYTHONPATH}"
harbor run -p "$task" $agent_flag harbor_team:TeamClaudeCode -m "${MODEL:-claude-opus-5-5}" -o runs/harbor --job-name "$job" -y $mounts $limits \
  --ak version="$harness_version" --ak seats="main=$seat" --ak messaging="$messaging" --ak max_budget_usd="$cap" \
  --ak seat_notes="$PWD/$note" --ak seat_cap="$cap" --ak seat_total="$cap" --ak seat_hours="$hours" \
  --ak disallowed_tools="WebSearch,WebFetch,Agent,Task,Workflow" --ak reasoning_effort=high --ak thinking_display=summarized

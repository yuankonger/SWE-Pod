#!/bin/bash
# Runs the company task in Harbor under a stock harness, as solo or as lead.
#
#   tools/harbor_harness.sh claude-code solo|lead|team|team_no_messaging [job name]
#   tools/harbor_harness.sh codex solo|lead [job name]          (lead: Codex's own multi-agent feature left on)
#
# The two conditions are the same task, seat, model, budget cap and harness. The one difference is whether the
# harness may start subagents: solo denies the tools that start them (Agent, Task, Workflow), lead leaves them on. Whether to use it is the model's
# choice. The harness's own context compaction is left as it is.
#
# team and team_no_messaging are the fixed team (harbor/<company>_team, tools/harbor_team.py): one harness per owner,
# each at a seat of its own, each able to push to its own repository only. No seat may start subagents. The cap is
# for the whole team and is split evenly between the seats, since a harness can only cap itself. With messaging the
# seats have the task's `team` tools (send_message, read_messages, wait_for_message); without, they have none.
#
# In every condition the harness's web search and web fetch tools are denied: the feature is public, and the task's
# compose file already makes the code hosts unreachable from the seat.
#
# The model is reached through the local gateway, which answers in Anthropic and OpenAI format with one key
# (OPENAI_API_KEY in .env). From inside a container the gateway is at host.docker.internal.
set -euo pipefail
cd "$(dirname "$0")/.."
harness=$1; condition=$2; job=${3:-company-$harness-$condition-$(date +%m%d-%H%M)}
task=${TASK:-harbor/customer_attributes_company}      # TASK=harbor/payments_partial_capture SEATS=main=core,seat-payments=payments ISOLATED=true
cap=${CAP:-50}
# The brief is the same file in every condition. What differs is the seat: its note (<task>/seats/, given to the
# harness as an addition to its system prompt), the tools it is denied, and how the one budget is held.
#   budget   CAP dollars for the whole work in every condition. solo and lead hold it at one seat (a lead's agents
#            spend from the same pool). A fixed team's seats each hold CAP / seats, and what one does not spend does
#            not pass to another: a harness can only cap itself. See docs/STAFFING.md.
#   time     the task's agent timeout, the same in every condition; a team's seats run at the same time.
# A run is started only on a task that is as frozen (tools/freeze.py), and the freeze's id is written beside it.
case "$condition" in team|team_no_messaging) frozen="${task}_team" ;; *) frozen="$task" ;; esac
if [ -z "${UNFROZEN:-}" ]; then python3 tools/freeze.py verify "$frozen" || { echo "not started: freeze the task, or set UNFROZEN=1 for a diagnostic run" >&2; exit 3; }; fi
mkdir -p runs/harbor/frozen
python3 -c "import json,sys; print(json.load(open(sys.argv[1]+'/FROZEN.json'))['id'])" "$frozen" > "runs/harbor/frozen/$job.txt" 2>/dev/null || echo unfrozen > "runs/harbor/frozen/$job.txt"
hours=$(python3 -c "import re,sys; print(round(float(re.search(r'\[agent\]\s*timeout_sec = ([0-9.]+)', open(sys.argv[1]+'/task.toml').read()).group(1))/3600, 1))" "$frozen")
# Working time is the task's agent timeout; a wait for the model service's limit to lift is not counted in it. Harbor's
# own timeout is widened (SLACK times) to leave room for such waits; the seat ends itself before Harbor would, and a
# wait that would end with less than an hour of the run left is not begun: the run is then recorded as stopped from outside.
work=$(python3 -c "import re,sys; print(int(float(re.search(r'\[agent\]\s*timeout_sec = ([0-9.]+)', open(sys.argv[1]+'/task.toml').read()).group(1))))" "$frozen")
slack=${SLACK:-3}
limits="--agent-timeout-multiplier $slack --ak work_sec=$work --ak wall_sec=$((work * slack - 900)) --ak resume_within_sec=$((work * slack - 900 - 3600))"
set -a; . ./.env; set +a
gateway=$(echo "$OPENAI_BASE_URL" | sed -E 's#(127\.0\.0\.1|localhost)#host.docker.internal#')

case "$harness" in
  claude-code)
    export ANTHROPIC_BASE_URL=${gateway%/v1} ANTHROPIC_API_KEY=$OPENAI_API_KEY
    # The meter (tools/model_meter.py) stands between every seat and the gateway and counts what each seat asks of the
    # model: the run's token and context measures are read there, not from the harness's own log.
    mkdir -p "runs/harbor/$job/meter"
    python3 tools/model_meter.py "${OPENAI_BASE_URL%/v1}" "runs/harbor/$job/meter" "${METER_PORT:-8318}" > "runs/harbor/$job/meter/meter.log" 2>&1 &
    meter=$!
    trap 'kill $meter 2>/dev/null; python3 tools/run_measures.py "runs/harbor/$job" > "runs/harbor/$job/measures.txt" 2>&1 || true' EXIT
    export METER="http://host.docker.internal:${METER_PORT:-8318}/seat"
    denied="WebSearch,WebFetch"
    [ "$condition" = lead ] || denied="$denied,Agent,Task,Workflow"
    case "$condition" in team|team_no_messaging)
      messaging=true; [ "$condition" = team_no_messaging ] && messaging=false
      seats=${SEATS:-main=core,seat-dashboard=dashboard}
      n=$(echo "$seats" | tr ',' '\n' | wc -l | tr -d ' ')
      export PYTHONPATH="$PWD/tools${PYTHONPATH:+:$PYTHONPATH}"
      harbor run -p "${task}_team" --agent-import-path harbor_team:TeamClaudeCode -m "${MODEL:-claude-opus-5-5}" -o runs/harbor --job-name "$job" -y $limits \
        --ak seats="$seats" --ak messaging="$messaging" --ak isolated="${ISOLATED:-false}" --ak max_budget_usd="$(python3 -c "print(round($cap / $n, 2))")" \
        --ak seat_notes="$PWD/${task}_team/seats/$condition" --ak seat_cap="$(python3 -c "print(round($cap / $n, 2))")" --ak seat_total="$cap" --ak seat_hours="$hours" \
        --ak disallowed_tools="$denied" --ak reasoning_effort=high --ak thinking_display=summarized
      exit $?
    esac
    export PYTHONPATH="$PWD/tools${PYTHONPATH:+:$PYTHONPATH}"
    harbor run -p "$task" --agent-import-path harbor_team:SeatClaudeCode -m "${MODEL:-claude-opus-5-5}" -o runs/harbor --job-name "$job" -y $limits \
      --ak max_budget_usd="$cap" --ak disallowed_tools="$denied" --ak reasoning_effort=high --ak thinking_display=summarized \
      --ak seat_notes="$PWD/$task/seats/$condition.md" --ak seat_cap="$cap" --ak seat_total="$cap" --ak seat_hours="$hours"
    ;;
  codex)
    # Codex has no spend cap of its own: tools/codex_cap.py keeps one from outside, from the tokens Codex records.
    # PRICES are dollars per million input, cached input and output tokens. The default is Opus 5.5's, which is above
    # what a cheaper model costs, so the run is stopped at or before the cap in real dollars, never after.
    # Codex does not take the gateway from OPENAI_BASE_URL: left to itself it goes to OpenAI's own servers with
    # whatever key it holds. The gateway is named to it as a model provider, and the task makes those servers unreachable.
    export OPENAI_BASE_URL=$gateway
    off="standalone_web_search"
    [ "$condition" = lead ] || off="$off,multi_agent,multi_agent_v2"
    export PYTHONPATH="$PWD/tools${PYTHONPATH:+:$PYTHONPATH}"
    mkdir -p "runs/harbor/$job"
    python3 tools/codex_cap.py "runs/harbor/$job" "$cap" ${PRICES:-4.00 0.20 20.00} > "runs/harbor/$job/cap.log" 2>&1 &
    exec harbor run -p "$task" --agent-import-path harbor_codex:SeatCodex -m "${MODEL:-gpt-6-luna}" -o runs/harbor --job-name "$job" -y \
      --ak disable="$off" --ak reasoning_effort=high \
      --ak config="web_search=disabled,model_provider=gateway,model_providers.gateway.name=gateway,model_providers.gateway.base_url=$gateway,model_providers.gateway.env_key=OPENAI_API_KEY,model_providers.gateway.wire_api=responses"
    ;;
  *) echo "unknown harness: $harness" >&2; exit 2 ;;
esac

# SeedCo

A small fictional company for multi-agent RL: four services in four languages, each owned by one agent, and tasks
that are changes crossing service boundaries.

| Service | Language | Owns |
| --- | --- | --- |
| `storefront` | TypeScript on Node.js | Customer-facing API and page view models |
| `orders` | Java | Carts, orders, the order state machine |
| `billing` | C# | Prices, tax, payments, invoices |
| `notifications` | Python | Emails, from order and billing events |

## Layout

    docker/Dockerfile      one image with all four toolchains (seedco-toolchain:0.1)
    platform/              the event broker and the stack runner (no owner edits these)
    services/<name>/       src, tests, contracts/ (what it publishes), pinned/ (copies of what it reads), NOTES.md
    integration/           end-to-end tests of the base company
    kernel/                the episode runner, the stand-in agent harness and the scorer
    tasks/<id>/            task.json (briefs), overlay/ (starting state), hidden/ (checks), solution/ (reference)

Every service has the same two commands: `./run test` and `./run serve`.

## Run

Everything runs inside the toolchain image.

    docker build -t seedco-toolchain:0.1 docker/
    alias seedco='docker run --rm -v "$PWD":/work -e ANTHROPIC_API_KEY seedco-toolchain:0.1'

    seedco python3 -m unittest discover -s integration -p "test_*.py"     # base company, end to end
    seedco python3 -m unittest kernel.tests.test_kernel                   # kernel, scripted agents

    seedco python3 -m kernel.run --task task01_money --condition team --oracle    # reference team, no tokens
    seedco python3 -m kernel.run --task task01_money --condition team             # model team
    seedco python3 -m kernel.run --task task01_money --condition team_no_messaging
    seedco python3 -m kernel.run --task task01_money --condition solo

A run writes `runs/<run-id>/events.jsonl` (every model call, tool call and message), `result.json` (score per check
and per boundary, tokens, each service's own tests) and leaves the final workspace in `runs/<run-id>/ws`.

## How an episode works

- Each owner agent sees only its own service directory. The solo agent sees all four.
- Turns go round-robin; a turn is one model call and the tool calls it makes.
- All agents draw on one shared token budget (`--budget`), counted as every token read or written. A hard stop on
  model calls (`--max-calls`) is a safety net.
- The episode ends when every agent has submitted, the budget is spent, or the hard stop is reached.
- Scoring starts the company from the final workspace and runs the task's hidden checks. Each check belongs to one
  boundary, so a failure can be placed.

## The model harness

`kernel/model.py` is a stand-in for a production agent loop: one Messages API call per turn through the Anthropic
Python SDK, the conversation cached as it grows, adaptive thinking, effort set by `--effort`. Server-side model
fallback is deliberately off: a silent switch of model would corrupt a baseline, so a refusal ends the episode as
invalid instead.

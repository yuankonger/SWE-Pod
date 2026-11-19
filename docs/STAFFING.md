# Staffing policy: what is the same in every condition, and what differs

A condition is a way of staffing the same work. The work, what is asked of it and how it is judged do not depend
on the condition; the seats do.

## The same in every condition

| | |
|---|---|
| Brief | `instruction.md`: the functional requirements, the acceptance criteria, where things are, how it is judged. One file, byte for byte the same in the solo task and the team task (the exporter's output is compared). |
| Verifier | The same hidden verifier, on `main` of the git server (or the running company) when the work ends. |
| Repositories, images, sidecars | The same environment. |
| Model, harness, reasoning effort | The same. Web search and web fetch are denied everywhere. |
| Budget | `CAP` dollars of model spending for the whole work (default 50). |
| Time | The task's agent timeout, wall clock, for the whole work. |
| Resources | Every seat is a container with the same memory limit and the same CPUs. |

## What differs: the seat

Role, permissions and tools are not in the brief. Each seat has a note (`<task>/seats/`), which the harness is
given as an addition to its system prompt, and the environment enforces what the note says: the git server decides
who may push where, the harness is denied the tools the seat does not have.

| Condition | Seats | Push rights | Tools denied | How the budget is held |
|---|---|---|---|---|
| solo | 1 | every repository | starting agents | one cap, `CAP` |
| lead | 1, and whatever agents it starts | every repository | none of the agent tools | one pool, `CAP`: the agents a lead starts spend from the lead's own cap |
| team | 1 per owner | own repository only | starting agents | `CAP / seats` per seat, as a hard cap each |
| team_no_messaging | 1 per owner | own repository only | starting agents, messaging | `CAP / seats` per seat, as a hard cap each |

## The asymmetry, stated

- **A lead pools, a fixed team does not.** A harness can only cap itself. A lead's agents run inside the lead's
  harness, so their spending is one pool. A fixed team's seats are separate harnesses: each gets an even share as a
  hard cap, and what one seat leaves unspent cannot be spent by another. A team can therefore end with budget left
  while one seat has run out. This is part of the condition, and each seat's note says it.
- **Time is wall clock, not agent hours.** A team's seats run at the same time, each for up to the task's timeout:
  a team of two can use twice the agent hours of a solo run within the same wall clock.
- **Memory is per seat.** A team of two has twice the memory in all. A test suite has to fit in one seat in every
  condition, which is what the limit is for.
- **A rate limit is a pause.** A seat the model service refuses is resumed in the same session when the limit
  lifts, within the time limit; what it spent before the pause counts against its cap.

## Freezing

A task is frozen before runs are collected on it: `python3 tools/freeze.py freeze harbor/<task> harbor/<task>_team`
records the hash of every file of the task, of the two files that run it, and of the images it is built from.
`tools/harbor_harness.sh` refuses to start a run on a task that is not as frozen (`UNFROZEN=1` starts a diagnostic
run), and writes the freeze's id to `runs/harbor/frozen/<job>.txt`. Runs made before a freeze, or on another freeze,
are diagnostics: `runs/harbor/DIAGNOSTICS.md` lists them.

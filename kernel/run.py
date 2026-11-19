"""Run one episode and score it.

    python3 -m kernel.run --task task01_order_confirmation --condition team --budget 10
    python3 -m kernel.run --task task01_order_confirmation --condition team --oracle    # scripted reference team, costs nothing

With --isolation containers every agent's tests run in a container that holds only that agent's files, and the
company is scored in a container of its own. That mode needs docker, so run it on the host:
    python3 -m kernel.run --task task01_order_confirmation --condition team --oracle --isolation containers

Conditions: team (the task's owners, with messaging), team_no_messaging, solo (one agent, the whole company), lead (one
agent that decides how to staff the work and may start others). Every condition gets the same budget, in dollars.

The reward puts being right first and being cheap second. Being right is the task's rubric: the share of feature
criteria passed times the share of regression criteria passed, so every ticket done earns something and an
untouched company earns nothing. Only when that is 1 is the unspent share of the budget added, so the reward
runs from 0 to 2.
Writes runs/<run-id>/{events.jsonl, result.json}, one ATIF trajectory per agent in runs/<run-id>/trajectories/, and
leaves the final workspace in runs/<run-id>/ws.
"""
import argparse
import json
import os
import time

from .episode import CONDITIONS, prepare_workspace, run_episode
from .model import AnthropicModel, OpenAIFormatModel, ScriptedModel
from . import atif
from .containers import IMAGE, Containers, score
from .score import run_hidden, run_own_tests

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def oracle_scripts(task: dict, task_dir: str, condition: str) -> dict:
    """The reference team: each owner writes the reference solution's files for its service, tests, and submits."""
    sol = os.path.join(task_dir, "solution", "services")
    team = list(task["briefs"])
    changed = sorted(os.listdir(sol))          # the owners the reference solution touches
    scripts = {}
    alone = {"solo": "solo", "lead": "lead"}.get(condition)      # one agent writes the whole solution
    for owner in ([alone] if alone else team):
        writes = []
        for s in (changed if alone else [owner]):
            for d, _, files in os.walk(os.path.join(sol, s)):
                for f in sorted(files):
                    full = os.path.join(d, f)
                    rel = os.path.relpath(full, sol if alone else os.path.join(sol, s))
                    writes.append(("write_file", {"path": rel, "content": open(full).read()}))
        tests = [("run_tests", {"service": s}) for s in changed] if alone else [("run_tests", {})]
        scripts[owner] = [writes, tests, [("submit", {"summary": "reference solution applied"})]]
    return scripts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True)
    ap.add_argument("--condition", choices=CONDITIONS, default="team")
    ap.add_argument("--budget", type=float, default=10.0, help="shared budget for the episode, in dollars")
    ap.add_argument("--max-calls", type=int, default=400, help="hard stop on model calls (safety net)")
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--effort", default="high")
    ap.add_argument("--api", choices=("openai", "anthropic"), default=os.environ.get("SEEDCO_API", "openai"),
                    help="how the model is reached: openai is an OpenAI-format endpoint (OPENAI_BASE_URL, OPENAI_API_KEY); "
                         "anthropic is the Messages API through the Anthropic SDK (ANTHROPIC_API_KEY)")
    ap.add_argument("--oracle", action="store_true", help="play the scripted reference team instead of a model")
    ap.add_argument("--runs-dir", default=os.environ.get("SEEDCO_RUNS", os.path.join(REPO, "runs")))
    ap.add_argument("--run-id")
    ap.add_argument("--isolation", choices=("process", "containers"), default="process",
                    help="process: tests run as child processes here; containers: one container per agent")
    ap.add_argument("--image", default=IMAGE, help="the toolchain image for --isolation containers")
    args = ap.parse_args()

    task_dir = os.path.join(REPO, "tasks", args.task)
    task = json.load(open(os.path.join(task_dir, "task.json")))
    run_id = args.run_id or "{}-{}-{}-{}".format(args.task, args.condition, "oracle" if args.oracle else args.model,
                                                  time.strftime("%Y%m%d-%H%M%S"))
    run_dir = os.path.join(args.runs_dir, run_id)
    workspace = prepare_workspace(REPO, task_dir, os.path.join(run_dir, "ws"))
    build_base = os.path.join("/tmp", "seedco-build-run", run_id)
    model = (ScriptedModel(oracle_scripts(task, task_dir, args.condition)) if args.oracle
             else OpenAIFormatModel(args.model, args.effort) if args.api == "openai" else AnthropicModel(args.model, args.effort))
    containers = Containers(run_id, args.image) if args.isolation == "containers" else None
    try:
        summary = run_episode(task, args.condition, model, workspace, os.path.join(run_dir, "events.jsonl"),
                              args.budget, args.max_calls, build_base, containers)
    finally:
        if containers:
            containers.stop()
    result = dict(summary, run_id=run_id, isolation=args.isolation)
    result["trajectories"] = [os.path.relpath(p, run_dir) for p in atif.write(run_dir)]      # before scoring: kept even if scoring fails
    if summary["valid"] and containers:
        result.update(score(task_dir, os.path.realpath(workspace), os.path.join(REPO, "kernel"), args.image))
    elif summary["valid"]:
        result["hidden"] = run_hidden(task_dir, workspace)
        result["own_tests"] = run_own_tests(workspace, build_base)
    if "hidden" in result:
        right = result["hidden"]["score"]
        unspent = max(0.0, 1 - summary["dollars_used"] / args.budget) if args.budget > 0 else 0.0
        result["reward"] = round(right + (unspent if right == 1.0 else 0.0), 4)
    json.dump(result, open(os.path.join(run_dir, "result.json"), "w"), indent=2)
    brief = {k: result.get(k) for k in ("run_id", "end", "error", "dollars_used", "tokens_used", "model_calls", "messages_sent", "reward")}
    brief["agents"] = {a: v["directories"] for a, v in result["agents"].items()}
    if "hidden" in result:
        hidden = result["hidden"]
        brief.update(score=hidden["score"], progress=hidden["progress"], regression=hidden["regression"],
                     tickets=hidden["tickets"], own_tests=result["own_tests"],
                     failed=[n for n, c in result["hidden"]["checks"].items() if not c["passed"]])
    print(json.dumps(brief, indent=2))


if __name__ == "__main__":
    main()

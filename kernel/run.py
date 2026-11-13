"""Run one episode and score it.

    python3 -m kernel.run --task task01_money --condition team --budget 3000000
    python3 -m kernel.run --task task01_money --condition team --oracle        # scripted reference team, no tokens

Conditions: team (four owners with messaging), team_no_messaging, solo (one agent, all four services, same budget).
Writes runs/<run-id>/{events.jsonl, result.json} and leaves the final workspace in runs/<run-id>/ws.
"""
import argparse
import json
import os
import time

from .episode import CONDITIONS, SERVICES, prepare_workspace, run_episode
from .model import AnthropicModel, ScriptedModel
from .score import run_hidden, run_own_tests

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def oracle_scripts(task_dir: str, condition: str) -> dict:
    """The reference team: each owner writes the reference solution's files for its service, tests, and submits."""
    sol = os.path.join(task_dir, "solution", "services")
    scripts = {}
    for owner in (["solo"] if condition == "solo" else SERVICES):
        writes = []
        for s in (SERVICES if owner == "solo" else [owner]):
            for d, _, files in os.walk(os.path.join(sol, s)):
                for f in sorted(files):
                    full = os.path.join(d, f)
                    rel = os.path.relpath(full, sol if owner == "solo" else os.path.join(sol, s))
                    writes.append(("write_file", {"path": rel, "content": open(full).read()}))
        tests = [("run_tests", {"service": s}) for s in SERVICES] if owner == "solo" else [("run_tests", {})]
        scripts[owner] = [writes, tests, [("submit", {"summary": "reference solution applied"})]]
    return scripts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True)
    ap.add_argument("--condition", choices=CONDITIONS, default="team")
    ap.add_argument("--budget", type=int, default=3_000_000, help="shared token budget for the episode")
    ap.add_argument("--max-calls", type=int, default=400, help="hard stop on model calls (safety net)")
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--effort", default="high")
    ap.add_argument("--oracle", action="store_true", help="play the scripted reference team instead of a model")
    ap.add_argument("--runs-dir", default=os.environ.get("SEEDCO_RUNS", os.path.join(REPO, "runs")))
    ap.add_argument("--run-id")
    args = ap.parse_args()

    task_dir = os.path.join(REPO, "tasks", args.task)
    task = json.load(open(os.path.join(task_dir, "task.json")))
    run_id = args.run_id or "{}-{}-{}-{}".format(args.task, args.condition, "oracle" if args.oracle else args.model,
                                                  time.strftime("%Y%m%d-%H%M%S"))
    run_dir = os.path.join(args.runs_dir, run_id)
    workspace = prepare_workspace(REPO, task_dir, os.path.join(run_dir, "ws"))
    build_base = os.path.join("/tmp", "seedco-build-run", run_id)
    model = (ScriptedModel(oracle_scripts(task_dir, args.condition)) if args.oracle
             else AnthropicModel(args.model, args.effort))
    summary = run_episode(task, args.condition, model, workspace, os.path.join(run_dir, "events.jsonl"),
                          args.budget, args.max_calls, build_base)
    result = dict(summary, run_id=run_id)
    if summary["valid"]:
        result["hidden"] = run_hidden(task_dir, workspace)
        result["own_tests"] = run_own_tests(workspace, build_base)
    json.dump(result, open(os.path.join(run_dir, "result.json"), "w"), indent=2)
    brief = {k: result.get(k) for k in ("run_id", "end", "error", "tokens_used", "model_calls", "messages_sent")}
    if "hidden" in result:
        brief.update(score=result["hidden"]["score"], boundaries=result["hidden"]["boundaries"],
                     own_tests=result["own_tests"],
                     failed=[n for n, c in result["hidden"]["checks"].items() if not c["passed"]])
    print(json.dumps(brief, indent=2))


if __name__ == "__main__":
    main()

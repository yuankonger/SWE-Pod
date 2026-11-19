"""Run one task under several conditions and print them side by side.

    python3 -m kernel.experiment --task task01_order_confirmation                       # solo, lead, team, team_no_messaging
    python3 -m kernel.experiment --task task01_order_confirmation --runs 3 --budget 5
    python3 -m kernel.experiment --task task01_order_confirmation --oracle              # scripted reference team: costs nothing

Every condition gets the same model, effort, tools and budget in dollars. Results go to runs/<experiment id>/:
one directory per episode (events.jsonl, result.json, the final workspace) and summary.json for the whole table.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def reached_outside(events_path: str) -> list:
    """Tool calls in which a team agent wrote something that points outside its own directory.

    Each agent's files are confined by the kernel, but in one shared container the tests an agent writes run as
    ordinary code. This lists writes that climb above the agent's directory (more `../` than the file is deep) or
    name the services directory, to be read by hand."""
    found = []
    with open(events_path) as f:
        for line in f:
            e = json.loads(line)
            if e.get("kind") != "tool" or e.get("name") not in ("write_file", "edit_file") or e.get("agent") == "solo":
                continue
            path = e["input"].get("path", "")
            depth = path.count("/")                       # directories between the agent's root and the file
            text = " ".join(str(e["input"].get(k, "")) for k in ("content", "new"))
            climbs = max((len(m.group(0)) // 3 for m in re.finditer(r"(?:\.\./)+", text)), default=0)
            if climbs > depth or "/work/services" in text or "services/" in text:
                found.append({"agent": e["agent"], "tool": e["name"], "path": path})
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True)
    ap.add_argument("--conditions", nargs="+", default=["solo", "lead", "team", "team_no_messaging"])
    ap.add_argument("--runs", type=int, default=1, help="episodes per condition")
    ap.add_argument("--budget", type=float, default=10.0, help="shared budget per episode in dollars, the same for every condition")
    ap.add_argument("--max-calls", type=int, default=400)
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--effort", default="high")
    ap.add_argument("--api", choices=("openai", "anthropic"), default=os.environ.get("SEEDCO_API", "openai"))
    ap.add_argument("--oracle", action="store_true", help="play the scripted reference team instead of a model")
    ap.add_argument("--isolation", choices=("process", "containers"), default="process")
    ap.add_argument("--id", default=time.strftime("exp-%Y%m%d-%H%M%S"))
    args = ap.parse_args()

    runs_dir = os.path.join(os.environ.get("SEEDCO_RUNS", os.path.join(REPO, "runs")), args.id)
    rows = []
    for condition in args.conditions:
        for i in range(1, args.runs + 1):
            run_id = "{}-{}".format(condition, i)
            cmd = [sys.executable, "-m", "kernel.run", "--task", args.task, "--condition", condition, "--budget", str(args.budget),
                   "--max-calls", str(args.max_calls), "--model", args.model, "--effort", args.effort, "--api", args.api, "--runs-dir", runs_dir,
                   "--run-id", run_id, "--isolation", args.isolation] + (["--oracle"] if args.oracle else [])
            print("running {} ...".format(run_id), flush=True)
            subprocess.run(cmd, cwd=REPO, stdout=subprocess.DEVNULL)
            path = os.path.join(runs_dir, run_id, "result.json")
            if not os.path.isfile(path):
                rows.append({"run": run_id, "condition": condition, "end": "crashed"})
                continue
            r = json.load(open(path))
            hidden = r.get("hidden") or {}
            rows.append({
                "run": run_id, "condition": condition, "end": r["end"], "error": r.get("error"),
                "passed": hidden.get("passed"), "total": hidden.get("total"),
                "progress": hidden.get("progress"), "regression": hidden.get("regression"), "tickets": hidden.get("tickets") or {},
                "failed": sorted(n for n, c in (hidden.get("checks") or {}).items() if not c["passed"]),
                "own_tests_failing": sorted(k for k, v in (r.get("own_tests") or {}).items() if not v),
                "dollars": r["dollars_used"], "reward": r.get("reward"), "tokens": r["tokens_used"],
                "model_calls": r["model_calls"], "messages": r["messages_sent"], "wall_seconds": r["wall_seconds"],
                "usage": r.get("usage", {}),
                "agents": {a: {"directories": v["directories"], "calls": v["calls"], "dollars": v["dollars"]} for a, v in r["agents"].items()},
                "reached_outside": reached_outside(os.path.join(runs_dir, run_id, "events.jsonl")),
            })
    summary = {"task": args.task, "model": "scripted reference" if args.oracle else args.model, "effort": args.effort,
               "budget": args.budget, "isolation": args.isolation, "rows": rows}
    json.dump(summary, open(os.path.join(runs_dir, "summary.json"), "w"), indent=2)

    print("\n{} on {} (effort {}, budget ${:,.2f} per episode)".format(args.task, summary["model"], args.effort, args.budget))
    print("{:<22} {:>8} {:>8} {:>10} {:>8} {:>7} {:>6} {:>6} {:>5} {:>7}  {}".format(
        "run", "criteria", "progress", "regression", "cost", "reward", "agents", "calls", "msgs", "minutes", "ended / tickets not finished"))
    for row in rows:
        if row["end"] == "crashed" or row.get("passed") is None:
            print("{:<22} {:>7}  {}".format(row["run"], "-", row.get("error") or row["end"]))
            continue
        unfinished = ", ".join("{} {:.0%}".format(t, s) for t, s in row["tickets"].items() if s < 1)
        print("{:<22} {:>8} {:>8.2f} {:>10.2f} {:>8} {:>7.3f} {:>6} {:>6} {:>5} {:>7.1f}  {} {}".format(
            row["run"], "{}/{}".format(row["passed"], row["total"]), row["progress"], row["regression"], "${:.2f}".format(row["dollars"]),
            row["reward"], len(row["agents"]), row["model_calls"], row["messages"], row["wall_seconds"] / 60, row["end"], unfinished))
        if row["condition"] == "lead" and len(row["agents"]) > 1:      # how the lead chose to staff the work
            for name, a in row["agents"].items():
                if name != "lead":
                    print("{:<22} started `{}` with {} (${:.2f}, {} calls)".format("", name, ", ".join(a["directories"]), a["dollars"], a["calls"]))
        if row["own_tests_failing"]:
            print("{:<22} own tests failing: {}".format("", ", ".join(row["own_tests_failing"])))
        if row["reached_outside"]:
            print("{:<22} wrote paths outside its own directory, check by hand: {}".format("", row["reached_outside"][:3]))
    print("\nsummary: {}".format(os.path.join(runs_dir, "summary.json")))


if __name__ == "__main__":
    main()

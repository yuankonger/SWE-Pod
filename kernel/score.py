"""Scoring: run a task's rubric against a finished workspace, and each service's own tests.

The rubric (`rubric.toml` in the task's hidden directory) lists the criteria; `kernel/rubric.py` runs them in a
process of its own and returns the reward: the share of feature criteria passed, times the share of regression
criteria passed. See that file for the format.
"""
import json
import os
import subprocess
import sys
import tempfile

from .episode import check_dirs, seed_dir

HERE = os.path.dirname(os.path.abspath(__file__))


def run_hidden(task_dir: str, workspace: str, base_port: int = 7100, judge: bool = False) -> dict:
    """Start the workspace's company and run the task's rubric against it.

    Returns the rubric's result (reward, progress, regression, tickets, criteria) with `score` (the reward) and
    `checks` ({criterion id: {passed, detail}}) beside it. The stack runner and the checks are the repository's,
    never the workspace's copies."""
    out = tempfile.mkdtemp(prefix="seedco-verify-")
    seed = seed_dir(task_dir)      # the company starts from the task's history, if it has one
    cmd = [sys.executable, os.path.join(HERE, "rubric.py"), "--workspace", workspace, "--out", out, "--base-port", str(base_port),
           "--platform", os.path.join(HERE, "..", "platform"), "--checks"] + check_dirs(task_dir)
    p = subprocess.run(cmd + (["--seed", seed] if seed else []) + (["--judge"] if judge else []),
                       capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    path = os.path.join(out, "rubric.json")
    if not os.path.isfile(path):      # the verifier itself failed: that is an error, never a score
        raise RuntimeError("the verifier did not finish:\n" + (p.stderr or p.stdout)[-3000:])
    with open(path) as f:
        result = json.load(f)
    result["score"] = result["reward"]
    result["checks"] = {c["id"]: {"passed": bool(c["passed"]), "detail": c["detail"]} for c in result["criteria"] if c["passed"] is not None}
    return result


def run_own_tests(workspace: str, build_base: str) -> dict:
    out = {}
    for s in sorted(os.listdir(os.path.join(workspace, "services"))):
        cwd = os.path.join(workspace, "services", s)
        if not os.path.isfile(os.path.join(cwd, "run")):
            continue
        try:
            p = subprocess.run(["./run", "test"], cwd=cwd, capture_output=True, text=True, timeout=300,
                               env=dict(os.environ, SEEDCO_BUILD_DIR=os.path.join(build_base, "score-" + s)))
            out[s] = p.returncode == 0
        except subprocess.TimeoutExpired:
            out[s] = False
    return out


if __name__ == "__main__":
    # python3 -m kernel.score <task dir> <workspace>: prints the scores as one line of JSON (used for container scoring)
    task_dir, workspace = sys.argv[1], sys.argv[2]
    print(json.dumps({"hidden": run_hidden(task_dir, workspace), "own_tests": run_own_tests(workspace, "/tmp/seedco-build-score")}))

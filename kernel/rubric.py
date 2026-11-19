"""The verifier: runs a task's rubric against a finished company and writes the reward.

A rubric is a list of criteria in `rubric.toml`. Each criterion says what it checks, how, and why:

    [[criterion]]
    id = "ops7-confirm-once"
    ticket = "OPS-7"            # the ticket it belongs to (feature criteria)
    kind = "feature"            # feature: what the work adds, fails on the company as it was
                                # regression: what must keep working, passes on the company as it was
    type = "test"               # how it is decided, one of:
    test = "test_core_api__staff_confirm_an_order_once"     #   test: a check method, run against the running company
    # run = "promtool check rules rules/*.yml"              #   command: a shell command in the company's directory; exit 0 passes
    # prompt = "..."  files = ["services/ops/runbooks/*.md"]  # judge: a question a model answers about those files
    weight = 1
    note = "Why this criterion exists, in a sentence or two."

The reward measures progress and is 0 for a company nobody touched:

    progress   = weighted share of feature criteria that pass
    regression = weighted share of regression criteria that pass
    reward     = progress x regression

Judge criteria need a model and are only run with --judge. Without it they are reported as not run and are left
out of the reward, so a reward computed with the judge and one computed without are not comparable.

    python3 kernel/rubric.py --workspace <company> --checks <dir> [<dir> ...] --out <dir>
        [--seed <dir>] [--platform <dir>] [--base-port 7100] [--judge] [--judge-model claude-opus-5-5]

`--checks` are the directories that hold `rubric.toml` files and the check code; every rubric found is used, and
the test class is the one in the last `test_task.py`. Writes `<out>/rubric.json` and `<out>/reward.txt`.
This file uses only the standard library (and the `anthropic` package for --judge), so it runs anywhere the
company does.
"""
import argparse
import glob
import importlib.util
import json
import os
import subprocess
import sys
import tomllib
import unittest

KINDS = ("feature", "regression")
TYPES = {"test": "test", "command": "run", "judge": "prompt"}       # type -> the key that holds what to run
JUDGE_SYSTEM = """You are grading one criterion of a software change. You are given the criterion and the files it is
about. Decide only what the criterion asks, from the files alone. Explain in two or three sentences, then end
with a last line that is exactly `VERDICT: PASS` or `VERDICT: FAIL`."""


def load(check_dirs: list) -> list:
    """Every criterion of the rubrics in `check_dirs`, in order, validated."""
    criteria = []
    for d in check_dirs:
        path = os.path.join(d, "rubric.toml")
        if os.path.isfile(path):
            with open(path, "rb") as f:
                criteria += tomllib.load(f).get("criterion", [])
    seen = set()
    for c in criteria:
        missing = [k for k in ("id", "kind", "type", "note") if not c.get(k)]
        if missing:
            raise ValueError("criterion {} has no {}".format(c.get("id", c), ", ".join(missing)))
        if c["id"] in seen:
            raise ValueError("two criteria are called {}".format(c["id"]))
        seen.add(c["id"])
        if c["kind"] not in KINDS or c["type"] not in TYPES or not c.get(TYPES[c["type"]]):
            raise ValueError("criterion {}: kind must be one of {}, type one of {} with its `{}`".format(
                c["id"], KINDS, tuple(TYPES), TYPES.get(c["type"], "...")))
        c.setdefault("weight", 1)
        c.setdefault("ticket", None)
        if c["kind"] == "feature" and not c["ticket"]:
            raise ValueError("criterion {}: a feature criterion names its ticket".format(c["id"]))
    if not criteria:
        raise ValueError("no rubric.toml with criteria in {}".format(check_dirs))
    return criteria


class _Collector(unittest.TextTestResult):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.outcomes, self.setup = {}, None

    def addSuccess(self, test):
        super().addSuccess(test)
        self.outcomes[test.id().split(".")[-1]] = (True, "")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.outcomes[test.id().split(".")[-1]] = (False, self._exc_info_to_string(err, test)[-1500:])

    def addError(self, test, err):
        super().addError(test, err)
        if "setUpClass" in test.id():
            self.setup = self._exc_info_to_string(err, test)[-3000:]
        else:
            self.outcomes[test.id().split(".")[-1]] = (False, self._exc_info_to_string(err, test)[-1500:])


def run_tests(criteria: list, check_dirs: list, stream) -> dict:
    """Runs the `test` criteria against one running company. Returns {criterion id: (passed, detail)}."""
    wanted = {c["test"]: c["id"] for c in criteria if c["type"] == "test"}
    if not wanted:
        return {}
    holder = [d for d in check_dirs if os.path.isfile(os.path.join(d, "test_task.py"))][-1]
    spec = importlib.util.spec_from_file_location("rubric_checks", os.path.join(holder, "test_task.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tests = {t.id().split(".")[-1]: t for group in unittest.defaultTestLoader.loadTestsFromModule(module) for t in group}
    # The rubric and the check code must name the same checks: a check nobody listed would run unexplained, and a
    # criterion with no check behind it would always fail.
    if set(tests) != set(wanted) or len(wanted) != sum(1 for c in criteria if c["type"] == "test"):
        raise ValueError("the rubric and the checks disagree. Not in the rubric: {}. Not in the checks: {}".format(
            sorted(set(tests) - set(wanted)), sorted(set(wanted) - set(tests))))
    result = unittest.TextTestRunner(stream=stream, resultclass=_Collector, verbosity=2).run(unittest.TestSuite(tests.values()))
    if result.setup:      # the company did not start: nothing could be checked
        return {wanted[name]: (False, "the company did not start:\n" + result.setup) for name in wanted}
    return {wanted[name]: result.outcomes.get(name, (False, "the check did not run")) for name in wanted}


def run_command(criterion: dict, workspace: str):
    try:
        p = subprocess.run(["bash", "-c", criterion["run"]], cwd=workspace, capture_output=True, text=True,
                           timeout=criterion.get("timeout", 300), env=dict(os.environ, SEEDCO_ROOT=workspace))
    except subprocess.TimeoutExpired:
        return False, "the command did not finish in time"
    return p.returncode == 0, "" if p.returncode == 0 else "exit code {}\n{}".format(p.returncode, (p.stdout + p.stderr)[-1500:])


def judge_with(model: str):
    """A judge that asks a Claude model. Returns ask(system, question) -> the model's answer."""
    import anthropic

    client = anthropic.Anthropic(max_retries=4)

    def ask(system, question):
        response = client.messages.create(model=model, max_tokens=4000, system=system, messages=[{"role": "user", "content": question}])
        return "\n".join(b.text for b in response.content if b.type == "text")
    return ask


def run_judge(criterion: dict, workspace: str, ask):
    """Shows the judge the criterion and the files it names. Passes only on an explicit `VERDICT: PASS`."""
    paths = sorted(p for pattern in criterion.get("files", []) for p in glob.glob(os.path.join(workspace, pattern), recursive=True)
                   if os.path.isfile(p))
    shown = []
    for path in paths[:40]:
        with open(path, errors="replace") as f:
            shown.append("=== {} ===\n{}".format(os.path.relpath(path, workspace), f.read()[:20000]))
    question = "Criterion:\n{}\n\nFiles ({}):\n\n{}".format(criterion["prompt"].strip(), len(shown), "\n\n".join(shown) or "(no file matches)")
    answer = ask(JUDGE_SYSTEM, question).strip()
    last = answer.splitlines()[-1].strip() if answer else ""
    return last == "VERDICT: PASS", answer[-1500:]


def share(rows: list):
    total = sum(r["weight"] for r in rows)
    return sum(r["weight"] for r in rows if r["passed"]) / total if total else None


def run(workspace: str, check_dirs: list, platform: str, seed: str = None, base_port: int = 7100, ask=None, stream=None) -> dict:
    """Runs every criterion and returns the result. `ask` is the judge (see judge_with); without one, judge criteria are not run."""
    workspace, check_dirs = os.path.abspath(workspace), [os.path.abspath(d) for d in check_dirs if os.path.isdir(d)]
    criteria = load(check_dirs)
    os.environ.update(SEEDCO_ROOT=workspace, SEEDCO_BASE_PORT=str(base_port))
    os.environ.pop("SEEDCO_SEED_DIR", None)
    if seed:
        os.environ["SEEDCO_SEED_DIR"] = os.path.abspath(seed)
    # The verifier's own stack runner and check code come first on the import path, never the company's copies.
    sys.path[:0] = [os.path.abspath(platform)] + check_dirs[::-1]
    from stack import OFFSETS, free_ports

    # Whatever was left listening on the company's ports is killed before the company is started on them.
    cleared = free_ports({base_port + off for off in OFFSETS.values()})
    outcomes = run_tests(criteria, check_dirs, stream or open(os.devnull, "w"))
    rows = []
    for c in criteria:
        if c["type"] == "test":
            passed, detail = outcomes[c["id"]]
        elif c["type"] == "command":
            passed, detail = run_command(c, workspace)
        elif ask:
            passed, detail = run_judge(c, workspace, ask)
        else:
            passed, detail = None, "not run: judge criteria need --judge"
        rows.append({"id": c["id"], "ticket": c["ticket"], "kind": c["kind"], "type": c["type"], "weight": c["weight"],
                     "note": " ".join(c["note"].split()), "passed": passed, "detail": detail,
                     "check": c[TYPES[c["type"]]] if c["type"] != "judge" else " ".join(c["prompt"].split())})
    scored = [r for r in rows if r["passed"] is not None]
    progress = share([r for r in scored if r["kind"] == "feature"]) or 0.0
    regression = share([r for r in scored if r["kind"] == "regression"])
    regression = 1.0 if regression is None else regression
    tickets = {}
    for r in scored:
        if r["kind"] == "feature":
            tickets.setdefault(r["ticket"], []).append(r)
    return {"reward": round(progress * regression, 4), "progress": round(progress, 4), "regression": round(regression, 4),
            "tickets": {t: round(share(v), 4) for t, v in tickets.items()},
            "passed": sum(1 for r in scored if r["passed"]), "total": len(scored),
            "not_run": [r["id"] for r in rows if r["passed"] is None], "judge": bool(ask),
            "ports_cleared": {str(port): pids for port, pids in sorted(cleared.items())}, "criteria": rows}


def reason(detail: str) -> str:
    """One line saying why a criterion failed: the check's own message if it gave one."""
    lines = [l.strip() for l in detail.strip().splitlines() if l.strip()]
    said = [l.split(" : ", 1)[1] for l in lines if " : " in l and not l.startswith(("File ", "self."))]
    errors = [l for l in lines if l.startswith(("AssertionError", "KeyError", "TypeError", "exit code"))]
    return (said or errors or lines or [""])[-1][:300]


def table(result: dict) -> str:
    """The result as text: one line per criterion with its note, then the reward."""
    lines = []
    for r in result["criteria"]:
        mark = {True: "PASS", False: "FAIL", None: "  - "}[r["passed"]]
        lines.append("{}  {:<10} {:<8} {:<7} {}\n      {}".format(mark, r["kind"], r["ticket"] or "", r["type"], r["id"], r["note"]))
        if r["passed"] is False and r["detail"]:
            lines.append("      -> " + reason(r["detail"]))
    lines.append("")
    lines.append("tickets: " + ", ".join("{} {:.0%}".format(t, s) for t, s in result["tickets"].items()))
    lines.append("progress {:.4f} x regression {:.4f} = reward {:.4f}   ({} of {} criteria pass{})".format(
        result["progress"], result["regression"], result["reward"], result["passed"], result["total"],
        "; not run: " + ", ".join(result["not_run"]) if result["not_run"] else ""))
    return "\n".join(lines)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", required=True, help="the company to verify")
    ap.add_argument("--checks", nargs="+", required=True, help="directories with rubric.toml files and the check code")
    ap.add_argument("--out", required=True, help="where rubric.json and reward.txt are written")
    ap.add_argument("--seed", help="the history the company is started from")
    ap.add_argument("--platform", default=os.path.join(here, "..", "platform"), help="the directory of the verifier's stack runner")
    ap.add_argument("--base-port", type=int, default=7100)
    ap.add_argument("--judge", action="store_true", help="run judge criteria (needs ANTHROPIC_API_KEY)")
    ap.add_argument("--judge-model", default="claude-opus-5-5")
    args = ap.parse_args()
    result = run(args.workspace, args.checks, args.platform, args.seed, args.base_port,
                 judge_with(args.judge_model) if args.judge else None, sys.stdout)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "rubric.json"), "w") as f:
        json.dump(result, f, indent=2)
    with open(os.path.join(args.out, "reward.txt"), "w") as f:
        f.write("{:.4f}\n".format(result["reward"]))
    print(table(result))


if __name__ == "__main__":
    main()

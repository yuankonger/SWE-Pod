"""Scoring: run a task's hidden checks against a finished workspace, and each service's own tests.

Hidden checks are unittest methods named `test_<boundary>__<what>`. Each one is a separate check, so a failure can
be placed at a boundary. The score is the share of hidden checks that pass.
"""
import importlib.util
import os
import subprocess
import sys
import unittest


class _Collector(unittest.TextTestResult):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.checks = {}

    def _note(self, test, outcome, detail=""):
        self.checks[test.id().split(".")[-1]] = {"passed": outcome == "pass", "detail": detail[-1500:]}

    def addSuccess(self, test):
        super().addSuccess(test)
        self._note(test, "pass")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._note(test, "fail", self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        if hasattr(test, "id") and "setUpClass" not in test.id():
            self._note(test, "error", self._exc_info_to_string(err, test))
        else:
            self.checks["__setup__"] = {"passed": False, "detail": self._exc_info_to_string(err, test)[-3000:]}


def run_hidden(task_dir: str, workspace: str, base_port: int = 7100) -> dict:
    """Start the workspace's company and run the task's hidden checks against it."""
    os.environ["SEEDCO_ROOT"] = workspace
    os.environ["SEEDCO_BASE_PORT"] = str(base_port)
    sys.path.insert(0, os.path.join(workspace, "platform"))
    try:
        spec = importlib.util.spec_from_file_location("hidden_checks", os.path.join(task_dir, "hidden", "test_task.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        suite = unittest.defaultTestLoader.loadTestsFromModule(module)
        names = sorted(t.id().split(".")[-1] for group in suite for t in group)
        result = unittest.TextTestRunner(stream=open(os.devnull, "w"), resultclass=_Collector).run(suite)
    finally:
        sys.path.pop(0)
        sys.modules.pop("stack", None)
    checks = result.checks
    if "__setup__" in checks:  # the company did not start: every check fails, with the reason attached once
        checks.update({n: {"passed": False, "detail": "the company did not start"} for n in names})
    passed = sum(1 for n in names if checks.get(n, {}).get("passed"))
    by_boundary = {}
    for n in names:
        b = n[len("test_"):].split("__")[0]
        by_boundary.setdefault(b, []).append(bool(checks.get(n, {}).get("passed")))
    return {"score": passed / len(names) if names else 0.0, "passed": passed, "total": len(names), "checks": checks,
            "boundaries": {b: sum(v) / len(v) for b, v in by_boundary.items()}}


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

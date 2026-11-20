"""A mined task, end to end: build its environment, prepare a workspace, run an agent on it, score the result.

    python3 tools/mined_pilot.py image     <task> <clone>                 build the task's image
    python3 tools/mined_pilot.py reference <task> <clone> <base.xml> <target.xml> [<scored target.xml>]   keep which tests are new and which preserved
    python3 tools/mined_pilot.py prepare   <task> <clone> <workspace>     the base tree, what is handed over, NOTES.md
    python3 tools/mined_pilot.py score     <task> <clone> <workspace> <out dir>     run the project's suite, write result.json
    python3 tools/mined_pilot.py run       <task> <clone> --model M [--budget 20] [--condition solo] [--oracle base|target]

`<task>` is a directory under mined/. `<clone>` is a local clone of the task's repository that holds both
commits. `run` uses the kernel (one container per agent, a shell in it) and so runs on this machine, not inside
an image. JUnit reports for `reference` come from running the suite at the base and at the target (see mined/README.md).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "tools"))


def git(clone, *args, text=True):
    return subprocess.run(["git", "-C", clone] + list(args), capture_output=True, text=text, check=True).stdout


def load(task):
    task_dir = os.path.join(REPO, "mined", task)
    with open(os.path.join(task_dir, "task.json")) as f:
        return task_dir, json.load(f)


def is_test_side(path):
    return path.endswith(".py") and ("/tests/" in path or path.endswith("conftest.py") or "/fixtures" in path)


def export(clone, commit, dest):
    """The commit's tree with no history."""
    os.makedirs(dest, exist_ok=True)
    archive = subprocess.Popen(["git", "-C", clone, "archive", commit], stdout=subprocess.PIPE)
    subprocess.run(["tar", "-x", "-C", dest], stdin=archive.stdout, check=True)
    archive.wait()


def put(clone, commit, paths, dest):
    for path in paths:
        out = os.path.join(dest, path)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as f:
            f.write(git(clone, "show", "{}:{}".format(commit, path), text=False))


def image(task, clone):
    task_dir, info = load(task)
    context = tempfile.mkdtemp(prefix="mined-image-")
    shutil.copy(os.path.join(task_dir, "Dockerfile"), context)
    # `deps`: the files at the base that the Dockerfile installs from (the lockfiles), at their paths in the repository
    put(clone, info["base"], info.get("deps", ["pyproject.toml", "uv.lock"]), context)
    subprocess.run(["docker", "build", "-q", "-t", info["image"], context], check=True)
    shutil.rmtree(context, ignore_errors=True)


def prepare(task, clone, workspace, commit=None):
    """`<workspace>/services/<directory>`: the base tree, the files handed over from the target, and NOTES.md."""
    _, info = load(task)
    dest = os.path.join(workspace, "services", info["directory"])
    shutil.rmtree(workspace, ignore_errors=True)
    export(clone, commit or info["base"], dest)
    put(clone, info["target"], info["handed_over"], dest)
    with open(os.path.join(dest, "NOTES.md"), "w") as f:
        f.write(info["notes"])
    # the names the hidden tests reach for that the base does not have (tools/mined_interface.py)
    interface = os.path.join(REPO, "mined", task, "interface.json")
    if os.path.isfile(interface):
        import mined_interface
        with open(interface) as f, open(os.path.join(dest, "INTERFACE.md"), "w") as out:
            out.write(mined_interface.render(json.load(f), info.get("language", "python")))
        with open(os.path.join(dest, "NOTES.md"), "a") as f:
            f.write("\n- `INTERFACE.md` lists the names the hidden tests import that do not exist yet. Use exactly those names and places.\n")
    return dest


def passed(report):
    cases = {}
    for case in ET.parse(report).getroot().iter("testcase"):
        ok = not any(child.tag in ("failure", "error", "skipped") for child in case)
        cases[(case.get("classname") or "") + "::" + (case.get("name") or "")] = ok
    return {name for name, ok in cases.items() if ok}


def reference(task, clone, base_report, target_report, scored_target_report=None):
    """`scored_target_report`: the target scored the way an agent's work is (no network). A test that passes at the
    target only with a network cannot be asked of an agent's work, so it is left out."""
    task_dir, _ = load(task)
    base, target = passed(base_report), passed(target_report)
    if scored_target_report:
        target &= passed(scored_target_report)
    sets = {"new": sorted(target - base), "preserved": sorted(target & base)}
    with open(os.path.join(task_dir, "reference.json"), "w") as f:
        json.dump(sets, f)
    print("{}: {:,} new tests, {:,} preserved tests ({:,} base tests are gone at the target)".format(
        task, len(sets["new"]), len(sets["preserved"]), len(base - target)))


def score(task, clone, workspace, out_dir):
    """Lays the target's test side over a copy of the workspace, runs the project's suite there, and compares."""
    task_dir, info = load(task)
    with open(os.path.join(task_dir, "reference.json")) as f:
        sets = json.load(f)
    os.makedirs(out_dir, exist_ok=True)
    copy = os.path.join(tempfile.mkdtemp(prefix="mined-score-"), "repo")
    shutil.copytree(os.path.join(workspace, "services", info["directory"]), copy, symlinks=True,
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    changed = [p for p in git(clone, "diff", "--name-only", "--diff-filter=AM", info["base"], info["target"]).splitlines() if is_test_side(p)]
    put(clone, info["target"], changed, copy)          # the hidden tests, and the fixtures as the project has them
    started = time.time()
    run = subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", copy + ":/repo", "-v", os.path.abspath(out_dir) + ":/out", "-w", "/repo",
                          info["image"], "bash", "-c", info["test_command"] + " --junitxml=/out/junit.xml > /out/tests.log 2>&1; echo exit $?"],
                         capture_output=True, text=True)
    ran = passed(os.path.join(out_dir, "junit.xml")) if os.path.isfile(os.path.join(out_dir, "junit.xml")) else set()
    new, kept = [t for t in sets["new"] if t in ran], [t for t in sets["preserved"] if t in ran]
    progress, regression = len(new) / len(sets["new"]), len(kept) / len(sets["preserved"])
    areas = {}
    for name in sets["new"]:
        area = name.split("::")[0].split(".tests")[0]
        areas.setdefault(area, [0, 0])
        areas[area][0] += name in ran
        areas[area][1] += 1
    result = {"reward": round(progress * regression, 4), "progress": round(progress, 4), "regression": round(regression, 4),
              "new_passed": len(new), "new_total": len(sets["new"]), "preserved_passed": len(kept), "preserved_total": len(sets["preserved"]),
              "suite_started": bool(ran), "seconds": round(time.time() - started), "suite_exit": run.stdout.strip()[-20:],
              "new_by_area": {a: "{}/{}".format(*v) for a, v in sorted(areas.items())}}
    with open(os.path.join(out_dir, "result.json"), "w") as f:
        json.dump(result, f, indent=2)
    shutil.rmtree(os.path.dirname(copy), ignore_errors=True)
    return result


def run(task, clone, args):
    from kernel import atif
    from kernel.containers import Containers
    from kernel.episode import run_episode
    from kernel.model import AnthropicModel, OpenAIFormatModel, ScriptedModel
    _, info = load(task)
    run_id = args.run_id or "{}-{}-{}-{}".format(task, args.condition, args.oracle or args.model, time.strftime("%Y%m%d-%H%M%S"))
    run_dir = os.path.join(REPO, "runs", run_id)
    workspace = os.path.join(run_dir, "ws")
    prepare(task, clone, workspace, commit=info["target"] if args.oracle == "target" else None)
    brief = info["brief"]
    # one repository: agents a lead starts work in the same tree, each in a container of its own
    spec = {"id": info["id"], "briefs": {info["directory"]: brief}, "solo_brief": brief, "lead_brief": brief,
            "overview": info.get("overview", ""), "what": "a software project", "shared_tree": True}
    if args.oracle:
        model = ScriptedModel({args.condition: [[("submit", {"summary": "the {} commit, untouched".format(args.oracle)})]]})
    else:
        model = OpenAIFormatModel(args.model, args.effort) if args.api == "openai" else AnthropicModel(args.model, args.effort)
    containers = Containers(run_id, info["image"])
    try:
        summary = run_episode(spec, args.condition, model, workspace, os.path.join(run_dir, "events.jsonl"), args.budget, args.max_calls,
                              os.path.join(tempfile.gettempdir(), "mined-build", run_id), containers)
    finally:
        containers.stop()
    result = dict(summary, run_id=run_id, trajectories=[os.path.relpath(p, run_dir) for p in atif.write(run_dir)])
    if summary["valid"]:
        result["hidden"] = score(task, clone, workspace, os.path.join(run_dir, "score"))
        right = result["hidden"]["reward"]
        unspent = max(0.0, 1 - summary["dollars_used"] / args.budget) if args.budget > 0 else 0.0
        result["reward"] = round(right + (unspent if right == 1.0 else 0.0), 4)
    with open(os.path.join(run_dir, "result.json"), "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps({k: result.get(k) for k in ("run_id", "end", "error", "dollars_used", "model_calls", "wall_seconds", "team_seconds", "agent_seconds", "reward", "hidden")}, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=("image", "reference", "prepare", "score", "run"))
    ap.add_argument("task")
    ap.add_argument("clone")
    ap.add_argument("rest", nargs="*")
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--effort", default="high")
    ap.add_argument("--api", choices=("openai", "anthropic"), default=os.environ.get("SEEDCO_API", "openai"))
    ap.add_argument("--condition", choices=("solo", "lead"), default="solo")
    ap.add_argument("--budget", type=float, default=20.0)
    ap.add_argument("--max-calls", type=int, default=1000)
    ap.add_argument("--oracle", choices=("base", "target"), help="score an untouched commit instead of running a model")
    ap.add_argument("--run-id")
    a = ap.parse_args()
    if a.command == "image":
        image(a.task, a.clone)
    elif a.command == "reference":
        reference(a.task, a.clone, *a.rest)
    elif a.command == "prepare":
        print(prepare(a.task, a.clone, a.rest[0]))
    elif a.command == "score":
        print(json.dumps(score(a.task, a.clone, *a.rest), indent=2))
    else:
        run(a.task, a.clone, a)

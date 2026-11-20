"""Exports a finished run's trajectories into the task, for whoever receives the task.

    python3 tools/export_trajectories.py <job dir> [<job dir> ...] [--task harbor/<company>] [--review <file>]

Run it as soon as a run finishes, before any review: the review reads what this writes. For each job
(runs/harbor/<job>), writes <task>/trajectories/<job>/:

    run.json                     model, condition, the freeze it ran on, the judge's reward, whether it is complete,
                                 every criterion, how each seat's work ended, the measures, the reward-hacking review
    <seat>.trajectory.json       one ATIF trajectory per seat. Harbor writes one for its own seat only; the others
                                 are converted here from their Claude Code session files, the same way
    judge/score.json, judge/rubric.txt     the judge's result (the reward to trust)
    records/git.jsonl, ci.json, chat.json, measures.json     the company's own records of the work
    REVIEW.md                    the review of the run (reward hacking, leakage, test quality), written after the
                                 export, from it. --review puts one in; exporting again keeps the one there

Secrets are removed: every git server, chat and judge token, the gateway key from .env, and local home paths.
The task's freeze excludes trajectories/ (tools/freeze.py), so adding runs does not change the frozen task.
A run whose work was stopped from outside, or whose scoring is incomplete, is exported with `complete: false`.
"""
import argparse
import glob
import json
import os
import re
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))


def secrets():
    """Every value that must not leave the machine: the company's tokens and the gateway's key."""
    import export_harbor_company as ex
    found = set(ex.TOKENS.values()) | {ex.CHAT_ADMIN, ex.JUDGE_TOKEN}
    found |= {"seat-{}-4e81b7".format(o) for o in ("core", "dashboard", "payments", "storefront", "apps", "taxes", "notifications")}
    env = os.path.join(REPO, ".env")
    if os.path.isfile(env):
        for line in open(env):
            if "=" in line and re.search(r"(KEY|TOKEN|SECRET)", line.split("=", 1)[0]):
                value = line.split("=", 1)[1].strip().strip("'\"")
                if len(value) >= 8:
                    found.add(value)
    return sorted(found, key=len, reverse=True)


def clean(text, hidden):
    for value in hidden:
        text = text.replace(value, "<redacted>")
    text = re.sub(r"/Users/[^/\s\"']+", "~", text)
    return re.sub(r"(OWNER|seat)-[a-z]+-(4e81b7|[0-9a-f]{12})\b", "<redacted>", text)


def convert(seat_dir, model):
    """The ATIF trajectory of one seat, from its Claude Code session files, as Harbor makes it for its own seat."""
    from pathlib import Path
    from harbor.agents.installed.claude_code import ClaudeCode
    agent = ClaudeCode(logs_dir=Path(seat_dir), model_name=model)
    session = agent._get_session_dir()
    trajectory = agent._convert_events_to_trajectory(session) if session else None
    return trajectory.to_json_dict() if trajectory else None


def export(job, task, review=None):
    trial = sorted(glob.glob(os.path.join(job, "*__*")))[0]
    name = os.path.basename(job.rstrip("/"))
    with open(os.path.join(trial, "config.json")) as f:
        config = json.load(f)
    agent = config["agent"]
    model = agent.get("model_name")
    team = "TeamClaudeCode" in (agent.get("import_path") or "")
    task = task or config["task"]["path"]
    out = os.path.join(task, "trajectories", name)
    kept_review = None      # a review written into an earlier export is kept when the run is exported again
    if not review and os.path.isfile(os.path.join(out, "REVIEW.md")):
        with open(os.path.join(out, "REVIEW.md")) as f:
            kept_review = f.read()
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(os.path.join(out, "judge"))
    os.makedirs(os.path.join(out, "records"))
    hidden = secrets()

    def put(text, *where):
        with open(os.path.join(out, *where), "w") as f:
            f.write(clean(text, hidden))

    # one trajectory per seat: Harbor's own seat, then each extra seat of a team (agent/<owner>/)
    seats = {}
    owners = [pair.split("=", 1) for pair in str(agent["kwargs"].get("seats", "main=solo")).split(",")] if team else [["main", "solo"]]
    for service, owner in owners:
        seat_dir = os.path.join(trial, "agent") if service == "main" else os.path.join(trial, "agent", owner)
        made = os.path.join(seat_dir, "trajectory.json")
        if os.path.isfile(made):
            with open(made) as f:
                trajectory = json.load(f)
        else:
            trajectory = convert(seat_dir, model)
        if trajectory is None:
            seats[owner] = {"trajectory": None, "note": "no session files were kept for this seat"}
            continue
        trajectory.setdefault("agent", {})["model_name"] = model      # Harbor's converter can leave "<synthetic>"
        trajectory.setdefault("extra", {})["seat"] = owner
        put(json.dumps(trajectory, indent=1, ensure_ascii=False), owner + ".trajectory.json")
        seats[owner] = {"trajectory": owner + ".trajectory.json", "steps": len(trajectory.get("steps", []))}
        run_file = os.path.join(seat_dir, "seat-run.json")
        if os.path.isfile(run_file):
            with open(run_file) as f:
                seats[owner]["run"] = json.load(f)

    judged = os.path.join(trial, "judge")
    score = {}
    for f in ("score.json", "rubric.txt"):
        if os.path.isfile(os.path.join(judged, f)):
            put(open(os.path.join(judged, f)).read(), "judge", f)
    if os.path.isfile(os.path.join(judged, "score.json")):
        with open(os.path.join(judged, "score.json")) as f:
            score = json.load(f)
    for rel, to in (("agent/git.jsonl", "git.jsonl"), ("agent/ci.json", "ci.json"), ("agent/chat.json", "chat.json")):
        if os.path.isfile(os.path.join(trial, rel)):
            put(open(os.path.join(trial, rel)).read(), "records", to)
    measures = {}
    if os.path.isfile(os.path.join(job, "measures.json")):
        with open(os.path.join(job, "measures.json")) as f:
            measures = json.load(f)
        put(json.dumps(measures, indent=1), "records", "measures.json")
    if review:
        put(open(review).read(), "REVIEW.md")
    elif kept_review:
        put(kept_review, "REVIEW.md")

    frozen = os.path.join(REPO, "runs", "harbor", "frozen", name + ".txt")
    stopped = {o: s["run"]["ended"] for o, s in seats.items() if s.get("run", {}).get("stopped_from_outside")}
    run = {"job": name, "model": model, "condition": ("team" if agent["kwargs"].get("messaging", True) not in (False, "false") else "team_no_messaging") if team else "solo",
           "harness": "claude-code " + str((json.load(open(os.path.join(trial, "agent", "trajectory.json"))).get("agent", {}).get("version")) if os.path.isfile(os.path.join(trial, "agent", "trajectory.json")) else ""),
           "budget_usd": agent["kwargs"].get("seat_total"), "frozen": open(frozen).read().strip() if os.path.isfile(frozen) else None,
           "reward": score.get("reward"), "scoring_complete": score.get("complete"), "stopped_from_outside": stopped,
           "complete": bool(score.get("complete")) and not stopped,
           "criteria": [{k: c.get(k) for k in ("id", "kind", "score", "detail")} for c in score.get("criteria", [])],
           "seats": seats, "outcome": measures.get("outcome"), "division": measures.get("division"), "control": measures.get("control"),
           "review": "REVIEW.md" if (review or kept_review) else "not reviewed yet"}
    now = os.path.join(task, "FROZEN.json")       # the task may have been frozen again since: say so, a reader compares runs
    if os.path.isfile(now) and run["frozen"]:
        with open(now) as f:
            run["task_frozen_now"] = json.load(f)["id"]
        run["ran_on_current_freeze"] = run["frozen"] == run["task_frozen_now"]
        if not run["ran_on_current_freeze"]:
            run["note"] = ("This run was scored on an earlier freeze of the task; its reward follows that freeze's "
                           "rubric and is not comparable with runs on the current one. See the task's DATASHEET.md.")
    put(json.dumps(run, indent=1, default=str), "run.json")
    leaks = [v for v in hidden if any(v in open(p, errors="ignore").read() for p in glob.glob(os.path.join(out, "**", "*"), recursive=True) if os.path.isfile(p))]
    assert not leaks, "a secret is still in the export"
    print("{}: {} seat(s), reward {}, complete {} -> {}".format(name, len(seats), run["reward"], run["complete"], out))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs", nargs="+")
    ap.add_argument("--task")
    ap.add_argument("--review")
    a = ap.parse_args()
    for job in a.jobs:
        export(job.rstrip("/"), a.task, a.review)

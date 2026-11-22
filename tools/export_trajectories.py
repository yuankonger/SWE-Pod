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



def atif_valid(trajectory):
    """Whether a trajectory is valid ATIF (the Agent Trajectory Interchange Format Harbor reads and writes), by
    Harbor's own validator. None when the Harbor at hand has no validator: nothing is then claimed."""
    try:
        from harbor.utils.trajectory_validator import validate_trajectory
    except ImportError:
        return None
    try:
        return bool(validate_trajectory(trajectory))
    except Exception:
        return False


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
    return re.sub(r"(OWNER|seat|person)-[a-z]+-(4e81b7|[0-9a-f]{12})\b", "<redacted>", text)


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
    # where Harbor records which agent ran: `import_path` (0.3), `name` (0.26, which takes the path as --agent)
    team = "TeamClaudeCode" in "{} {}".format(agent.get("import_path") or "", agent.get("name") or "")
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
        seats[owner] = {"trajectory": owner + ".trajectory.json", "steps": len(trajectory.get("steps", [])),
                        "format": trajectory.get("schema_version"), "valid": atif_valid(trajectory)}
        if seats[owner]["valid"] is False:
            print("{}: seat {}: the trajectory is NOT valid {}".format(name, owner, trajectory.get("schema_version")), file=sys.stderr)
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
    # a coworker episode: its arm and variant, and what the people were asked and said (sidecars/people.py)
    episode, asked = {}, None
    if os.path.isfile(os.path.join(job, "episode.json")):
        with open(os.path.join(job, "episode.json")) as f:
            episode = json.load(f)
    said = os.path.join(trial, "people", "people.jsonl")
    if os.path.isfile(said):
        put(open(said).read(), "records", "people.jsonl")
        entries = [json.loads(line) for line in open(said) if line.strip()]
        messages = [e for e in entries if e.get("event") == "message"]
        pushes = []
        if os.path.isfile(os.path.join(trial, "agent", "git.jsonl")):
            pushes = [json.loads(line) for line in open(os.path.join(trial, "agent", "git.jsonl")) if line.strip()]
            pushes = sorted(e["at"] for e in pushes if e.get("action") == "push" and e.get("allowed") and e.get("agent") not in ("ci", "oracle", "verifier"))
        first_push = pushes[0] if pushes else None
        # late replies (docs/COWORKER_SPEC.md, 3.3): when each reply was due and reached the seat on the seat's virtual
        # clock, what the seat pushed while it was on its way, and how much of the clock was waiting
        talk = {}
        if os.path.isfile(os.path.join(trial, "agent", "chat.json")):
            with open(os.path.join(trial, "agent", "chat.json")) as f:
                talk = json.load(f)
        replies = {(m["from"], m.get("due_at_v")): m for m in talk.get("messages", []) if m.get("due_at_v") is not None}
        clock = talk.get("clock")

        def timing(e):
            reply = replies.get((e["person"], e.get("due_at_v")))
            if e.get("due_at_v") is None:
                return {}
            reached = reply.get("delivered_at") if reply else None
            waits = [j for j in (clock or {}).get("jumps", []) if e["asked_at_v"] <= j["at_v"] < e["due_at_v"]]
            return {"asked_at_min": round(e["asked_at_v"] / 60, 1), "reply_due_at_min": round(e["due_at_v"] / 60, 1),
                    "reply_reached_seat": reached is not None,
                    "pushes_while_reply_on_its_way": sum(1 for at in pushes if e["at"] <= at < (reached if reached is not None else float("inf"))),
                    "waits_while_reply_on_its_way": len(waits), "minutes_waited_for_it": round(sum(j["by_s"] for j in waits) / 60, 1)}
        asked = {"messages_to_people": len(messages),
                 "reply_delay_min": next((e.get("reply_delay_min") for e in entries if e.get("event") == "started"), None),
                 "clock": clock and {"minutes": round(clock["now_v"] / 60, 1), "minutes_waited": round(clock["jumped_s"] / 60, 1),
                                     "waits": len(clock["jumps"]), "replies_never_delivered": clock["not_delivered"]},
                 "exchanges": [dict({"to": e["person"], "asked": e["text"], "decision": e.get("decision"), "revealed": e.get("revealed", []),
                                     "reply": e.get("reply"), "before_first_push": None if first_push is None else e["at"] < first_push,
                                     "failed": e.get("failed")}, **timing(e)) for e in messages],
                 "revealed": sorted({i for e in messages for i in e.get("revealed", [])}),
                 "people_sidecar_failures": sum(1 for e in messages if e.get("failed")),
                 "variant_at_people": sorted({e.get("variant") for e in entries})}
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
    if episode:
        run.update(condition="coworker/" + episode["arm"], arm=episode["arm"], variant=episode["variant"], budget_usd=episode.get("cap_usd", run["budget_usd"]),
                   judged_variant=(score.get("variant") or {}).get("value"), asked=asked,
                   reply_delay_min=episode.get("reply_delay_min", 0))
        if asked and asked["people_sidecar_failures"]:
            run["complete"] = False
            run["people_sidecar_failed"] = asked["people_sidecar_failures"]
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

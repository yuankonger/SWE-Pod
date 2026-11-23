"""What every Harbor verifier here shares: reading a task's rubric, and the kinds of criterion any task may use.

A rubric is `rubric.toml` in the task's tests: a list of criteria, each saying what it checks, how, and why.

    [[criterion]]
    id = "..."
    kind = "target"       # gate:    must pass for anything to be scored; if it fails the reward is 0
                          # target:  what the work is to achieve; fails (scores 0) as the work starts
                          # guard:   what must keep working; passes as the work starts
                          # fit:     whether the parts fit each other as they would be deployed
                          # measure: reported beside the reward, never part of it
    type = "..."          # how it is decided. The verifier that runs the rubric says which types it has; these two
                          # are here for every verifier, and as measures only:
    # run = "..."         #   command: a shell command in the verifier's seat; exit 0 passes
    # prompt = "..."      #   judge:   a question a model answers about what was pushed to `main` (the diff from where
                          #            the work started). Needs JUDGE_BASE_URL, JUDGE_API_KEY and JUDGE_MODEL (an
                          #            OpenAI-format endpoint); without them it is reported as not run.
    weight = 1
    note = "Why this criterion exists."

A criterion ends with a score from 0 to 1 (1 is a pass), or with none if it was not run. How the scores make the
reward is the verifier's, and is said at the top of each rubric. Standard library only.
"""
import json
import os
import subprocess
import tomllib
import urllib.request

KINDS = ("gate", "target", "guard", "fit", "measure")
COMMON = {"command": "run", "judge": "prompt"}
JUDGE = ("You are judging one criterion of a piece of engineering work from the change that was made. Answer from the change "
         "alone. Give your reasons briefly, then end with a line that is exactly `VERDICT: PASS` or `VERDICT: FAIL`.")


def load(path, types):
    """The rubric's settings and its criteria. `types`: {type: the field a criterion of that type must have, or None}."""
    with open(path, "rb") as f:
        rubric = json.loads(json.dumps(tomllib.load(f)))
    types, seen = dict(COMMON, **types), set()
    for c in rubric.get("criterion", []):
        missing = [k for k in ("id", "kind", "type", "note") if not c.get(k)]
        if missing or c["id"] in seen or c["kind"] not in KINDS or c["type"] not in types or (types[c["type"]] and c.get(types[c["type"]]) in (None, "")):
            raise ValueError("rubric.toml: criterion {} is not well formed (missing {}; kind one of {}, type one of {})".format(c.get("id", c), missing, KINDS, tuple(types)))
        if c["type"] in COMMON and c["kind"] != "measure":
            raise ValueError("rubric.toml: criterion {}: a {} criterion is a measure".format(c["id"], c["type"]))
        seen.add(c["id"])
        c.setdefault("weight", 1)
    if not rubric.get("criterion"):
        raise ValueError("rubric.toml has no criteria")
    return rubric, rubric["criterion"]


def row(c, score, detail=""):
    """A criterion's result. `score`: 0 to 1, True or False, or None if it was not run."""
    score = None if score is None else round(float(score), 4)
    return {"id": c["id"], "kind": c["kind"], "type": c["type"], "weight": c["weight"], "note": " ".join(c["note"].split()),
            "score": score, "passed": None if score is None else score == 1.0, "detail": detail}


def share(rows, kind):
    """The weighted mean score of the criteria of a kind that were run. 1 if there are none."""
    rows = [r for r in rows if r["kind"] == kind and r["score"] is not None]
    total = sum(r["weight"] for r in rows)
    return round(sum(r["weight"] * r["score"] for r in rows) / total, 4) if total else 1.0


def product(rows, kind):
    found = 1.0
    for r in rows:
        if r["kind"] == kind and r["score"] is not None:
            found *= r["score"]
    return round(found, 4)


def gates(rows):
    return all(r["passed"] for r in rows if r["kind"] == "gate")


def pushed(git, repositories, limit=60000):
    """What was pushed to `main` of each repository since the work started, as a diff, for a judge to read."""
    parts = []
    for r in repositories:
        at = "/tmp/judge-" + r
        subprocess.run(["rm", "-rf", at])
        subprocess.run(["git", "clone", "-q", "{}/{}.git".format(git, r), at], capture_output=True)
        first = subprocess.run(["git", "-C", at, "rev-list", "--max-parents=0", "HEAD"], capture_output=True, text=True).stdout.split()
        diff = subprocess.run(["git", "-C", at, "diff", first[-1], "HEAD"], capture_output=True, text=True, errors="replace").stdout if first else ""
        parts.append("=== repository `{}` ===\n{}".format(r, diff[:limit] or "(nothing was pushed)"))
        subprocess.run(["rm", "-rf", at])
    return "\n\n".join(parts)


def judge(criterion, change):
    """Asks a model. Passes only on an explicit `VERDICT: PASS`. (None, why) if no judge is configured or it did not answer."""
    base, key, model = (os.environ.get(k) for k in ("JUDGE_BASE_URL", "JUDGE_API_KEY", "JUDGE_MODEL"))
    if not (base and key and model):
        return None, "not run: no judge is configured (JUDGE_BASE_URL, JUDGE_API_KEY, JUDGE_MODEL)"
    body = {"model": model, "messages": [{"role": "system", "content": JUDGE},
                                         {"role": "user", "content": "Criterion:\n{}\n\nThe change:\n\n{}".format(criterion["prompt"].strip(), change)}]}
    request = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(request, timeout=600) as r:
            answer = (json.loads(r.read())["choices"][0]["message"].get("content") or "").strip()
    except (OSError, ValueError, KeyError, IndexError) as e:
        return None, "not run: the judge did not answer: {}".format(e)
    return (answer.splitlines() or [""])[-1].strip() == "VERDICT: PASS", answer[-1500:]


def command(criterion, cwd=None):
    try:
        p = subprocess.run(["bash", "-c", criterion["run"]], cwd=cwd, capture_output=True, text=True, timeout=criterion.get("timeout", 300))
    except subprocess.TimeoutExpired:
        return False, "the command did not finish in time"
    return p.returncode == 0, "" if p.returncode == 0 else "exit code {}: {}".format(p.returncode, (p.stdout + p.stderr)[-600:])


def table(rows, last):
    """The result as text: one criterion a line with its note, then `last` (how the reward came about)."""
    lines = []
    for r in rows:
        mark = "  - " if r["score"] is None else "PASS" if r["passed"] else "FAIL" if r["score"] == 0 else "{:.2f}".format(r["score"])
        lines.append("{}  {:<8} {:<9} {}\n      {}".format(mark, r["kind"], r["type"], r["id"], r["note"]))
        if not r["passed"] and r.get("detail"):
            lines.append("      -> " + str(r["detail"])[:400])
    return "\n".join(lines + ["", last])

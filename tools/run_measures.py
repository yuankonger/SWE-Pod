"""A run's measures, from what the gateway and the company recorded: the same for any harness at the seats.

    python3 tools/run_measures.py runs/harbor/<job>

Read from:
    <job>/meter/<seat>.jsonl          every request a seat made of the model (tools/model_meter.py)
    <job>/<trial>/agent/**/git.jsonl  the git server's record: who fetched and pushed what, and what it refused
    <job>/<trial>/agent/**/ci.json    every CI run
    <job>/<trial>/agent/**/chat.json  every message between seats (a team with messaging)
    <job>/<trial>/verifier/           the reward

Written to <job>/measures.json and printed:
    context    per seat: requests, tokens in and out, the largest context one request carried, and the contexts the
               seat held (a context is one conversation growing; a seat that starts subagents holds several)
    division   who did the work: each seat's share of the tokens, its active minutes, what it pushed where, what it said
    control    what the environment refused or had to absorb: pushes the git server refused, CI runs that failed,
               requests the model service refused
    outcome    the reward and the wall-clock minutes
Reliability is a property of several runs of one condition: tools/run_measures.py --compare <job> <job> ... prints them side by side.
Standard library only.
"""
import glob
import json
import os
import sys


def lines(path):
    out = []
    try:
        with open(path) as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def first(job, name):
    """The environment's record of that name: the verifier's copy (any harness), else the one kept beside the harness logs."""
    found = sorted(glob.glob(os.path.join(job, "*__*", "verifier", "records", name))) or sorted(glob.glob(os.path.join(job, "*__*", "agent", "**", name), recursive=True))
    return found[0] if found and os.path.getsize(found[0]) else None


def measure(job):
    seats, total = {}, {"input": 0, "cache_read": 0, "cache_write": 0, "output": 0}
    by_seat = {os.path.basename(p)[:-6]: lines(p) for p in sorted(glob.glob(os.path.join(job, "meter", "*.jsonl")))}
    if not by_seat:      # the task's own meter, kept by its verifier
        for r in lines(first(job, "model.jsonl") or ""):
            by_seat.setdefault(r.get("seat"), []).append(r)
    for seat, recorded in sorted(by_seat.items()):
        asked = [r for r in recorded if r.get("messages")]
        answered = [r for r in asked if r.get("status") == 200]
        contexts = {}
        for r in answered:
            c = contexts.setdefault(r.get("context"), {"requests": 0, "peak_context_tokens": 0, "output": 0, "model": r.get("model")})
            c["requests"] += 1
            c["peak_context_tokens"] = max(c["peak_context_tokens"], r.get("context_tokens", 0))
            c["output"] += r.get("output", 0)
        held = sorted((c for c in contexts.values() if c["requests"] >= 3), key=lambda c: -c["peak_context_tokens"])
        tokens = {k: sum(r.get(k, 0) for r in answered) for k in total}
        for k in total:
            total[k] += tokens[k]
        seats[seat] = dict(tokens, requests=len(answered), refused=sum(1 for r in asked if r.get("status") != 200),
                           peak_context_tokens=max([r.get("context_tokens", 0) for r in answered] or [0]),
                           contexts=len(held), side_contexts=len(contexts) - len(held), largest_contexts=held[:6],
                           models=sorted({r.get("model") for r in answered if r.get("model")}),
                           active_minutes=round((max(r["at"] + r.get("seconds", 0) for r in answered) - min(r["at"] for r in answered)) / 60, 1) if answered else 0)
    read = lambda s: s["input"] + s["cache_read"] + s["cache_write"]
    everything = sum(read(s) + s["output"] for s in seats.values()) or 1
    git = lines(first(job, "git.jsonl") or "")
    work = {}
    for e in git:
        if e.get("agent") in ("ci", "verifier", "oracle"):
            continue
        w = work.setdefault(e["agent"], {"pushes": {}, "pushes_refused": {}, "fetches": 0})
        if e.get("action") == "push":
            kind = "pushes" if e.get("allowed") else "pushes_refused"
            w[kind][e["repository"]] = w[kind].get(e["repository"], 0) + 1
        else:
            w["fetches"] += 1
    try:
        with open(first(job, "ci.json") or "") as f:
            runs = json.load(f).get("runs", [])
    except (OSError, ValueError):
        runs = None
    try:
        with open(first(job, "chat.json") or "") as f:
            chat = json.load(f)
        said = (chat.get("messages") or chat.get("log") or []) if isinstance(chat, dict) else chat      # the chat sidecar keeps {"messages", "done", "pauses"}
        messages = {}
        for m in said if isinstance(said, list) else []:
            if isinstance(m, dict) and m.get("from"):
                messages[m["from"]] = messages.get(m["from"], 0) + 1
    except (OSError, ValueError):
        messages = None
    reward, minutes, seat_reward = None, None, None
    for path in glob.glob(os.path.join(job, "*__*", "result.json")):
        with open(path) as f:
            r = json.load(f)
        seat_reward = reward = ((r.get("verifier_result") or {}).get("rewards") or {}).get("reward")
        judged = os.path.join(os.path.dirname(path), "judge", "reward.txt")      # the judge's own copy: the one to trust
        if os.path.isfile(judged):
            with open(judged) as f:
                reward = float(f.read().strip() or 0)
        ae = r.get("agent_execution") or {}
        if ae.get("started_at") and ae.get("finished_at"):
            from datetime import datetime
            t = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
            minutes = round((t(ae["finished_at"]) - t(ae["started_at"])).total_seconds() / 60, 1)
    # how each seat's work ended, as its runner recorded it: a stop by the model service makes the run incomplete
    runs = {}
    for path in sorted(glob.glob(os.path.join(job, "*__*", "agent", "**", "seat-run.json"), recursive=True)):
        try:
            with open(path) as f:
                r = json.load(f)
            runs[r.get("seat") or path] = r
        except (OSError, ValueError):
            pass
    outside = {s: r["ended"] for s, r in runs.items() if r.get("stopped_from_outside")}
    return {"job": os.path.basename(job.rstrip("/")),
            "outcome": {"reward": reward, "minutes": minutes, "seat_says": seat_reward,
                        "complete": not outside, "stopped_from_outside": outside, "seat_runs": runs,
                        "seat_disagrees_with_judge": seat_reward is not None and reward is not None and abs(float(seat_reward) - reward) > 1e-9},
            "context": {"total": dict(total, read=sum(total[k] for k in ("input", "cache_read", "cache_write"))), "seats": seats},
            "division": {"token_share": {n: round((read(s) + s["output"]) / everything, 3) for n, s in seats.items()},
                         "active_minutes": {n: s["active_minutes"] for n, s in seats.items()}, "git": work, "messages": messages},
            "control": {"pushes_refused": sum(sum(w["pushes_refused"].values()) for w in work.values()),
                        "ci_runs": None if runs is None else len(runs), "ci_runs_failed": None if runs is None else sum(1 for r in runs if r.get("state") == "failed"),
                        "model_requests_refused": sum(s["refused"] for s in seats.values())}}


def said(m):
    c, d, k, o = m["context"], m["division"], m["control"], m["outcome"]
    out = ["{}: reward {}{}  {} min  read {:.1f}M tokens (fresh {:.2f}M, cached {:.1f}M, cache written {:.2f}M)  wrote {:.0f}k".format(
        m["job"], o["reward"], "" if o.get("complete", True) else " (INCOMPLETE: stopped from outside: {})".format(o["stopped_from_outside"]), o["minutes"], c["total"]["read"] / 1e6, c["total"]["input"] / 1e6, c["total"]["cache_read"] / 1e6, c["total"]["cache_write"] / 1e6, c["total"]["output"] / 1e3)]
    for name, s in c["seats"].items():
        w = d["git"].get(name) or d["git"].get("solo") or {}
        out.append("  seat {:10} {:4} requests  share {:4.0%}  active {:5.1f} min  largest context {:6.0f}k  contexts {} (+{} side)  pushed {}  refused {}  said {}".format(
            name, s["requests"], d["token_share"][name], s["active_minutes"], s["peak_context_tokens"] / 1e3, s["contexts"], s["side_contexts"],
            w.get("pushes", {}), w.get("pushes_refused", {}), (d["messages"] or {}).get(name)))
    for name, r in o.get("seat_runs", {}).items():
        out.append("  run  {:10} {}  working {:.0f} min  paused {:.0f} min ({} pauses)  spent ${}".format(name, r["ended"][:80], r["working_s"] / 60, r["paused_s"] / 60, r["pauses"], r["spent_usd"]))
    out.append("  control: pushes refused {}  CI runs {} (failed {})  model requests refused {}".format(k["pushes_refused"], k["ci_runs"], k["ci_runs_failed"], k["model_requests_refused"]))
    return "\n".join(out)


if __name__ == "__main__":
    jobs = [a for a in sys.argv[1:] if not a.startswith("--")]
    for job in jobs:
        m = measure(job)
        with open(os.path.join(job, "measures.json"), "w") as f:
            json.dump(m, f, indent=1)
        print(said(m))

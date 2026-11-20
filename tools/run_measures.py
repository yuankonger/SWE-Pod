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
import re
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


IDLE_S = 600      # a stretch this long with no request to the model is a wait, not work


def working(answered):
    """The seat's working time, from the meter alone, whichever harness ran: from its first request to its last, less
    every stretch of IDLE_S or more with no request (a pause for a rate limit, a wait on a background job, a session
    kept open after its answer). Each such wait is listed, with what the request after it had to write to the cache."""
    rs = sorted(answered, key=lambda r: r["at"])
    waits, work = [], 0.0
    for a, b in zip(rs, rs[1:]):
        gap = b["at"] - (a["at"] + a.get("seconds", 0))
        if gap >= IDLE_S:
            waits.append({"minutes": round(gap / 60, 1), "cache_rewritten": b.get("cache_write", 0)})
        else:
            work += b["at"] - a["at"]
    if rs:
        work += rs[0].get("seconds", 0)
    return {"working_minutes": round(work / 60, 1), "waits": waits,
            "cache_rewritten_after_waits": sum(w["cache_rewritten"] for w in waits)}


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
                           active_minutes=round((max(r["at"] + r.get("seconds", 0) for r in answered) - min(r["at"] for r in answered)) / 60, 1) if answered else 0,
                           **working(answered))
    read = lambda s: s["input"] + s["cache_read"] + s["cache_write"]
    everything = sum(read(s) + s["output"] for s in seats.values()) or 1
    git = lines(first(job, "git.jsonl") or "")
    work, pushes, said = {}, [], []
    for e in git:
        if e.get("agent") in ("ci", "verifier", "oracle"):
            continue
        w = work.setdefault(e["agent"], {"pushes": {}, "pushes_refused": {}, "fetches": 0})
        if e.get("action") == "push" and e.get("allowed") and e.get("at"):
            pushes.append((e["agent"], e["at"]))
        if e.get("action") == "push":
            kind = "pushes" if e.get("allowed") else "pushes_refused"
            w[kind][e["repository"]] = w[kind].get(e["repository"], 0) + 1
        else:
            w["fetches"] += 1
    try:
        with open(first(job, "ci.json") or "") as f:
            runs = json.load(f).get("runs", [])
        runs = [r for r in (runs.values() if isinstance(runs, dict) else runs) if isinstance(r, dict)]
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
    contract = contract_measures(runs, said if isinstance(said, list) else [], pushes) if runs else None
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
    seat_runs = {}
    for path in sorted(glob.glob(os.path.join(job, "*__*", "agent", "**", "seat-run.json"), recursive=True)):
        try:
            with open(path) as f:
                r = json.load(f)
            seat_runs[r.get("seat") or path] = r
        except (OSError, ValueError):
            pass
    outside = {s: r["ended"] for s, r in seat_runs.items() if r.get("stopped_from_outside")}
    return {"job": os.path.basename(job.rstrip("/")),
            "outcome": {"reward": reward, "minutes": minutes, "seat_says": seat_reward,
                        "complete": not outside, "stopped_from_outside": outside, "seat_runs": seat_runs,
                        "seat_disagrees_with_judge": seat_reward is not None and reward is not None and abs(float(seat_reward) - reward) > 1e-9},
            "context": {"total": dict(total, read=sum(total[k] for k in ("input", "cache_read", "cache_write"))), "seats": seats},
            "division": {"token_share": {n: round((read(s) + s["output"]) / everything, 3) for n, s in seats.items()},
                         "active_minutes": {n: s["active_minutes"] for n, s in seats.items()}, "git": work, "messages": messages},
            "control": {"pushes_refused": sum(sum(w["pushes_refused"].values()) for w in work.values()),
                        "ci_runs": None if runs is None else len(runs), "ci_runs_failed": None if runs is None else sum(1 for r in runs if r.get("state") == "failed"),
                        "model_requests_refused": sum(s["refused"] for s in seats.values())},
            "contract": contract}


def contract_measures(runs, messages, pushes):
    """How the API's contract reached the application that calls it, from the company's own records: when the API
    first served something it gained, how often what it serves changed after the caller had pushed, how often CI
    found the caller asking for what the API did not serve, and what was said before the first publication.
    Times are minutes from the first CI run (the start of the work). A change is seen as a change in how many fields
    the running API has gained, so a rename that keeps the count is missed."""
    runs = sorted((r for r in runs if r.get("started_at")), key=lambda r: r["started_at"])
    if not runs:
        return None
    start = runs[0]["started_at"]
    minute = lambda at: round((at - start) / 60, 1)
    check = lambda r, name: next((c for c in r.get("checks", []) if c.get("name", "").endswith(name)), None)

    def gained(r):
        c = check(r, "answers what it gained")
        found = re.match(r"(\d+) gained", (c or {}).get("detail", ""))
        return int(found.group(1)) if found else None

    providers = {c["name"].split(" answers")[0] for r in runs for c in r.get("checks", []) if c.get("name", "").endswith("answers what it gained")}
    published = [{"minute": minute(r.get("finished_at") or r["started_at"]), "gained_fields": gained(r), "ci_run": r.get("id"), "passed": r.get("state") == "passed"}
                 for r in runs if gained(r) is not None and set(r.get("moved", [])) & providers]
    published = [p for i, p in enumerate(published) if p["gained_fields"] != (published[i - 1]["gained_fields"] if i else 0)]
    first = next((p["minute"] for p in published if p["gained_fields"]), None)
    callers_first_push = min((at for who, at in pushes if who not in providers and who not in ("ci", "oracle", "verifier", "solo")), default=None)
    refused = [{"minute": minute(r["started_at"]), "ci_run": r.get("id"), "detail": check(r, "calls")["detail"]}
               for r in runs if check(r, "calls") and not check(r, "calls").get("ok")]
    return {"first_published_minute": first,
            "publications": published,
            "caller_first_pushed_minute": None if callers_first_push is None else minute(callers_first_push),
            "changes_after_caller_pushed": None if callers_first_push is None else sum(1 for p in published if p["minute"] > minute(callers_first_push)),
            "ci_runs_caller_asked_what_api_lacks": refused,
            "messages_before_first_publication": sum(1 for m in messages if isinstance(m, dict) and m.get("at") and (first is None or minute(m["at"]) < first)),
            "messages": len(messages)}


def said(m):
    c, d, k, o = m["context"], m["division"], m["control"], m["outcome"]
    out = ["{}: reward {}{}  {} min  read {:.1f}M tokens (fresh {:.2f}M, cached {:.1f}M, cache written {:.2f}M)  wrote {:.0f}k".format(
        m["job"], o["reward"], "" if o.get("complete", True) else " (INCOMPLETE: stopped from outside: {})".format(o["stopped_from_outside"]), o["minutes"], c["total"]["read"] / 1e6, c["total"]["input"] / 1e6, c["total"]["cache_read"] / 1e6, c["total"]["cache_write"] / 1e6, c["total"]["output"] / 1e3)]
    for name, s in c["seats"].items():
        w = d["git"].get(name) or d["git"].get("solo") or {}
        out.append("  seat {:10} {:4} requests  share {:4.0%}  working {:5.1f} min (span {:5.1f}, {} waits)  largest context {:6.0f}k  contexts {} (+{} side)  pushed {}  refused {}  said {}".format(
            name, s["requests"], d["token_share"][name], s["working_minutes"], s["active_minutes"], len(s["waits"]), s["peak_context_tokens"] / 1e3, s["contexts"], s["side_contexts"],
            w.get("pushes", {}), w.get("pushes_refused", {}), (d["messages"] or {}).get(name)))
    for name, r in o.get("seat_runs", {}).items():
        out.append("  run  {:10} {}  working {:.0f} min  paused {:.0f} min ({} pauses)  spent ${}".format(name, r["ended"][:80], r["working_s"] / 60, r["paused_s"] / 60, r["pauses"], r["spent_usd"]))
    t = m.get("contract")
    if t:
        out.append("  contract: API first published at min {}  publications {}  caller first pushed at min {}  changes after that {}  CI runs with the caller asking what the API lacks {}  messages before publication {} of {}".format(
            t["first_published_minute"], [(p["minute"], p["gained_fields"]) for p in t["publications"]], t["caller_first_pushed_minute"], t["changes_after_caller_pushed"],
            len(t["ci_runs_caller_asked_what_api_lacks"]), t["messages_before_first_publication"], t["messages"]))
    out.append("  control: pushes refused {}  CI runs {} (failed {})  model requests refused {}".format(k["pushes_refused"], k["ci_runs"], k["ci_runs_failed"], k["model_requests_refused"]))
    return "\n".join(out)


if __name__ == "__main__":
    jobs = [a for a in sys.argv[1:] if not a.startswith("--")]
    for job in jobs:
        m = measure(job)
        with open(os.path.join(job, "measures.json"), "w") as f:
            json.dump(m, f, indent=1)
        print(said(m))

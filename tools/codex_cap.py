"""A spend cap for a Codex run under Harbor, kept from outside: Codex has none of its own.

    python3 tools/codex_cap.py <job dir> <cap in dollars> <input $/M> <cached input $/M> <output $/M>

Codex records the tokens it has used so far in its session files, which Harbor mounts under the trial's agent/
directory as they are written. This watches them, turns tokens into dollars at the prices given, and when the cap
is reached stops Codex in the seat. Harbor then goes on to the verifier, which scores what is on `main`: the same
ending a harness that caps itself has. Writes <job dir>/cap.json with what it saw. Ends when the trial has a result.
"""
import glob
import json
import os
import subprocess
import sys
import time

JOB, CAP = sys.argv[1], float(sys.argv[2])
IN, CACHED, OUT = (float(x) for x in sys.argv[3:6])


def used():
    """Tokens so far, summed over every session of the run (an agent Codex starts has a session of its own)."""
    total = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
    for path in glob.glob(os.path.join(JOB, "*", "agent", "sessions", "**", "rollout-*.jsonl"), recursive=True):
        last = None
        with open(path, errors="replace") as f:
            for line in f:
                if '"token_count"' in line:
                    try:
                        info = json.loads(line)["payload"]["info"]
                    except (ValueError, KeyError, TypeError):
                        continue
                    if info and info.get("total_token_usage"):
                        last = info["total_token_usage"]
        for key in total:
            total[key] += int((last or {}).get(key) or 0)
    return total


def dollars(t):
    return ((t["input_tokens"] - t["cached_input_tokens"]) * IN + t["cached_input_tokens"] * CACHED + t["output_tokens"] * OUT) / 1e6


def stop():
    """Ends Codex in the seat of this job's trial. Returns the compose projects it was stopped in."""
    stopped = []
    for trial in glob.glob(os.path.join(JOB, "*", "agent")):
        project = os.path.basename(os.path.dirname(trial)).lower()
        done = subprocess.run(["docker", "compose", "-p", project, "exec", "-T", "main", "pkill", "-f", "codex"], capture_output=True, text=True)
        stopped.append((project, done.returncode))
    return stopped


state = {"cap": CAP, "prices_per_million": {"input": IN, "cached_input": CACHED, "output": OUT}, "stopped": False}
while True:
    tokens = used()
    state.update(tokens=tokens, dollars=round(dollars(tokens), 4), at=time.strftime("%H:%M:%S"))
    if state["dollars"] >= CAP and not state["stopped"]:
        state["stopped"], state["stop"] = True, stop()
    with open(os.path.join(JOB, "cap.json.tmp"), "w") as f:
        json.dump(state, f, indent=1)
    os.replace(os.path.join(JOB, "cap.json.tmp"), os.path.join(JOB, "cap.json"))
    if glob.glob(os.path.join(JOB, "*", "verifier", "reward.txt")) or glob.glob(os.path.join(JOB, "*", "exception.txt")) or os.path.isfile(os.path.join(JOB, "result.json")):
        break
    time.sleep(20)

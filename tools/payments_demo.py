"""Shows, without any model, what a payment-path task's verifier says of the company in each state of repair.

    python3 tools/payments_demo.py <task> [--states start,core,payments,both,reverse] [--soak seconds] [--out runs/payments_demo/<task>] [--solution dir]

For each state the task's company is started from nothing (harbor/<task>/environment, the same compose file a run
uses, with a seat that only waits), the reference patches of that state are pushed to `main` through the git
server as the oracle (one repository at a time, `--soak` seconds apart, so that each deploy has orders of its own),
and the task's own verifier is run in the seat. `start` pushes nothing; `both` pushes core's fix and then the payment app's, `reverse` the payment app's and then core's. What the verifier wrote is kept under
<out>/<state>/, and a table of all states is printed.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OVERRIDE = "services:\n  main:\n    build: {context: .}\n    command: [\"sleep\", \"infinity\"]\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task")
    ap.add_argument("--states", default="start,core,payments,both")
    ap.add_argument("--soak", type=float, default=150)
    ap.add_argument("--out")
    ap.add_argument("--solution", help="patches to push in place of the task's reference ones: a directory of <repository>.patch")
    a = ap.parse_args()
    task = os.path.join(REPO, "harbor", a.task)
    out = a.out or os.path.join(REPO, "runs", "payments_demo", a.task)
    os.makedirs(out, exist_ok=True)
    override = os.path.join(out, "override.yaml")
    with open(override, "w") as f:
        f.write(OVERRIDE)
    project = "demo-" + a.task.replace("_", "-")
    compose = ["docker", "compose", "-p", project, "-f", os.path.join(task, "environment", "docker-compose.yaml"), "-f", override]
    seat = project + "-main-1"
    run = lambda *args, **kw: subprocess.run(list(args), capture_output=True, text=True, **kw)
    oracle = json.load(open(os.path.join(task, "tests", "config.json")))["git"].replace("verifier:verifier-c41f09be73", "oracle:oracle-9a17c3e55b")
    built = run(*compose, "build")
    if built.returncode != 0:
        sys.exit("the image did not build:\n" + built.stderr[-2000:])
    rows = []
    for state in a.states.split(","):
        fixes = {"start": [], "both": ["core", "payments"], "reverse": ["payments", "core"]}.get(state, state.split("+"))      # "core+apps": core's, then apps'
        run(*compose, "down", "-v")
        up = run(*compose, "up", "-d")
        if up.returncode != 0:
            sys.exit("the company did not start for `{}`:\n{}".format(state, up.stderr[-2000:]))
        run("docker", "cp", os.path.join(task, "tests"), seat + ":/tests")
        run("docker", "cp", a.solution or os.path.join(task, "solution"), seat + ":/solution")
        time.sleep(a.soak)      # orders of the state the work starts from
        for owner in fixes:
            pushed = run("docker", "exec", seat, "bash", "-c",
                         "rm -rf /tmp/o-{0} && git clone -q {1}/{0}.git /tmp/o-{0} && cd /tmp/o-{0} && git apply --whitespace=nowarn /solution/{0}.patch "
                         "&& git add -A && git commit -qm 'Fix' && git push -q origin HEAD:main && git rev-parse HEAD".format(owner, oracle))
            if pushed.returncode != 0:
                sys.exit("the fix of {} was not pushed: {}".format(owner, pushed.stderr[-800:]))
            time.sleep(a.soak)
        run("docker", "exec", seat, "bash", "/tests/test.sh")
        kept = os.path.join(out, state)
        shutil.rmtree(kept, ignore_errors=True)
        run("docker", "cp", seat + ":/logs/verifier", kept)
        with open(os.path.join(kept, "score.json")) as f:
            score = json.load(f)
        rows.append((state, score))
        m = score.get("measures", {})
        print("{:9} reward {}  targets {}  guards {}  deployed {}".format(state, score["reward"], score["targets"], score["guards"],
              {k: (v or "")[:10] for k, v in (score["deploy"].get("main") or {}).items()}), flush=True)
        for s in score["scenarios"]:
            last = s["runs"][-1]
            print("    {} {:6} {}/{}  {}  provider {}  api {}  {}".format("ok " if s["ok"] else "NOT", s["kind"], s["passed"], len(s["runs"]), s["name"],
                  last.get("provider"), last.get("api"), last.get("why", "")), flush=True)
        for c in score["criteria"]:
            if c["type"] not in ("scenario", "records"):
                print("    {} {:6} {}  {}".format("ok " if c["passed"] else ("-- " if c["passed"] is None else "NOT"), c["kind"], c["id"], c["detail"][:260]), flush=True)
        if m.get("harm"):
            print("    harm: over-refunded {}  orders lost {}".format(m["harm"]["over_refunded"], m["harm"]["orders_lost"]), flush=True)
            for d in m["harm"]["by_deployment"]:
                print("      deployment {} orders {}  over-refunded {}  orders lost {}".format({k: (v or "")[:8] for k, v in (d["commits"] or {}).items()}, d["orders"],
                      d["over_refunded"], d["orders_lost"]), flush=True)
        for name in ("ledger_agreement", "idempotency", "traffic_success", "refunded_as_asked"):
            if name in m:
                print("    {:17} share {}  first passing deployment {}  stays passing {}".format(name, m[name]["share"],
                      (m[name]["first_deployment_passing"] or {}).get("index"), m[name]["stays_passing"]), flush=True)
        for d in m.get("deployments", []):
            print("      deployment {} orders {}  ledger {}  idempotency {}  traffic {}  refunded as asked {}".format({k: (v or "")[:8] for k, v in (d["commits"] or {}).items()}, d["orders"],
                  d["ledger_agreement"]["share"], d["idempotency"]["share"], d["traffic_success"]["share"], d.get("refunded_as_asked", {}).get("share")), flush=True)
        if "traffic_success_during_rollout" in m:
            print("    during rollout: {}".format(m["traffic_success_during_rollout"]), flush=True)
    run(*compose, "down", "-v")
    with open(os.path.join(out, "summary.json"), "w") as f:
        json.dump({state: score for state, score in rows}, f, indent=1)


if __name__ == "__main__":
    main()

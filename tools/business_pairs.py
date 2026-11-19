"""Runs the business outcome check on frozen pairs of commits, each in a container of its own, started from nothing.

    python3 tools/business_pairs.py --core <saleor clone> --dashboard <dashboard clone> [--only name,...] [--out runs/business_pairs]

The four pairs are the two repositories at the commit the work starts from and at the reference feature, in every
combination. Each pair gets a new container of the check's image (the seat's image with a Chromium), the two trees
exactly as `git archive` gives them, and tools/harbor_business_check.py with the same sample data. Nothing is
shared between pairs. What each produced (business.json, logs, screenshots) is kept under <out>/<pair>/.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
import mined_company as mc      # noqa: E402

IMAGE = "seedco-business-check:1"


def sh(*args, **kwargs):
    return subprocess.run(list(args), capture_output=True, text=True, **kwargs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--core", required=True)
    ap.add_argument("--dashboard", required=True)
    ap.add_argument("--only")
    ap.add_argument("--out", default=os.path.join(REPO, "runs", "business_pairs"))
    a = ap.parse_args()
    info, repos = mc.load_company("customer_attributes_company")
    full = lambda clone, commit: sh("git", "-C", clone, "rev-parse", commit).stdout.strip()
    commits = {"core": {"base": full(a.core, repos["core"]["base"]), "reference": full(a.core, mc.target_commit(a.core, repos["core"]))},
               "dashboard": {"base": full(a.dashboard, repos["dashboard"]["base"]), "reference": full(a.dashboard, mc.target_commit(a.dashboard, repos["dashboard"]))}}
    pairs = [("base_base", "base", "base"), ("core_only", "reference", "base"), ("dashboard_only", "base", "reference"), ("reference", "reference", "reference")]
    summary = []
    for name, core, dashboard in pairs:
        if a.only and name not in a.only.split(","):
            continue
        out = os.path.join(a.out, name)
        shutil.rmtree(out, ignore_errors=True)
        os.makedirs(out)
        container = "business-pair-" + name.replace("_", "-")
        sh("docker", "rm", "-f", container)
        started = sh("docker", "run", "-d", "--name", container, IMAGE, "sleep", "infinity")
        row = {"pair": name, "core": commits["core"][core], "dashboard": commits["dashboard"][dashboard]}
        try:
            if started.returncode != 0:
                raise RuntimeError("no container: " + started.stderr.strip()[-300:])
            sh("docker", "exec", container, "mkdir", "-p", "/pair/core", "/pair/dashboard", "/tests", "/out")
            for owner, clone, commit in (("core", a.core, row["core"]), ("dashboard", a.dashboard, row["dashboard"])):
                archive = subprocess.Popen(["git", "-C", clone, "archive", commit], stdout=subprocess.PIPE)
                laid = subprocess.run(["docker", "exec", "-i", container, "tar", "-x", "-C", "/pair/" + owner], stdin=archive.stdout)
                if archive.wait() != 0 or laid.returncode != 0:
                    raise RuntimeError("could not lay out {} at {}".format(owner, commit))
            for source, name_there in (("harbor_business_check.py", "business.py"), ("business_customer_tier.cjs", "business_customer_tier.cjs")):
                subprocess.run(["docker", "cp", os.path.join(REPO, "tools", source), "{}:/tests/{}".format(container, name_there)], check=True, capture_output=True)
            subprocess.run(["docker", "exec", container, "bash", "-lc", "python3 /tests/business.py /tests /pair/core /pair/dashboard /out > /out/run.log 2>&1"])
            subprocess.run(["docker", "cp", container + ":/out/.", out], capture_output=True)
            with open(os.path.join(out, "business.json")) as f:
                row.update(json.load(f))
        except Exception as e:      # the runner's own trouble, not the pair's
            row.update(verdict="infrastructure", failed_stage="runner", reason="{}: {}".format(type(e).__name__, e))
        finally:
            sh("docker", "rm", "-f", container)
        with open(os.path.join(out, "pair.json"), "w") as f:
            json.dump(row, f, indent=2)
        summary.append(row)
        print("{:15} core {} dashboard {}  {}  {}  {}".format(name, row["core"][:10], row["dashboard"][:10], row["verdict"].upper(), row.get("failed_stage") or "", row.get("reason") or ""), flush=True)
    with open(os.path.join(a.out, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()

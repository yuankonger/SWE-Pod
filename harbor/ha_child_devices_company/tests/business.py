"""The business outcome check of a Home Assistant company: can the owner do, on the running company, what the
feature is for?

    python3 business.py <tests dir> <out dir> core=<core tree> frontend=<frontend tree>

As a module it is what tools/harbor_company_score.py calls (copied to the task's tests/business.py, with ha_seed.py
and the company's browser script beside it; config.json's `business` says which script).

The two trees are started together from nothing: the frontend's production build is made, and Home Assistant from
the core tree is started on a configuration of its own (ha_seed.py: the demo integration, the frontend's build
served from the frontend tree) and onboarded. Then a browser does a piece of real work through the frontend, and
what came of it is read back over the WebSocket API (the company's script, e.g. tests/business_ha_child_devices.cjs).

The verdict is one of
    pass             every stage did what it should
    fail             a stage did not, because of what the trees do; `failed_stage` and `reason` say which and why
    infrastructure   the check itself could not run (the browser, a port, a tool): nothing is said about the trees
It does not change the reward by itself. Standard library only (the browser part needs Playwright and a Chromium).
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import time

URL = "http://127.0.0.1:8123/"      # Home Assistant's default port (ha_seed.py)


def as_work(command, env=None):
    """The work's own code runs as the scorer's unprivileged user where there is one (see score.py)."""
    try:
        import score
        return score.as_work(command, env)
    except Exception:
        return ["bash", "-lc", command]


def sh(command, cwd=None, timeout=None, env=None, work=False):
    try:
        if work and os.environ.get("SEEDCO_SCORER"):
            return subprocess.run(as_work(command, env), cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return subprocess.run(["bash", "-c", command], cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(command, 124, "", "timed out")


def stop(proc):
    if proc and proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass


def check(tests, trees, out, deadline=None, script=None):
    """`trees`: {"core": path, "frontend": path}. `deadline`: a time.time() by which the check must be over."""
    os.makedirs(out, exist_ok=True)
    left = lambda cap: max(30, min(cap, (deadline or float("inf")) - time.time()))
    result = {"verdict": "infrastructure", "failed_stage": None, "reason": None, "stages": [], "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    core, frontend = trees["core"], trees["frontend"]
    config, token = os.path.join(out, "config"), os.path.join(out, "token")
    hass = None
    scored = bool(os.environ.get("SEEDCO_SCORER"))
    node = dict(os.environ, NODE_PATH=os.environ.get("NODE_PATH", "/deps/node_modules"))

    def ended(verdict, stage=None, reason=None):
        result.update(verdict=verdict, failed_stage=stage, reason=reason)
        return result

    def stage(name, ok, detail=""):
        result["stages"].append({"stage": name, "ok": bool(ok), "detail": detail})
        return ok

    try:
        # ---- the check's own footing: nothing here says anything about the trees
        sh("pkill -f '[h]omeassistant -c {}' ; true".format(config))
        browser = sh("node -e \"require('playwright').chromium.launch().then(b => b.close())\"", env=node, timeout=120)
        if browser.returncode != 0:
            return ended("infrastructure", "browser", "no browser could be started: " + (browser.stderr.strip().splitlines() or ["?"])[-1][:300])
        shutil.rmtree(config, ignore_errors=True)
        sh("python3 {}/ha_seed.py config {} --frontend {}".format(tests, config, frontend))
        if scored:
            subprocess.run(["chown", "-R", os.environ["SEEDCO_SCORER"], out], capture_output=True)

        # ---- the frontend's production build, made from its tree
        if not os.path.exists(os.path.join(frontend, "node_modules")) and os.path.isdir("/deps/node_modules"):
            os.symlink("/deps/node_modules", os.path.join(frontend, "node_modules"))
        built = sh("(rm -rf hass_frontend && IS_TEST=true ./node_modules/.bin/gulp build-app-modern) > {}/build.log 2>&1".format(out), cwd=frontend, env=node,
                   timeout=left(1200), work=True)
        if not stage("frontend_builds", built.returncode == 0 and os.path.isfile(os.path.join(frontend, "hass_frontend", "index.html")),
                     "" if built.returncode == 0 else "see build.log"):
            return ended("fail", "frontend_builds", "the frontend's production build does not build")

        # ---- Home Assistant from the core tree, onboarded
        sh("(python3 -m script.translations develop --all) > {}/translations.log 2>&1".format(out), cwd=core, timeout=left(600), work=True)
        hass = subprocess.Popen(as_work("exec python3 -m homeassistant -c {} --skip-pip > {}/hass.log 2>&1".format(config, out)), cwd=core, start_new_session=True)
        onboarded = sh("python3 {}/ha_seed.py onboard {} {} > {}/onboard.log 2>&1".format(tests, URL.rstrip("/"), token, out), timeout=left(420))
        if not stage("core_serves", onboarded.returncode == 0 and os.path.isfile(token), "" if onboarded.returncode == 0 else "see onboard.log and hass.log"):
            return ended("fail", "core_serves", "Home Assistant does not start, or cannot be onboarded")

        # ---- the work itself, in a browser
        found = os.path.join(out, "browser.json")
        if os.path.isfile(found):
            os.remove(found)
        ran = sh("node {}/{} {} {} {} > {}/browser.log 2>&1".format(tests, script, URL, token, out, out), env=node, timeout=left(1800))
        if not os.path.isfile(found):
            return ended("infrastructure", "browser", "the browser part ended without a result (exit {}); see browser.log".format(ran.returncode))
        with open(found) as f:
            seen = json.load(f)
        result["stages"] += seen["stages"]
        result["evidence"] = {"devices": seen.get("devices"), "probe": seen.get("probe")}
        if seen.get("infrastructure"):
            return ended("infrastructure", "browser", seen["infrastructure"])
        failed = next((s for s in seen["stages"] if not s["ok"]), None)
        return ended("fail", failed["stage"], failed["detail"]) if failed else ended("pass")
    finally:
        stop(hass)
        if scored:      # whatever the work's code left running
            subprocess.run(["pkill", "-9", "-u", os.environ["SEEDCO_SCORER"]], capture_output=True)
        result["seconds"] = round(time.time() - time.mktime(time.strptime(result["started"], "%Y-%m-%dT%H:%M:%SZ")) + time.timezone)
        with open(os.path.join(out, "business.json"), "w") as f:
            json.dump(result, f, indent=2)


if __name__ == "__main__":
    tests, out = (os.path.abspath(p) for p in sys.argv[1:3])
    trees = dict(a.split("=", 1) for a in sys.argv[3:5])
    print(json.dumps(check(tests, {k: os.path.abspath(v) for k, v in trees.items()}, out, script="business_ha_child_devices.cjs"), indent=2))

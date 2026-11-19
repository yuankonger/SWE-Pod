"""The company's business outcome check: can staff do, on the running company, what the feature is for?

    python3 business.py <tests dir> <core tree> <dashboard tree> <out dir>

As a module it is what tools/harbor_company_score.py calls after the partial-credit score (copied to the task's
tests/business.py, with tests/business_customer_tier.cjs beside it).

The two trees are started together from nothing: a database of their own with the project's sample data (the same
for every pair of trees), the API on it, the staff application's own server pointed at that API. Then a browser
does a piece of real work (tests/business_customer_tier.cjs): through the staff application it sets a customer's
contract tier, and in a new session finds that customer with the tier filter; the API is then asked, outside the
staff application, whether the tier is kept. The database is read directly at the end, as a diagnosis only.

The verdict is one of
    pass             every stage did what it should
    fail             a stage did not, because of what the trees do; `failed_stage` and `reason` say which and why
    infrastructure   the check itself could not run (database server, browser, a port, a tool): nothing is said
                     about the trees
It does not change the reward. Standard library only (the browser part needs Playwright and a Chromium).
"""
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

DATABASE, API_PORT, APP_PORT = "seedco_business", 8766, 9123
API = "http://127.0.0.1:{}/graphql/".format(API_PORT)
APP = "http://127.0.0.1:{}/".format(APP_PORT)
CUSTOMER = "tier.check@example.com"


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


def answers(url, body=None, tries=60, wait=3):
    for _ in range(tries):
        try:
            request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"} if body else {})
            with urllib.request.urlopen(request, timeout=8) as r:
                if r.status == 200:
                    return True
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(wait)
    return False


def stop(proc):
    if proc and proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass


def psql(query):
    done = sh("su postgres -c \"psql -At -F ' | ' -d {} -c \\\"{}\\\"\"".format(DATABASE, query), timeout=60)
    return (done.stdout.strip().splitlines() if done.returncode == 0 else ["not readable: " + (done.stderr.strip().splitlines() or ["?"])[0].replace("ERROR:", "").strip()])


def database_reads():
    """What the database itself holds, for whoever reads the result. It decides nothing."""
    return {
        "tables_for_customer_types_and_customer_attributes": psql("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename ~ 'customer_?type|user_?attribute' ORDER BY 1"),
        "customer_row": psql("SELECT id, email FROM account_user WHERE email = '{}'".format(CUSTOMER)),
        "customer_tier_rows": psql("SELECT u.email, a.slug, v.slug FROM attribute_assigneduserattributevalue x JOIN account_user u ON u.id = x.user_id "
                                   "JOIN attribute_attributevalue v ON v.id = x.value_id JOIN attribute_attribute a ON a.id = v.attribute_id "
                                   "WHERE u.email = '{}'".format(CUSTOMER)),
        "migrations_applied_to_account": psql("SELECT count(*) FROM django_migrations WHERE app = 'account'"),
    }


def check(tests, core, dashboard, out, deadline=None):
    """`deadline`: a time.time() by which the check must be over; every wait inside it is cut to fit."""
    os.makedirs(out, exist_ok=True)
    left = lambda cap: max(30, min(cap, (deadline or float("inf")) - time.time()))
    result = {"verdict": "infrastructure", "failed_stage": None, "reason": None, "stages": [], "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    api = app = None

    def ended(verdict, stage=None, reason=None):
        result.update(verdict=verdict, failed_stage=stage, reason=reason)
        return result

    def stage(name, ok, detail=""):
        result["stages"].append({"stage": name, "ok": bool(ok), "detail": detail})
        return ok

    try:
        # ---- the check's own footing: nothing here says anything about the trees
        sh("pkill -f '[u]vicorn saleor.asgi.*{}' ; pkill -f '[v]ite.*{}' ; true".format(API_PORT, APP_PORT))
        for _ in range(30):      # a container that has only just started is still starting its database server
            if sh("su postgres -c 'psql -qAtc \"SELECT 1\"'", timeout=20).returncode == 0:
                break
            time.sleep(2)
        sh("su postgres -c \"psql -qc \\\"CREATE ROLE saleor SUPERUSER LOGIN PASSWORD 'saleor'\\\"\"", timeout=30)      # there already, as a rule
        made = sh("su postgres -c \"psql -qc 'DROP DATABASE IF EXISTS {0}' -c 'CREATE DATABASE {0} OWNER saleor'\"".format(DATABASE), timeout=120)
        if made.returncode != 0:
            return ended("infrastructure", "database_server", "a database could not be made: " + made.stderr.strip()[-300:])
        browser = sh("node -e \"require('playwright').chromium.launch().then(b => b.close())\"", env=dict(os.environ, NODE_PATH=os.environ.get("NODE_PATH", "/deps/node_modules")), timeout=120)
        if browser.returncode != 0:
            return ended("infrastructure", "browser", "no browser could be started: " + (browser.stderr.strip().splitlines() or ["?"])[-1][:300])
        env = dict(os.environ, DATABASE_URL=re.sub(r"/[^/]*$", "/" + DATABASE, os.environ.get("DATABASE_URL", "postgres://saleor:saleor@127.0.0.1:5432/saleor")), ALLOWED_HOSTS="*")

        # ---- the API, on the project's sample data, served by its own ASGI application (which answers a browser's
        # cross-origin requests; Django's development server does not)
        if os.environ.get("SEEDCO_SCORER"):
            subprocess.run(["chown", "-R", os.environ["SEEDCO_SCORER"], out], capture_output=True)
        migrated = sh("(python manage.py migrate) > {}/migrate.log 2>&1".format(out), cwd=core, env=env, timeout=left(900), work=True)
        if not stage("core_migrates", migrated.returncode == 0, "" if migrated.returncode == 0 else "see migrate.log"):
            return ended("fail", "core_migrates", "the API's database migration does not run")
        seeded = sh("(python manage.py populatedb --createsuperuser) > {}/seed.log 2>&1".format(out), cwd=core, env=env, timeout=left(1200), work=True)
        if not stage("core_seeds", seeded.returncode == 0, "" if seeded.returncode == 0 else "see seed.log"):
            return ended("fail", "core_seeds", "the API cannot load the project's sample data")
        scored = bool(os.environ.get("SEEDCO_SCORER"))
        api = subprocess.Popen(as_work("exec uvicorn saleor.asgi:application --host 0.0.0.0 --port {} --lifespan off > {}/api.log 2>&1".format(API_PORT, out), env),
                               cwd=core, env=None if scored else env, start_new_session=True)
        if not stage("core_serves", answers(API, json.dumps({"query": "{ __typename }"}).encode(), tries=40)):
            return ended("fail", "core_serves", "the API does not answer")

        # ---- the staff application, by its own development server, calling that API
        if not os.path.exists(os.path.join(dashboard, "node_modules")) and os.path.isdir("/deps/node_modules"):
            os.symlink("/deps/node_modules", os.path.join(dashboard, "node_modules"))
        app_env = dict(os.environ, API_URL=API, APP_MOUNT_URI="/")
        app = subprocess.Popen(as_work("exec npx vite --host 127.0.0.1 --port {} --strictPort > {}/app.log 2>&1".format(APP_PORT, out), app_env), cwd=dashboard,
                               env=None if scored else app_env, start_new_session=True)
        if not stage("dashboard_serves", answers(APP, tries=60)):
            return ended("fail", "dashboard_serves", "the staff application's server does not answer")

        # ---- the work itself, in a browser
        found = os.path.join(out, "browser.json")
        if os.path.isfile(found):
            os.remove(found)
        ran = sh("node {}/business_customer_tier.cjs {} {} {} {} > {}/browser.log 2>&1".format(tests, API, APP, CUSTOMER, out, out),
                 env=dict(os.environ, NODE_PATH=os.environ.get("NODE_PATH", "/deps/node_modules")), timeout=left(3600))
        if not os.path.isfile(found):
            return ended("infrastructure", "browser", "the browser part ended without a result (exit {}); see browser.log".format(ran.returncode))
        with open(found) as f:
            seen = json.load(f)
        result["stages"] += seen["stages"]
        result["customer"] = seen.get("customer")
        result["evidence"] = seen.get("probe")      # what the staff application asked the API and what it showed
        result["database"] = database_reads()
        if seen.get("infrastructure"):
            return ended("infrastructure", "browser", seen["infrastructure"])
        failed = next((s for s in seen["stages"] if not s["ok"]), None)
        return ended("fail", failed["stage"], failed["detail"]) if failed else ended("pass")
    finally:
        stop(api)
        stop(app)
        if os.environ.get("SEEDCO_SCORER"):      # whatever the work's code left running
            subprocess.run(["pkill", "-9", "-u", os.environ["SEEDCO_SCORER"]], capture_output=True)
        result["seconds"] = round(time.time() - time.mktime(time.strptime(result["started"], "%Y-%m-%dT%H:%M:%SZ")) + time.timezone)
        with open(os.path.join(out, "business.json"), "w") as f:
            json.dump(result, f, indent=2)


if __name__ == "__main__":
    tests, core, dashboard, out = (os.path.abspath(p) for p in sys.argv[1:5])
    print(json.dumps(check(tests, core, dashboard, out), indent=2))

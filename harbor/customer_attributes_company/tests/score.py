"""The company verifier as it runs inside a Harbor seat (copied to the task's tests/score.py).

    python3 score.py <tests dir> <work dir> <out dir>

The work is what is on `main` of the company's git server, cloned afresh with the verifier's own token; the seat's
checkouts are not looked at. It runs the task's rubric, <tests dir>/rubric.toml (the format, and the `command` and
`judge` types every verifier has: tests/rubric.py). The types of criterion this verifier adds:

    tests      `repository`, `set`: the share that pass of a repository's tests. The feature's hidden tests are laid
               over the clone and the whole suite is run there once. `set = "new"`: the tests written for the
               feature. `set = "preserved"`: every test that passed as the work started.
    contract   `check`: the provider's API is taken from the clone, migrated on a database of its own, asked for its
               schema and served, and the consumer is held against it:
                 works           the API migrates a fresh database and answers, and the consumer's operations were found
                 valid_share     the share of the operations the consumer sends that are valid against that schema
                 uses_new_api    the share the consumer uses of what the real consumer uses of what the API gained
                 copies_current  the share of what the API gained that the consumer's own copies of the schema state
    browser    the task's business check (tests/business.py): the systems started together from nothing and a piece
               of real work done on them in a browser. `stages`: the stages of it the criterion is decided by (all of
               them by default); it passes if every one of them did, fails if one failed or was never reached because
               the work stopped it earlier, and has no score if the check itself could not run.
    untouched  the tests and test settings that were there as the work started, and that the hidden tests do not
               replace, are as they were. Lists what was changed: a test suite decides most of the reward, and the
               suite is the work's own.

    reward = 0 if a gate fails, else weighted mean of targets x product of guards x product of fits

    scoring    gate: the pushed code leaves the scoring alone. Code that is not a test (the tests and test settings
               are the start's, see below) must not reach into the test runners: no pytest or Jest hooks or internals,
               no report writing, no interpreter start-up files.

How the work is run when it is scored. The tests and test settings of every repository (test directories, conftest
files, pytest and Jest configuration, snapshots) are taken as they were at the start of the work, the feature's hidden
tests are laid over them, and the work's own code runs against that. So is the run configuration at a repository's root
(pyproject.toml, which holds core's pytest options, and the dashboard's .swcrc), whole. The start is the commit each repository was at
when the company started (SEEDCO_START, kept by the judge), not whatever a pushed history now begins with.

In the judge (sidecars/judge.py: SEEDCO_SCORER is set) the scorer runs as root in a container the agent never had,
and everything that runs the work's code (its tests, its migrations, its servers) runs as that unprivileged user, with
a plain environment and no login shell, and every process it left is ended before anything it wrote is read. The
hidden reference (which tests count, what the real consumer uses, the API before the feature) is read before any of
the work's code runs. The API's schema is the one the API serves, asked for over HTTP.

Writes <out>/reward.txt, <out>/score.json and <out>/rubric.txt (the criteria, one a line), and, if the rubric has
a browser criterion, <out>/business_verdict.txt. Standard library only.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

TESTS, WORK, OUT = (os.path.abspath(p) for p in sys.argv[1:4])
# One deadline for all of the scoring, inside the verifier's own (task.toml: 10,800 s), with room to write the result.
# Each phase gets at most its share, and never more than is left. A suite that takes ten minutes alone takes four
# times that on a machine that is busy.
BUDGET_S = float(os.environ.get("SEEDCO_BUDGET_S", "10200"))
BEGAN = time.time()
PHASE_S = {"core": 4800, "dashboard": 2400, "contract": 1200, "browser": 1800}


def left(phase, reserve=300):
    """Seconds this phase may take: its share, or what is left of the whole before the reserve, whichever is less."""
    return max(60, min(PHASE_S.get(phase, 1800), BEGAN + BUDGET_S - reserve - time.time()))
SCRATCH = "/tmp/seedco-score"
DATABASE = "seedco_score"
PORT = 8765


SCORER = os.environ.get("SEEDCO_SCORER")      # the unprivileged user the work's code runs as, in the judge
PLAIN_PATH = "/venv/bin:/usr/local/bin:/usr/bin:/bin"
UNSAFE = ("LD_", "PYTHONPATH", "PYTHONSTARTUP", "PYTHONHOME", "PYTEST_", "NODE_OPTIONS", "JEST_", "BASH_ENV", "ENV", "PROMPT_COMMAND")


def as_work(command, env=None):
    """The argv that runs a shell command of the work's own code: as the scorer user with a plain environment where
    there is one, else as it is (outside the judge, as before)."""
    if not SCORER:
        return ["bash", "-lc", command]
    base = dict(env or os.environ)
    keep = {k: v for k, v in base.items() if not k.startswith(UNSAFE) and k not in ("HOME", "USER", "LOGNAME", "PATH", "SHELL")}
    keep.update(PATH=PLAIN_PATH, HOME="/home/" + SCORER, USER=SCORER, LANG="C.UTF-8")
    return ["/usr/sbin/runuser", "-u", SCORER, "--", "/usr/bin/env", "-i"] + ["{}={}".format(k, v) for k, v in sorted(keep.items())] + ["bash", "--noprofile", "--norc", "-c", command]


def end_work():
    """Ends every process the work's code left behind, before anything it wrote is read."""
    if SCORER:
        subprocess.run(["pkill", "-9", "-u", SCORER], capture_output=True)
        time.sleep(1)


def sh(command, cwd=None, timeout=None, env=None, work=False):
    """A shell command. `work`: it runs the work's own code (see as_work)."""
    argv = as_work(command, env) if work else ["bash", "-c", command]
    try:
        return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=None if work and SCORER else env)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(command, 124, "", "timed out")
    finally:
        if work:
            end_work()


def for_work(path):
    """A directory the work's code may write into (its tree, its logs)."""
    os.makedirs(path, exist_ok=True)
    if SCORER:
        subprocess.run(["chown", "-R", SCORER, path], capture_output=True)
    return path


def passed(report, root):
    """The tests that passed, from a JUnit report (.xml) or a Jest one (.json)."""
    if report.endswith(".json"):
        with open(report) as f:
            data = json.load(f)
        return {suite["name"][len(root) + 1:] + "::" + case["fullName"]
                for suite in data["testResults"] for case in suite["assertionResults"] if case["status"] == "passed"}
    cases = {}
    for case in ET.parse(report).getroot().iter("testcase"):
        ok = not any(child.tag in ("failure", "error", "skipped") for child in case)
        cases[(case.get("classname") or "") + "::" + (case.get("name") or "")] = ok
    return {name for name, ok in cases.items() if ok}


GIT = None       # the company's git server, with the verifier's own token; None: score the checkouts under <work dir>
HEADS = {}
START = {}       # repository: the commit it was at when the company started (the judge's record), if known
OWNERS = {}      # the config's owners
# Run configuration that decides how the tests run, kept at a repository's root: put back whole from the start, like
# the tests (pytest reads core's addopts, Django settings and socket rules from pyproject.toml; @swc/jest reads .swcrc).
# Nothing of these files matters to the work once its toolchain is installed, and nothing can be installed here.
RUN_CONFIG = re.compile(r"^(pyproject\.toml|setup\.cfg|tox\.ini|pytest\.ini|\.swcrc|babel\.config\.[cm]?js|\.babelrc(\.[a-z]+)?)$")
TEST_INFRA = re.compile(r"(^|/)(tests?|__tests__|testUtils|fixtures|__snapshots__|__mocks__)/|(^|/)conftest\.py$|\.(test|spec)\.[jt]sx?$"
                        r"|(^|/)(jest|vitest|playwright)\.config\.|(^|/)(pytest\.ini|setup\.cfg|tox\.ini|\.coveragerc)$|(^|/)setupTests?\.")


def git(at, *args):
    return subprocess.run(["git", "-C", at] + list(args), capture_output=True, text=True)


def copy_of(owner, name=None):
    """The work as it counts: `main` of the git server, freshly cloned, with the tests and test settings the work
    started with in place of its own (the hidden tests are laid over these later). Its links to the toolchain
    (node_modules) are the image's, whatever was pushed in their place. (Without a git server, the checkout.)"""
    copy = os.path.join(SCRATCH, name or owner)
    shutil.rmtree(copy, ignore_errors=True)
    if GIT:
        done = subprocess.run(["git", "clone", "-q", "--branch", "main", "{}/{}.git".format(GIT, owner), copy], capture_output=True, text=True)
        if done.returncode != 0:
            raise RuntimeError("could not clone {} from the git server: {}".format(owner, done.stderr.strip()[-300:]))
        HEADS[owner] = git(copy, "rev-parse", "HEAD").stdout.strip()
        start = START.get(owner) or git(copy, "rev-list", "--max-parents=0", "HEAD").stdout.split()[-1]
        if git(copy, "cat-file", "-e", start + "^{commit}").returncode != 0:
            raise RuntimeError("{}: the commit the work started from ({}) is not in the history of main".format(owner, start[:12]))
        # What was scored, to score it again later: all of `main`. The start commit must be in it, as the git server
        # makes it fresh for every trial and keeps it nowhere else; without it, the bundle cannot be opened.
        kept = os.path.join(OUT, "repos", owner + ".bundle")
        if not os.path.isfile(kept):
            os.makedirs(os.path.dirname(kept), exist_ok=True)
            git(copy, "bundle", "create", kept, "main")
        removed = set(OWNERS.get(owner, {}).get("removed_by_feature", []))
        put_back = lambda f: f and (TEST_INFRA.search(f) or RUN_CONFIG.search(f))
        now = [f for f in git(copy, "ls-files").stdout.split("\n") if put_back(f)]
        then = [f for f in git(copy, "ls-tree", "-r", "--name-only", start).stdout.split("\n") if put_back(f)]
        for f in now:
            os.remove(os.path.join(copy, f)) if os.path.lexists(os.path.join(copy, f)) else None
        restore = [f for f in then if not (f in removed and f not in now)]
        for i in range(0, len(restore), 200):
            git(copy, "checkout", start, "--", *restore[i:i + 200])
        shutil.rmtree(os.path.join(copy, ".git"))
    else:
        shutil.copytree(os.path.join(WORK, owner), copy, symlinks=True, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
    for link, target in (OWNERS.get(owner, {}).get("links") or {}).items():
        path = os.path.join(copy, link)
        if os.path.lexists(path):
            shutil.rmtree(path) if os.path.isdir(path) and not os.path.islink(path) else os.remove(path)
        os.symlink(target, path)
        if SCORER and os.path.basename(link) == "node_modules" and os.path.isdir(target):
            # the dashboard's development server keeps its dependency cache here; the toolchain itself stays root's
            for cache in (".vite", ".cache"):
                for_work(os.path.join(target, cache))
    return for_work(copy)


REFERENCE = {}      # read before any of the work's code runs


def run_outcome(code, seconds, cap, reported):
    """How one run of a suite ended. `ran`: the runner ran to an end of its own, with a report (its tests may have
    failed) or without one (the tests could not be loaded against the work's code: none of them passed). Anything
    else (a timeout, a kill, a runner that could not start) is a run the scorer could not complete, which the score
    says, whatever the work's part in it."""
    if reported and code not in (124, 137):
        cause = "ran"
    elif code in (124, 137) and seconds >= cap - 5:
        cause = "timed out"
    elif code == 137:
        cause = "killed (out of memory, most likely)"
    elif code in (126, 127):
        cause = "the test runner could not be started (exit {})".format(code)
    else:      # the runner ran and stopped without a report: the tests could not even be loaded against the work's code
        cause = "ran"
    return {"exit": code, "seconds": round(seconds), "limit": cap, "report": reported, "cause": cause,
            "note": "" if reported else "no report: the suite stopped before reporting (exit {}), so none of its tests passed".format(code)}


def score_repo(owner, spec):
    sets = REFERENCE[owner]
    out = for_work(os.path.join(OUT, owner))
    for stale in os.listdir(out):      # nothing found here before this run counts
        os.remove(os.path.join(out, stale))
    copy = copy_of(owner)
    subprocess.run(["tar", "--no-same-owner", "--no-same-permissions", "-xzf", os.path.join(TESTS, "hidden", owner + "-tests.tar.gz"), "-C", copy], check=True)
    os.chmod(copy, 0o755)      # the archive's own top folder would otherwise set the tree's mode
    for_work(copy)
    started, runs = time.time(), []
    if spec["report"] == "jest":
        # A seat has a memory limit, and Jest with four workers on this project goes past six gigabytes (compiling
        # the sources for the first time most of all). A worker killed for it leaves Jest waiting for ever, with no
        # report. So the suite is run in parts, each a new process, and with two workers.
        listed = sh("npx jest --listTests 2>/dev/null", cwd=copy, timeout=300, work=True).stdout.split()
        files = sorted(f for f in listed if f.startswith(copy))
        parts = max(1, int(spec.get("parts", 4)))
        ran, budget = set(), left(owner)
        for n in range(parts):
            chunk = files[n::parts]
            report = os.path.join(out, "report-{}.json".format(n))
            command = re.sub(r"--maxWorkers=\d+", "--maxWorkers=2", spec["test_command"]).replace("/out/report.json", report) + " --runTestsByPath " + " ".join("'{}'".format(f) for f in chunk)
            cap, began = max(60, int(budget / parts)), time.time()
            done = sh("timeout -s KILL {} {} > {}/tests-{}.log 2>&1".format(cap, command, out, n), cwd=copy, work=True)
            runs.append(run_outcome(done.returncode, time.time() - began, cap, os.path.isfile(report)))
            if os.path.isfile(report):
                ran |= passed(report, copy)
    else:
        report = os.path.join(out, "junit.xml")
        cap, began = int(left(owner)), time.time()
        done = sh("timeout -s KILL {} {} --junitxml={} > {}/tests.log 2>&1".format(cap, spec["test_command"], report, out), cwd=copy, work=True)
        runs.append(run_outcome(done.returncode, time.time() - began, cap, os.path.isfile(report)))
        ran = passed(report, copy) if os.path.isfile(report) else set()
    new, kept = [t for t in sets["new"] if t in ran], [t for t in sets["preserved"] if t in ran]
    shutil.rmtree(copy, ignore_errors=True)
    return {"passed": sorted(ran & set(sets["new"]) | ran & set(sets["preserved"])), "sets": sets,
            "progress": round(len(new) / len(sets["new"]), 4), "regression": round(len(kept) / len(sets["preserved"]), 4),
            "new_passed": len(new), "new_total": len(sets["new"]), "preserved_passed": len(kept), "preserved_total": len(sets["preserved"]),
            "suite_started": bool(ran), "seconds": round(time.time() - started), "runs": runs,
            "complete": all(r["cause"] == "ran" for r in runs)}


def agreement(contract):
    out = os.path.join(OUT, "agreement")
    os.makedirs(out, exist_ok=True)
    copy = copy_of(contract["provider"])
    consumer = copy_of(contract["consumer"])
    built = os.path.join(out, "built_schema.graphql")
    # a database of its own, so that what the agent did to the seat's database decides nothing
    sh("su postgres -c \"psql -qc 'DROP DATABASE IF EXISTS {0}' -c 'CREATE DATABASE {0} OWNER saleor'\"".format(DATABASE))
    env = dict(os.environ, DATABASE_URL=re.sub(r"/[^/]*$", "/" + DATABASE, os.environ.get("DATABASE_URL", "postgres://saleor:saleor@127.0.0.1:5432/saleor")))
    serve = contract["serve"].replace("8000", str(PORT))
    url = "http://127.0.0.1:{}/graphql/".format(PORT)
    for_work(out)
    migrates = sh("({}) > {}/migrate.log 2>&1".format(contract["migrate"], out), cwd=copy, env=env, timeout=left("contract"), work=True).returncode == 0
    server = subprocess.Popen(as_work("exec {} > {}/server.log 2>&1".format(serve, out), env), cwd=copy, env=None if SCORER else env, start_new_session=True)
    code = "000"
    for _ in range(40):
        code = sh("curl -s -m 5 -o /dev/null -w '%{{http_code}}' -X POST -H 'Content-Type: application/json' -d '{{\"query\":\"{{ __typename }}\"}}' {}".format(url)).stdout.strip()
        if code == "200":
            break
        time.sleep(3)
    # the schema is what the API serves, asked for as any client would; not what a command of the work prints
    prints = code == "200" and sh("NODE_PATH=/deps/node_modules node {}/fetch_schema.cjs {} {} 2> {}/schema.log".format(TESTS, url, built, out), timeout=120).returncode == 0
    sh("pkill -s {} || true".format(server.pid))
    server.kill()
    end_work()
    result = {"api_migrates": migrates, "api_prints_schema": prints and os.path.isfile(built) and os.path.getsize(built) > 0, "api_serves": code == "200",
              "operations": 0, "valid": 0, "invalid": {}, "uses_new_api": 0.0, "copies_current": 0.0}
    if result["api_prints_schema"]:
        sh("node {t}/mined_graphql_agreement.cjs {b} {c} {o}/agreement.json --base {base} --reference {usage} --copies {copies} > {o}/agreement.log 2>&1".format(
            t=TESTS, b=built, c=consumer, o=out, base=REFERENCE["base_schema"], usage=REFERENCE["usage"],
            copies=",".join(contract["copies"])), timeout=600)
        if os.path.isfile(os.path.join(out, "agreement.json")):
            with open(os.path.join(out, "agreement.json")) as f:
                found = json.load(f)
            result.update(operations=found["operations"], valid=found["valid"], invalid=found["invalid"], unreadable=found.get("unreadable", {}),
                          collisions=found.get("collisions", {}), uses_new_api=round(found["uses_new_api"], 4),
                          new_api_not_used=found["new_api_not_used"], copies_current=round(found["copies_current"], 4), copies=found["copies"])
    works = result["api_migrates"] and result["api_serves"] and result["operations"] > 0
    result["valid_share"] = round(result["valid"] / result["operations"], 4) if result["operations"] else 0.0
    result["agreement"] = round(result["valid_share"] * result["uses_new_api"] * result["copies_current"], 4) if works else 0.0
    shutil.rmtree(copy, ignore_errors=True)
    shutil.rmtree(consumer, ignore_errors=True)
    return dict(result, provider=contract["provider"], consumer=contract["consumer"])


TEST_FILES = re.compile(r"(^|/)(tests?|__tests__|testUtils|fixtures)/|(^|/)conftest\.py$|\.(test|spec)\.[jt]sx?$|(^|/)jest\.config\.|(^|/)(pytest\.ini|setup\.cfg|tox\.ini)$"
                        r"|^pyproject\.toml$|^\.swcrc$|^babel\.config\.|^\.babelrc")


def untouched(owners):
    """The tests and test settings of the work's start that were changed, renamed or removed, leaving out what the
    hidden tests replace: ({owner: [paths]}, {owner: [test files added]}). Files the work added are not changes to
    what it started with; they are listed apart."""
    changed, added = {}, {}
    for owner in owners:
        at = os.path.join(SCRATCH, "history-" + owner)
        shutil.rmtree(at, ignore_errors=True)
        subprocess.run(["git", "clone", "-q", "{}/{}.git".format(GIT, owner), at], capture_output=True)
        first = [START[owner]] if START.get(owner) else subprocess.run(["git", "-C", at, "rev-list", "--max-parents=0", "HEAD"], capture_output=True, text=True).stdout.split()
        names = subprocess.run(["git", "-C", at, "diff", "--name-only", "--diff-filter=MDR", first[-1], "HEAD"], capture_output=True, text=True).stdout.split("\n") if first else []
        new = subprocess.run(["git", "-C", at, "diff", "--name-only", "--diff-filter=A", first[-1], "HEAD"], capture_output=True, text=True).stdout.split("\n") if first else []
        laid = set(n[2:] if n.startswith("./") else n for n in subprocess.run(
            ["tar", "-tzf", os.path.join(TESTS, "hidden", owner + "-tests.tar.gz")], capture_output=True, text=True).stdout.split("\n"))
        changed[owner] = sorted(n for n in names if n and TEST_FILES.search(n) and n not in laid and n not in owners[owner].get("removed_by_feature", []))
        added[owner] = sorted(n for n in new if n and TEST_FILES.search(n) and n not in laid)
        shutil.rmtree(at, ignore_errors=True)
    return changed, added


# The scan of the pushed code is a second line, behind the first: the tests and run configuration are put back from
# the start, and the work runs unprivileged in a container of its own. It only looks at code (not prose, not comments),
# and only what it finds that is unmistakably aimed at the test runner fails the gate. The rest is listed for a
# reviewer and decides nothing.
CODE = re.compile(r"\.(py|pyi|js|cjs|mjs|jsx|ts|tsx|json|toml|cfg|ini|sh)$")
COMMENT = re.compile(r"^\s*(#|//|/\*|\*|\"\"\"|\'\'\')")
AIMED = re.compile(      # code that hooks into or rewrites the test runners, or writes what the scorer reads
    r"^\s*(import|from)\s+(_pytest|pluggy|xdist)\b"
    r"|\bdef\s+pytest_(runtest|collection|configure|sessionstart|sessionfinish|report|terminal|make|unconfigure|plugin)\w*\s*\("
    r"|@pytest\.hookimpl|\bpytest_plugins\s*="
    r"|require\(\s*['\"](@jest/(reporters|test-result|core)|jest-circus|_pytest)"
    r"|\btestResultsProcessor\b"
    r"|(open|write\w*|unlink|remove|rename)\s*\(.*(/logs/verifier|reward\.txt|junit\.xml|/srv/judge|/tests/hidden)")
SIGNAL = re.compile(      # worth a reviewer's look, no more: these words turn up in honest code too
    r"_pytest|\bpluggy\b|xdist|junitxml|junit\.xml|@jest/|jest-circus|setupFilesAfterEnv|\breporters\s*:|sitecustomize|usercustomize"
    r"|/tests/hidden|seedco-score|/logs/verifier|reward\.txt|/srv/judge")
STARTUP_FILES = re.compile(r"(^|/)(sitecustomize|usercustomize)\.py$|\.pth$|(^|/)(pytest|_pytest|pluggy|conftest)(/|\.py$)")


def scoring_untouched(owners):
    """What of the pushed code, outside the tests and test settings, reaches into the scoring: (aimed, signals).
    `aimed` fails the gate; `signals` are for a reviewer."""
    aimed, signals = [], []
    for owner in owners:
        at = os.path.join(SCRATCH, "scan-" + owner)
        shutil.rmtree(at, ignore_errors=True)
        subprocess.run(["git", "clone", "-q", "{}/{}.git".format(GIT, owner), at], capture_output=True)
        start = START.get(owner) or git(at, "rev-list", "--max-parents=0", "HEAD").stdout.split()[-1]
        for name in git(at, "diff", "--name-only", "--diff-filter=AMR", start, "HEAD").stdout.split("\n"):
            if name and not TEST_INFRA.search(name) and not RUN_CONFIG.search(name) and STARTUP_FILES.search(name):
                aimed.append("{}: adds {}".format(owner, name))
        diff = git(at, "diff", "-U0", "--diff-filter=AMR", start, "HEAD").stdout
        current = None
        for line in diff.split("\n"):
            if line.startswith("+++ b/"):
                current = line[6:]
                continue
            if not (line.startswith("+") and not line.startswith("+++") and current):
                continue
            if TEST_INFRA.search(current) or RUN_CONFIG.search(current) or not CODE.search(current):
                continue      # tests and run configuration are put back anyway; prose decides nothing
            text = line[1:]
            if COMMENT.search(text):
                continue
            where = "{}: {}: {}".format(owner, current, text.strip()[:160])
            if AIMED.search(text):
                aimed.append(where)
            elif SIGNAL.search(text):
                signals.append(where)
        shutil.rmtree(at, ignore_errors=True)
    return aimed, signals


def main():
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(TESTS, "config.json")) as f:
        config = json.load(f)
    sys.path.insert(0, TESTS)
    import rubric
    _, criteria = rubric.load(os.path.join(TESTS, "rubric.toml"), {"tests": "repository", "contract": "check", "browser": None, "untouched": None, "scoring": None})
    global GIT
    GIT = config.get("git")
    OWNERS.update(config["owners"])
    if os.environ.get("SEEDCO_START") and os.path.isfile(os.environ["SEEDCO_START"]):
        with open(os.environ["SEEDCO_START"]) as f:
            START.update(json.load(f))
    # the hidden reference, read before any of the work's code runs
    for owner in config["owners"]:
        with open(os.path.join(TESTS, "hidden", owner + "-reference.json")) as f:
            REFERENCE[owner] = json.load(f)
    hold = os.path.join(SCRATCH, "reference")
    os.makedirs(hold, exist_ok=True)
    for key in ("base_schema", "usage"):
        REFERENCE[key] = os.path.join(hold, os.path.basename(config["contract"][key]))
        shutil.copy(os.path.join(TESTS, config["contract"][key]), REFERENCE[key])
    os.chmod(hold, 0o700)
    # whatever the agent left running must not answer in the scorer's place, or hold its memory
    sh("pkill -f 'manage.py runserver' ; pkill -f jest ; pkill -f pytest ; true")
    result = {"repositories": {owner: score_repo(owner, spec) for owner, spec in config["owners"].items()},
              "contracts": [agreement(config["contract"])]}
    contract = result["contracts"][0]
    contract["works"] = bool(contract["api_migrates"] and contract["api_serves"] and contract["operations"] > 0)
    rows, change = [], None

    def write(final):
        """Writes reward.txt, score.json and rubric.txt from the criteria so far. The scored criteria come first and are
        written before any measure runs: a measure that is slow or breaks cannot keep or change the reward."""
        result["criteria"] = list(rows)
        result["gates"] = rubric.gates(rows)
        result["progress"], result["regression"], result["agreement"] = rubric.share(rows, "target"), rubric.product(rows, "guard"), rubric.product(rows, "fit")
        result["reward"] = round(result["progress"] * result["regression"] * result["agreement"], 4) if result["gates"] else 0.0
        result["not_run"] = [r["id"] for r in rows if r["score"] is None]
        result["scored_commits"] = HEADS
        result["measures_done"] = final
        incomplete = {o: [r["cause"] for r in v.get("runs", []) if r["cause"] != "ran"] for o, v in result["repositories"].items()}
        incomplete = {o: v for o, v in incomplete.items() if v}
        incomplete.update({c["id"]: "not run: " + c["detail"][:200] for c in rows if c["score"] is None and c["kind"] != "measure"})
        result["complete"], result["incomplete"] = not incomplete, incomplete
        said = rubric.table(rows, "targets {} x guards {} x fit {} = reward {}{}{}".format(result["progress"], result["regression"], result["agreement"], result["reward"],
                                                                                         "" if result["gates"] else "   (a gate failed: nothing else counts)",
                                                                                         "" if not incomplete else "   (INCOMPLETE: {})".format(json.dumps(incomplete)[:300])))
        kept = json.loads(json.dumps(result, default=str))
        for r in kept["repositories"].values():      # the lists are for the criteria; score.json keeps the counts
            r.pop("passed", None)
            r.pop("sets", None)
        with open(os.path.join(OUT, "score.json"), "w") as f:
            json.dump(kept, f, indent=2)
        with open(os.path.join(OUT, "rubric.txt"), "w") as f:
            f.write(said + "\n")
        with open(os.path.join(OUT, "reward.txt"), "w") as f:
            f.write(str(result["reward"]))
        return said

    criteria = [c for c in criteria if c["kind"] != "measure"] + [c for c in criteria if c["kind"] == "measure"]
    written = False
    for c in criteria:
        if c["kind"] == "measure" and not written:
            write(False)
            written = True
        score, detail = None, ""
        if c["type"] == "tests":
            r = result["repositories"][c["repository"]]
            which = "new" if c.get("set", "new") == "new" else "preserved"
            # `only` / `exclude`: a regular expression on the test's name (its file first) that narrows the set
            chosen = [t for t in r["sets"][which] if (not c.get("only") or re.search(c["only"], t)) and not (c.get("exclude") and re.search(c["exclude"], t))]
            got = len(set(chosen) & set(r["passed"]))
            score = round(got / len(chosen), 4) if chosen else None
            detail = "{} of {} pass{}".format(got, len(chosen), "" if r["suite_started"] else "; the suite gave no report")
        elif c["type"] == "contract":
            score = contract[c["check"]]
            detail = {"works": "migrates {}, serves {}, operations found {}".format(contract["api_migrates"], contract["api_serves"], contract["operations"]),
                      "valid_share": "{} of {} valid (documents that could not be read and fragments defined twice count as not valid); invalid: {}{}{}".format(
                          contract["valid"], contract["operations"], json.dumps(contract["invalid"])[:240],
                          "; unreadable: " + ", ".join(sorted(contract.get("unreadable") or {}))[:200] if contract.get("unreadable") else "",
                          "; fragments defined twice: " + ", ".join(sorted(contract.get("collisions") or {}))[:200] if contract.get("collisions") else ""),
                      "uses_new_api": "not used: {}".format(json.dumps(contract.get("new_api_not_used"))[:300]),
                      "copies_current": json.dumps(contract.get("copies"))[:300]}.get(c["check"], "")
        elif c["type"] == "browser":
            if "business" not in result:      # run once, for every browser criterion
                try:
                    import business
                    trees = {role: copy_of(owner, "business-" + owner) for role, owner in config["business"].items()}
                    found = business.check(TESTS, trees["core"], trees["dashboard"], os.path.join(OUT, "business"), deadline=time.time() + left("browser"))
                    for tree in trees.values():
                        shutil.rmtree(tree, ignore_errors=True)
                except Exception as e:      # the check's own trouble: it says nothing about the work
                    found = {"verdict": "infrastructure", "failed_stage": "scorer", "reason": "{}: {}".format(type(e).__name__, e), "stages": []}
                result["business"] = found
                said = "{}{}".format(found["verdict"], "" if found["verdict"] == "pass" else " at {}: {}".format(found.get("failed_stage"), found.get("reason")))
                with open(os.path.join(OUT, "business_verdict.txt"), "w") as f:
                    f.write(said + "\n")
            found = result["business"]
            got = {st["stage"]: st["ok"] for st in found.get("stages", [])}
            wanted = c.get("stages") or list(got)
            failed = [st for st in found.get("stages", []) if not st["ok"]]
            if wanted and all(got.get(w) for w in wanted):
                score, detail = True, "passed: " + ", ".join(wanted)
            elif any(got.get(w) is False for w in wanted):
                which = next(w for w in wanted if got.get(w) is False)
                score, detail = False, "failed at {}: {}".format(which, next(st["detail"] for st in found["stages"] if st["stage"] == which))
            elif failed:      # a stage before them failed, so they were never reached: the work stopped them
                score, detail = False, "not reached: {} failed first ({})".format(failed[0]["stage"], failed[0]["detail"][:300])
            else:      # not reached, and nothing the work did failed: the check itself could not run
                score, detail = None, "not run: {}".format(found.get("reason") or "the check could not run")
        elif c["type"] == "scoring":
            if "reaches_into_scoring" not in result:
                aimed, signals = scoring_untouched(config["owners"]) if GIT else ([], [])
                result["reaches_into_scoring"], result["scoring_review_signals"] = aimed, signals
            found = result["reaches_into_scoring"] if c.get("signals") != "review" else result["scoring_review_signals"]
            score, detail = not found, "; ".join(found[:8])
        elif c["type"] == "untouched":
            changed, added = untouched(config["owners"]) if GIT else ({}, {})
            result["tests_changed"], result["tests_added"] = changed, added
            score = not any(changed.values())
            detail = "; ".join("{}: {}".format(o, ", ".join(v[:12]) + (" and {} more".format(len(v) - 12) if len(v) > 12 else "")) for o, v in changed.items() if v)
            if any(added.values()):      # for the reader: what the work added is no change, but worth knowing
                detail = (detail + "; " if detail else "") + "added (not counted): " + "; ".join("{}: {} test files".format(o, len(v)) for o, v in added.items() if v)
        elif c["type"] == "command":
            score, detail = rubric.command(c)
        elif c["type"] == "judge":
            if change is None:
                change = rubric.pushed(GIT, list(config["owners"]))
            score, detail = rubric.judge(c, change)
        rows.append(rubric.row(c, score, detail))
    said = write(True)
    print(json.dumps({k: v for k, v in result.items() if k not in ("contracts", "business", "criteria", "repositories")}, indent=2, default=str))
    print(said)


if __name__ == "__main__":
    main()

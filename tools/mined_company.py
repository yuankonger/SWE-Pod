"""A company made of real repositories, and a feature that crosses them.

Each owner's directory is a real repository at the commit before the feature (a mined task under mined/, one per
repository). The company task (mined/<company>/task.json) says which repositories, who owns each, how they are
joined, and what each owner is told.

    python3 tools/mined_company.py reference <repo task> <base report> <target report> [<report of the base under the target's tests> <clone>]
    python3 tools/mined_company.py interface <repo task> <clone>
    python3 tools/mined_company.py base      <repo task> <clone>       (a task with `base_recipe`: build its start in the clone)
    python3 tools/mined_company.py usage     <company> --clone owner=path ...
    python3 tools/mined_company.py prepare   <company> <workspace> --clone owner=path ... [--oracle base|target]
    python3 tools/mined_company.py score     <company> <workspace> <out dir> --clone owner=path ...
    python3 tools/mined_company.py run       <company> --clone owner=path ... --model M [--condition solo|team|team_no_messaging|lead] [--budget 40]

How the repositories are joined, as in the real project:
- One calls the other's API. The caller keeps a copy of the API's schema and generates code from it. At the start
  the copy is put back to the API as it is before the feature (`contracts`), so the caller's owner has to get the
  new API from the owner who builds it.
- During a run the company has a git server. Every agent works in checkouts of its own, one container per
  repository with that repository's toolchain, and the containers of the run can reach each other by name, so one
  agent can call the service another has started. Who may read and push what is set by the environment (`--others`)
  and is the same whatever the condition. Only what is on `main` of the server counts.
- `main` is recorded every `--checkpoint` dollars and each record is scored: the work's worth against its cost.

Scoring: every repository's own tests (the feature's, hidden, and the ones that passed before), and whether the
two sides agree: the API must migrate and serve; every operation the caller sends must be valid against the
schema the built API really has; the caller must use what the real caller uses of what the API gained; and the
caller's schema copies must state what the API gained. reward = mean progress x product of regression x agreement.
"""
import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "tools"))
import mined_interface                                      # noqa: E402
from mined_pilot import export, git, is_test_side, load, put   # noqa: E402

TOOLS = os.path.join(REPO, "tools")
SCORE_TIMEOUT_S = 2400


def load_company(company):
    """The company and its repositories' tasks. An owner's `override` replaces fields of its repository's task for
    this company alone (a version of a company that starts the same repositories differently)."""
    with open(os.path.join(REPO, "mined", company, "task.json")) as f:
        info = json.load(f)
    return info, {owner: dict(load(spec["task"])[1], **spec.get("override", {})) for owner, spec in info["owners"].items()}


def company_file(company, name):
    """A file of mined/<company>/, or of the company it is `based_on` when it has none of its own."""
    path = os.path.join(REPO, "mined", company, name)
    if os.path.isfile(path):
        return path
    with open(os.path.join(REPO, "mined", company, "task.json")) as f:
        base = json.load(f).get("based_on")
    return company_file(base, name) if base else path


API_SECTION = """
## The API the tests call

The tests call the API by the names below, so the API must have them, spelt and typed as shown. This is all the
feature adds to the API's schema: the new types whole, then what types that exist today gain. Descriptions are
yours to write. `{schema}` is not updated for you: it must be what the code generates.

```graphql
{types}
```

Added to types that exist today:

```graphql
{members}
```
"""


def api_section(contract, repos, clones):
    """What the provider's schema gains with the feature, as its INTERFACE.md states it when the schema file itself
    is not handed over (the provider's hidden tests query these names)."""
    provider, consumer = repos[contract["provider"]], repos[contract["consumer"]]
    holder = tempfile.mkdtemp(prefix="mined-api-")
    _schema_at(clones[contract["provider"]], provider["base"], contract, os.path.join(holder, "base.graphql"))
    _schema_at(clones[contract["provider"]], target_commit(clones[contract["provider"]], provider), contract, os.path.join(holder, "target.graphql"))
    done = subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", TOOLS + ":/tools:ro", "-v", holder + ":/c", "-e", "NODE_PATH=/deps/node_modules",
                           consumer["image"], "node", "/tools/mined_api_names.cjs", "/c/base.graphql", "/c/target.graphql", "/c/api.json"], capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError("could not list what {}'s API gained: {}".format(contract["provider"], (done.stdout + done.stderr)[-800:]))
    with open(os.path.join(holder, "api.json")) as f:
        api = json.load(f)
    shutil.rmtree(holder, ignore_errors=True)
    by_type = {}
    for m in api["members"]:
        by_type.setdefault((m["kind"], m["type"]), []).append(m["sdl"])
    members = "\n\n".join("{} {} {{\n  # ...what it has today, and:\n{}\n}}".format(kind, name, "\n".join("  " + line for sdl in sdls for line in sdl.splitlines()))
                          for (kind, name), sdls in sorted(by_type.items(), key=lambda x: x[0][1]))
    members += "".join("\n\nunion {} gains the member {}".format(u["type"], u["name"]) for u in api["unions"])
    members += "".join("\n\n{}.{} gains the argument {}".format(a["type"], a["field"], a["sdl"]) for a in api["args"])
    return API_SECTION.format(schema=contract["schema"], types="\n\n".join(t["sdl"] for t in api["types"]), members=members)


def base_commit(clone, info):
    """The start. A task whose feature cannot be picked alone on the commit before it (a later pick needs another
    feature's code that landed in between) names `base_recipe`: {"from": a later upstream commit, "reverts": the
    feature's commits merged before it, newest first} and/or {"patch": a patch file beside the task, applied to
    `from`}. The start is then upstream at `from` with only the feature (or, for a slice, one part of it) taken out. It is built with a fixed identity and dates, so its hash is the same on every machine; `base` holds
    that hash and the build is checked against it."""
    recipe = info.get("base_recipe")
    if not recipe:
        return info["base"]
    found = subprocess.run(["git", "-C", clone, "cat-file", "-e", info["base"] + "^{commit}"], capture_output=True)
    if found.returncode == 0:
        return info["base"]
    start = git(clone, "rev-parse", recipe["from"]).strip()
    when = git(clone, "show", "-s", "--format=%cI", start).strip()
    env = dict(os.environ, GIT_AUTHOR_NAME="mined", GIT_AUTHOR_EMAIL="mined@example.com", GIT_COMMITTER_NAME="mined",
               GIT_COMMITTER_EMAIL="mined@example.com", GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    tree = os.path.join(tempfile.mkdtemp(prefix="mined-base-"), "tree")
    git(clone, "worktree", "add", "-q", "--detach", tree, start)
    try:
        for commit in recipe.get("reverts", []):
            subprocess.run(["git", "-C", tree, "revert", "--no-edit", commit], capture_output=True, text=True, check=True, env=env)
        if recipe.get("patch"):      # a slice: upstream at `from` with a part taken out by a patch kept beside the task
            patch = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mined", info["id"], recipe["patch"])
            subprocess.run(["git", "-C", tree, "apply", "--index", patch], capture_output=True, text=True, check=True)
            subprocess.run(["git", "-C", tree, "commit", "-q", "--no-verify", "-m", recipe.get("message", "The start of " + info["id"])], capture_output=True, text=True, check=True, env=env)
        sha = git(tree, "rev-parse", "HEAD").strip()
    finally:
        git(clone, "worktree", "remove", "--force", tree)
    if not sha.startswith(info["base"]):
        raise SystemExit("{}: the recipe built {}, not the base {}".format(info["id"], sha[:12], info["base"]))
    git(clone, "update-ref", "refs/mined/{}-base".format(info["id"]), sha)
    return sha


def target_commit(clone, info):
    """The feature's commit. A task that names `picks` has no such commit in history: the feature's changes are
    applied alone on the base, once, and kept under a ref in the clone."""
    if "target" in info:
        return info["target"]
    ref = "refs/mined/" + info["id"]
    found = subprocess.run(["git", "-C", clone, "rev-parse", "--verify", "-q", ref], capture_output=True, text=True)
    if found.returncode == 0:
        return found.stdout.strip()
    tree = os.path.join(tempfile.mkdtemp(prefix="mined-picks-"), "tree")
    git(clone, "worktree", "add", "-q", "--detach", tree, base_commit(clone, info))
    try:
        for commit in info["picks"]:
            subprocess.run(["git", "-C", tree, "-c", "user.name=mined", "-c", "user.email=mined@example.com", "cherry-pick", commit],
                           capture_output=True, text=True, check=True)
        sha = git(tree, "rev-parse", "HEAD").strip()
        git(clone, "update-ref", ref, sha)
    finally:
        git(clone, "worktree", "remove", "--force", tree)
    return sha


def test_side(info):
    patterns = [re.compile(p) for p in info.get("test_side", [])]
    return (lambda path: any(p.search(path) for p in patterns)) if patterns else is_test_side


def changed_tests(clone, info):
    names = git(clone, "diff", "--name-only", "--diff-filter=AM", info["base"], target_commit(clone, info)).splitlines()
    return [p for p in names if test_side(info)(p)]


def passed(report):
    """The tests that passed, from a JUnit report (.xml) or a Jest one (.json)."""
    if report.endswith(".json"):
        with open(report) as f:
            data = json.load(f)
        return {re.sub(r"^/repo/", "", suite["name"]) + "::" + case["fullName"]
                for suite in data["testResults"] for case in suite["assertionResults"] if case["status"] == "passed"}
    from mined_pilot import passed as junit
    return junit(report)


def ran(report):
    """Every test a Jest report (.json) or a JUnit one (.xml) holds a result for, passed or not. A file that could
    not be loaded has none (pytest reports a collection error as a case of its own, which never names a test)."""
    if not report.endswith(".json"):
        return {(c.get("classname") or "") + "::" + (c.get("name") or "") for c in ET.parse(report).getroot().iter("testcase")}
    with open(report) as f:
        data = json.load(f)
    return {re.sub(r"^/repo/", "", suite["name"]) + "::" + case["fullName"] for suite in data["testResults"] for case in suite["assertionResults"]}


def reference(task, base_report, target_report, base_under_target_tests=None, clone=None):
    """Sorts the tests that pass at the target into the feature's (`new`) and the ones that must keep passing
    (`preserved`), and writes the task's reference.json.

    A test is the feature's if the base cannot pass it. The plain way to tell is to compare the base's own run with
    the target's, but the feature also changes existing tests, and a changed test that passed before may no longer
    pass on the base, while a new one may pass there without any work. So when there is a run of the base tree
    under the target's tests (`base_under_target_tests`, with `clone` to say which test files the feature touched):
    a test that ran there is preserved if it passed and the feature's if it failed; a test whose file could not
    even be loaded there is the feature's if the feature touched the file. Everything else goes by the base's own
    run. If nothing at all ran under the target's tests (one shared file failed to load), that run says nothing
    and the base's own run decides everything."""
    task_dir, info = load(task)
    base, target = passed(base_report), passed(target_report)
    sets = {"new": sorted(target - base), "preserved": sorted(target & base)}
    moved = {}
    if base_under_target_tests:
        there, passed_there = ran(base_under_target_tests), passed(base_under_target_tests)
        touched = set(changed_tests(clone, info))
        if there:
            keeps = lambda t: t in passed_there if t in there else (t in base and t.split("::")[0] not in touched)
            new, preserved = {t for t in target if not keeps(t)}, {t for t in target if keeps(t)}
            moved = {"to_new": len(new - set(sets["new"])), "to_preserved": len(preserved - set(sets["preserved"]))}
            sets = {"new": sorted(new), "preserved": sorted(preserved)}
    with open(os.path.join(task_dir, "reference.json"), "w") as f:
        json.dump(sets, f)
    print("{}: {:,} new tests, {:,} preserved tests ({:,} base tests are gone at the target){}".format(
        task, len(sets["new"]), len(sets["preserved"]), len(base - target),
        "; against the base's own run, {to_new} moved to new and {to_preserved} to preserved".format(**moved) if moved else ""))


def interface(task, clone):
    """Writes the task's interface.json: the names its hidden tests use that the base does not have."""
    task_dir, info = load(task)
    holder = tempfile.mkdtemp(prefix="mined-interface-")
    base, target = os.path.join(holder, "base"), os.path.join(holder, "target")
    export(clone, info["base"], base)
    export(clone, target_commit(clone, info), target)
    files = changed_tests(clone, info)
    if info.get("language") == "typescript":
        found = mined_interface.typescript_interface(base, target, [f for f in files if re.search(r"\.tsx?$", f)], test_side(info), info.get("aliases", {}),
                                                     re.compile(info["generated"]) if info.get("generated") else None)
    else:
        found = mined_interface.python_interface(base, target, files, test_side(info))
    with open(os.path.join(task_dir, "interface.json"), "w") as f:
        json.dump(found, f, indent=1)
    shutil.rmtree(holder, ignore_errors=True)
    modules = [v for k, v in found.items() if k != mined_interface.LOOKED_FOR]
    looked = found.get(mined_interface.LOOKED_FOR, {})
    print("{}: {} new names and {} changed ones in {} modules ({} new); {} test ids and {} texts looked for".format(
        task, sum(len(v["names"]) for v in modules), sum(len(v["changed"]) for v in modules), len(modules), sum(not v["exists_at_base"] for v in modules),
        sum(len(v["test ids"]) for v in looked.values()), sum(len(v["text"]) for v in looked.values())))


def prepare(company, clones, workspace, oracle=None):
    """`<workspace>/services/<owner>` for every owner: the base tree, what is handed over, NOTES.md, INTERFACE.md,
    and the callers' schema copies put back to the API before the feature. `oracle`: every repository untouched at
    its base or at its target, with nothing handed over, to check the scoring."""
    info, repos = load_company(company)
    shutil.rmtree(workspace, ignore_errors=True)
    for owner, repo in repos.items():
        dest = os.path.join(workspace, "services", owner)
        target = target_commit(clones[owner], repo)
        export(clones[owner], target if oracle == "target" else base_commit(clones[owner], repo), dest)
        for link, to in repo.get("links", {}).items():
            os.symlink(to, os.path.join(dest, link))
        notes = repo["notes"] + info.get("notes", {}).get(owner, "")
        if not oracle:
            put(clones[owner], target, repo["handed_over"], dest)
            given = os.path.join(REPO, "mined", info["owners"][owner]["task"], "interface.json")
            if os.path.isfile(given):
                with open(given) as f, open(os.path.join(dest, "INTERFACE.md"), "w") as out:
                    out.write(mined_interface.render(json.load(f), repo.get("language", "python")))
                    if repo.get("api_names"):   # the schema file is not handed over: the API the tests call is stated here
                        out.write(api_section(next(c for c in info["contracts"] if c["provider"] == owner), repos, clones))
                    if repo.get("exact"):       # what the tests assert to the letter and the brief cannot be expected to imply
                        out.write("\n## What the tests check to the letter\n\nBehaviour the hidden tests assert exactly, which the description of the feature does not settle.\n\n"
                                  + "".join("- {}\n".format(line) for line in repo["exact"]))
                notes += "- `INTERFACE.md` lists the names the hidden tests import that do not exist yet{}. Use exactly those names and places.\n".format(", and the behaviour they check to the letter" if repo.get("exact") else "")
        with open(os.path.join(dest, "NOTES.md"), "w") as f:
            f.write(notes)
    if oracle != "target":
        for contract in info.get("contracts", []):
            if contract_type(contract) == "graphql":      # a websocket consumer keeps no copy of the contract: its types are its own code
                _wind_back(contract, repos, clones, workspace)
            elif contract_type(contract) == "lexicon":
                _wind_back_lexicon(contract, repos, clones, workspace)
    return workspace


def contract_type(contract):
    return contract.get("type", "graphql")


def _wind_back(contract, repos, clones, workspace):
    """The consumer's copies of the provider's schema, as the provider is before the feature; its generated code redone."""
    provider, consumer = repos[contract["provider"]], repos[contract["consumer"]]
    holder = tempfile.mkdtemp(prefix="mined-contract-")
    for name, commit in (("base.graphql", provider["base"]), ("target.graphql", target_commit(clones[contract["provider"]], provider))):
        with open(os.path.join(holder, name), "wb") as f:
            f.write(git(clones[contract["provider"]], "show", "{}:{}".format(commit, contract["schema"]), text=False))
    command = "node /tools/mined_strip_schema.cjs /contract/base.graphql /contract/target.graphql {} && {}".format(
        " ".join(contract["copies"]), contract["regenerate"])
    done = subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", TOOLS + ":/tools:ro", "-v", holder + ":/contract:ro",
                           "-v", os.path.join(os.path.abspath(workspace), "services", contract["consumer"]) + ":/repo", "-w", "/repo",
                           consumer["image"], "bash", "-lc", command], capture_output=True, text=True)
    shutil.rmtree(holder, ignore_errors=True)
    if done.returncode != 0:
        raise RuntimeError("could not wind back {}'s copy of {}'s schema: {}".format(contract["consumer"], contract["provider"], (done.stdout + done.stderr)[-800:]))


def _lexicon_files(clone, commit):
    """nsid -> path of every lexicon document under `lexicons/` at a commit, read by its `id`."""
    found = {}
    for path in git(clone, "ls-tree", "-r", "--name-only", commit, "--", "lexicons/").splitlines():
        if path.endswith(".json"):
            try:
                doc = json.loads(git(clone, "show", "{}:{}".format(commit, path)))
            except ValueError:
                continue
            if isinstance(doc, dict) and isinstance(doc.get("id"), str):
                found[doc["id"]] = (path, json.dumps(doc.get("defs"), sort_keys=True))
    return found


def feature_lexicons(contract, repos, clones):
    """The nsids the provider's feature adds and changes, from its `lexicons/` at the start and the target."""
    clone, provider = clones[contract["provider"]], repos[contract["provider"]]
    start, target = _lexicon_files(clone, base_commit(clone, provider)), _lexicon_files(clone, target_commit(clone, provider))
    return sorted(set(target) - set(start)), sorted(k for k in set(start) & set(target) if start[k][1] != target[k][1])


def _wind_back_lexicon(contract, repos, clones, workspace):
    """The consumer's vendored lexicons (`lexicons/`, and the manifest `lexicons.json` with its `resolutions`) as they
    are at the consumer's target, less what the provider's feature adds, and with what it changes as the consumer had
    it at its start. So the consumer starts with every other schema it vendored in the meantime (an unrelated re-sync
    is given, not asked for) and without the feature's, which it has to take from whoever builds the API. There is no
    generated code to redo: social-app generates it from `lexicons/` when its dependencies are linked."""
    added, changed = feature_lexicons(contract, repos, clones)
    clone, consumer = clones[contract["consumer"]], repos[contract["consumer"]]
    start, target = base_commit(clone, consumer), target_commit(clone, consumer)
    dest = os.path.join(workspace, "services", contract["consumer"])
    before, after = _lexicon_files(clone, start), _lexicon_files(clone, target)
    shutil.rmtree(os.path.join(dest, "lexicons"), ignore_errors=True)
    for nsid, (path, _) in after.items():
        if nsid in added:
            continue
        put(clone, start if nsid in changed and nsid in before else target, [before[nsid][0] if nsid in changed and nsid in before else path], dest)
    manifest = json.loads(git(clone, "show", "{}:lexicons.json".format(target)))
    manifest["lexicons"] = [n for n in manifest.get("lexicons", []) if n not in added]
    for nsid in added:
        manifest.get("resolutions", {}).pop(nsid, None)
    for nsid in changed:
        if nsid in before:
            old = json.loads(git(clone, "show", "{}:lexicons.json".format(start))).get("resolutions", {})
            if nsid in old:
                manifest["resolutions"][nsid] = old[nsid]
    with open(os.path.join(dest, "lexicons.json"), "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print("{}: lexicons wound back: without {}; as at the start: {}".format(contract["consumer"], ", ".join(added) or "nothing",
          ", ".join(n for n in changed if n in after) or "nothing"))


def _copy(tree):
    copy = os.path.join(tempfile.mkdtemp(prefix="mined-score-"), "repo")
    shutil.copytree(tree, copy, symlinks=True, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    return copy


def score_repo(owner, task, repo, clone, tree, out_dir):
    """One repository's own tests on the work: the target's test side laid over a copy, the suite run there."""
    with open(os.path.join(REPO, "mined", task, "reference.json")) as f:
        sets = json.load(f)
    os.makedirs(out_dir, exist_ok=True)
    copy = _copy(tree)
    put(clone, target_commit(clone, repo), changed_tests(clone, repo), copy)
    jest = repo.get("report") == "jest"
    report = os.path.join(out_dir, "report.json" if jest else "junit.xml")
    if os.path.isfile(report):
        os.remove(report)
    command = repo["test_command"] if jest else repo["test_command"] + " --junitxml=/out/junit.xml"
    started = time.time()
    subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", copy + ":/repo", "-v", os.path.abspath(out_dir) + ":/out", "-w", "/repo",
                    repo["image"], "bash", "-lc", "timeout -s KILL {} {} > /out/tests.log 2>&1; echo exit $?".format(SCORE_TIMEOUT_S, command)],
                   capture_output=True, text=True)
    ran = passed(report) if os.path.isfile(report) else set()
    new, kept = [t for t in sets["new"] if t in ran], [t for t in sets["preserved"] if t in ran]
    shutil.rmtree(os.path.dirname(copy), ignore_errors=True)
    result = {"progress": round(len(new) / len(sets["new"]), 4), "regression": round(len(kept) / len(sets["preserved"]), 4),
              "new_passed": len(new), "new_total": len(sets["new"]), "preserved_passed": len(kept), "preserved_total": len(sets["preserved"]),
              "suite_started": bool(ran), "seconds": round(time.time() - started)}
    with open(os.path.join(out_dir, "result.json"), "w") as f:
        json.dump(result, f, indent=2)
    return result


def _schema_at(clone, commit, contract, path):
    with open(path, "wb") as f:
        f.write(git(clone, "show", "{}:{}".format(commit, contract["schema"]), text=False))


def _usage_file(company, contract):
    return company_file(company, "usage-{}-{}.json".format(contract["provider"], contract["consumer"]))


def usage(company, clones):
    """For each contract, writes what the real consumer at the feature's commit uses of what the provider's API
    gained: the measure a run's consumer is held against, so that not calling the feature cannot pass."""
    info, repos = load_company(company)
    for contract in info.get("contracts", []):
        if contract_type(contract) == "websocket":
            _websocket_usage(company, contract, repos, clones)
            continue
        if contract_type(contract) == "lexicon":
            _lexicon_usage(company, contract, repos, clones)
            continue
        provider, consumer = repos[contract["provider"]], repos[contract["consumer"]]
        holder = tempfile.mkdtemp(prefix="mined-usage-")
        _schema_at(clones[contract["provider"]], provider["base"], contract, os.path.join(holder, "base.graphql"))
        _schema_at(clones[contract["provider"]], target_commit(clones[contract["provider"]], provider), contract, os.path.join(holder, "target.graphql"))
        tree = os.path.join(holder, "repo")
        export(clones[contract["consumer"]], target_commit(clones[contract["consumer"]], consumer), tree)
        done = subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", TOOLS + ":/tools:ro", "-v", holder + ":/out", "-v", tree + ":/repo:ro",
                               consumer["image"], "bash", "-lc", "node /tools/mined_graphql_agreement.cjs /out/target.graphql /repo /out/found.json "
                               "--base /out/base.graphql --copies {}".format(",".join(contract["copies"]))], capture_output=True, text=True, timeout=600)
        with open(os.path.join(holder, "found.json")) as f:
            found = json.load(f)
        with open(_usage_file(company, contract), "w") as f:
            json.dump({"used_new": found["used_new"]}, f, indent=1)
        print("{} -> {}: the real {} selects {} fields the API gained; its schema copies state {:.1%} of what the API gained; {} of {} operations valid".format(
            contract["provider"], contract["consumer"], contract["consumer"], len(found["used_new"]), found["copies_current"], found["valid"], found["operations"]))
        print(done.stdout.strip()[-300:])
        shutil.rmtree(holder, ignore_errors=True)


def ha_answers(image, tree, asks, out_dir, name):
    """Home Assistant from `tree`, started on a configuration of its own (tools/ha_seed.py) and asked `asks` over its
    WebSocket API once it runs: <out_dir>/<name>.json. Home Assistant needs its translations generated in the tree to
    start (onboarding names the default areas with them), as its tests do. Also the commands the tree registers, read from its source
    (tools/mined_ws_contract.py): <out_dir>/<name>-commands.json."""
    command = ("python3 -m script.translations develop --all > /out/{n}-translations.log 2>&1 && python3 /tools/ha_seed.py config /tmp/cfg && (python3 -m homeassistant -c /tmp/cfg --skip-pip > /out/{n}-hass.log 2>&1 &) "
               "&& python3 /tools/ha_seed.py onboard http://127.0.0.1:8123 /tmp/token && python3 /tools/ha_seed.py ask http://127.0.0.1:8123 /tmp/token /out/{n}.json {asks} "
               "&& python3 /tools/mined_ws_contract.py /repo /out/{n}-commands.json").format(n=name, asks=" ".join(shlex.quote(json.dumps(a)) for a in asks))
    done = subprocess.run(["docker", "run", "--rm", "--network", "none", "-m", "4g", "-v", TOOLS + ":/tools:ro", "-v", os.path.abspath(out_dir) + ":/out",
                           "-v", tree + ":/repo", "-w", "/repo", image, "bash", "-lc", command], capture_output=True, text=True, timeout=900)
    if done.returncode != 0:
        raise RuntimeError("Home Assistant from {} did not answer: {}".format(tree, (done.stdout + done.stderr)[-800:]))
    with open(os.path.join(out_dir, name + ".json")) as f:
        return json.load(f)


def _lexicon_usage(company, contract, repos, clones):
    """For a lexicon contract, read from the sources (tools/mined_lexicon_contract.py), nothing started: the
    lexicons the provider's feature adds and changes; the methods the AppView serves at the start and gains; what the
    real consumer at its target calls of what was gained; and which of the methods the real consumer calls the AppView
    never serves (the PDS's, the video service's: left out of the check, which is of the AppView)."""
    import mined_lexicon_contract as lc
    provider, consumer = repos[contract["provider"]], repos[contract["consumer"]]
    holder = tempfile.mkdtemp(prefix="mined-usage-")
    sides = {}
    for name, clone, repo, commit in (("provider-base", clones[contract["provider"]], provider, base_commit(clones[contract["provider"]], provider)),
                                      ("provider-target", clones[contract["provider"]], provider, target_commit(clones[contract["provider"]], provider)),
                                      ("consumer-target", clones[contract["consumer"]], consumer, target_commit(clones[contract["consumer"]], consumer))):
        tree = os.path.join(holder, name)
        export(clone, commit, tree)
        sides[name] = (lc.provider if name.startswith("provider") else lc.consumer)(tree)
    added, changed = feature_lexicons(contract, repos, clones)
    gained = sorted(set(sides["provider-target"]["served"]) - set(sides["provider-base"]["served"]))
    calls = sides["consumer-target"]["calls"]
    elsewhere = sorted(n for n in calls if n not in sides["provider-target"]["served"])
    used_new = sorted(n for n in gained if n in calls)
    copies = {n: sides["consumer-target"]["schemas"].get(n) == sides["provider-target"]["schemas"].get(n) for n in added + changed
              if n in sides["consumer-target"]["schemas"]}
    if not used_new:
        raise SystemExit("the real {} calls nothing of what {} gained ({}): there is nothing for it to fit".format(contract["consumer"], contract["provider"], gained))
    if not all(copies.values()):
        raise SystemExit("the real {}'s copies of the feature's lexicons differ from {}'s: {}".format(contract["consumer"], contract["provider"], copies))
    with open(_usage_file(company, contract), "w") as f:
        json.dump({"used_new": used_new, "gained": gained, "served_at_start": sides["provider-base"]["served"], "ignore": elsewhere,
                   "lexicons": {"added": added, "changed": changed, "vendored": sorted(copies)}}, f, indent=1)
    print("{} -> {}: the AppView gained {}; the real {} calls {} of them; it calls {} methods the AppView never serves (left out: {}); "
          "feature lexicons added {}, changed {}; the real copies state them: {}".format(contract["provider"], contract["consumer"], gained, contract["consumer"],
          used_new, len(elsewhere), ", ".join(elsewhere), added, changed, sorted(copies)))
    shutil.rmtree(holder, ignore_errors=True)


def _websocket_usage(company, contract, repos, clones):
    """What the real frontend at the feature's commit uses of what core's answers gained, which of the commands it
    sends core does not register in a way that can be read (left out of the check), and core's answers before the
    feature (what was gained is read against them)."""
    provider, consumer = repos[contract["provider"]], repos[contract["consumer"]]
    holder = tempfile.mkdtemp(prefix="mined-usage-")
    answers = {}
    for name, commit in (("base", provider["base"]), ("target", target_commit(clones[contract["provider"]], provider))):
        tree = os.path.join(holder, "core-" + name)
        export(clones[contract["provider"]], commit, tree)
        answers[name] = ha_answers(provider["image"], tree, contract["ask"], holder, name)
    tree = os.path.join(holder, "frontend")
    export(clones[contract["consumer"]], target_commit(clones[contract["consumer"]], consumer), tree)
    for link, to in consumer.get("links", {}).items():
        os.symlink(to, os.path.join(tree, link))
    done = subprocess.run(["docker", "run", "--rm", "--network", "none", "-m", "6g", "-v", TOOLS + ":/tools:ro", "-v", holder + ":/out", "-v", tree + ":/repo:ro",
                           consumer["image"], "bash", "-lc", "node /tools/mined_ws_agreement.cjs /repo /out/target-commands.json /out/target.json /out/found.json "
                           "--base-answers /out/base.json"], capture_output=True, text=True, timeout=900)
    with open(os.path.join(holder, "found.json")) as f:
        found = json.load(f)
    if not found["gained"]:
        raise SystemExit("{}'s answers to {} are the same before and after the feature: there is nothing for the frontend to fit".format(
            contract["provider"], [a["type"] for a in contract["ask"]]))
    with open(_usage_file(company, contract), "w") as f:
        json.dump({"used_new": found["used_new"], "ignore": sorted(found["invalid"]), "base_answers": answers["base"], "asks": contract["ask"]}, f, indent=1)
    print("{} -> {}: core's answers gained {}; the real {} declares {}; it sends {} command types core does not register readably (left out); "
          "{} of {} command places valid; payload fit {:.3f}".format(contract["provider"], contract["consumer"], found["gained"], contract["consumer"],
                                                                     found["used_new"], len(found["invalid"]), found["valid"], found["operations"], found["payload_share"]))
    print(done.stdout.strip()[-300:])
    shutil.rmtree(holder, ignore_errors=True)


def agreement(company, contract, repos, clones, workspace, out_dir):
    """Do the two sides fit? The API is built from the provider's work: it must migrate a fresh database, print its
    schema and answer a request. Then, against the schema it really has: every operation the consumer sends must be
    valid (`valid`), the consumer must select what the real consumer selects of what the API gained (`uses_new_api`),
    and its copies of the schema must state what the API gained (`copies_current`). The three multiply, so a
    consumer that never calls the feature, or whose copies were left as they were, does not agree."""
    if contract_type(contract) != "graphql":
        raise SystemExit("this scorer checks GraphQL contracts only; a {} contract is checked by the Harbor export's (tools/harbor_company_score.py)".format(contract_type(contract)))
    os.makedirs(out_dir, exist_ok=True)
    provider, consumer = repos[contract["provider"]], repos[contract["consumer"]]
    built = os.path.join(out_dir, "built_schema.graphql")
    for stale in (built, os.path.join(out_dir, "agreement.json")):
        if os.path.isfile(stale):
            os.remove(stale)
    _schema_at(clones[contract["provider"]], provider["base"], contract, os.path.join(out_dir, "base_schema.graphql"))
    shutil.copy(_usage_file(company, contract), os.path.join(out_dir, "reference_usage.json"))
    copy = _copy(os.path.join(workspace, "services", contract["provider"]))
    serve = ("({migrate}) > /out/migrate.log 2>&1; echo migrate $?; ({schema}) > /out/built_schema.graphql 2> /out/schema.log; echo schema $?; "
             "(nohup {serve} > /out/server.log 2>&1 &); code=000; for i in $(seq 1 40); do code=$(curl -s -m 5 -o /dev/null -w '%{{http_code}}' "
             "-X POST -H 'Content-Type: application/json' -d '{{\"query\":\"{{ __typename }}\"}}' {url}); [ \"$code\" = 200 ] && break; sleep 3; done; echo serves $code"
             ).format(migrate=contract["migrate"], schema=contract["print_schema"], serve=contract["serve"], url=contract["url"])
    ran_ = subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", copy + ":/repo", "-v", os.path.abspath(out_dir) + ":/out", "-w", "/repo",
                           provider["image"], "bash", "-lc", serve], capture_output=True, text=True, timeout=1800)
    shutil.rmtree(os.path.dirname(copy), ignore_errors=True)
    said = dict(line.split(" ", 1) for line in ran_.stdout.splitlines() if " " in line)
    result = {"api_migrates": said.get("migrate") == "0", "api_prints_schema": said.get("schema") == "0" and os.path.getsize(built) > 0,
              "api_serves": said.get("serves") == "200", "operations": 0, "valid": 0, "invalid": {}, "uses_new_api": 0.0, "copies_current": 0.0}
    if result["api_prints_schema"]:
        subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", TOOLS + ":/tools:ro", "-v", os.path.abspath(out_dir) + ":/out",
                        "-v", os.path.join(os.path.abspath(workspace), "services", contract["consumer"]) + ":/repo:ro", consumer["image"],
                        "bash", "-lc", "node /tools/mined_graphql_agreement.cjs /out/built_schema.graphql /repo /out/agreement.json --base /out/base_schema.graphql "
                        "--reference /out/reference_usage.json --copies {} > /out/agreement.log 2>&1".format(",".join(contract["copies"]))],
                       capture_output=True, text=True, timeout=600)
        if os.path.isfile(os.path.join(out_dir, "agreement.json")):
            with open(os.path.join(out_dir, "agreement.json")) as f:
                found = json.load(f)
            result.update(operations=found["operations"], valid=found["valid"], invalid=found["invalid"], uses_new_api=round(found["uses_new_api"], 4),
                          new_api_not_used=found["new_api_not_used"], copies_current=round(found["copies_current"], 4), copies=found["copies"])
    works = result["api_migrates"] and result["api_serves"] and result["operations"] > 0
    result["valid_share"] = round(result["valid"] / result["operations"], 4) if result["operations"] else 0.0
    result["agreement"] = round(result["valid_share"] * result["uses_new_api"] * result["copies_current"], 4) if works else 0.0
    return result


def score(company, clones, workspace, out_dir):
    info, repos = load_company(company)
    result = {"repositories": {}, "contracts": []}
    for owner, repo in repos.items():       # one after another: side by side the suites starve each other and tests time out
        result["repositories"][owner] = score_repo(owner, info["owners"][owner]["task"], repo, clones[owner],
                                                   os.path.join(workspace, "services", owner), os.path.join(out_dir, owner))
    for contract in info.get("contracts", []):
        found = agreement(company, contract, repos, clones, workspace, os.path.join(out_dir, "agreement-{}-{}".format(contract["provider"], contract["consumer"])))
        result["contracts"].append(dict(found, provider=contract["provider"], consumer=contract["consumer"]))
    parts = list(result["repositories"].values())
    result["progress"] = round(sum(p["progress"] for p in parts) / len(parts), 4)
    result["regression"] = 1.0
    for p in parts:
        result["regression"] = round(result["regression"] * p["regression"], 4)
    result["agreement"] = 1.0
    for c in result["contracts"]:
        result["agreement"] = round(result["agreement"] * c["agreement"], 4)
    result["reward"] = round(result["progress"] * result["regression"] * result["agreement"], 4)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "result.json"), "w") as f:
        json.dump(result, f, indent=2)
    return result


def statement(info, repos) -> str:
    """What is to be built, as everyone is told it whatever the condition and whatever they may read or push. A
    company with a `description` states the feature once, by what it does: no repository's part of it is marked out,
    and no file, name or design is given (those, where hidden tests need them, are in each repository's
    INTERFACE.md). Without one, each repository's own brief is given under its name."""
    if info.get("description"):
        return "\n## The feature\n\n{}\n".format(info["description"])
    return "".join("\n## `{}`\n\n{}\n".format(owner, repo.get("what", repo["brief"])) for owner, repo in repos.items())


def spec_of(company):
    """The company as the kernel's episode takes it. Everyone the episode starts with is given the same statement
    of the work, whatever the condition: the feature and how it is judged."""
    info, repos = load_company(company)
    whole = info["feature"] + "\n" + statement(info, repos) + "\n" + info["done"]
    return {"id": info["id"], "briefs": {owner: whole for owner in repos}, "solo_brief": whole, "lead_brief": whole, "overview": info["overview"]}


def curve(company, clones, server, checkpoints, run_dir):
    """Scores `main` as it was at each checkpoint: what the work was worth against what it had cost by then.
    Checkpoints at which `main` had not moved share one scoring."""
    scored, points = {}, []
    for n, point in enumerate(checkpoints):
        key = tuple(sorted(point["heads"].items()))
        if key not in scored:
            tree = os.path.join(run_dir, "main", "at-{:02d}".format(n))
            shutil.rmtree(tree, ignore_errors=True)
            for repository, commit in point["heads"].items():
                server.export(repository, os.path.join(tree, "services", repository), commit)
            scored[key] = (score(company, clones, tree, os.path.join(run_dir, "score", "at-{:02d}".format(n))), n)
        found, first = scored[key]
        points.append({"dollars": point["dollars"], "end": point["end"], "team_seconds": point["team_seconds"], "heads": point["heads"],
                       "scored_as": first, "reward": found["reward"], "progress": found["progress"], "regression": found["regression"],
                       "agreement": found["agreement"], "new_passed": {o: r["new_passed"] for o, r in found["repositories"].items()}})
        print("  ${:>6.2f}{}  reward {:.4f}  {}".format(point["dollars"], " (end)" if point["end"] else "      ", found["reward"], points[-1]["new_passed"]), flush=True)
    return points, scored[tuple(sorted(checkpoints[-1]["heads"].items()))][0]


def run(company, clones, args):
    from kernel import atif
    from kernel.containers import Containers
    from kernel.episode import run_episode
    from kernel.gitserver import GitServer, grants
    from kernel.model import AnthropicModel, OpenAIFormatModel, ScriptedModel
    info, repos = load_company(company)
    run_id = args.run_id or "{}-{}-{}-{}".format(company, args.condition, args.oracle or args.model, time.strftime("%Y%m%d-%H%M%S"))
    run_dir = os.path.join(REPO, "runs", run_id)
    workspace = os.path.join(run_dir, "ws")
    prepare(company, clones, workspace, args.oracle)
    if args.oracle:
        done = [("submit", {"summary": "the {} commits, untouched".format(args.oracle)})]
        model = ScriptedModel({name: [done] for name in list(repos) + ["solo", "lead"]})
    else:
        model = OpenAIFormatModel(args.model, args.effort) if args.api == "openai" else AnthropicModel(args.model, args.effort)
    containers = Containers(run_id, images={owner: repo["image"] for owner, repo in repos.items()}, env=info.get("env", {}), network=True)
    # Who may read and push what is the environment's, not the condition's: one rule (`--others`) for every condition.
    # A condition only decides who there is: one agent that holds everything, or one owner per repository.
    holders = {owner: [owner] for owner in repos} if args.condition.startswith("team") else {"lead" if args.condition == "lead" else "solo": list(repos)}
    server = GitServer(run_id, containers.network, repos[next(iter(repos))]["image"])
    try:
        server.start({owner: os.path.join(workspace, "services", owner) for owner in repos}, grants(args.condition, holders, args.others))
        summary = run_episode(spec_of(company), args.condition, model, workspace, os.path.join(run_dir, "events.jsonl"), args.budget, args.max_calls,
                              os.path.join(tempfile.gettempdir(), "mined-build", run_id), containers, git=server,
                              compact_at_tokens=args.compact_at or None, checkpoint_dollars=args.checkpoint or None)
        with open(os.path.join(run_dir, "git.jsonl"), "w") as f:
            f.writelines(json.dumps(e) + "\n" for e in server.log())
        result = dict(summary, run_id=run_id, others=args.others, trajectories=[os.path.relpath(p, run_dir) for p in atif.write(run_dir)])
        with open(os.path.join(run_dir, "result.json"), "w") as f:      # kept before scoring, which takes long
            json.dump(result, f, indent=2)
        if summary["valid"]:
            result["curve"], result["hidden"] = curve(company, clones, server, summary["checkpoints"], run_dir)
            result["reward"] = result["hidden"]["reward"]
    finally:
        containers.stop()
        server.stop()
        containers.stop()        # again: the network can go only once the server has
    pushes = [e for e in server_log(run_dir) if e.get("action") == "push"]
    result["git"] = {"pushes": sum(e["allowed"] for e in pushes), "refused_pushes": sum(not e["allowed"] for e in pushes),
                     "moves_of_main": sum(e.get("action") == "moved" and e.get("ref") == "refs/heads/main" for e in server_log(run_dir))}
    with open(os.path.join(run_dir, "result.json"), "w") as f:
        json.dump(result, f, indent=2)
    hidden = result.get("hidden", {})
    print(json.dumps({"run_id": run_id, "end": result["end"], "error": result["error"], "dollars_used": result["dollars_used"],
                      "model_calls": result["model_calls"], "team_seconds": result["team_seconds"], "agent_seconds": result["agent_seconds"],
                      "messages": result["messages_sent"], "compactions": result["compactions"], "git": result["git"],
                      "reward": result.get("reward"), "progress": hidden.get("progress"), "regression": hidden.get("regression"),
                      "agreement": hidden.get("agreement"), "repositories": hidden.get("repositories"),
                      "curve": [[p["dollars"], p["reward"]] for p in result.get("curve", [])]}, indent=2))


def server_log(run_dir):
    with open(os.path.join(run_dir, "git.jsonl")) as f:
        return [json.loads(line) for line in f if line.strip()]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=("base", "reference", "interface", "usage", "prepare", "score", "run"))
    ap.add_argument("name")
    ap.add_argument("rest", nargs="*")
    ap.add_argument("--clone", action="append", default=[], help="owner=path to a local clone of that owner's repository")
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--effort", default="high")
    ap.add_argument("--api", choices=("openai", "anthropic"), default=os.environ.get("SEEDCO_API", "openai"))
    ap.add_argument("--condition", choices=("solo", "team", "team_no_messaging", "lead"), default="solo")
    ap.add_argument("--budget", type=float, default=40.0, help="dollars for the whole work, the same whatever the condition")
    ap.add_argument("--checkpoint", type=float, default=5.0, help="record and score `main` every time this many more dollars are spent (0: only the end)")
    ap.add_argument("--compact-at", type=int, default=0, help="parked: an agent's conversation is replaced by its summary at this many tokens (0: never, the default)")
    ap.add_argument("--others", choices=("read", "none"), default="read", help="what anyone may do with a repository they cannot push to")
    ap.add_argument("--max-calls", type=int, default=1500)
    ap.add_argument("--oracle", choices=("base", "target"), help="score untouched commits instead of running a model")
    ap.add_argument("--run-id")
    a = ap.parse_args()
    clone_of = dict(c.split("=", 1) for c in a.clone)
    if a.command == "base":
        print(base_commit(a.rest[0], load(a.name)[1]))
    elif a.command == "reference":
        reference(a.name, *a.rest)
    elif a.command == "interface":
        interface(a.name, a.rest[0])
    elif a.command == "usage":
        usage(a.name, clone_of)
    elif a.command == "prepare":
        print(prepare(a.name, clone_of, a.rest[0], a.oracle))
    elif a.command == "score":
        print(json.dumps(score(a.name, clone_of, *a.rest), indent=2))
    else:
        run(a.name, clone_of, a)

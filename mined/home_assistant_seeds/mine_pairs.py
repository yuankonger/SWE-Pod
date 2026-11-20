"""Home Assistant seeds: frontend PRs (from search results) that link core PRs, measured from the clones."""
import glob, json, re, subprocess, sys
from collections import defaultdict

REPOS = sys.argv[1]          # .cache/repos
HERE = sys.argv[2]           # folder with the search results


def git(repo, *args):
    return subprocess.run(["git", "-C", f"{REPOS}/{repo}", *args], capture_output=True, text=True).stdout


def by_pr(repo):
    """PR number -> (commit, date, subject), from squash-merge subjects on the default branch."""
    out = {}
    for line in git(repo, "log", "--first-parent", "--format=%H\t%cs\t%s").splitlines():
        h, d, s = line.split("\t", 2)
        m = re.search(r"\(#(\d+)\)\s*$", s)
        if m:
            out.setdefault(int(m.group(1)), (h, d, s))
    return out


def is_test(repo, path):
    if repo == "core":
        return path.startswith("tests/")
    return path.startswith("test/") or re.search(r"\.(test|spec)\.ts$", path) is not None


def measure(repo, commit):
    src = tst = files = 0
    tfiles, areas = 0, set()
    for line in git(repo, "show", "--numstat", "--format=", commit).splitlines():
        a, d, p = line.split("\t", 2)
        if a == "-":
            continue
        n = int(a) + int(d)
        if "/translations/" in p or p.endswith((".json", ".lock", ".snap", ".ambr")) and not p.endswith("strings.json"):
            continue
        files += 1
        if is_test(repo, p):
            tst += n; tfiles += 1
        else:
            src += n
        m = re.match(r"(?:homeassistant|tests)/components/([^/]+)/", p)
        if m:
            areas.add(m.group(1))
        elif repo == "frontend":
            m = re.match(r"src/(?:data|panels|components|dialogs)/([^/]+)", p)
            if m:
                areas.add(m.group(1).replace(".ts", ""))
    return {"src": src, "test": tst, "test_files": tfiles, "files": files, "areas": sorted(areas)}


WS = re.compile(r"""["'](?:type)["']\s*\)?\s*:\s*["']([a-z0-9_]+/[a-z0-9_/]+)["']|vol\.Required\(\s*["']type["']\s*\)\s*:\s*["']([a-z0-9_/]+)["']""")
FE_WS = re.compile(r"""type:\s*["']([a-z0-9_]+/[a-z0-9_/]+)["']""")


def ws_types(repo, commit, pattern):
    """WebSocket command types added in this commit's diff."""
    added = set()
    for line in git(repo, "show", "--format=", "-U0", commit).splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            for m in pattern.finditer(line):
                added.add(next(g for g in m.groups() if g))
    return sorted(added)


items = {}
for f in glob.glob(f"{HERE}/f[es]_*.json"):
    for it in json.load(open(f)).get("items", []):
        items[it["number"]] = it
fe, core = by_pr("frontend"), by_pr("core")
rows = []
for n, it in sorted(items.items()):
    body = it.get("body") or ""
    linked = sorted({int(x) for x in re.findall(r"home-assistant/core(?:/pull/|#)(\d+)", body)})
    if n not in fe or not linked:
        continue
    fh, fd, fs = fe[n]
    f = measure("frontend", fh)
    f["ws_calls"] = ws_types("frontend", fh, FE_WS)
    cs = []
    for c in linked:
        if c in core:
            ch, cd, csub = core[c]
            m = measure("core", ch)
            m.update(pr=c, date=cd, title=csub, ws_added=ws_types("core", ch, WS))
            cs.append(m)
        else:
            cs.append({"pr": c, "missing": True})
    rows.append({"frontend": dict(f, pr=n, date=fd, title=fs, user=it["user"]["login"]), "core": cs})
json.dump(rows, open(f"{HERE}/pairs.json", "w"), indent=1)
print(len(items), "search hits;", len(rows), "with a frontend commit and a core link")

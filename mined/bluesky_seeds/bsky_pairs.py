"""Pair social-app commits that change vendored lexicons with atproto commits that changed the same lexicon files."""
import re, subprocess, sys, json
R = sys.argv[1]
def git(repo, *a): return subprocess.run(["git", "-C", f"{R}/{repo}", *a], capture_output=True, text=True).stdout
def is_test(p): return bool(re.search(r"(^|/)(__tests__|tests?)/|\.(test|spec)\.tsx?$", p))
def skip(p): return p.endswith((".lock", ".snap", ".po", "lock.yaml")) or "/locale/" in p or p.startswith("lexicons/") or p == "lexicons.json"
def measure(repo, c):
    src = tst = tf = lex = 0; files = 0; pk = set()
    for line in git(repo, "show", "--numstat", "--format=", c).splitlines():
        a, d, p = line.split("\t", 2)
        if a == "-": continue
        n = int(a) + int(d)
        if p.startswith("lexicons/") or (repo=="atproto" and "/lexicons/" in p): lex += n; continue
        if repo == "atproto" and re.match(r"packages/(api|lex/lex-cli)?.*/src/client/|packages/.*/src/lexicon/", p): continue  # generated
        if skip(p) or p.endswith(".md") and "CHANGELOG" in p or p.startswith(".changeset/"): continue
        files += 1
        m = re.match(r"packages/([^/]+(?:/[^/]+)?)/", p)
        if repo == "atproto" and m: pk.add(m.group(1))
        if is_test(p): tst += n; tf += 1
        else: src += n
    return dict(src=src, test=tst, test_files=tf, lex=lex, files=files, pkgs=sorted(pk))
def lexfiles(repo, c):
    return [p for p in git(repo, "show", "--name-only", "--format=", c).splitlines() if p.startswith("lexicons/") and p.endswith(".json")]
at = {}
for line in git("atproto", "log", "--first-parent", "--since=2026-06-01", "--format=%H\t%cs\t%s", "--", "lexicons/").splitlines():
    h, d, s = line.split("\t", 2)
    for f in lexfiles("atproto", h): at.setdefault(f, []).append((h, d, s))
out = []
for line in git("social-app", "log", "--first-parent", "--since=2026-08-13", "--format=%H\t%cs\t%s", "--", "lexicons/").splitlines():
    h, d, s = line.split("\t", 2)
    lf = lexfiles("social-app", h)
    linked = {}
    for f in lf:
        for (ah, ad, asub) in at.get(f, []):
            if ad <= d: linked[ah] = (ad, asub)
    # keep the most recent atproto commits per file only (within 45 days)
    from datetime import date
    dd = date.fromisoformat(d)
    linked = {k: v for k, v in linked.items() if (dd - date.fromisoformat(v[0])).days <= 45}
    out.append(dict(sa=h[:9], date=d, subject=s, nsids=[f[9:-5].replace("/", ".") for f in lf], sa_size=measure("social-app", h),
                    atproto=[dict(c=k[:9], date=v[0], subject=v[1], size=measure("atproto", k)) for k, v in sorted(linked.items(), key=lambda x: x[1][0])]))
json.dump(out, sys.stdout, indent=1)

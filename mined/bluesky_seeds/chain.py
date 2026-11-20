import re, subprocess, sys
R=sys.argv[1]
def git(repo,*a): return subprocess.run(["git","-C",f"{R}/{repo}",*a],capture_output=True,text=True).stdout
def chain(repo, prs):
    log={}
    for l in git(repo,"log","--first-parent","--since=2026-08-01","--format=%H\t%cs\t%s").splitlines():
        h,d,s=l.split("\t",2); m=re.search(r"\(#(\d+)\)\s*$",s)
        if m: log[int(m.group(1))]=(h,d)
    t=dict(src=0,test=0,tf=set(),lex=0,files=set(),mig=0,nsid=set(),gen=0)
    for p in prs:
        h,d=log[p]
        for line in git(repo,"show","--numstat","--format=",h).splitlines():
            a,dl,f=line.split("\t",2)
            if a=="-": continue
            n=int(a)+int(dl)
            if f.startswith("lexicons/") or "/lexicons/" in f:
                t["lex"]+=n; t["nsid"].add(f.split("lexicons/")[-1][:-5].replace("/",".")); continue
            if re.search(r"/src/lexicons?/|/src/client/|lexicons\.json$|\.snap$|lock|\.po$|CHANGELOG|^\.changeset/|/locale/",f): t["gen"]+=n; continue
            t["files"].add(f)
            if "/migrate/" in f or "migrations/" in f: t["mig"]+=1
            if re.search(r"(^|/)(__tests__|tests?)/|\.(test|spec)\.tsx?$",f): t["test"]+=n; t["tf"].add(f)
            else: t["src"]+=n
    print(f"{repo} {prs}: src {t['src']} test {t['test']} ({len(t['tf'])} files) files {len(t['files'])} migrations {t['mig']} lexicon lines {t['lex']} skipped-gen {t['gen']}")
    print("   nsids:", sorted(t["nsid"])[:14])
chain("atproto",[5568,5577,5633,5656]); chain("social-app",[11933,11952,12012])
chain("atproto",[5603,5617,5636,5674,5679]) if True else None
chain("social-app",[12188,12110])

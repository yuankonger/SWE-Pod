"""Recall probe for the MCP Skills seed (SEP-2640): does a model, asked cold, already know the design the task holds back?

    python3 -I mined/mcp_seeds/recall_probe.py [--model claude-sonnet-5-5] [--n 5] [--dry-run]

The model is reached as the Harbor runs reach it: the local gateway named by OPENAI_BASE_URL and OPENAI_API_KEY in
seedco/.env (or the environment), in Anthropic format (tools/harbor_harness.sh sets ANTHROPIC_BASE_URL to the same).
No tools, no brief, no web: one user message per call.

Three kinds of prompt:
  recall   names SEP-2640 and asks for its wire protocol.
  design   asks for the same extension to be designed, without naming the SEP. What a model writes here is what it can
           guess; a marker that appears under recall and not under design is evidence of recall.
  paths    names one SDK repository and asks where the Skills extension lives in it, and its PR number (the file-path
           probe of "The SWE-Bench Illusion" and BC-Bench, adapted to one side of a cross-repo task).

Markers are read from the answer text with regular expressions. `final` markers are details of the released design
(ext-skills specification/beta/skills.mdx) that are hard to guess; `draft` markers are the June 2026 draft's design,
which a model that saw the draft would reach for. Paths and PR numbers are the merged implementations'.

No refusal fallback is requested: an answer from another model would not measure this one. Refusals are recorded.
Results: mined/mcp_seeds/recall/<model>-<date>.jsonl (every answer) and .md (the table).
"""
import argparse
import concurrent.futures
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

DONT_KNOW = " If you do not know, say so rather than guess."

PROMPTS = {
    "recall": ("Model Context Protocol SEP-2640 defines the Skills extension (`io.modelcontextprotocol/skills`). "
               "Describe its wire protocol in detail: the JSON-RPC methods and their parameters and results, the "
               "resource URIs, every field of a skill entry, how a server declares support and which optional "
               "settings it has, and any limits it fixes." + DONT_KNOW),
    "design": ("Design an extension to the Model Context Protocol, identified as `io.modelcontextprotocol/skills`, "
               "that lets a server offer Agent Skills (folders with a SKILL.md and supporting files) to clients. "
               "Specify its wire protocol in detail: the JSON-RPC methods and their parameters and results, the "
               "resource URIs, every field of a skill entry, how a server declares support and which optional "
               "settings it has, and any limits it fixes."),
}
SDKS = {
    "typescript-sdk": {"paths": [r"packages/(server|client|core)/src/ext/skills"], "pr": ["3047", "3065"]},
    "python-sdk": {"paths": [r"src/mcp/client/extensions/skills\.py", r"src/mcp/(server|shared)/skills\.py"],
                   "pr": ["3485"]},
    "csharp-sdk": {"paths": [r"ModelContextProtocol\.Extensions\.Skills"], "pr": ["1856", "1993"]},
    "rust-sdk": {"paths": [r"crates/rmcp/src/model/skill\.rs"], "pr": ["1392"]},
}
for sdk in SDKS:
    PROMPTS["paths:" + sdk] = (
        "In the GitHub repository modelcontextprotocol/{} the Skills extension (SEP-2640) was implemented in "
        "October 2026. Which files and directories hold the implementation? Give exact paths, and the number of "
        "the pull request that added it.{}".format(sdk, DONT_KNOW))

FINAL = {   # the released design; each is hard to reach by guessing
    "skills/list": r"skills/list",
    "skills/get": r"skills/get",
    "resources/directory/read": r"resources/directory/read",
    "directoryRead": r"\bdirectoryRead\b",
    "resources: \"dynamic\"": r"[\"']dynamic[\"']",
    "digest sha256:{hex}": r"sha256:",
    # the number alone also matches path and string lengths, so it must sit by what it counts
    "512 resources per skill": r"\b512\s*(entries|resources|files)|(resources|entries|files)\b[^\n.]{0,40}\b512\b",
    "16 MiB per skill": r"16\s*MiB|16,777,216|16777216",
    "declared via server/discover": r"server/discover",
}
DRAFT = {"skill://index.json": r"index\.json"}
# In the June draft and the release alike (checked against ext-skills fff35ee): a sign of having seen either.
DRAFT["meta prefix io.modelcontextprotocol.skills/ (both)"] = r"io\.modelcontextprotocol\.skills/"


def credentials():
    env = {}
    path = os.path.join(REPO, ".env")
    if os.path.exists(path):
        for line in open(path):
            m = re.match(r"\s*(?:export\s+)?([A-Z_]+)\s*=\s*(.*?)\s*$", line)
            if m:
                env[m.group(1)] = m.group(2).strip("'\"")
    base = os.environ.get("OPENAI_BASE_URL") or env.get("OPENAI_BASE_URL")
    key = os.environ.get("OPENAI_API_KEY") or env.get("OPENAI_API_KEY")
    if not base or not key:
        sys.exit("no gateway: set OPENAI_BASE_URL and OPENAI_API_KEY in seedco/.env, as tools/harbor_harness.sh reads them")
    base = base.rstrip("/")
    return (base if base.endswith("/v1") else base + "/v1") + "/messages", key


def ask(url, key, model, prompt):
    body = json.dumps({"model": model, "max_tokens": 16000,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "content-type": "application/json", "anthropic-version": "2023-06-01",
        "x-api-key": key, "authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            out = json.load(r)
    except urllib.error.HTTPError as e:
        return {"error": "HTTP {}: {}".format(e.code, e.read()[:500].decode("utf-8", "replace"))}
    except Exception as e:                      # noqa: BLE001 - a failed call is recorded, not fatal
        return {"error": repr(e)}
    text = "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text")
    return {"text": text, "stop_reason": out.get("stop_reason"), "model": out.get("model"),
            "usage": out.get("usage"), "stop_details": out.get("stop_details")}


def score(kind, text):
    hits = {name: bool(re.search(rx, text, re.I)) for name, rx in {**FINAL, **DRAFT}.items()} if not kind.startswith("paths:") else {}
    if kind.startswith("paths:"):
        sdk = SDKS[kind.split(":", 1)[1]]
        hits["exact path"] = any(re.search(rx, text) for rx in sdk["paths"])
        hits["PR number"] = any(re.search(r"#\s*{}\b|pull/{}\b".format(n, n), text) for n in sdk["pr"])
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-sonnet-5-5")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rescore", metavar="JSONL", help="score a run's saved answers again; no calls are made")
    a = ap.parse_args()
    if a.rescore:
        rows = [json.loads(line) for line in open(a.rescore)]
        for r in rows:
            r["hits"] = score(r["kind"], r.get("text", "")) if "text" in r else {}
        with open(a.rescore, "w") as log:
            log.writelines(json.dumps(r) + "\n" for r in rows)
        stem = a.rescore[:-len(".jsonl")]
        date = "-".join(os.path.basename(stem).split("-")[-3:])      # <model>-YYYY-MM-DD
        write_summary(stem + ".md", a.model, date, rows)
        print(open(stem + ".md").read())
        return
    jobs = [(kind, i) for kind in PROMPTS for i in range(a.n)]
    if a.dry_run:
        for kind, p in PROMPTS.items():
            print("[{}] {}\n".format(kind, p))
        print("{} calls to {}".format(len(jobs), a.model))
        return
    url, key = credentials()
    stamp = datetime.date.today().isoformat()
    out_dir = os.path.join(HERE, "recall")
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.join(out_dir, "{}-{}".format(a.model, stamp))
    rows = []
    with concurrent.futures.ThreadPoolExecutor(a.workers) as pool, open(stem + ".jsonl", "w") as log:
        futures = {pool.submit(ask, url, key, a.model, PROMPTS[k]): (k, i) for k, i in jobs}
        for f in concurrent.futures.as_completed(futures):
            kind, i = futures[f]
            r = f.result()
            r.update(kind=kind, sample=i, hits=score(kind, r.get("text", "")) if "text" in r else {})
            rows.append(r)
            log.write(json.dumps(r) + "\n")
            log.flush()
            print("{:<24} #{} {}".format(kind, i, r.get("error") or r.get("stop_reason")), flush=True)
    write_summary(stem + ".md", a.model, stamp, rows)
    print(open(stem + ".md").read())


def write_summary(path, model, stamp, rows):
    ok = lambda k: [r for r in rows if r["kind"] == k and "text" in r and r.get("stop_reason") != "refusal"]  # noqa: E731
    lines = ["# Recall probe: {} ({})".format(model, stamp), "",
             "Share of answers that state each marker. `final` = the released design, `draft` = the June 2026 draft.", "",
             "| Marker | Kind | recall | design |", "|---|---|---|---|"]
    for name in list(FINAL) + list(DRAFT):
        cells = []
        for k in ("recall", "design"):
            got = ok(k)
            cells.append("{}/{}".format(sum(r["hits"][name] for r in got), len(got)))
        label = "final" if name in FINAL else ("both" if "(both)" in name else "draft")
        lines.append("| `{}` | {} | {} | {} |".format(name, label, *cells))
    lines += ["", "| SDK | exact path | PR number |", "|---|---|---|"]
    for sdk in SDKS:
        got = ok("paths:" + sdk)
        lines.append("| {} | {}/{} | {}/{} |".format(sdk, sum(r["hits"]["exact path"] for r in got), len(got),
                                                    sum(r["hits"]["PR number"] for r in got), len(got)))
    bad = [r for r in rows if "error" in r or r.get("stop_reason") in ("refusal", "max_tokens")]
    lines += ["", "Calls not counted (errors, refusals, truncated): {}".format(len(bad))]
    lines += ["- {} #{}: {}".format(r["kind"], r["sample"], r.get("error") or r.get("stop_reason")) for r in bad]
    usage = [r["usage"] for r in rows if r.get("usage")]
    lines += ["", "Tokens: {} in, {} out over {} calls.".format(sum(u.get("input_tokens", 0) for u in usage),
                                                             sum(u.get("output_tokens", 0) for u in usage), len(usage))]
    open(path, "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

"""The lexicon contract between an atproto tree (the provider) and a social-app tree (the consumer), read from their
sources without starting either.

    python3 mined_lexicon_contract.py provider <atproto tree> <out.json>
    python3 mined_lexicon_contract.py consumer <social-app tree> <out.json>
    python3 mined_lexicon_contract.py diff <start.json> <target.json>

provider: {"schemas": {nsid: defs}, "served": [nsid, ...]}. `schemas` is every lexicon document under `lexicons/`;
`served` is every method the AppView registers (`server.add(<nsid>, ...)` under `packages/bsky/src/api/`).

consumer: {"schemas": {nsid: defs}, "manifest": [nsid, ...], "calls": {nsid: [file, ...]}}. `schemas` is the vendored
copy under `lexicons/`; `manifest` is `lexicons.json`'s list; `calls` is every method the app's own code calls
(`.call(<nsid>, ...)`, across line breaks), outside tests, fixtures and the Storybook.

A document is compared by its `defs` alone, with keys sorted: `lex install` adds a top-level `$type` and reformats
the file, so the vendored copy of an unchanged schema is not byte-identical to the provider's.

diff: what changed between two extractions of the same side: nsids added, removed and with changed defs, and (for a
provider) methods newly served, (for a consumer) methods newly called. Check it at the seed's start and target: it
must find the feature's lexicons and nothing else.
"""
import json
import os
import re
import sys

NSID = r"(?:app|chat|com|tools)\.[a-z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9]*){2,3}"
SERVED = re.compile(r"server\.add\(\s*(" + NSID + r")\b")
CALLED = re.compile(r"\.call\(\s*(" + NSID + r")\b")
NOT_APP = re.compile(r"(^|/)(__tests__|__fixtures__|__mocks__|Storybook)(/|$)|\.test\.tsx?$")


def canonical(defs):
    return json.loads(json.dumps(defs, sort_keys=True))


def schemas(root):
    found = {}
    base = os.path.join(root, "lexicons")
    for folder, _, files in os.walk(base):
        for name in files:
            if not name.endswith(".json"):
                continue
            path = os.path.join(folder, name)
            try:
                with open(path) as f:
                    doc = json.load(f)
            except (OSError, ValueError):
                found[os.path.relpath(path, base)] = {"unreadable": True}
                continue
            if isinstance(doc, dict) and isinstance(doc.get("id"), str) and "defs" in doc:
                found[doc["id"]] = canonical(doc["defs"])
    return found


def sources(root, sub, skip=None):
    for folder, dirs, files in os.walk(os.path.join(root, sub)):
        dirs[:] = [d for d in dirs if d not in ("node_modules", "dist")]
        for name in files:
            if name.endswith((".ts", ".tsx")):
                path = os.path.join(folder, name)
                rel = os.path.relpath(path, root)
                if skip and skip.search(rel):
                    continue
                with open(path, errors="replace") as f:
                    yield rel, f.read()


def provider(root):
    served = set()
    for _, text in sources(root, "packages/bsky/src/api"):
        served.update(SERVED.findall(text))
    return {"schemas": schemas(root), "served": sorted(served)}


def consumer(root):
    calls = {}
    for rel, text in sources(root, "src", NOT_APP):
        for nsid in set(CALLED.findall(text)):
            calls.setdefault(nsid, []).append(rel)
    try:
        with open(os.path.join(root, "lexicons.json")) as f:
            manifest = sorted(json.load(f).get("lexicons", []))
    except (OSError, ValueError):
        manifest = []
    return {"schemas": schemas(root), "manifest": manifest, "calls": {k: sorted(v) for k, v in sorted(calls.items())}}


def diff(start, target):
    a, b = start["schemas"], target["schemas"]
    out = {"added": sorted(set(b) - set(a)), "removed": sorted(set(a) - set(b)),
           "changed": sorted(k for k in set(a) & set(b) if a[k] != b[k])}
    if "served" in target:
        out["newly_served"] = sorted(set(target["served"]) - set(start["served"]))
    if "calls" in target:
        out["newly_called"] = sorted(set(target["calls"]) - set(start["calls"]))
    return out


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "diff":
        with open(sys.argv[2]) as f, open(sys.argv[3]) as g:
            print(json.dumps(diff(json.load(f), json.load(g)), indent=1))
    else:
        result = (provider if mode == "provider" else consumer)(sys.argv[2])
        with open(sys.argv[3], "w") as f:
            json.dump(result, f, indent=1, sort_keys=True)
        print("{}: {} schemas, {} {}".format(mode, len(result["schemas"]),
              len(result.get("served", result.get("calls", []))), "served" if mode == "provider" else "called"))

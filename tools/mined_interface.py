"""The names a mined task's hidden tests need that do not exist at the base commit.

A project's tests are tied to its internals: they import classes, functions and files by name. Work that behaves
the same under other names fails those tests without being wrong. So the names the hidden tests reach for, and
that the base does not have, are handed to the agents as part of the task: where each must live and how the
project declared it. Nothing about what they do is handed over.

    python3 tools/mined_interface.py <base tree> <target tree> <language: python|typescript> <test file>...

Prints JSON: {module: {"exists_at_base": bool, "names": {name: declaration at the target},
"changed": {name: declaration at the target, for a name the base has under another declaration}}}, and under
"(looked for)" the test ids and visible text the tests search the page for that the base's source does not hold.
A declaration is the whole signature: every parameter, and for a component the properties it takes.
Trees are plain directories (an exported commit each). Test files are paths relative to the tree.
"""
import ast
import json
import os
import re
import sys

WILD = "*"


# ---- Python -------------------------------------------------------------------------------------------------

def _py_file(root, module):
    base = os.path.join(root, *module.split("."))
    for path in (base + ".py", os.path.join(base, "__init__.py")):
        if os.path.isfile(path):
            return path
    return None


def _py_top(path):
    """{name: declaration} for what a module defines or imports at its top level. `*` if it star-imports."""
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except (SyntaxError, OSError):
        return {WILD: ""}
    found = {}

    def walk(body):
        for node in body:
            if isinstance(node, ast.ClassDef):
                found[node.name] = "class {}({})".format(node.name, ", ".join(ast.unparse(b) for b in node.bases))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found[node.name] = "def {}({})".format(node.name, ast.unparse(node.args))
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                for target in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                    for name in ast.walk(target):
                        if isinstance(name, ast.Name):
                            found[name.id] = "{} = ...".format(name.id)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    if alias.name == "*":
                        found[WILD] = ""
                    else:
                        found[(alias.asname or alias.name).split(".")[0]] = "(imported there)"
            elif isinstance(node, (ast.If, ast.Try, ast.With)):
                for part in ("body", "orelse", "finalbody"):
                    walk(getattr(node, part, []))
                for handler in getattr(node, "handlers", []):
                    walk(handler.body)
    walk(tree.body)
    return found


def _py_declared(root, module, name):
    """How `module.name` is declared in this tree, or None if it is not there. A submodule counts."""
    path = _py_file(root, module)
    if path is None:
        return None
    if _py_file(root, module + "." + name):
        return "(a module)"
    top = _py_top(path)
    if name in top:
        if top[name] == "(imported there)":        # re-exported: say what it is where it is defined
            for node in ast.walk(ast.parse(open(path, encoding="utf-8").read())):
                if isinstance(node, ast.ImportFrom) and any((a.asname or a.name) == name for a in node.names):
                    package = module if path.endswith("__init__.py") else module.rpartition(".")[0]
                    source = ".".join(package.split(".")[:len(package.split(".")) - node.level + 1] + ([node.module] if node.module else [])) if node.level else node.module
                    original = next(a.name for a in node.names if (a.asname or a.name) == name)
                    deeper = _py_declared(root, source, original) if source else None
                    return deeper or top[name]
        return top[name]
    return "(star-imported there)" if WILD in top else None


def _py_wanted(target, test_file):
    """(module, name) pairs a test file takes from the project itself: what it imports, what it patches by a
    dotted name, and what it reaches through a module it imported (`module.name`)."""
    source = open(os.path.join(target, test_file), encoding="utf-8").read()
    package = os.path.dirname(test_file).replace(os.sep, ".")
    wanted, modules = set(), {}

    def dotted(text):
        parts = text.split(".")
        for cut in range(len(parts) - 1, 0, -1):        # the longest prefix that is a module at the target
            if _py_file(target, ".".join(parts[:cut])):
                wanted.add((".".join(parts[:cut]), parts[cut]))
                return

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                module = ".".join(parts[:len(parts) - node.level + 1] + ([node.module] if node.module else []))
            else:
                module = node.module or ""
            for alias in node.names:
                if alias.name != "*":
                    wanted.add((module, alias.name))
                    if _py_file(target, module + "." + alias.name):
                        modules[alias.asname or alias.name] = module + "." + alias.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname and _py_file(target, alias.name):
                    modules[alias.asname] = alias.name
        elif isinstance(node, ast.Call):                    # patch("a.b.c"), mock.patch("a.b" ".c"), patch.object(module, "c")
            called = ast.unparse(node.func)
            first = node.args[0] if node.args else None
            if called.split(".")[-1] == "patch" or called.endswith("patch.dict"):
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    dotted(first.value)
            elif called.endswith("patch.object") and len(node.args) > 1 and isinstance(first, ast.Name) and first.id in modules \
                    and isinstance(node.args[1], ast.Constant):
                wanted.add((modules[first.id], str(node.args[1].value)))
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in modules:
            wanted.add((modules[node.value.id], node.attr))
    return wanted


def python_interface(base, target, test_files, is_test_side):
    out = {}
    for test_file in (f for f in test_files if f.endswith(".py")):     # not the snapshots (.ambr) or fixtures beside them
        for module, name in _py_wanted(target, test_file):
            path = _py_file(target, module)
            if path is None or is_test_side(os.path.relpath(path, target)):
                continue            # not the project's own code, or test code that is laid over anyway
            sub = _py_file(target, module + "." + name)
            if sub and is_test_side(os.path.relpath(sub, target)):
                continue
            before, after = _py_declared(base, module, name), _py_declared(target, module, name)
            if after is None or before == after:
                continue
            entry = out.setdefault(module, {"exists_at_base": _py_file(base, module) is not None, "names": {}, "changed": {}})
            entry["names" if before is None else "changed"][name] = after
    return out


# ---- TypeScript ---------------------------------------------------------------------------------------------

TS_ENDINGS = ("", ".ts", ".tsx", "/index.ts", "/index.tsx")
TS_IMPORT = re.compile(r"""import\s+(?:type\s+)?([^;]*?)\s+from\s+["']([^"']+)["']""", re.S)
TS_MOCK = re.compile(r"""jest\.mock\(\s*["']([^"']+)["']""")


def _ts_file(root, test_file, spec, aliases):
    for prefix, to in aliases.items():
        if spec.startswith(prefix):
            stem = os.path.join(root, to, spec[len(prefix):])
            break
    else:
        if not spec.startswith("."):
            return None, None       # a package
        stem = os.path.normpath(os.path.join(root, os.path.dirname(test_file), spec))
    for ending in TS_ENDINGS:
        if os.path.isfile(stem + ending):
            return os.path.relpath(stem + ending, root), stem
    # ES modules written in TypeScript import a file by the name it is compiled to (`./grouping.js` is grouping.ts)
    compiled = re.match(r"(.*)\.(m|c)?js$", stem)
    if compiled:
        for ending in (".ts", ".tsx", ".mts", ".cts"):
            if os.path.isfile(compiled.group(1) + ending):
                return os.path.relpath(compiled.group(1) + ending, root), compiled.group(1)
    return False, os.path.relpath(stem, root)


TS_DECLARED = re.compile(r"^[ \t]*(export\s+)?(default\s+)?(?:declare\s+)?(?:async\s+)?(const|let|function\*?|class|type|interface|enum)\s+(\w+)", re.M)
MAX_DECLARATION = 1500
PAIRS = {"(": ")", "[": "]", "{": "}"}


def _ts_span(source, at, stop):
    """Reads on from `at`, keeping count of brackets and skipping strings and comments, until `stop(i, depth)` says so.
    Returns the index."""
    depth, i, quote = 0, at, None
    while i < len(source) and i - at < 6000:
        c = source[i]
        if not quote and source.startswith("//", i):      # a comment's apostrophe is no string
            i = source.find("\n", i)
            i = len(source) if i < 0 else i
            continue
        if not quote and source.startswith("/*", i):
            i = source.find("*/", i + 2)
            i = len(source) if i < 0 else i + 2
            continue
        if quote:
            if c == "\\":
                i += 1
            elif c == quote:
                quote = None
        elif c in "\"'`":
            quote = c
        elif c in PAIRS:
            depth += 1
        elif c in ")]}":
            depth -= 1
        if not quote and stop(i, depth):
            return i
        i += 1
    return i


def _ts_declaration(source, m):
    """The whole of a declaration's signature: a function's parameters and return type, an arrow function's up to
    its `=>`, the body of an interface, a type or an enum. A value that is not a function is its first line."""
    kind, start = m.group(3), m.start()
    if kind == "class":
        return _ts_class(source, m)
    if kind.startswith("function"):
        end = _ts_span(source, m.end(), lambda i, depth: depth == 1 and source[i] == "{" and (source[:i].rstrip().endswith((")", ">")) or re.search(r"\)\s*:\s*[^=;]*$", source[m.end():i])))
    elif kind in ("interface", "enum"):
        end = _ts_span(source, m.end(), lambda i, depth: depth == 0 and source[i] == "}") + 1
    elif kind == "type":
        end = _ts_span(source, m.end(), lambda i, depth: depth == 0 and (source[i] == ";" or (source[i] == "\n" and not re.match(r"\s*[|&]", source[i + 1:i + 40])
                                                                                               and not source[:i].rstrip().endswith(("|", "&", "=")))))
    else:
        equals = _ts_span(source, m.end(), lambda i, depth: depth == 0 and source[i] == "=" and source[i + 1] not in "=>" and source[i - 1] not in "=!<>")
        after = re.match(r"\s*(?:async\s+)?(?:<[^>(]*>\s*)?\(", source[equals + 1:equals + 200])
        if after:                                   # an arrow function: to its `=>`
            end = _ts_span(source, equals + 1, lambda i, depth: depth == 0 and source[i:i + 2] == "=>") + 2
        else:
            end = source.find("\n", equals)
            end = len(source) if end < 0 else end
    declared = re.sub(r"/\*.*?\*/|//[^\n]*", "", source[start:end], flags=re.S)      # the project's comments are prose, not the declaration
    text = re.sub(r"\s+", " ", declared).strip().rstrip("{").strip()
    text = text + " ..." if text.endswith("=>") else text
    return text if len(text) <= MAX_DECLARATION else text[:MAX_DECLARATION] + " ..."


def _ts_header_end(source, at):
    """Where a class's body opens: the first `{` outside brackets and outside generic arguments (`<{ a: b }>`)."""
    angle, i = 0, at
    while i < len(source):
        c = source[i]
        if c == "<":
            angle += 1
        elif c == ">" and source[i - 1] != "=":
            angle -= 1
        elif c in "([":
            i = _ts_span(source, i, lambda j, depth: depth == 0)
        elif c == "{":
            if angle == 0:
                return i
            i = _ts_span(source, i, lambda j, depth: depth == 0)
        i += 1
    return i


def _ts_method_body(source, at):
    """Where a method's body opens, after its parameters: the first `{` that is not a type. A `{` right after `:`,
    `|`, `&`, `,` or `<` begins an object type (a return type such as `: { a?: string }`), and is read past."""
    angle, i = 0, at
    while i < len(source):
        c = source[i]
        if c == "<":
            angle += 1
        elif c == ">" and source[i - 1] != "=":
            angle -= 1
        elif c in "([":
            i = _ts_span(source, i, lambda j, depth: depth == 0)
        elif c == "{":
            before = source[:i].rstrip()[-1:]
            if angle == 0 and before not in (":", "|", "&", ",", "<", "("):
                return i
            i = _ts_span(source, i, lambda j, depth: depth == 0)
        elif c == ";" and angle == 0:
            return i
        i += 1
    return i


CLASS_MEMBER = re.compile(r"^[ \t]+(?:(?:public|static|async|readonly|override|get|set)\s+)*(?!private\b|protected\b)([A-Za-z_$][\w$]*)\s*(<[^>(]*>)?\(", re.M)


def _ts_class(source, m):
    """A class: its header whole (generic arguments too), then the signature of every method it declares that is not
    private: the names and types its callers, and the tests, use."""
    open_at = _ts_header_end(source, m.end())
    close_at = _ts_span(source, open_at, lambda i, depth: depth == 0 and source[i] == "}")
    header = re.sub(r"\s+", " ", source[m.start():open_at]).strip()
    body, members, i = source[open_at + 1:close_at], [], 0
    while True:
        found = CLASS_MEMBER.search(body, i)
        if not found:
            break
        if found.group(1) in ("if", "for", "while", "switch", "return", "catch", "function", "await", "new", "typeof"):
            i = found.end()
            continue
        params_end = _ts_span(body, found.end() - 1, lambda j, depth: depth == 0 and body[j] == ")")
        body_open = _ts_method_body(body, params_end + 1)
        members.append(re.sub(r"\s+", " ", body[found.start():body_open]).strip())
        i = (_ts_span(body, body_open, lambda j, depth: depth == 0 and body[j] == "}") + 1) if body[body_open:body_open + 1] == "{" else body_open + 1
    text = header + (" { " + "; ".join(members) + " }" if members else "")
    return text if len(text) <= MAX_DECLARATION else text[:MAX_DECLARATION] + " ..."


def _ts_local(source):
    """{name: match} for everything a file declares at its top level, exported or not."""
    return {m.group(4): m for m in TS_DECLARED.finditer(source)}


def _ts_exports(path, seen=None):
    """{name: declaration} for what a file exports, through any `export * from` it has. A function or component is
    followed by the declarations of the types of the same file that its signature names (its properties)."""
    seen = seen if seen is not None else set()
    if path in seen or not os.path.isfile(path):
        return {}
    seen.add(path)
    found = {}
    source = open(path, encoding="utf-8").read()
    local = _ts_local(source)

    def full(m):
        text = _ts_declaration(source, m)
        if m.group(3) in ("const", "let", "function", "function*"):
            for name in dict.fromkeys(re.findall(r"\b[A-Z]\w+\b", text)):
                other = local.get(name)
                if other is not None and other is not m and other.group(3) in ("interface", "type"):
                    text += " ; " + _ts_declaration(source, other)
        return text if len(text) <= 4 * MAX_DECLARATION else text[:4 * MAX_DECLARATION] + " ..."

    for m in TS_DECLARED.finditer(source):
        if m.group(1):
            found["default" if m.group(2) else m.group(4)] = full(m)
    for m in re.finditer(r"^[ \t]*export\s+default\s+(\w+)\s*;?\s*$", source, re.M):
        found["default"] = full(local[m.group(1)]) if m.group(1) in local else m.group(0).strip()
    for names in re.findall(r"export\s*(?:type\s*)?\{([^}]*)\}", source):
        for part in names.split(","):
            inner, _, outer = part.strip().partition(" as ")
            name = (outer or inner).strip()
            if name:
                found[name] = full(local[inner.strip()]) if inner.strip() in local else "export { " + part.strip() + " }"
    for spec in re.findall(r"""export\s*\*\s*from\s*["']([^"']+)["']""", source):
        if spec.startswith("."):
            stem = os.path.normpath(os.path.join(os.path.dirname(path), spec))
            for ending in TS_ENDINGS:
                if os.path.isfile(stem + ending):
                    for name, line in _ts_exports(stem + ending, seen).items():
                        found.setdefault(name, line)
                    break
        else:
            found[WILD] = ""
    return found


TS_LOOKED_FOR = re.compile(r"""(?:get|query|find)(?:All)?By(TestId|Text|LabelText|PlaceholderText|Title|DisplayValue)\(\s*(["'`])((?:(?!\2).)+)\2""")
TS_ROLE_NAME = re.compile(r"""(?:get|query|find)(?:All)?ByRole\(\s*["'](\w+)["']\s*,\s*\{[^}]*?name:\s*(["'`])((?:(?!\2).)+)\2""")
TS_TEST_ID = re.compile(r"""data-test-id(?:=|\]?=|["']?\s*[:,]\s*)\\?["'`]([\w.-]+)""")


def _tree_text(root, keep):
    parts = []
    for d, dirs, files in os.walk(os.path.join(root, "src")):
        dirs[:] = [x for x in dirs if x != "node_modules"]
        for f in files:
            path = os.path.join(d, f)
            if f.endswith((".ts", ".tsx", ".json")) and keep(os.path.relpath(path, root)):
                try:
                    parts.append(open(path, encoding="utf-8").read())
                except (OSError, UnicodeDecodeError):
                    pass
    return "\n".join(parts)


SHARED = "src/components/"      # the shared component library: what every page renders through it is no news


def typescript_looked_for(base, target, test_files, is_test_side):
    """{directory of the tests: {"test ids": [...], "text": [...]}}: what the tests search the rendered page for
    that the base's source does not hold and that is not data the tests bring themselves."""
    source_at_base = _tree_text(base, lambda p: not is_test_side(p))
    brought = _tree_text(target, lambda p: is_test_side(p) and ".test." not in p)      # fixtures and mocks: laid over with the tests
    out = {}
    for test_file in test_files:
        if ".test." not in test_file:
            continue
        text = open(os.path.join(target, test_file), encoding="utf-8").read()
        ids = {v for kind, _, v in TS_LOOKED_FOR.findall(text) if kind == "TestId"} - set(TS_TEST_ID.findall(text))     # not the ids of the test's own stand-ins
        shown = {v for kind, _, v in TS_LOOKED_FOR.findall(text) if kind != "TestId"} | {"{} named {}".format(role, v) for role, _, v in TS_ROLE_NAME.findall(text)}
        # an id is already there only if the components under test render it today: one that exists on another
        # component (a status pill's id on another card, say) is still news to whoever builds this one
        here = os.path.dirname(test_file)
        source_here = _tree_text(base, lambda p, here=here: not is_test_side(p) and (os.path.dirname(p).startswith(here) or p.startswith(SHARED)))
        ids = sorted(v for v in ids if "${" not in v and '"{}"'.format(v) not in source_here and "'{}'".format(v) not in source_here)

        def is_data(v):         # text the test itself supplies (a fixture's name, a property it passes) is not the page's own
            plain = v.split(" named ", 1)[-1]
            words = re.findall(r"\w+", plain)
            pieces = bool(words) and all(re.search(r"""["'`]""" + re.escape(w) + r"""["'`]""", text) for w in words)      # put together from the test's own values
            return plain in brought or text.count(plain) > _searches(text, plain) or pieces

        shown = sorted(v for v in shown if "${" not in v and v.split(" named ", 1)[-1] not in source_at_base and not is_data(v))
        if ids or shown:
            entry = out.setdefault(os.path.dirname(test_file), {"test ids": [], "text": []})
            entry["test ids"] = sorted(set(entry["test ids"]) | set(ids))
            entry["text"] = sorted(set(entry["text"]) | set(shown))
    return out


def _searches(text, plain):
    """How often `plain` is the thing a page search looks for in this test file."""
    return len(re.findall(r"""By\w+\(\s*["'`]""" + re.escape(plain) + r"""["'`]""", text)) + len(re.findall(r"""name:\s*["'`]""" + re.escape(plain) + r"""["'`]""", text))


def typescript_interface(base, target, test_files, is_test_side, aliases, generated=None):
    """`generated` (a compiled pattern): files the project's own tools write. Their names are listed without their
    declarations, and a changed declaration there is not listed at all: the tool that writes them decides both."""
    out = {}
    for test_file in test_files:
        source = open(os.path.join(target, test_file), encoding="utf-8").read()
        wanted = []
        for clause, spec in TS_IMPORT.findall(source):
            names = []
            default = re.match(r"\s*(\w+)\s*(,|$)", clause)
            if default:
                names.append("default")
            for group in re.findall(r"\{([^}]*)\}", clause):
                names += [p.strip().split(" as ")[0].replace("type ", "").strip() for p in group.split(",") if p.strip()]
            wanted.append((spec, names))
        wanted += [(spec, []) for spec in TS_MOCK.findall(source)]
        for spec, names in wanted:
            at_target, _ = _ts_file(target, test_file, spec, aliases)
            if not at_target or is_test_side(at_target):
                continue
            at_base, _ = _ts_file(base, test_file, spec, aliases)
            there = _ts_exports(os.path.join(target, at_target))
            had = _ts_exports(os.path.join(base, at_target)) if at_base and os.path.isfile(os.path.join(base, at_target)) else {}
            for name in names or [None]:
                if name is None:
                    if at_base:
                        continue
                    out.setdefault(at_target, {"exists_at_base": False, "names": {}, "changed": {}})
                elif name not in had and WILD not in had:
                    entry = out.setdefault(at_target, {"exists_at_base": bool(at_base), "names": {}, "changed": {}})
                    entry["names"][name] = "(generated)" if generated and generated.search(at_target) else there.get(name, "(exported at the target)")
                elif name in had and name in there and had[name] != there[name] and not (generated and generated.search(at_target)):
                    entry = out.setdefault(at_target, {"exists_at_base": bool(at_base), "names": {}, "changed": {}})
                    entry["changed"][name] = there[name]
    looked_for = typescript_looked_for(base, target, test_files, is_test_side)
    if looked_for:
        out[LOOKED_FOR] = looked_for
    return out


LOOKED_FOR = "(looked for)"


def render(interface: dict, language: str) -> str:
    """The hand-over as the agents read it."""
    lines = ["# What the hidden tests rely on",
             "",
             "The work is judged by the project's own tests, which you cannot see. They use the names below. Each must",
             "exist at exactly this place under exactly this name, declared as shown (every parameter and property), or",
             "the tests that use it cannot run. This says where things live and what they are called, not what they do.",
             ""]
    modules = sorted(m for m in interface if m != LOOKED_FOR)
    for title, key in (("Names that do not exist yet", "names"), ("Names that exist and whose declaration changes", "changed")):
        chosen = [m for m in modules if interface[m].get(key) or (key == "names" and not interface[m]["exists_at_base"])]
        if not chosen:
            continue
        lines += ["## " + title, ""]
        for module in chosen:
            entry = interface[module]
            lines.append("### `{}`{}".format(module, "" if entry["exists_at_base"] else "  (new {})".format("module" if language == "python" else "file")))
            for name in sorted(entry.get(key, {})):
                lines.append("- `{}`: `{}`".format(name, entry[key][name]))
            lines.append("")
    if interface.get(LOOKED_FOR):
        lines += ["## What the tests look for on the page", "",
                  "Tests of the components in each directory find elements by these test ids (`data-test-id`) and by this",
                  "exact visible text. The components there do not render them yet (some ids are used elsewhere already).", ""]
        for where in sorted(interface[LOOKED_FOR]):
            entry = interface[LOOKED_FOR][where]
            lines.append("### `{}`".format(where))
            if entry["test ids"]:
                lines.append("- test ids: " + ", ".join("`{}`".format(v) for v in entry["test ids"]))
            if entry["text"]:
                lines.append("- text: " + "; ".join("\"{}\"".format(v) for v in entry["text"]))
            lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    base, target, language = sys.argv[1:4]
    test_side = lambda p: "/tests/" in p or p.endswith("conftest.py") or "/fixtures" in p or ".test." in p
    if language == "python":
        result = python_interface(base, target, sys.argv[4:], test_side)
    else:
        result = typescript_interface(base, target, sys.argv[4:], test_side, {"@dashboard/": "src", "@test/": "testUtils"})
    json.dump(result, sys.stdout, indent=1)

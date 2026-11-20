"""The WebSocket commands a Home Assistant core tree registers, read from its source without starting it.

    python3 mined_ws_contract.py <core tree> <out.json>

Writes {command type: {"required": [...], "optional": [...], "file": path}}. A command is registered either by the
`websocket_command` decorator, whose schema's `type` key holds the command, or by `async_register_command(hass,
"<type>", handler, schema)`. A `type` given by a constant defined in the same module is resolved; one that cannot
be read (built at run time) is skipped and counted. Runs on any Python able to parse the tree: core uses syntax
of 3.12 and later, so run it in the core image.
"""
import ast
import json
import os
import sys


def _constants(tree):
    found = {}
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                if isinstance(target, ast.Name):
                    found[target.id] = node.value.value
    return found


def _text(node, constants):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.Attribute):     # e.g. const.TYPE: read by name only, as the module's own constants
        return constants.get(node.attr)
    return None


def _key(node, constants):
    """`vol.Required("x")` / `vol.Optional("x", default=...)` / a bare "x": the key and whether it is required."""
    if isinstance(node, ast.Call) and node.args:
        called = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        if called in ("Required", "Optional", "Exclusive", "Inclusive"):
            return _text(node.args[0], constants), called == "Required"
    return _text(node, constants), True


def _schema(node, constants):
    """A schema dict as written: its `type`, and its other keys."""
    if isinstance(node, ast.Call) and node.args:            # vol.Schema({...}) or a .extend({...})
        node = node.args[-1] if isinstance(node.args[-1], ast.Dict) else node.args[0]
    if not isinstance(node, ast.Dict):
        return None, [], []
    command, required, optional = None, [], []
    for k, v in zip(node.keys, node.values):
        if k is None:
            continue
        name, needed = _key(k, constants)
        if name == "type":
            command = _text(v, constants)
        elif name:
            (required if needed else optional).append(name)
    return command, sorted(required), sorted(optional)


def commands(root):
    found, unread = {}, 0
    for directory, dirs, files in os.walk(os.path.join(root, "homeassistant")):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(directory, name)
            with open(path, encoding="utf-8") as f:
                source = f.read()
            if "websocket_command" not in source and "async_register_command" not in source:
                continue
            tree = ast.parse(source)
            constants = _constants(tree)
            for node in ast.walk(tree):
                entries = []
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for deco in node.decorator_list:
                        called = deco.func if isinstance(deco, ast.Call) else None
                        if called is not None and (getattr(called, "attr", None) or getattr(called, "id", None)) == "websocket_command" and deco.args:
                            entries.append(_schema(deco.args[0], constants))
                elif isinstance(node, ast.Call) and (getattr(node.func, "attr", None) or getattr(node.func, "id", None)) == "async_register_command" \
                        and len(node.args) >= 2 and _text(node.args[1], constants):
                    schema = _schema(node.args[3], constants) if len(node.args) > 3 else (None, [], [])
                    entries.append((_text(node.args[1], constants), schema[1], schema[2]))
                for command, required, optional in entries:
                    if command:
                        found[command] = {"required": required, "optional": optional, "file": os.path.relpath(path, root)}
                    else:
                        unread += 1
    return found, unread


if __name__ == "__main__":
    found, unread = commands(sys.argv[1])
    with open(sys.argv[2], "w") as f:
        json.dump(found, f, indent=1, sort_keys=True)
    print("{} commands registered; {} whose type could not be read".format(len(found), unread))

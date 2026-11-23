"""The messaging tools at a seat: an MCP server (stdio) in front of the company's chat sidecar.

The harness starts it (`python3 /opt/seedco/team_mcp.py`). Who the seat belongs to comes from SEAT and SEAT_TOKEN.
Tools: send_message(to, text), read_messages(), wait_for_message(minutes).
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

CHAT = os.environ.get("CHAT_URL", "http://chat:8080")
ME, TOKEN = os.environ.get("SEAT", ""), os.environ.get("SEAT_TOKEN", "")
OTHERS = [n for n in os.environ.get("TEAM", "").split(",") if n and n != ME]

TOOLS = [
    {"name": "send_message",
     "description": "Send a message to another person working on this change ({}). They work at the same time as you and read it "
                    "when they next look at their messages. They see what you push, not your checkout or your conversation. "
                    "A message to someone who has already finished is not read, and you are told so.".format(", ".join(OTHERS) or "nobody else"),
     "inputSchema": {"type": "object", "properties": {"to": {"type": "string", "enum": OTHERS}, "text": {"type": "string"}}, "required": ["to", "text"]}},
    {"name": "read_messages",
     "description": "Read the messages that have reached you since you last looked. Returns at once.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "wait_for_message",
     "description": "Wait until a message reaches you, for at most `minutes` (1 to 10), and return what arrived. Returns at once if "
                    "nobody else is still working. Time passes while you wait, so do what you can do first.",
     "inputSchema": {"type": "object", "properties": {"minutes": {"type": "number"}}}},
]


def call(method, path, body=None):
    request = urllib.request.Request(CHAT + path, data=json.dumps(body).encode() if body is not None else None, method=method,
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=660) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read() or b"{}")
    except OSError as e:
        return {"error": "the chat could not be reached: {}".format(e)}


def inbox(wait):
    got = call("GET", "/inbox?" + urllib.parse.urlencode({"name": ME, "token": TOKEN, "wait": wait}))
    if "error" in got:
        return "ERROR: " + got["error"]
    lines = ["Message from {}:\n{}".format(m["from"], m["text"]) for m in got["messages"]] or ["No message."]
    if (got.get("waited_s") or 0) >= 30:      # a coworker task's clock: how long the wait took
        minutes = max(1, round(got["waited_s"] / 60))
        lines.insert(0, "You waited {} minute{}.".format(minutes, "" if minutes == 1 else "s"))
    away = got.get("others_paused") or {}
    if got["others_working"]:
        lines.append("Still working: {}.".format(", ".join(got["others_working"])))
    for who, until in sorted(away.items()):
        lines.append("{} is paused by a limit on the model service, not finished, and is expected back around {} UTC. "
                     "Messages sent meanwhile are kept and read then.".format(who, time.strftime("%H:%M", time.gmtime(until))))
    if not got["others_working"] and not away:
        lines.append("Everyone else has finished.")
    return "\n\n".join(lines)


def use(name, args):
    if name == "send_message":
        got = call("POST", "/send", {"from": ME, "token": TOKEN, "to": args.get("to"), "text": args.get("text")})
        return "ERROR: " + got["error"] if "error" in got else got["note"]
    if name == "read_messages":
        return inbox(0)
    if name == "wait_for_message":
        return inbox(60 * max(1.0, min(10.0, float(args.get("minutes") or 5))))
    return "ERROR: unknown tool " + name


for line in sys.stdin:
    try:
        message = json.loads(line)
    except ValueError:
        continue
    method, ident = message.get("method"), message.get("id")
    if ident is None:                      # a notification: nothing to answer
        continue
    if method == "initialize":
        result = {"protocolVersion": message.get("params", {}).get("protocolVersion", "2024-11-05"), "capabilities": {"tools": {}},
                  "serverInfo": {"name": "team", "version": "1"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = message.get("params", {})
        text = use(params.get("name"), params.get("arguments") or {})
        result = {"content": [{"type": "text", "text": text}], "isError": text.startswith("ERROR:")}
    elif method == "ping":
        result = {}
    else:
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": "unknown method"}}) + "\n")
        sys.stdout.flush()
        continue
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": ident, "result": result}) + "\n")
    sys.stdout.flush()

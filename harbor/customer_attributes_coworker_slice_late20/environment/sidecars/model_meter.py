"""Meters what each seat asks of the model, at the gateway, whatever harness is at the seat.

    python3 tools/model_meter.py <upstream base, e.g. http://127.0.0.1:8317> <out dir> [port]

A seat is given this meter as its model service, under a path of its own:

    http://<meter>:<port>/seat/<seat>/...     passed on to <upstream>/...

Every request is passed on unchanged and answered with the upstream's answer unchanged (streamed if it streams).
For each request one line is written to <out dir>/<seat>.jsonl. Nothing of what was said is kept: no prompt, no
answer, only sizes and counts, and a fingerprint that tells one conversation from another.

    at, seconds        when it was asked, how long the answer took
    seat, path, status
    model              the model asked for
    context            a fingerprint of the conversation's start (system prompt and first message): requests with the
                       same fingerprint are one context growing; a new fingerprint is a new context (a subagent,
                       or the harness's own side requests)
    messages, tools    how many messages and tool definitions the request carried
    request_bytes      the size of the request
    input, cache_read, cache_write, output   tokens, as the model service counted them (Anthropic and OpenAI formats)
    context_tokens     input + cache_read + cache_write: what the model was given to read for this one request

    GET /_records      every line written so far (the task's verifier keeps them with its own records)

A task carries it as its `meter` sidecar (upstream from METER_UPSTREAM). A harness is measured by giving it
http://meter:8318/seat/<seat> as its model service; one that is not given it is simply not measured.
tools/run_measures.py turns these lines into a run's measures. Standard library only.
"""
import hashlib
import http.client
import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

UPSTREAM, OUT = urlparse(sys.argv[1]), sys.argv[2]
PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 8318
lock = threading.Lock()
USAGE = {"input": ("input_tokens", "prompt_tokens"), "cache_read": ("cache_read_input_tokens", "cached_tokens"),
         "cache_write": ("cache_creation_input_tokens",), "output": ("output_tokens", "completion_tokens")}
NUMBER = {name: re.compile(rb'"(?:%s)"\s*:\s*(\d+)' % "|".join(keys).encode()) for name, keys in USAGE.items()}


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return ""


def describe(raw):
    """What a request carries, without what it says."""
    try:
        body = json.loads(raw or b"{}")
    except ValueError:
        return {}
    if not isinstance(body, dict):
        return {}
    messages = body.get("messages") or body.get("input") or []
    messages = messages if isinstance(messages, list) else []
    first = next((text_of(m.get("content")) for m in messages if isinstance(m, dict) and m.get("role") == "user"), "")
    start = (text_of(body.get("system")) or text_of(body.get("instructions")))[:4000] + "\n" + first[:4000]
    return {"model": body.get("model"), "messages": len(messages), "tools": len(body.get("tools") or []),
            "context": hashlib.sha1(start.encode()).hexdigest()[:12] if messages else None, "stream": bool(body.get("stream"))}


def usage(seen):
    """The token counts in an answer: the last figure given for each (a stream gives them as it goes)."""
    found = {}
    for name, pattern in NUMBER.items():
        hits = pattern.findall(seen)
        if hits:
            found[name] = max(int(h) for h in hits)
    return found


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def handle_any(self):
        if self.path.split("?")[0] == "/_records":      # every line written so far, for whoever judges the work
            data = b""
            for name in sorted(os.listdir(OUT)):
                if name.endswith(".jsonl"):
                    with open(os.path.join(OUT, name), "rb") as f:
                        data += f.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        parts = self.path.split("/", 3)
        if len(parts) < 4 or parts[1] != "seat":
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        seat, rest = parts[2], "/" + parts[3]
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        entry = dict({"at": round(time.time(), 3), "seat": seat, "path": rest.split("?")[0], "request_bytes": len(raw)}, **describe(raw))
        make = http.client.HTTPSConnection if UPSTREAM.scheme == "https" else http.client.HTTPConnection
        upstream = make(UPSTREAM.hostname, UPSTREAM.port, timeout=1800)
        headers = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "content-length", "accept-encoding", "connection")}
        headers["Host"] = UPSTREAM.netloc
        seen = b""
        try:
            upstream.request(self.command, (UPSTREAM.path.rstrip("/") + rest), body=raw or None, headers=headers)
            answer = upstream.getresponse()
            entry["status"] = answer.status
            self.send_response(answer.status)
            for k, v in answer.getheaders():
                if k.lower() not in ("transfer-encoding", "content-length", "connection"):
                    self.send_header(k, v)
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("Connection", "close")
            self.end_headers()
            while True:
                chunk = answer.read1(65536)
                if not chunk:
                    break
                seen = seen[:50000] + (seen[50000:] + chunk)[-200000:] if len(seen) > 300000 else seen + chunk      # the counts are at the start and the end
                self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
        except OSError as e:
            entry["error"] = type(e).__name__
            if "status" not in entry:
                try:
                    self.send_response(502)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                except OSError:
                    pass
        finally:
            upstream.close()
            self.close_connection = True
        entry.update(usage(seen))
        entry["context_tokens"] = sum(entry.get(k, 0) for k in ("input", "cache_read", "cache_write"))
        entry["seconds"] = round(time.time() - entry["at"], 2)
        with lock, open(os.path.join(OUT, re.sub(r"[^A-Za-z0-9_.-]", "_", seat) + ".jsonl"), "a") as f:
            f.write(json.dumps(entry) + "\n")

    do_GET = do_POST = do_PUT = do_DELETE = handle_any


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

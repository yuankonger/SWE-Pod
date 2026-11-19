"""Metrics and logs. Metric and attribute names follow Saleor's telemetry (saleor.graphql.*, saleor.webhook.*),
written the way an OpenTelemetry-to-Prometheus pipeline writes them: dots become underscores, counters end in
`_total`. Logs are one JSON object per line on stdout.
"""
import json
import sys
import threading
import time

_lock = threading.Lock()
_counters = {}
SERVICE = "core"


def count(name: str, amount: float = 1, **labels):
    key = (name, tuple(sorted(labels.items())))
    with _lock:
        _counters[key] = _counters.get(key, 0) + amount


def render() -> str:
    """The Prometheus text exposition format."""
    with _lock:
        items = sorted(_counters.items())
    lines, seen = [], set()
    for (name, labels), value in items:
        if name not in seen:
            seen.add(name)
            lines.append("# TYPE {} counter".format(name))
        text = ",".join('{}="{}"'.format(k, str(v).replace("\\", "\\\\").replace('"', '\\"')) for k, v in labels)
        lines.append("{}{{{}}} {}".format(name, text, value) if text else "{} {}".format(name, value))
    return "\n".join(lines) + "\n"


def log(level: str, message: str, **attributes):
    record = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "level": level, "service": SERVICE,
              "message": message}
    record.update(attributes)
    print(json.dumps(record, default=str), file=sys.stdout, flush=True)

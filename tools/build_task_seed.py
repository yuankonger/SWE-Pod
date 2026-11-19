"""Builds a task's seed: the databases every service has after the task's history has happened.

Starts the company as the task finds it (the base company with the task's overlay), replays
tasks/<task>/history.py against it, waits until Core has delivered every event,
stops it, and keeps each service's database under tasks/<task>/seed/<service>/. An episode gives each owner a
copy of its own database to look into, and scoring starts the company from the seed.

Run inside the toolchain image:  python3 tools/build_task_seed.py task01_order_confirmation
The seed describes the base company as it is today. Rebuild it after changing how a service stores its data.
"""
import importlib.util
import os
import shutil
import sqlite3
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "platform"))
sys.path.insert(0, os.path.join(REPO, "integration"))

sys.path.insert(0, REPO)

from shop import Browser  # noqa: E402
from stack import Stack  # noqa: E402
from kernel.episode import prepare_workspace  # noqa: E402


def main(task):
    task_dir = os.path.join(REPO, "tasks", task)
    seed = os.path.join(task_dir, "seed")
    spec = importlib.util.spec_from_file_location("history", os.path.join(task_dir, "history.py"))
    history = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(history)
    shutil.rmtree(seed, ignore_errors=True)
    os.makedirs(seed)
    root = REPO
    if os.path.isdir(os.path.join(task_dir, "overlay")):     # the history happens in the company the task starts from
        root = prepare_workspace(REPO, task_dir, "/tmp/seedco-seed-build/" + task)
        for owner in os.listdir(os.path.join(root, "services")):
            shutil.rmtree(os.path.join(root, "services", owner, "data"), ignore_errors=True)
    logs = os.path.join(task_dir, "logs")           # what every service logged while the history happened
    shutil.rmtree(logs, ignore_errors=True)
    # a history may need something in place before the company starts (see task 3's): it says so with `before_start`
    more = history.before_start(7600) if hasattr(history, "before_start") else {}
    stack = Stack(root=root, base_port=7600, data_dir=seed, log_dir=logs, **more).start()
    try:
        history.replay(stack, Browser)

        def pending():
            db = sqlite3.connect("file:{}?mode=ro".format(os.path.join(seed, "core", "core.db")), uri=True)
            try:
                return db.execute("SELECT COUNT(*) FROM docs WHERE kind = 'delivery' AND lookup = 'pending'").fetchone()[0]
            finally:
                db.close()

        # An event still on its way when the company stops would be sent to the wrong place when it starts again.
        if not stack.wait_for(lambda: pending() == 0, timeout=120):
            raise RuntimeError("Core still has {} undelivered events".format(pending()))
        dropped = stack.get("notifications", "/dropped")[1]["dropped"]
        if dropped:
            raise RuntimeError("the history dropped events: {}".format(dropped[:3]))
    finally:
        stack.stop()
    shutil.rmtree(os.path.join(seed, "prometheus"), ignore_errors=True)     # monitoring keeps no history worth seeding
    if os.path.isfile(os.path.join(logs, "prometheus.log")):
        os.remove(os.path.join(logs, "prometheus.log"))
    for name in sorted(os.listdir(seed)):
        path = os.path.join(seed, name)
        for f in os.listdir(path):
            if f.endswith(".trace.db"):
                os.remove(os.path.join(path, f))
        if not os.listdir(path):
            os.rmdir(path)                                                  # a service with no database
    for name in sorted(os.listdir(seed)):
        size = sum(os.path.getsize(os.path.join(seed, name, f)) for f in os.listdir(os.path.join(seed, name)))
        print("{:14} {:>8} bytes  {}".format(name, size, ", ".join(sorted(os.listdir(os.path.join(seed, name))))))


if __name__ == "__main__":
    main(sys.argv[1])

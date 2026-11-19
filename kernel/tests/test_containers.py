"""Container isolation for agents. Needs docker, so it runs on the host:  python3 -m unittest kernel.tests.test_containers"""
import json
import os
import shutil
import tempfile
import unittest

from kernel.containers import Containers
from kernel.episode import build_agents, prepare_workspace, run_episode
from kernel.model import ScriptedModel

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TASK_DIR = os.path.join(REPO, "tasks", "task01_order_confirmation")
TASK = json.load(open(os.path.join(TASK_DIR, "task.json")))

PEEK = '''import os, unittest, urllib.request
class Peek(unittest.TestCase):
    def test_what_an_agents_own_test_code_can_reach(self):
        print("OWNERS", sorted(os.listdir("/work/services")))
        print("CORE_NOTES", os.path.exists("../core/NOTES.md"))
        try:
            urllib.request.urlopen("http://example.com", timeout=3)
            print("NETWORK yes")
        except Exception:
            print("NETWORK no")
'''


@unittest.skipUnless(shutil.which("docker"), "docker is not available")
class ContainersTest(unittest.TestCase):
    def setUp(self):
        # under the repository, so that docker can mount it on every platform
        self.tmp = tempfile.mkdtemp(prefix="containers-", dir=os.path.join(REPO, "runs") if os.path.isdir(os.path.join(REPO, "runs")) else None)
        self.ws = prepare_workspace(REPO, TASK_DIR, os.path.join(self.tmp, "ws"))
        self.containers = Containers("test-" + os.path.basename(self.tmp))

    def tearDown(self):
        self.containers.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def agent(self, condition, name):
        return next(a for a in build_agents(TASK, condition, self.ws, os.path.join(self.tmp, "build"), self.containers) if a.name == name)

    def test_an_owners_tests_run_alone_with_no_network(self):
        box = self.agent("team", "notifications").sandbox
        self.assertEqual(sorted(self.containers.names), ["core", "dashboard", "notifications", "taxes"])
        self.assertTrue(box.call("run_tests", {}).startswith("exit code 0"))
        box.call("write_file", {"path": "test/test_peek.py", "content": PEEK})
        out = box.call("run_tests", {})
        self.assertIn("OWNERS ['notifications']", out)       # test code the agent wrote sees no other owner
        self.assertIn("CORE_NOTES False", out)
        self.assertIn("NETWORK no", out)
        self.assertTrue(os.path.isfile(os.path.join(self.ws, "services", "notifications", "test", "test_peek.py")))

    def test_an_agents_shell_runs_in_its_own_container(self):
        core = self.agent("team", "core")
        self.assertIn("shell", [t["name"] for t in core.tools])
        seen = core.sandbox.call("shell", {"command": "pwd; ls /work/services; ls /work; grep -c order_fulfill src/core.py"})
        self.assertTrue(seen.startswith("exit code 0\n/work/services/core\ncore\n"), seen)       # its own directory, and no other owner's
        self.assertIn("platform", seen)
        self.assertIn("regression", seen)
        for outside in ("ls /work/services/taxes", "ls /work/tasks", "ls /work/kernel", "cat /work/regression/../hidden/rubric.toml"):
            self.assertFalse(core.sandbox.call("shell", {"command": outside}).startswith("exit code 0"), outside)
        self.assertFalse(core.sandbox.call("shell", {"command": "touch /work/platform/x"}).startswith("exit code 0"))   # shared files are read-only
        self.assertFalse(core.sandbox.call("shell", {"command": "curl -s -m 3 http://example.com >/dev/null || python3 -c \"import urllib.request as u; u.urlopen('http://example.com', timeout=3)\""}).startswith("exit code 0"))
        core.sandbox.call("shell", {"command": "echo changed > NOTES.md"})
        self.assertEqual(open(os.path.join(self.ws, "services", "core", "NOTES.md")).read(), "changed\n")      # what it changes is the workspace

    def test_the_solo_agent_can_start_the_company_in_its_shell(self):
        solo = self.agent("solo", "solo")
        out = solo.sandbox.call("shell", {"command": "cd /tmp && (nohup python3 /work/platform/stack.py > stack.out 2>&1 &) ; "
                                                     "for i in $(seq 90); do grep -q '^up:' stack.out && break; sleep 1; done; "
                                                     "python3 -c \"import urllib.request as u; print(u.urlopen('http://127.0.0.1:7000/health').status)\"; head -c 200 stack.out"})
        self.assertTrue(out.startswith("exit code 0\n200"), out)

    def test_the_solo_agent_gets_the_whole_company(self):
        box = self.agent("solo", "solo").sandbox
        self.assertEqual(list(self.containers.names), ["solo"])
        box.call("write_file", {"path": "notifications/test/test_peek.py", "content": PEEK})
        out = box.call("run_tests", {"service": "notifications"})
        self.assertIn("'core'", out)
        self.assertIn("CORE_NOTES True", out)
        self.assertIn("NETWORK no", out)


    def test_an_agent_the_lead_starts_gets_a_container_with_only_its_directories(self):
        peek = PEEK.replace('"../core/NOTES.md"', '"/work/services/core/NOTES.md"')
        summary = run_episode(TASK, "lead", ScriptedModel({
            "lead": [[("spawn_agent", {"name": "apps", "directories": ["notifications", "taxes"], "instructions": "Look around."})],
                     [("submit", {"summary": "done"})]],
            "apps": [[("write_file", {"path": "notifications/test/test_peek.py", "content": peek}),
                      ("run_tests", {"service": "notifications"})], [("submit", {"summary": "done"})]],
        }), self.ws, os.path.join(self.tmp, "events.jsonl"), 10.0, containers=self.containers)
        self.assertEqual(summary["end"], "all_submitted")
        self.assertEqual(sorted(self.containers.names), ["apps", "lead"])
        with open(os.path.join(self.tmp, "events.jsonl")) as f:
            events = [json.loads(line) for line in f]
        out = next(e["result"] for e in events if e["kind"] == "tool" and e["name"] == "run_tests")
        self.assertIn("OWNERS ['notifications', 'taxes']", out)
        self.assertIn("CORE_NOTES False", out)


if __name__ == "__main__":
    unittest.main()

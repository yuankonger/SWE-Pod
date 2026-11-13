"""Kernel behaviour, with scripted agents (no model, no services started)."""
import json
import os
import tempfile
import unittest

from kernel.episode import prepare_workspace, run_episode
from kernel.model import ScriptedModel
from kernel.tools import Sandbox

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TASK_DIR = os.path.join(REPO, "tasks", "task01_money")
TASK = json.load(open(os.path.join(TASK_DIR, "task.json")))


class KernelTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="seedco-kernel-")
        self.ws = prepare_workspace(REPO, TASK_DIR, os.path.join(self.tmp, "ws"))
        self.log = os.path.join(self.tmp, "events.jsonl")

    def events(self, kind):
        with open(self.log) as f:
            return [e for e in map(json.loads, f) if e["kind"] == kind]

    def run_scripts(self, scripts, condition="team", budget=10_000, tokens_per_call=0, **kw):
        return run_episode(TASK, condition, ScriptedModel(scripts, tokens_per_call), self.ws, self.log, budget, **kw)

    def test_an_owner_cannot_reach_outside_its_service(self):
        box = Sandbox(os.path.join(self.ws, "services", "orders"), ["orders"], os.path.join(self.tmp, "build"))
        self.assertTrue(box.call("read_file", {"path": "NOTES.md"}).startswith("# Orders"))
        for path in ("../billing/NOTES.md", "/etc/passwd", "../../platform/broker.py"):
            self.assertTrue(box.call("read_file", {"path": path}).startswith("ERROR:"), path)
        self.assertTrue(box.call("write_file", {"path": "../billing/x", "content": "x"}).startswith("ERROR:"))
        self.assertNotIn("Billing.cs", box.call("list_files", {}))

    def test_the_overlay_gives_only_billing_the_decision_record(self):
        self.assertTrue(os.path.isfile(os.path.join(self.ws, "services", "billing", "docs", "FIN-12.md")))
        for s in ("orders", "storefront", "notifications"):
            self.assertFalse(os.path.exists(os.path.join(self.ws, "services", s, "docs")))

    def test_a_message_wakes_an_owner_who_had_submitted(self):
        done = [("submit", {"summary": "done"})]
        summary = self.run_scripts({
            "storefront": [done], "notifications": [done],
            "orders": [done, [("read_file", {"path": "NOTES.md"})], done],
            "billing": [[], [("send_message", {"to": "orders", "text": "Money is {currency, minor}"})], done]})
        self.assertEqual(summary["end"], "all_submitted")
        self.assertEqual(summary["messages_sent"], 1)
        self.assertEqual(summary["agents"]["orders"]["calls"], 3)
        self.assertEqual(self.events("message")[0]["to"], "orders")

    def test_no_messaging_condition_has_no_channel(self):
        summary = self.run_scripts({"billing": [[("send_message", {"to": "orders", "text": "hi"})]]},
                                   condition="team_no_messaging")
        self.assertEqual(summary["messages_sent"], 0)
        self.assertTrue(self.events("tool")[0]["result"].startswith("ERROR: unknown tool"))

    def test_the_shared_budget_ends_the_episode(self):
        loop = [[("list_files", {})]] * 50
        summary = self.run_scripts({s: list(loop) for s in ("storefront", "orders", "billing", "notifications")},
                                   budget=1000, tokens_per_call=300)
        self.assertEqual(summary["end"], "budget_exhausted")
        self.assertEqual(summary["model_calls"], 4)   # 4 x 300 passes 1000 on the fourth call
        self.assertEqual(summary["tokens_used"], 1200)

    def test_idle_owners_are_stopped_and_the_hard_stop_holds(self):
        summary = self.run_scripts({})   # nobody ever calls a tool
        self.assertEqual(summary["end"], "all_submitted")
        self.assertEqual(summary["model_calls"], 12)
        self.assertEqual(len(self.events("idle_stop")), 4)
        loop = [[("list_files", {})]] * 50
        summary = self.run_scripts({"solo": list(loop)}, condition="solo", max_model_calls=7)
        self.assertEqual((summary["end"], summary["model_calls"]), ("hard_stop", 7))


if __name__ == "__main__":
    unittest.main()

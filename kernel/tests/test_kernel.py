"""Kernel behaviour, with scripted agents (no model, no services started)."""
import json
import os
import tempfile
import unittest

from kernel.episode import build_agents, prepare_workspace, run_episode
from kernel.model import ScriptedModel
from kernel.tools import Sandbox

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TASK_DIR = os.path.join(REPO, "tasks", "task01_order_confirmation")
TASK = json.load(open(os.path.join(TASK_DIR, "task.json")))


class KernelTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="seedco-kernel-")
        self.ws = prepare_workspace(REPO, TASK_DIR, os.path.join(self.tmp, "ws"))
        self.log = os.path.join(self.tmp, "events.jsonl")

    def events(self, kind):
        with open(self.log) as f:
            return [e for e in map(json.loads, f) if e["kind"] == kind]

    def run_scripts(self, scripts, condition="team", budget=100.0, dollars_per_call=0.0, task=TASK, **kw):
        kw.setdefault("clock", "turns")      # every turn one unit: the same order on every run
        return run_episode(task, condition, ScriptedModel(scripts, dollars_per_call), self.ws, self.log, budget, **kw)

    def test_an_owner_cannot_reach_outside_its_service(self):
        box = Sandbox(os.path.join(self.ws, "services"), ["taxes"], os.path.join(self.tmp, "build"))
        self.assertTrue(box.call("read_file", {"path": "NOTES.md"}).startswith("# Taxes"))
        for path in ("../core/NOTES.md", "/etc/passwd", "../../platform/stack.py"):
            self.assertTrue(box.call("read_file", {"path": path}).startswith("ERROR:"), path)
        self.assertTrue(box.call("write_file", {"path": "../core/x", "content": "x"}).startswith("ERROR:"))
        self.assertNotIn("core.py", box.call("list_files", {}))

    def test_the_overlay_gives_only_core_the_decision_record(self):
        self.assertTrue(os.path.isfile(os.path.join(self.ws, "services", "core", "docs", "OPS-7.md")))
        for s in ("dashboard", "notifications", "taxes", "storefront"):
            self.assertFalse(os.path.exists(os.path.join(self.ws, "services", s, "docs")))

    def test_a_message_wakes_an_owner_who_had_submitted(self):
        done = [("submit", {"summary": "done"})]
        summary = self.run_scripts({
            "dashboard": [done], "notifications": [done],
            "taxes": [done, [("read_file", {"path": "NOTES.md"})], done],
            "core": [[], [("send_message", {"to": "taxes", "text": "The new event is ORDER_CONFIRMED"})], done]})
        self.assertEqual(summary["end"], "all_submitted")
        self.assertEqual(summary["messages_sent"], 1)
        self.assertEqual(summary["agents"]["taxes"]["calls"], 3)
        self.assertEqual(self.events("message")[0]["to"], "taxes")

    def test_no_messaging_condition_has_no_channel(self):
        summary = self.run_scripts({"core": [[("send_message", {"to": "taxes", "text": "hi"})]]},
                                   condition="team_no_messaging")
        self.assertEqual(summary["messages_sent"], 0)
        self.assertTrue(self.events("tool")[0]["result"].startswith("ERROR: unknown tool"))

    def test_the_shared_budget_ends_the_episode(self):
        loop = [[("list_files", {})]] * 50
        summary = self.run_scripts({s: list(loop) for s in TASK["briefs"]},
                                   budget=1.00, dollars_per_call=0.30)
        self.assertEqual(summary["end"], "budget_exhausted")
        self.assertEqual(summary["model_calls"], 4)   # 4 x $0.30 passes $1.00 on the fourth call
        self.assertEqual(summary["dollars_used"], 1.2)
        self.assertEqual(summary["agents"]["core"]["dollars"], 0.3)

    def test_idle_owners_are_stopped_and_the_hard_stop_holds(self):
        summary = self.run_scripts({})   # nobody ever calls a tool
        self.assertEqual(summary["end"], "all_submitted")
        self.assertEqual(summary["model_calls"], 12)
        self.assertEqual(len(self.events("idle_stop")), 4)
        loop = [[("list_files", {})]] * 50
        summary = self.run_scripts({"solo": list(loop)}, condition="solo", max_model_calls=7)
        self.assertEqual((summary["end"], summary["model_calls"]), ("hard_stop", 7))

    def test_an_agent_with_several_directories_is_confined_to_them(self):
        box = Sandbox(os.path.join(self.ws, "services"), ["payments", "subscriptions"], os.path.join(self.tmp, "build"))
        self.assertTrue(box.call("read_file", {"path": "payments/NOTES.md"}).startswith("# Payments"))
        listing = box.call("list_files", {})
        self.assertIn("subscriptions/NOTES.md", listing)
        self.assertNotIn("core/", listing)
        for path in ("core/NOTES.md", "payments/../core/NOTES.md", "../platform/stack.py", "NOTES.md"):
            self.assertTrue(box.call("read_file", {"path": path}).startswith("ERROR:"), path)
        self.assertTrue(box.call("write_file", {"path": "core/x", "content": "x"}).startswith("ERROR:"))
        self.assertTrue(box.call("run_tests", {"service": "core"}).startswith("ERROR:"))

    def test_a_lead_starts_agents_gives_them_directories_and_works_with_them(self):
        done = [("submit", {"summary": "done"})]
        summary = self.run_scripts({
            "lead": [[("spawn_agent", {"name": "apps", "directories": ["taxes", "notifications"], "instructions": "Do OPS-7 for the apps."}),
                      ("spawn_agent", {"name": "ui", "directories": ["dashboard"], "instructions": "Add the button."}),
                      ("spawn_agent", {"name": "dup", "directories": ["taxes"], "instructions": "x"}),          # taxes is taken
                      ("spawn_agent", {"name": "ui", "directories": ["mobile"], "instructions": "x"}),          # the name is taken
                      ("spawn_agent", {"name": "ghost", "directories": ["nowhere"], "instructions": "x"}),
                      ("send_message", {"to": "apps", "text": "The event is ORDER_CONFIRMED."})],
                     done, done],
            "apps": [[("read_file", {"path": "taxes/NOTES.md"}), ("read_file", {"path": "core/NOTES.md"}),
                      ("send_message", {"to": "lead", "text": "Which statuses are held?"})], done],
            "ui": [[("read_file", {"path": "NOTES.md"})], done],
        }, condition="lead", dollars_per_call=0.25)
        self.assertEqual(summary["end"], "all_submitted")
        self.assertEqual({a: v["directories"] for a, v in summary["agents"].items() if a != "lead"},
                         {"apps": ["notifications", "taxes"], "ui": ["dashboard"]})
        self.assertEqual(len(summary["agents"]["lead"]["directories"]), 10)
        self.assertEqual([e["agent"] for e in self.events("spawn")], ["apps", "ui"])
        results = {(e["agent"], e["input"].get("path")): e["result"] for e in self.events("tool")}
        self.assertTrue(results[("apps", "taxes/NOTES.md")].startswith("# Taxes"))
        self.assertTrue(results[("apps", "core/NOTES.md")].startswith("ERROR:"))             # not one of its directories
        self.assertTrue(results[("ui", "NOTES.md")].startswith("# Dashboard"))               # one directory: paths are relative to it
        self.assertEqual([(m["sender"], m["to"]) for m in self.events("message")], [("lead", "apps"), ("apps", "lead")])
        self.assertEqual(summary["agents"]["lead"]["calls"], 2)                              # the agents began at once: the question came before the lead had submitted
        self.assertEqual(summary["dollars_used"], 0.25 * summary["model_calls"])
        worker = build_agents(TASK, "lead", self.ws, os.path.join(self.tmp, "build"))[0]
        self.assertIn("spawn_agent", [t["name"] for t in worker.tools])
        self.assertNotIn("spawn_agent", [t["name"] for t in build_agents(TASK, "solo", self.ws, os.path.join(self.tmp, "build"))[0].tools])

    def test_an_agent_that_has_stopped_is_moved_on_to_when_its_message_arrives(self):
        done = [("submit", {"summary": "done"})]
        look = [("list_files", {})]
        summary = self.run_scripts({
            "dashboard": [done], "notifications": [done], "taxes": [done, done],
            "core": [look, look, look, [("send_message", {"to": "taxes", "text": "The new event is ORDER_CONFIRMED"})], done]})
        taxes, core = summary["agents"]["taxes"], summary["agents"]["core"]
        self.assertEqual((taxes["waited_seconds"], taxes["seconds"]), (2.0, 4.0))     # stopped at 1, the message was sent at 3
        self.assertEqual((core["waited_seconds"], core["seconds"]), (0.0, 5.0))
        self.assertEqual(summary["team_seconds"], 5.0)                                  # the furthest clock, not the sum
        self.assertEqual(summary["agent_seconds"], 9.0)                                 # the turns one after another: 5 + 2 + 1 + 1
        self.assertEqual(self.events("message")[0]["at"], 3.0)

    def test_waiting_stops_an_agent_until_a_message_and_is_ended_when_nobody_is_left_to_write(self):
        done = [("submit", {"summary": "done"})]
        wait = [("wait_for_message", {})]
        look = [("list_files", {})]
        summary = self.run_scripts({
            "dashboard": [done], "notifications": [done],
            "taxes": [wait, done],
            "core": [look, look, [("send_message", {"to": "taxes", "text": "go"})], done]})
        self.assertEqual(summary["end"], "all_submitted")
        self.assertEqual(summary["agents"]["taxes"]["calls"], 2)                        # no turns spent while it waited
        self.assertEqual(summary["agents"]["taxes"]["waited_seconds"], 1.0)
        # everyone left waits for someone else: they are told so, and stopped if they only wait again
        summary = self.run_scripts({"dashboard": [done], "notifications": [done], "taxes": [wait] * 9, "core": [wait] * 9})
        self.assertEqual(summary["end"], "all_submitted")
        self.assertEqual(len(self.events("idle_stop")), 2)
        self.assertEqual(summary["agents"]["core"]["calls"], 1 + 3)
        self.assertTrue(any("No message came" in e["text"] for e in self.events("turn")))

    def test_with_measured_time_a_message_is_not_read_before_it_was_sent(self):
        from unittest import mock
        fake = {"now": 1000.0}
        pace = {"core": 100.0, "taxes": 10.0}

        class Paced(ScriptedModel):
            def call(self, agent, system, tools, messages):
                fake["now"] += pace.get(agent, 1.0)          # what this agent's model call took
                return super().call(agent, system, tools, messages)

        done = [("submit", {"summary": "done"})]
        look = [("list_files", {})]
        model = Paced({"dashboard": [done], "notifications": [done],
                       "core": [[("send_message", {"to": "taxes", "text": "The new event is ORDER_CONFIRMED"})], done],
                       "taxes": [look] * 12 + [done]})
        with mock.patch("kernel.episode.time.monotonic", lambda: fake["now"]):
            summary = run_episode(TASK, "team", model, self.ws, self.log, 100.0, clock="measured")
        self.assertEqual(self.events("message")[0]["at"], 100.0)
        read = [e for e in self.events("turn") if e["agent"] == "taxes" and "Message from core" in e["text"]]
        self.assertEqual([e["clock"] for e in read], [100.0])       # taxes had taken ten turns by then, and saw nothing in them
        self.assertEqual(summary["agents"]["core"]["seconds"], 200.0)
        self.assertEqual(summary["agents"]["taxes"]["seconds"], 130.0)
        self.assertEqual(summary["team_seconds"], 200.0)
        self.assertEqual(summary["agent_seconds"], 332.0)
        self.assertIn("Time since the work began: 1m 40s", read[0]["text"])

    def test_a_task_can_let_a_leads_agents_work_in_the_same_directory(self):
        done = [("submit", {"summary": "done"})]
        scripts = lambda: {"lead": [[("spawn_agent", {"name": "one", "directories": ["core"], "instructions": "The models."}),
                                     ("spawn_agent", {"name": "two", "directories": ["core"], "instructions": "The API."})], done],
                           "one": [[("write_file", {"path": "shared.txt", "content": "from one"})], done],
                           "two": [[("read_file", {"path": "shared.txt"})], done]}
        self.run_scripts(scripts(), condition="lead")
        self.assertEqual([e["agent"] for e in self.events("spawn")], ["one"])                 # not unless the task says so
        summary = self.run_scripts(scripts(), condition="lead", task=dict(TASK, shared_tree=True, overview="One repository."))
        self.assertEqual({a: v["directories"] for a, v in summary["agents"].items() if a != "lead"}, {"one": ["core"], "two": ["core"]})
        results = {(e["agent"], e["name"]): e["result"] for e in self.events("tool")}
        self.assertEqual(results[("two", "read_file")], "from one")                           # the same files
        started = {e["agent"]: e for e in self.events("agent_start")}
        self.assertTrue(started["one"]["system"].startswith("One repository."))
        self.assertIn("work on the same files", started["one"]["system"])
        self.assertIn("may hold the same directory", started["lead"]["system"])

    def test_each_owner_can_query_its_own_copy_of_the_history(self):
        team = {a.name: a for a in build_agents(TASK, "team", self.ws, os.path.join(self.tmp, "build"))}
        self.assertTrue(os.path.isfile(os.path.join(self.ws, "services", "core", "data", "core.db")))
        self.assertFalse(os.path.exists(os.path.join(self.ws, "services", "dashboard", "data")))      # the dashboard keeps no data
        self.assertIn("query_data", [t["name"] for t in team["core"].tools])
        self.assertNotIn("query_data", [t["name"] for t in team["dashboard"].tools])
        orders = team["core"].sandbox.call("query_data", {"sql": "SELECT COUNT(*) AS n FROM docs WHERE kind = 'order'"})
        self.assertIn('{"n": 45}', orders)
        emails = team["notifications"].sandbox.call("query_data", {"sql": "SELECT COUNT(*) AS n FROM emails WHERE kind = 'order_confirmation'"})
        self.assertIn('{"n": 45}', emails)
        refused = team["core"].sandbox.call("query_data", {"sql": "DELETE FROM docs"})
        self.assertTrue(refused.startswith("exit code 1"), refused[:200])                             # read-only
        solo = build_agents(TASK, "solo", self.ws, os.path.join(self.tmp, "build"))[0]
        tool = next(t for t in solo.tools if t["name"] == "query_data")
        self.assertEqual(tool["input_schema"]["properties"]["service"]["enum"], ["core", "notifications", "payments", "subscriptions", "support", "taxes"])

    def test_rules_differ_between_conditions_only_where_they_must(self):
        build = os.path.join(self.tmp, "build")
        solo, lead, owner = (build_agents(TASK, c, self.ws, build)[0].system.splitlines() for c in ("solo", "lead", "team"))
        only = lambda a, b: [line for line in a if line not in b]
        # solo against lead: who it is, who else there is, and the lead's two extra tools
        self.assertEqual([l.split(".")[0] for l in only(solo, lead)], ["You are `solo`", "Nobody else is working on this", "- When your work is finished, call `submit`"])
        extra = "\n".join(only(lead, solo))
        self.assertIn("spawn_agent", extra)
        self.assertIn("send_message", extra)
        # an owner against the lead: what it holds, who else there is, its data, and no starting of agents
        self.assertEqual([l[:12] for l in only(owner, lead)], ["You are `cor", "Working on t", "- If you hav", "  service's ", "  empty data"])

    def test_a_long_conversation_is_replaced_by_the_agents_own_summary(self):
        from kernel.model import Reply

        class Growing(ScriptedModel):          # every call reports a conversation 60 tokens longer; a summary is plain text
            def call(self, agent, system, tools, messages):
                asked = "[conversation limit]" in messages[-1]["content"][-1]["text"]
                seen.append((len(messages), asked, messages[0]["content"][-1]["text"]))
                if asked:
                    return Reply(content=[{"type": "text", "text": "Read the notes; nothing changed yet."}], tool_uses=[], text="Read the notes; nothing changed yet.",
                                 stop_reason="end_turn", usage={"input_tokens": 10}, cost=0.01, logged=[])
                reply = super().call(agent, system, tools, messages)
                reply.usage = {"input_tokens": 60 * len(messages)}
                return reply

        seen = []
        read = [("read_file", {"path": "core/NOTES.md"})]
        log = os.path.join(self.tmp, "compact.jsonl")
        summary = run_episode(TASK, "solo", Growing({"solo": [read, read, read, [("submit", {"summary": "done"})]]}), self.ws, log, 10.0,
                              clock="turns", compact_at_tokens=150)
        self.assertEqual((summary["compactions"], summary["agents"]["solo"]["compactions"], summary["model_calls"]), (1, 1, 5))
        after = seen[[asked for _, asked, _ in seen].index(True) + 1]
        self.assertEqual(after[0], 1)                                           # the conversation starts again
        self.assertIn(TASK["solo_brief"][:40], after[2])                        # with the task as first given
        self.assertIn("replaced by the summary you wrote of it:\n\nRead the notes; nothing changed yet.", after[2])
        self.assertEqual(summary["end"], "all_submitted")

    def test_the_team_is_the_tasks_owners_and_solo_owns_the_whole_company(self):
        team = build_agents(TASK, "team", self.ws, os.path.join(self.tmp, "build"))
        self.assertEqual([a.name for a in team], ["core", "dashboard", "notifications", "taxes"])
        self.assertIn("Working on this at the same time as you: `dashboard` (owns dashboard), `notifications` (owns notifications), `taxes` (owns taxes).", team[0].system)
        self.assertEqual([t["name"] for t in team[1].tools if t["name"] == "send_message"], ["send_message"])
        solo = build_agents(TASK, "solo", self.ws, os.path.join(self.tmp, "build"))[0]
        lead = build_agents(TASK, "lead", self.ws, os.path.join(self.tmp, "build"))[0]
        for agent in (solo, lead, team[0]):    # everyone is told the same about the company, whatever the condition
            self.assertIn("notifications (Python)", agent.system)
        self.assertEqual(solo.services, ["core", "dashboard", "mobile", "notifications", "ops", "payments", "storefront",
                                         "subscriptions", "support", "taxes"])

    def test_agents_can_read_the_regression_suite_and_not_the_hidden_checks(self):
        self.assertTrue(os.path.isfile(os.path.join(self.ws, "regression", "regression_checks.py")))
        hidden = [f for _, _, files in os.walk(self.ws) for f in files if f in ("ops7_checks.py", "test_task.py")]
        # the regression suite's own criteria are there to read; a feature criterion never is
        hidden += [d for d, _, files in os.walk(self.ws) if "rubric.toml" in files and 'kind = "feature"' in open(os.path.join(d, "rubric.toml")).read()]
        self.assertEqual(hidden, [], "the workspace holds verifier files")
        for agent in build_agents(TASK, "team", self.ws, os.path.join(self.tmp, "build")) + build_agents(TASK, "solo", self.ws, os.path.join(self.tmp, "build")):
            self.assertLessEqual({"run_regression", "read_regression"}, {t["name"] for t in agent.tools})
            listed = agent.sandbox.call("read_regression", {})
            self.assertIn("regression_checks.py", listed)
            self.assertIn("def test_core_storefront__a_customer_buys_in_the_web_shop", agent.sandbox.call("read_regression", {"path": "regression_checks.py"}))
            for path in ("../services/core/src/core.py", "/etc/passwd", "../../../tasks/task01_order_confirmation/hidden/rubric.toml"):
                self.assertTrue(agent.sandbox.call("read_regression", {"path": path}).startswith("ERROR:"), path)

    def test_the_rubric_gives_credit_per_ticket_and_charges_for_regressions(self):
        from kernel import rubric
        checks = os.path.join(self.tmp, "checks")
        os.makedirs(checks)
        with open(os.path.join(checks, "rubric.toml"), "w") as f:
            f.write("""
[[criterion]]
id = "keeps-readme"
kind = "regression"
type = "command"
run = "test -f README"
note = "The README is still there."

[[criterion]]
id = "keeps-licence"
kind = "regression"
type = "command"
run = "test -f LICENCE"
note = "The licence is still there."

[[criterion]]
id = "a-done"
ticket = "A"
kind = "feature"
type = "command"
run = "test -f a"
weight = 3
note = "Ticket A's file exists."

[[criterion]]
id = "b-done"
ticket = "B"
kind = "feature"
type = "command"
run = "test -f b"
note = "Ticket B's file exists."

[[criterion]]
id = "b-reads-well"
ticket = "B"
kind = "feature"
type = "judge"
files = ["b"]
prompt = "Is b written clearly?"
note = "Only a reader can tell."
""")
        company = os.path.join(self.tmp, "company")
        os.makedirs(company)

        def have(*names):
            for name in ("README", "LICENCE", "a", "b"):
                path = os.path.join(company, name)
                if name in names:
                    open(path, "w").write("clear\n")
                elif os.path.exists(path):
                    os.remove(path)
            return rubric.run(company, [checks], os.path.join(REPO, "platform"))

        untouched = have("README", "LICENCE")
        self.assertEqual((untouched["reward"], untouched["progress"], untouched["regression"]), (0.0, 0.0, 1.0))
        self.assertEqual(untouched["not_run"], ["b-reads-well"])            # no judge: left out, and said so
        part = have("README", "LICENCE", "a")
        self.assertEqual((part["reward"], part["tickets"]), (0.75, {"A": 1.0, "B": 0.0}))      # weights 3 and 1
        broke = have("README", "a", "b")
        self.assertEqual((broke["progress"], broke["regression"], broke["reward"]), (1.0, 0.5, 0.5))
        asked = []
        judged = rubric.run(company, [checks], os.path.join(REPO, "platform"),
                            ask=lambda system, question: asked.append(question) or "It only says clear.\nVERDICT: FAIL")
        self.assertIn("=== b ===\nclear", asked[0])
        self.assertEqual((judged["progress"], judged["not_run"]), (0.8, []))                   # 4 of 5 by weight
        self.assertIn("FAIL  feature    B        judge   b-reads-well", rubric.table(judged))

    def test_a_run_is_kept_as_one_atif_trajectory_per_agent(self):
        from kernel import atif
        scripts = {"core": [[("read_file", {"path": "NOTES.md"}), ("send_message", {"to": "taxes", "text": "the event is ORDER_CONFIRMED"})],
                            [("submit", {"summary": "done"})]],
                   "taxes": [[("submit", {"summary": "done"})]], "dashboard": [[("submit", {"summary": "done"})]],
                   "notifications": [[("submit", {"summary": "done"})]]}
        log = os.path.join(self.tmp, "run-1", "events.jsonl")
        run_episode(TASK, "team", ScriptedModel(scripts, dollars_per_call=0.25), self.ws, log, 10.0)
        paths = atif.write(os.path.dirname(log))
        self.assertEqual(sorted(os.path.basename(p) for p in paths), ["core.json", "dashboard.json", "notifications.json", "taxes.json"])
        core = json.load(open(os.path.join(self.tmp, "run-1", "trajectories", "core.json")))
        self.assertEqual((core["schema_version"], core["session_id"], core["agent"]["extra"]["directories"]), ("ATIF-v1.8", "run-1:core", ["core"]))
        self.assertEqual([s["source"] for s in core["steps"]], ["system", "user", "agent", "user", "agent"])
        self.assertEqual([s["step_id"] for s in core["steps"]], [1, 2, 3, 4, 5])
        self.assertIn("You are `core`.", core["steps"][0]["message"])
        self.assertIn("OPS-7", core["steps"][1]["message"])                              # the brief, as the agent was given it
        first = core["steps"][2]
        self.assertEqual([c["function_name"] for c in first["tool_calls"]], ["read_file", "send_message"])
        answered = {r["source_call_id"]: r["content"] for r in first["observation"]["results"]}
        self.assertEqual(set(answered), {c["tool_call_id"] for c in first["tool_calls"]})   # every call has its result
        self.assertIn("Core: owner's notes", answered[first["tool_calls"][0]["tool_call_id"]])
        self.assertEqual((first["metrics"]["cost_usd"], core["final_metrics"]["total_cost_usd"], core["final_metrics"]["total_steps"]), (0.25, 0.5, 5))
        taxes = json.load(open(os.path.join(self.tmp, "run-1", "trajectories", "taxes.json")))
        self.assertIn("Message from core:\nthe event is ORDER_CONFIRMED", "".join(s["message"] for s in taxes["steps"] if s["source"] == "user"))

    def test_agents_get_the_logs_of_the_history_and_no_shell_without_a_container(self):
        task3 = os.path.join(REPO, "tasks", "task03_payment_incidents")
        ws = prepare_workspace(REPO, task3, os.path.join(self.tmp, "ws3"))
        log = os.path.join(ws, "services", "core", "logs", "production.log")
        self.assertIn("refund request sent again", open(log).read())
        self.assertFalse(os.path.exists(os.path.join(ws, "services", "payments", "logs", "core.log")))     # each owner gets its own log only
        agents = build_agents(json.load(open(os.path.join(task3, "task.json"))), "team", ws, os.path.join(self.tmp, "build3"))
        payments = next(a for a in agents if a.name == "payments")
        self.assertIn("payments listening", payments.sandbox.call("read_file", {"path": "logs/production.log"}))
        self.assertTrue(payments.sandbox.call("read_file", {"path": "../core/logs/production.log"}).startswith("ERROR:"))
        self.assertNotIn("shell", [t["name"] for t in payments.tools])                     # a shell here would see the verifier's files
        self.assertTrue(payments.sandbox.call("shell", {"command": "ls /"}).startswith("ERROR:"))

    def test_the_harbor_export_is_what_its_sources_say(self):
        """harbor/ holds copies (the rubric, the checks, the company). A copy that has fallen behind fails here."""
        import subprocess
        import sys
        if not os.path.isdir(os.path.join(REPO, "harbor")):
            self.skipTest("nothing has been exported")
        check = subprocess.run([sys.executable, os.path.join(REPO, "tools", "export_harbor.py"), REPO, "--check"], capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr[-800:])

    def test_ports_are_cleared_before_a_company_is_started(self):
        import socket
        import subprocess
        import sys
        sys.path.insert(0, os.path.join(REPO, "platform"))
        from stack import free_ports
        if not os.path.exists("/proc/net/tcp"):
            self.skipTest("needs /proc (Linux)")
        squatter = subprocess.Popen([sys.executable, "-c", "import socket, time; s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); "
                                     "s.bind(('127.0.0.1', 7455)); s.listen(); print('up', flush=True); time.sleep(600)"], stdout=subprocess.PIPE)
        try:
            squatter.stdout.readline()
            self.assertEqual(free_ports([7455, 7456]), {7455: [squatter.pid]})
            self.assertEqual(squatter.wait(timeout=5), -9)
            with socket.socket() as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", 7455))                                  # the port is free again
            self.assertEqual(free_ports([7455, 7456]), {})
        finally:
            squatter.kill()


if __name__ == "__main__":
    unittest.main()

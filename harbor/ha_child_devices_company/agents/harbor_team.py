"""A fixed team under Harbor: one stock harness per owner, each at a seat (a container) of its own.

    harbor run -p harbor/<company>_team --agent-import-path harbor_team:TeamClaudeCode --ak seats=main=core,seat-dashboard=dashboard ...

Harbor knows one agent in one container. This agent is that one agent, and what it does is start the same
harness at every seat at the same time and wait for all of them. Each harness is given the task's instruction
followed by a few lines saying whose seat it is. Nothing else differs between seats, and nothing differs from
the solo task but the seats: who may push where is the git server's, and messaging (if the task has it) is a
tool the task registers.

`seat_notes`: what each seat's holder is told about the seat (role, permissions, tools), kept apart from the brief:
a file for one seat, a directory of <owner>.md for a team. Given it, the brief goes to every seat unchanged and the
note is added to the harness's system prompt; without it the older seat paragraph is appended to the brief.

`seats`: service=owner pairs; the first must be `main`. `isolated=true` says what a task with one repository per seat
(nothing of the others readable) is: the seat's paragraph then says so. `messaging=false` leaves the task's messaging tools out.
A seat's harness log is at /logs/agent in its own container; the task mounts each extra seat's under
<trial>/agent/<owner>/.
"""
import asyncio
import json
import os
import re
import shlex
import subprocess
import time

from harbor.agents.installed.base import CliFlag, NonZeroAgentExitCodeError
from harbor.agents.installed.claude_code import ClaudeCode

SEAT = """

## Your seat

You are `{owner}`, the owner of the `{owner}` repository: you may push to `{owner}`, and you can read {others_repos} but
not push to {them}. {others} at the same time as you, each at a seat of their own.{messaging}"""
SEAT_ISOLATED = """

## Your seat

You are `{owner}`, the owner of the `{owner}` repository: it is the one repository you have, and you may push to it.
You cannot read or push to {others_repos}, and of the running company you can look at what your repository's
`NOTES.md` names. {others} at the same time as you, each at a seat of their own.{messaging}"""
WITH_MESSAGING = (" You can reach them with the `send_message` tool; `read_messages` shows what has reached you and "
                  "`wait_for_message` waits for it. They see what you push, not your checkout or your conversation, so anything "
                  "else they need from you has to be said. Someone who has finished reads no more messages.")
NO_MESSAGING = " There is no way to contact them: work from what you can read yourself."
CHAT_ADMIN = "chat-admin-5d02e7"


class Seat:
    """The environment, with commands going to another container of it."""

    def __init__(self, environment, service):
        self._environment, self._service = environment, service

    def __getattr__(self, name):
        return getattr(self._environment, name)

    async def exec(self, command, cwd=None, env=None, timeout_sec=None, user=None):
        e = self._environment
        user, env = e._resolve_user(user), e._merge_env(env)
        args = ["exec"]
        if cwd:
            args += ["-w", cwd]
        for key, value in (env or {}).items():
            args += ["-e", "{}={}".format(key, value)]
        if user is not None:
            args += ["-u", str(user)]
        return await e._run_docker_compose_command(args + [self._service, "bash", "-c", command], check=False, timeout_sec=timeout_sec)


# A limit on the model service is a pause, not the end of the work. The seat's container and checkout outlive the
# refusal; only the harness process exits. So the seat waits out the limit and takes up the same session again.
LIMIT = re.compile(r"\b429\b|\b529\b|rate.?limit|overloaded|cooling down", re.I)
RESET = re.compile(r"reset after (?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?")
RESUMED = ("The model service refused requests for a while (a rate limit), and this session was paused until it lifted. "
           "Anything you had running in the background was stopped with the session; start again what you still need. "
           "Nothing else has changed. Carry on with the work from where you stopped.")
# Ends the harness and every process under it (its background jobs among them), and nothing else of the seat: the
# seat's own services (its database, say) keep running.
KILL_HARNESS = ("all=$(pgrep -f '[c]laude --verbose'); next=$all; "
                "while [ -n \"$next\" ]; do next=$(for p in $next; do pgrep -P $p; done); all=\"$all $next\"; done; "
                "[ -n \"$all\" ] && kill -KILL $all 2>/dev/null; true")
CHAT = ("curl -s -m 10 -X POST -H 'Content-Type: application/json' "
        "-d \"{{\\\"name\\\": \\\"$SEAT\\\", \\\"token\\\": \\\"$SEAT_TOKEN\\\"{more}}}\" http://chat:8080/{what} >/dev/null 2>&1 || true")


class SeatClaudeCode(ClaudeCode):
    """Claude Code as Harbor runs it, with two additions.

    `thinking_display=summarized`: left to itself the harness asks the API to leave the text of the model's reasoning
    out, and the trajectory then holds empty thinking blocks. With it the reasoning is recorded.

    A session the model service ends with a rate limit is resumed (`--resume`, same session, same log) once the limit
    lifts: after the time the refusal names, or `resume_wait_sec` when it names none. What is left of the spend cap
    carries over. A wait that would end later than `resume_within_sec` after the seat started is not begun. In a
    team the chat is told, so the others see the seat as paused and not as finished."""
    CLI_FLAGS = ClaudeCode.CLI_FLAGS + [CliFlag("thinking_display", cli="--thinking-display", type="str")]

    def __init__(self, *args, resume_within_sec=12000, resume_wait_sec=600, work_sec=None, wall_sec=None, seat_notes=None, seat_cap="", seat_total="", seat_hours="", **kwargs):
        super().__init__(*args, **kwargs)
        self._resume_within, self._resume_wait = float(resume_within_sec), float(resume_wait_sec)
        self._wall = float(wall_sec) if wall_sec else self._resume_within + 1800      # Harbor's timeout for the agent, less room to end
        self._work = float(work_sec) if work_sec else (float(seat_hours) * 3600 if seat_hours else float("inf"))
        self._seat_notes = str(seat_notes) if seat_notes else None      # a file (one seat) or a directory of <owner>.md
        self._seat_figures = {"cap": seat_cap, "total": seat_total, "hours": seat_hours}
        self._launched = {}      # seat -> (command, env, cwd) of the harness as it was started there
        self._ended_by_runner = {}      # seat -> why the runner ended a stretch of its harness, each time it did

    @staticmethod
    def name() -> str:
        return "seat-claude-code"

    def _owner(self, seat):
        return seat

    def seat_note(self, seat):
        """What this seat's holder is told about the seat itself: role, permissions, tools. It is no part of the
        brief, which is the same for every condition; the harness is given it as an addition to its system prompt."""
        if not self._seat_notes:
            return None
        path = self._seat_notes if os.path.isfile(self._seat_notes) else os.path.join(self._seat_notes, self._owner(seat) + ".md")
        with open(path) as f:
            note = f.read().strip()
        for name, value in self._seat_figures.items():
            note = note.replace("{" + name + "}", str(value))
        return note

    async def exec_as_agent(self, environment, command, env=None, cwd=None, timeout_sec=None):
        note = self.seat_note(getattr(environment, "_service", "main")) if "--print -- " in command and "--resume " not in command else None
        if note:
            command = command.replace("--print -- ", "--append-system-prompt {} --print -- ".format(shlex.quote(note)), 1)
            await environment.exec("mkdir -p /logs/agent && cat > /logs/agent/seat-note.md <<'SEAT_NOTE_END'\n{}\nSEAT_NOTE_END".format(note))
        if os.environ.get("METER") and env and env.get("ANTHROPIC_BASE_URL"):      # each seat reaches the model through the meter, under its own name
            env = dict(env, ANTHROPIC_BASE_URL="{}/{}".format(os.environ["METER"].rstrip("/"), self._owner(getattr(environment, "_service", "main"))))
        if "--print -- " in command and "--resume " not in command:
            self._launched[getattr(environment, "_service", "main")] = (command, env, cwd)
        return await super().exec_as_agent(environment, command, env=env, cwd=cwd, timeout_sec=timeout_sec)

    async def _results(self, environment):
        """Every result record the harness has written at this seat: one per time it was started."""
        got = await environment.exec("grep -a '\"type\":\"result\"' /logs/agent/claude-code.txt || true")
        records = []
        for line in (got.stdout or "").splitlines():
            try:
                records.append(json.loads(line))
            except ValueError:
                pass
        return records

    TRAJECTORY_EVERY_S = 300      # how often each seat's trajectory is written while it works

    def _seat_logs(self, seat):
        """The seat's harness logs on this machine: Harbor's own for its seat, <logs>/<owner> for every other seat."""
        from pathlib import Path
        return Path(self.logs_dir) if seat == "main" else Path(self.logs_dir) / self._owner(seat)

    def write_trajectory(self, seat):
        """Writes the seat's trajectory, in ATIF, from its Claude Code session files: `trajectory.json` in the seat's
        logs. The same conversion Harbor makes for its own seat once the run is over, here for every seat, and
        while the work goes on, so that a run that breaks off still leaves one. Returns the number of steps."""
        logs = self._seat_logs(seat)
        converter = ClaudeCode(logs_dir=logs, model_name=self.model_name)
        session = converter._get_session_dir()
        trajectory = converter._convert_events_to_trajectory(session) if session else None
        if not trajectory:
            return 0
        written = trajectory.to_json_dict()
        written.setdefault("agent", {})["model_name"] = self.model_name      # the converter can leave "<synthetic>"
        written["agent"].setdefault("extra", {})["seat"] = self._owner(seat)
        path = os.path.join(str(logs), "trajectory.json")
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(written, f, indent=2, ensure_ascii=False)
        os.replace(path + ".tmp", path)
        return len(written.get("steps", []))

    async def _keep_trajectory(self, seat):
        """Writes the seat's trajectory every few minutes until cancelled."""
        while True:
            await asyncio.sleep(self.TRAJECTORY_EVERY_S)
            try:
                await asyncio.to_thread(self.write_trajectory, seat)
            except Exception as e:      # the record is beside the work: never let it stop the work
                print("seat {}: trajectory not written: {}".format(seat, e), flush=True)

    def populate_context_post_run(self, context):
        super().populate_context_post_run(context)
        try:      # Harbor's own conversion of its seat: put the model's name back
            self.write_trajectory("main")
        except Exception as e:
            print("trajectory not rewritten: {}".format(e), flush=True)

    @staticmethod
    def _spent(records):
        """What the seat has spent. The harness reports a session's cost as a running total, and a resumed session
        carries its total on: the spend is the largest total, not the sum of them."""
        return max([float(r.get("total_cost_usd") or 0) for r in records] or [0.0])

    def _pause(self, record, waited):
        """Seconds to wait if this result is the model service refusing for a while; None if it is anything else."""
        if not record or not record.get("is_error") or not LIMIT.search(str(record.get("result") or "")):
            return None
        named = RESET.search(str(record.get("result")))
        if named and any(named.groups()):
            h, m, sec = (int(g or 0) for g in named.groups())
            return h * 3600 + m * 60 + sec + 60
        return min(self._resume_wait * 2 ** waited, 3600)

    WATCH_EVERY_S = 15      # how often the harness's log is read while it runs
    FINISH_GRACE_S = 30     # how long a harness that has given its final answer may take to exit by itself

    async def _working(self, environment, seat, step, limit):
        """Runs one stretch of the harness for at most `limit` seconds of working time. Returns (failure, out of time).

        The stretch also ends on what the harness writes, not only when it exits. A harness keeps running while a
        job it started in the background is alive, and wakes on it later: so a turn the model service ended with a
        rate limit sat idle until the job's own timeout instead of pausing, and an answer given as final was
        reopened by a leftover job, re-caching the whole conversation. Now a rate limit ends the stretch at once (and
        the seat pauses as usual), and a final answer ends it after FINISH_GRACE_S: when you stop, the work stops, as
        every seat is told. Ending it stops the harness and everything it started, and nothing else of the seat."""
        before = len(await self._results(environment))
        task = asyncio.ensure_future(step)
        deadline, answered, ended_by_us, out_of_time = time.time() + max(0.05, limit), None, None, False
        while not task.done():
            await asyncio.wait({task}, timeout=max(0.01, min(self.WATCH_EVERY_S, deadline - time.time())))
            if task.done():
                break
            if time.time() >= deadline:      # the seat's working time is up, as the task's own timeout would end it
                ended_by_us, out_of_time = "working time is up", True
            else:
                records = await self._results(environment)
                last = records[-1] if len(records) > before else None
                if last is not None and self._pause(last, 0) is not None:
                    ended_by_us = "a rate limit ended its turn while a background job kept the harness running"
                elif last is not None and not last.get("is_error"):
                    answered = answered or time.time()
                    if time.time() - answered >= self.FINISH_GRACE_S:
                        ended_by_us = "it gave its final answer and a background job kept the harness running"
            if ended_by_us:
                await environment.exec(KILL_HARNESS)
                print("seat {}: harness ended: {}".format(seat, ended_by_us), flush=True)
                self._ended_by_runner.setdefault(seat, []).append(ended_by_us)
                break
        try:
            await task
            return None, out_of_time
        except NonZeroAgentExitCodeError as e:
            return (None if ended_by_us else e), out_of_time

    async def run(self, instruction, environment, context):
        """Paused time is not working time. The seat works for at most `work_sec` (the task's agent timeout) of time
        when the model service is answering; a wait for a limit to lift is not counted against it. Harbor's own timeout
        is set wider (tools/harbor_harness.sh) to leave room for the waits, and `resume_within_sec` (wall time from the
        seat's start) is the last moment a wait may end. How the seat's work ended is written to /logs/agent/seat-run.json:
        a stop by the model service makes the run incomplete, whatever the score."""
        seat, started, failure, waited, paused = getattr(environment, "_service", "main"), time.time(), None, 0, 0.0
        keeping = asyncio.create_task(self._keep_trajectory(seat))
        try:
            return await self._run(instruction, environment, context, seat, started, waited, paused)
        finally:
            keeping.cancel()
            try:
                steps = await asyncio.to_thread(self.write_trajectory, seat)
                print("seat {}: trajectory written ({} steps)".format(seat, steps), flush=True)
            except Exception as e:
                print("seat {}: trajectory not written: {}".format(seat, e), flush=True)

    async def _run(self, instruction, environment, context, seat, started, waited, paused):
        failure, out_of_time = await self._working(environment, seat, super().run(instruction, environment, context), self._work)
        ended = "working time up" if out_of_time else None
        while seat in self._launched and not ended:
            records = await self._results(environment)
            wait = self._pause(records[-1] if records else None, waited)
            if wait is None:
                break
            if time.time() + wait - started > self._resume_within:
                ended = "stopped by the model service: its limit lifts after the run's last moment to resume"
                break
            await environment.exec(CHAT.format(what="paused", more=", \\\"until\\\": {}".format(int(time.time() + wait))))
            print("seat {}: paused by a limit on the model service for {:.0f} s".format(seat, wait), flush=True)
            await asyncio.sleep(wait)
            paused += wait
            await environment.exec(CHAT.format(what="resumed", more=""))
            waited += 1
            command, env, cwd = self._launched[seat]
            again = "--resume {} --print -- {} 2>&1 </dev/null | tee -a ".format(records[-1]["session_id"], shlex.quote(RESUMED))
            command = re.sub(r"--print -- .* 2>&1 </dev/null \| tee ", lambda _: again, command, flags=re.S)
            spent = self._spent(records)
            command = re.sub(r"--max-budget-usd (\S+)", lambda m: "--max-budget-usd {:.2f}".format(max(0.01, float(m.group(1)) - spent)), command)
            left = self._work - (time.time() - started - paused)
            wall = self._wall - (time.time() - started)      # Harbor's own timeout, less room to end cleanly
            if left <= 0:
                ended = "working time up"
                break
            failure, out_of_time = await self._working(environment, seat, super().exec_as_agent(environment, command, env=env, cwd=cwd), min(left, wall))
            if out_of_time:
                ended = "working time up" if left <= wall else "stopped by the model service: its waits left too little of the run's time to finish"
        records = await self._results(environment)
        if not ended:
            last = records[-1] if records else None
            ended = "finished" if last and not last.get("is_error") else "budget spent" if last and last.get("subtype") == "error_max_budget_usd" else "the harness ended with an error: {}".format(str((last or {}).get("result") or failure)[:300])
        run = {"seat": seat, "ended": ended, "stopped_from_outside": ended.startswith("stopped by"),
               "working_s": round(time.time() - started - paused), "paused_s": round(paused), "pauses": waited,
               "work_limit_s": self._work, "spent_usd": round(self._spent(records), 2),
               "ended_by_runner": self._ended_by_runner.get(seat, [])}
        await environment.exec("mkdir -p /logs/agent && cat > /logs/agent/seat-run.json <<'SEAT_RUN_END'\n{}\nSEAT_RUN_END".format(json.dumps(run)))
        if type(self) is SeatClaudeCode:
            await self.keep_environment_records(environment)
        if failure and ended != "budget spent" and not ended.startswith("stopped by"):
            raise failure

    async def keep_environment_records(self, environment):
        """What the company itself recorded of the work, kept beside the harness logs before the company is taken
        down: who fetched and pushed what at the git server (and what it refused), and every CI run. These are the
        environment's own records: they do not depend on which harness was at the seats."""
        try:
            await environment.exec("curl -s -m 20 http://ci:8080/status.json > /logs/agent/ci.json || true")
            names = subprocess.run(["docker", "ps", "--filter", "label=com.docker.compose.service=git", "--format", "{{.Names}}"],
                                   capture_output=True, text=True, timeout=30).stdout.split()
            if len(names) == 1:
                kept = subprocess.run(["docker", "exec", names[0], "cat", "/srv/log.jsonl"], capture_output=True, text=True, timeout=30).stdout
                with open(os.path.join(str(self.logs_dir), "git.jsonl"), "w") as f:
                    f.write(kept)
            else:
                print("the git server's record was not kept: {} git servers are running".format(len(names)), flush=True)
        except Exception as e:      # keeping records is beside the work
            print("the environment's records were not kept: {}".format(e), flush=True)


class TeamClaudeCode(SeatClaudeCode):
    def __init__(self, *args, seats="main=core,seat-dashboard=dashboard", messaging="true", isolated="false", **kwargs):
        super().__init__(*args, **kwargs)
        self._isolated = str(isolated).lower() in ("true", "1", "yes")      # the task gives each seat its own repository only
        self._seats = [tuple(pair.split("=", 1)) for pair in str(seats).split(",")]
        self._messaging = str(messaging).lower() not in ("false", "0", "no")
        if not self._messaging:
            self.mcp_servers = []

    @staticmethod
    def name() -> str:
        return "team-claude-code"

    def _owner(self, seat):
        return dict(self._seats).get(seat, seat)

    def _at(self, environment, service):
        return environment if service == "main" else Seat(environment, service)

    async def install(self, environment):
        await asyncio.gather(*(super(TeamClaudeCode, self).install(self._at(environment, service)) for service, _ in self._seats))

    async def run(self, instruction, environment, context):
        owners = [owner for _, owner in self._seats]

        async def one(service, owner):
            others = [o for o in owners if o != owner]
            told = instruction if self._seat_notes else instruction + (SEAT_ISOLATED if self._isolated else SEAT).format(
                owner=owner, others_repos=", ".join("`{}`".format(o) for o in others), them="them" if len(others) > 1 else "it",
                others=("The owners of {} are" if len(others) > 1 else "The owner of {} is").format(", ".join("`{}`".format(o) for o in others)) + " working on this",
                messaging=WITH_MESSAGING if self._messaging else NO_MESSAGING)
            seat = self._at(environment, service)
            try:
                await super(TeamClaudeCode, self).run(told, seat, context)
            finally:        # whoever has finished reads no more messages
                await seat.exec("curl -s -m 10 -X POST -H 'Content-Type: application/json' -d \"{\\\"name\\\": \\\"$SEAT\\\", \\\"token\\\": \\\"$SEAT_TOKEN\\\"}\" http://chat:8080/done || true")

        results = await asyncio.gather(*(one(service, owner) for service, owner in self._seats), return_exceptions=True)
        await environment.exec("curl -s -m 10 'http://chat:8080/log?token={}' > /logs/agent/chat.json || true".format(CHAT_ADMIN))
        await self.keep_environment_records(environment)
        failed = [r for r in results if isinstance(r, Exception)]
        if failed:
            raise failed[0]

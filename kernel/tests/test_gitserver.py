"""The git server enforces who may push where, the same way under every condition. Needs Docker."""
import os
import shutil
import subprocess
import tempfile
import unittest

from kernel import gitserver


def docker_ready():
    if not shutil.which("docker"):
        return False
    return subprocess.run(["docker", "image", "inspect", gitserver.IMAGE], capture_output=True).returncode == 0


class Grants(unittest.TestCase):
    def test_conditions_differ_only_in_the_table(self):
        team = gitserver.grants("team", {"api": ["core"], "web": ["dashboard"]}, others="read")
        self.assertEqual(team, {"api": {"core": "write", "dashboard": "read"}, "web": {"dashboard": "write", "core": "read"}})
        strict = gitserver.grants("team", {"api": ["core"], "web": ["dashboard"]}, others="none")
        self.assertEqual(strict, {"api": {"core": "write"}, "web": {"dashboard": "write"}})
        solo = gitserver.grants("solo", {"solo": ["core", "dashboard"]})
        self.assertEqual(solo, {"solo": {"core": "write", "dashboard": "write"}})


@unittest.skipUnless(docker_ready(), "needs Docker and the toolchain image")
class Server(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        for name in ("core", "dashboard"):
            os.makedirs(os.path.join(cls.tmp, name))
            with open(os.path.join(cls.tmp, name, "README"), "w") as f:
                f.write(name + "\n")
        cls.server = gitserver.GitServer("test-gitserver")
        cls.server.start({n: os.path.join(cls.tmp, n) for n in ("core", "dashboard")},
                         gitserver.grants("lead", {"lead": ["core", "dashboard"]}))

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def git(self, script):
        """Runs a shell script inside the server's container, as a client talking to it over HTTP."""
        p = subprocess.run(["docker", "exec", self.server.name, "sh", "-c", "export GIT_TERMINAL_PROMPT=0; " + script],
                           capture_output=True, text=True, timeout=120)
        return p.returncode, p.stdout + p.stderr

    def url(self, agent, repository):
        return self.server.url(agent, repository, host="127.0.0.1")

    def push(self, agent, repository, name):
        return self.git("d=$(mktemp -d) && git clone -q {} $d && cd $d && echo {} > {} && git add -A && git commit -qm change && git push -q origin main"
                        .format(self.url(agent, repository), name, name))

    def test_holder_pushes_and_main_is_what_gets_exported(self):
        code, out = self.push("lead", "core", "by-lead")
        self.assertEqual(code, 0, out)
        out_dir = tempfile.mkdtemp()
        self.server.export("core", out_dir)
        self.assertTrue(os.path.exists(os.path.join(out_dir, "by-lead")))
        moved = [e for e in self.server.log() if e["action"] == "moved"]
        self.assertTrue(any(e["agent"] == "lead" and e["repository"] == "core" and e["ref"] == "refs/heads/main" for e in moved))

    def test_lead_gives_only_what_it_holds_and_the_server_holds_the_line(self):
        self.server.grant("lead", "web", {"dashboard": "write", "core": "read"})
        self.assertEqual(self.push("web", "dashboard", "by-web")[0], 0)
        code, out = self.push("web", "core", "by-web")              # can read core, cannot push to it
        self.assertNotEqual(code, 0)
        self.assertIn("403", out)
        self.assertTrue(any(e["agent"] == "web" and e["repository"] == "core" and e["action"] == "push" and not e["allowed"]
                            for e in self.server.log()))
        with self.assertRaises(PermissionError):                    # web cannot pass on more than it has
            self.server.grant("web", "helper", {"core": "write"})
        self.server.grant("web", "helper", {"core": "read"})
        self.assertEqual(self.git("git ls-remote {} >/dev/null".format(self.url("helper", "core")))[0], 0)
        self.assertNotEqual(self.git("git ls-remote {}".format(self.url("helper", "dashboard")))[0], 0)   # never given

    def test_no_token_no_access(self):
        code, out = self.git("git ls-remote http://127.0.0.1:{}/core.git".format(gitserver.PORT))
        self.assertNotEqual(code, 0)
        code, out = self.git("git ls-remote http://lead:wrong@127.0.0.1:{}/core.git".format(gitserver.PORT))
        self.assertNotEqual(code, 0)

    def test_two_writers_of_one_repository_collide(self):
        self.server.grant("lead", "second", {"core": "write"})
        code, out = self.git("a=$(mktemp -d) && b=$(mktemp -d) && git clone -q {0} $a && git clone -q {1} $b "
                             "&& cd $a && echo one > one && git add -A && git commit -qm one && git push -q origin main "
                             "&& cd $b && echo two > two && git add -A && git commit -qm two && git push -q origin main"
                             .format(self.url("lead", "core"), self.url("second", "core")))
        self.assertNotEqual(code, 0)                                # the second push is behind main: it must merge first
        self.assertIn("rejected", out)


if __name__ == "__main__":
    unittest.main()

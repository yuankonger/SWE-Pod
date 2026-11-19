"""One container per agent, for running that agent's tests.

An agent's tests are code the agent wrote, so they must not be able to read another owner's files or reach
another owner's service. In this mode each owner agent gets a container that holds only its own directory and
has no network; the solo agent gets one that holds every owner's directory. The kernel still reads and writes
files itself, confined to the agent's directory; only test runs happen inside the container.

Needs the `docker` command, so the kernel runs on the host in this mode, not inside the toolchain image.
"""
import os
import subprocess

IMAGE = "seedco-toolchain:0.4"
TEST_TIMEOUT_S = 300


class Containers:
    def __init__(self, run_id: str, image: str = IMAGE, images: dict = None, env: dict = None, network: bool = False):
        """`images` ({directory: image}): each directory has a toolchain of its own, so an agent gets one container
        per directory it holds, not one for all of them. `env` ({directory: {name: value}}) is set in them.
        `network`: the containers of this run can reach each other, and nothing else, each under its directory's
        name; without it a container has no network at all."""
        self.image = image
        self.images = dict(images or {})
        self.env = dict(env or {})
        self.prefix = "seedco-{}".format("".join(c if c.isalnum() else "-" for c in run_id.lower()))[:48]
        self.names = {}          # agent -> container, or (agent, directory) -> container when each directory has its own
        self.hosts = set()       # the names taken on the run's network
        self.network = None
        if network:
            self.network = self.prefix + "-net"
            subprocess.run(["docker", "network", "rm", self.network], capture_output=True)
            made = subprocess.run(["docker", "network", "create", "--internal", self.network], capture_output=True, text=True)
            if made.returncode != 0:
                raise RuntimeError("could not make a network for the run: {}".format(made.stderr.strip()[-300:]))

    def _start(self, key, name: str, image: str, mounts: list, host: str = None, env: dict = None, plain: bool = True):
        net = ["--network", "none"]
        if self.network:
            net = ["--network", self.network]
            if host:
                net += ["--network-alias", "{}-{}".format(key[0], host)]      # every container: <agent>-<directory>
                if plain and host not in self.hosts:     # and the first holder of a directory answers to its name alone
                    net += ["--network-alias", host]
                    self.hosts.add(host)
        variables = [x for k, v in (env or {}).items() for x in ("-e", "{}={}".format(k, v))]
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        started = subprocess.run(["docker", "run", "-d", "--rm", "--name", name] + net + variables + mounts
                                 + [image, "sleep", "infinity"], capture_output=True, text=True)
        if started.returncode != 0:
            raise RuntimeError("could not start a container for {}: {}".format(key, started.stderr.strip()[-500:]))
        self.names[key] = name

    def start(self, agent: str, services_dir: str, services: list, named: list = None):
        """Starts the agent's container, or one per directory when directories have images of their own.
        `services_dir` is the workspace's services directory on this machine. `named`: the directories for which
        this agent's container may answer to the directory's name alone (default: all); with a git server, the ones
        the agent may push to, so that a reader's copy never stands in for the owner's.

        Besides the agent's own directories a container holds, read-only, what every agent may see: the stack runner
        and the regression suite. With every directory, that is enough to start the whole company inside it."""
        shared = []
        for part in ("platform", "regression"):
            path = os.path.join(os.path.dirname(services_dir), part)
            if os.path.isdir(path):
                shared += ["-v", "{}:/work/{}:ro".format(path, part)]
        if self.images:
            for s in services:
                self._start((agent, s), "{}-{}-{}".format(self.prefix, agent, s), self.images[s],
                            ["-v", "{}/{}:/work/services/{}".format(services_dir, s, s)] + shared, s, self.env.get(s),
                            named is None or s in named)
            return
        mounts = []
        for s in services:
            mounts += ["-v", "{}/{}:/work/services/{}".format(services_dir, s, s)]
        self._start(agent, "{}-{}".format(self.prefix, agent), self.image, mounts + shared)

    def execute(self, agent: str, command: list, workdir: str = "/work/services", timeout: float = TEST_TIMEOUT_S, service: str = None):
        """Runs a command in the agent's container (the one for `service`, when it has one per directory).
        Returns (exit code, output)."""
        name = self.names[(agent, service)] if self.images else self.names[agent]
        try:
            p = subprocess.run(["docker", "exec", "-w", workdir, name] + command,
                               capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return None, ""
        return p.returncode, p.stdout + p.stderr

    def run(self, agent: str, service: str, args: list):
        """Runs one owner's `./run <args>` in the agent's container. Returns (exit code, output); None means it timed out."""
        return self.execute(agent, ["env", "SEEDCO_BUILD_DIR=/tmp/seedco-build/" + service, "./run"] + list(args),
                            "/work/services/" + service, service=service if self.images else None)

    def regression(self, workspace: str, timeout: float):
        """Runs the workspace's regression suite in a container of its own that holds the whole company and has no
        network. Returns (exit code, output); None means it timed out."""
        name = "{}-regression".format(self.prefix)
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        try:
            p = subprocess.run(["docker", "run", "--rm", "--network", "none", "--name", name, "-e", "PYTHONDONTWRITEBYTECODE=1",
                                "-e", "SEEDCO_ROOT=/work", "-e", "SEEDCO_LOG_DIR=/work/.regression-logs",
                                "-v", workspace + ":/work", "-w", "/work/regression", self.image,
                                "python3", "-m", "unittest", "-v", "test_regression"], capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True)
            return None, ""
        return p.returncode, p.stdout + p.stderr

    def stop(self):
        for name in self.names.values():
            subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        self.names = {}
        if self.network:
            subprocess.run(["docker", "network", "rm", self.network], capture_output=True)


def score(task_dir: str, workspace: str, kernel_dir: str, image: str = IMAGE) -> dict:
    """Scores a finished workspace in a container of its own, which holds the whole company. Returns the scores.

    The verifier's stack runner and checks are mounted from the repository, read-only, beside the workspace."""
    import json
    # every task is mounted, because a task may take its history and checks from another one
    tasks, task = os.path.dirname(os.path.abspath(task_dir)), os.path.basename(os.path.abspath(task_dir))
    platform = os.path.join(os.path.dirname(os.path.abspath(kernel_dir)), "platform")
    p = subprocess.run(["docker", "run", "--rm", "-e", "PYTHONDONTWRITEBYTECODE=1", "-v", workspace + ":/score/ws",
                        "-v", kernel_dir + ":/score/kernel:ro", "-v", platform + ":/score/platform:ro",
                        "-v", tasks + ":/score/tasks:ro", "-w", "/score", image,
                        "python3", "-m", "kernel.score", "/score/tasks/" + task, "/score/ws"], capture_output=True, text=True, timeout=1800)
    lines = [l for l in p.stdout.splitlines() if l.startswith("{")]
    if p.returncode != 0 or not lines:
        raise RuntimeError("scoring failed: {}".format((p.stderr or p.stdout)[-1500:]))
    return json.loads(lines[-1])

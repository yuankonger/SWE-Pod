"""Codex under Harbor at a seat whose image already has it.

    harbor run -p harbor/<company> --agent-import-path harbor_codex:SeatCodex -m gpt-6-luna --ak disable=multi_agent,multi_agent_v2 ...

Harbor's own Codex agent installs Codex from hosts the seat cannot reach, so the task's image carries it and
`install` only checks it is there. `disable` / `enable`: Codex features to turn off or on (comma-separated);
`config`: further `key=value` settings (comma-separated). Nothing else differs from Harbor's agent.
"""
from harbor.agents.installed.codex import Codex


class SeatCodex(Codex):
    def __init__(self, *args, disable="", enable="", config="", **kwargs):
        super().__init__(*args, **kwargs)
        split = lambda text: [x for x in str(text).split(",") if x]
        self._extra = ["--disable " + f for f in split(disable)] + ["--enable " + f for f in split(enable)] + ["-c " + c for c in split(config)]

    @staticmethod
    def name() -> str:
        return "seat-codex"

    async def install(self, environment):
        found = await environment.exec("codex --version")
        if found.return_code != 0:
            raise RuntimeError("the seat's image has no Codex: {}".format((found.stdout or "")[-300:]))

    def build_cli_flags(self) -> str:
        return " ".join([super().build_cli_flags()] + self._extra).strip()

"""A Home Assistant that starts from nothing, set up the way its owner would set it up, and asked over its WebSocket API.

Runs in the core image (it needs aiohttp, which Home Assistant brings). Nothing here is Home Assistant's own code
or written into its repository: the configuration directory is the deployment's, and onboarding goes through the
same HTTP steps the frontend's onboarding screens take.

    python3 ha_seed.py config <config dir> [--frontend <built frontend repo>]
    python3 ha_seed.py onboard <base url> <token file>
    python3 ha_seed.py ask <base url> <token file> <out.json> <command as JSON> ...
    python3 ha_seed.py serve <config dir> <token file>

`config` writes a configuration with the demo integration (`kitchen_sink`), whose power strip has two outlets. It has
no `http:` block, so Home Assistant serves at its default port, 8123: an `http:` block in YAML is taken in as a trial
of new HTTP settings, which the frontend asks the owner to confirm.
`onboard` waits for the server, creates the owner (`USER` / `PASSWORD`), finishes onboarding and keeps a
long-lived token. `ask` sends each command and records its answer, or its error, by the command's `type`. `serve`
runs Home Assistant in the foreground, onboarding it once it answers (a deployed system: sidecars/service.py).
"""
import asyncio
import json
import os
import sys
import time

import aiohttp

USER, PASSWORD, NAME = "owner", "owner-password", "Owner"
CLIENT_ID = "http://seedco.invalid/"

CONFIG = """\
homeassistant:
  name: Home
  latitude: 52.37
  longitude: 4.89
  elevation: 0
  unit_system: metric
  time_zone: Europe/Amsterdam
  country: NL
  currency: EUR
  language: en
frontend:{frontend}
config:
kitchen_sink:
logger:
  default: warning
"""


def config(directory, frontend=None):
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, "configuration.yaml"), "w") as f:
        f.write(CONFIG.format(frontend="\n  development_repo: {}".format(frontend) if frontend else ""))


async def _wait(session, base, seconds=300):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            async with session.get(base + "/api/onboarding") as r:
                if r.status in (200, 401, 404):      # 404: onboarded on an earlier start, its API is gone
                    return
        except aiohttp.ClientError:
            pass
        await asyncio.sleep(2)
    raise SystemExit("Home Assistant did not answer at {} within {}s".format(base, seconds))


async def _token(session, base, code):
    async with session.post(base + "/auth/token", data={"grant_type": "authorization_code", "code": code, "client_id": CLIENT_ID}) as r:
        r.raise_for_status()
        return (await r.json())["access_token"]


async def _login(session, base):
    """The login flow the frontend's sign-in page takes, for an install whose onboarding is done."""
    async with session.post(base + "/auth/login_flow", json={"client_id": CLIENT_ID, "handler": ["homeassistant", None], "redirect_uri": CLIENT_ID}) as r:
        flow = await r.json()
    async with session.post(base + "/auth/login_flow/" + flow["flow_id"], json={"client_id": CLIENT_ID, "username": USER, "password": PASSWORD}) as r:
        done = await r.json()
    return await _token(session, base, done["result"])


async def onboard(base, token_file):
    async with aiohttp.ClientSession() as session:
        await _wait(session, base)
        async with session.get(base + "/api/onboarding") as r:
            if r.status == 200:
                steps = {s["step"]: s["done"] for s in await r.json()}
            elif r.status == 404:      # onboarding is over: Home Assistant no longer serves its API
                steps = {"user": True, "core_config": True, "analytics": True, "integration": True}
            else:
                steps = {"user": True}
        if not steps.get("user"):
            async with session.post(base + "/api/onboarding/users", json={"client_id": CLIENT_ID, "name": NAME, "username": USER,
                                                                          "password": PASSWORD, "language": "en"}) as r:
                r.raise_for_status()
                access = await _token(session, base, (await r.json())["auth_code"])
        else:
            access = await _login(session, base)
        auth = {"Authorization": "Bearer " + access}
        for step, body in (("core_config", {}), ("analytics", {}), ("integration", {"client_id": CLIENT_ID, "redirect_uri": CLIENT_ID})):
            if not steps.get(step):
                async with session.post(base + "/api/onboarding/" + step, json=body, headers=auth) as r:
                    if r.status not in (200, 403):      # 403: that step is done already
                        raise SystemExit("onboarding step {} answered {}: {}".format(step, r.status, await r.text()))
        # a token's name must be new on every start: Home Assistant refuses a second one of the same name
        answers = await _ask(session, base, access, [{"type": "auth/long_lived_access_token", "client_name": "seedco {:.0f}".format(time.time()),
                                                      "lifespan": 3650}])
    token = answers["auth/long_lived_access_token"]
    if not token["success"]:
        raise SystemExit("no long-lived token: {}".format(token["error"]))
    with open(token_file + ".tmp", "w") as f:
        f.write(token["result"])
    os.replace(token_file + ".tmp", token_file)
    print("onboarded; token in", token_file)


async def _ask(session, base, token, commands):
    answers = {}
    async with session.ws_connect(base.replace("http", "ws", 1) + "/api/websocket", max_msg_size=0) as ws:
        await ws.receive_json()
        await ws.send_json({"type": "auth", "access_token": token})
        if (await ws.receive_json())["type"] != "auth_ok":
            raise SystemExit("the token was refused")
        # answers are taken once Home Assistant has started, with every integration of the configuration set up
        ids = iter(range(1, 10000))      # Home Assistant takes message ids only in increasing order
        for _ in range(90):
            n = next(ids)
            await ws.send_json({"id": n, "type": "get_config"})
            while (msg := await ws.receive_json(timeout=60)).get("id") != n:
                pass
            if (msg.get("result") or {}).get("state") == "RUNNING":
                break
            await asyncio.sleep(2)
        for command in commands:
            n = next(ids)
            await ws.send_json(dict(command, id=n))
            while True:
                msg = await ws.receive_json(timeout=60)
                if msg.get("id") == n and msg["type"] == "result":
                    break
            answers[command["type"]] = {"success": msg["success"], "result": msg.get("result"), "error": msg.get("error")}
    return answers


async def ask(base, token_file, out, commands):
    with open(token_file) as f:
        token = f.read().strip()
    async with aiohttp.ClientSession() as session:
        await _wait(session, base)
        answers = await _ask(session, base, token, commands)
    with open(out, "w") as f:
        json.dump(answers, f, indent=1)
    print(" ".join("{}={}".format(t, "ok" if a["success"] else a["error"]["code"]) for t, a in answers.items()))


def serve(directory, token_file, url="http://127.0.0.1:8123"):
    """Home Assistant on `directory`, onboarded, in the foreground: it ends when Home Assistant does."""
    import subprocess
    hass = subprocess.Popen([sys.executable, "-m", "homeassistant", "-c", directory, "--skip-pip"])
    try:
        asyncio.run(onboard(url, token_file))
    except BaseException as e:      # Home Assistant may still be of use without the token; say why there is none
        print("onboarding failed: {}".format(e), file=sys.stderr, flush=True)
    sys.exit(hass.wait())


if __name__ == "__main__":
    what, args = sys.argv[1], sys.argv[2:]
    if what == "serve":
        serve(*args)
    elif what == "config":
        config(args[0], args[2] if len(args) > 2 and args[1] == "--frontend" else None)
    elif what == "onboard":
        asyncio.run(onboard(*args))
    elif what == "ask":
        asyncio.run(ask(args[0], args[1], args[2], [json.loads(c) for c in args[3:]]))
    else:
        raise SystemExit(__doc__)

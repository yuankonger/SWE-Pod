"""The company with one container per owner (docker/compose.yaml), driven from this machine.

Run on the host, not inside the toolchain image:  python3 -m unittest integration/test_compose.py
Skipped when docker is not available.
"""
import json
import os
import shutil
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from shop import Browser  # noqa: E402

COMPOSE = ["docker", "compose", "-f", os.path.join(HERE, "..", "docker", "compose.yaml")]
PORTS = {"core": 7000, "storefront": 7001, "dashboard": 7002, "payments": 7003, "taxes": 7004, "notifications": 7005,
         "subscriptions": 7006, "support": 7007, "prometheus": 7009}


def get(service, path):
    with urllib.request.urlopen("http://127.0.0.1:{}{}".format(PORTS[service], path), timeout=20) as r:
        return json.loads(r.read())


def wait_for(check, timeout=240, interval=0.5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            value = check()
            if value:
                return value
        except (urllib.error.URLError, OSError, ValueError, KeyError):
            pass
        time.sleep(interval)
    return None


@unittest.skipUnless(shutil.which("docker"), "docker is not available")
class ComposeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(COMPOSE + ["down", "-v"], capture_output=True)
        up = subprocess.run(COMPOSE + ["up", "-d"], capture_output=True, text=True)
        if up.returncode != 0:
            raise RuntimeError("docker compose up failed:\n" + up.stderr[-2000:])
        # Core is healthy once it has installed every app, so this waits for the whole company.
        if not wait_for(lambda: get("core", "/health")["ok"]):
            logs = subprocess.run(COMPOSE + ["logs", "--tail", "30"], capture_output=True, text=True).stdout
            subprocess.run(COMPOSE + ["down", "-v"], capture_output=True)
            raise RuntimeError("the company did not become healthy:\n" + logs[-4000:])

    @classmethod
    def tearDownClass(cls):
        subprocess.run(COMPOSE + ["down", "-v"], capture_output=True)

    def test_a_purchase_crosses_the_containers(self):
        status, location, text = Browser("http://127.0.0.1:{}".format(PORTS["storefront"])).buy({"BOX-S": 2, "ADD-TEA": 1})
        self.assertEqual(status, 303, text[-600:])
        emails = wait_for(lambda: len(get("notifications", "/outbox?email=pat%40example.com")["emails"]) >= 2
                          and get("notifications", "/outbox?email=pat%40example.com")["emails"], timeout=30)
        self.assertTrue(emails)
        self.assertIn("Total: $66.15", [e for e in emails if e["kind"] == "receipt"][0]["body"])
        self.assertEqual([(i["amount"], i["status"]) for i in get("payments", "/api/payment-intents")["payment_intents"]], [(6615, "succeeded")])
        self.assertTrue(wait_for(lambda: get("taxes", "/api/tax-documents")["documents"], timeout=30))
        self.assertTrue(wait_for(lambda: get("subscriptions", "/api/subscriptions?email=pat%40example.com")["subscriptions"], timeout=30))

    def test_each_container_holds_only_its_own_owner(self):
        for owner in ("taxes", "storefront", "core"):
            seen = subprocess.run(COMPOSE + ["exec", "-T", owner, "ls", "/work/services"], capture_output=True, text=True).stdout.split()
            self.assertEqual(seen, [owner])
        # and it cannot be written to: the running company is not where owners edit
        touch = subprocess.run(COMPOSE + ["exec", "-T", "taxes", "touch", "/work/services/taxes/x"], capture_output=True, text=True)
        self.assertNotEqual(touch.returncode, 0)

    def test_prometheus_scrapes_every_container_by_name(self):
        def up():
            result = get("prometheus", "/api/v1/query?query=" + urllib.parse.quote("up == 1"))["data"]["result"]
            return len(result) == 8 and sorted(r["metric"]["service"] for r in result)
        self.assertEqual(wait_for(up, timeout=60), sorted(s for s in PORTS if s != "prometheus"))


if __name__ == "__main__":
    unittest.main()

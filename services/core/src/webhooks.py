"""Apps and webhooks, the way Saleor does them.

An app is installed from its manifest. The manifest lists webhooks; each webhook names the events it wants and
carries a GraphQL subscription query that selects the fields the app reads. For every event Core runs that query
against the event and sends the result: the payload holds exactly what the app asked for and nothing else.

Synchronous events (taxes, payments) are answered in the HTTP response. Asynchronous events (order.*) are stored
as deliveries and sent by a background worker, with retries. A delivery can arrive more than once.
"""
import json
import secrets
import threading
import time
import urllib.error
import urllib.request
import uuid

from graphql import execute, parse, validate

import telemetry

SCHEMA_VERSION = "3.23"
SYNC_TIMEOUT_S = 20
MAX_ATTEMPTS = 5
PERMISSIONS = {"MANAGE_ORDERS": "Manage orders.", "MANAGE_APPS": "Manage apps.", "HANDLE_PAYMENTS": "Handle payments.",
               "HANDLE_TAXES": "Handle taxes.", "MANAGE_CHECKOUTS": "Manage checkouts.", "MANAGE_PRODUCTS": "Manage products."}


class WebhookError(RuntimeError):
    """A synchronous webhook could not be called or did not answer with JSON."""


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _request(url: str, body: bytes, headers: dict, timeout: float):
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


class Apps:
    def __init__(self, store, schema, api_url: str):
        self.store, self.schema, self.api_url = store, schema, api_url
        self.domain = api_url.split("//", 1)[-1].split("/", 1)[0]

    # ---- installation ----

    def install(self, manifest_url: str) -> dict:
        """Fetches the manifest, records the app and its webhooks, and hands the app its token."""
        with urllib.request.urlopen(manifest_url, timeout=5) as r:
            manifest = json.loads(r.read())
        identifier = manifest["id"]
        known = self.find(identifier) or {}
        app = {"id": known.get("id") or str(uuid.uuid4()), "identifier": identifier, "name": manifest.get("name", identifier),
               "version": manifest.get("version", ""), "isActive": True, "token": known.get("token") or secrets.token_hex(16),
               "permissions": [p for p in manifest.get("permissions", []) if p in PERMISSIONS], "webhooks": []}
        for i, w in enumerate(manifest.get("webhooks", [])):
            problems = validate(self.schema, parse(w["query"]))   # a query the schema does not allow is refused
            if problems:
                telemetry.log("error", "webhook refused: its subscription query is not valid", **{
                    "saleor.app.identifier": identifier, "webhook": w.get("name"), "reason": problems[0].message})
                continue
            app["webhooks"].append({"id": "{}:{}".format(app["id"], i), "name": w.get("name", ""), "targetUrl": w["targetUrl"],
                                    "isActive": w.get("isActive", True), "syncEvents": w.get("syncEvents", []),
                                    "asyncEvents": w.get("asyncEvents", []), "query": w["query"]})
        _request(manifest["tokenTargetUrl"], json.dumps({"auth_token": app["token"]}).encode(), self._headers("app_installed"), 5)
        self.store.put("app", app, identifier)
        telemetry.log("info", "app installed", **{"saleor.app.identifier": identifier, "webhooks": len(app["webhooks"])})
        return app

    def all(self) -> list:
        return self.store.all("app")

    def find(self, identifier: str):
        found = self.store.all("app", identifier)
        return found[0] if found else None

    def by_token(self, token: str):
        return next((a for a in self.all() if a["token"] == token), None)

    def webhook(self, app: dict, event_type: str, sync: bool):
        key = "syncEvents" if sync else "asyncEvents"
        return next((w for w in app["webhooks"] if w["isActive"] and event_type in w[key]), None)

    # ---- sending ----

    def _headers(self, event_type: str) -> dict:
        return {"Saleor-Event": event_type.lower(), "Saleor-Domain": self.domain, "Saleor-Api-Url": self.api_url,
                "Saleor-Schema-Version": SCHEMA_VERSION}

    def payload(self, app: dict, webhook: dict, typename: str, fields: dict) -> dict:
        """Runs the webhook's subscription query against the event. The result is the payload."""
        event = dict(fields, __typename=typename, issuedAt=_now(), version=SCHEMA_VERSION, recipient=app)
        result = execute(self.schema, parse(webhook["query"]), root_value={"event": event})
        if result.errors:
            raise WebhookError("the subscription query of {} failed: {}".format(webhook["name"], result.errors[0].message))
        return (result.data or {}).get("event") or {}

    def sync(self, app: dict, event_type: str, typename: str, fields: dict) -> dict:
        """Calls the app's synchronous webhook for the event and returns its JSON answer."""
        webhook = self.webhook(app, event_type, sync=True)
        if webhook is None:
            raise WebhookError("app {} has no webhook for {}".format(app["identifier"], event_type))
        body = json.dumps(self.payload(app, webhook, typename, fields)).encode()
        labels = {"saleor_webhook_event_type": event_type.lower(), "saleor_webhook_execution_mode": "sync",
                  "saleor_app_identifier": app["identifier"]}
        try:
            status, raw = _request(webhook["targetUrl"], body, self._headers(event_type), SYNC_TIMEOUT_S)
            answer = json.loads(raw)
            if not isinstance(answer, dict):
                raise ValueError("the answer is not a JSON object")
        except (urllib.error.URLError, OSError, ValueError) as exc:
            telemetry.count("saleor_webhook_request_count_total", outcome="failure", **labels)
            telemetry.log("error", "sync webhook failed", reason=str(exc), **labels)
            raise WebhookError("{} did not answer {}: {}".format(app["identifier"], event_type, exc)) from exc
        telemetry.count("saleor_webhook_request_count_total", outcome="success", **labels)
        return answer

    def emit(self, event_type: str, typename: str, fields: dict):
        """Stores one delivery of an asynchronous event for every app subscribed to it."""
        for app in self.all():
            webhook = self.webhook(app, event_type, sync=False)
            if webhook is None:
                continue
            try:
                payload = self.payload(app, webhook, typename, fields)
            except WebhookError as exc:
                telemetry.log("error", "event not delivered", reason=str(exc), **{"saleor.app.identifier": app["identifier"]})
                continue
            self.store.put("delivery", {"id": str(uuid.uuid4()), "app": app["identifier"], "event_type": event_type,
                                        "target_url": webhook["targetUrl"], "payload": json.dumps(payload),
                                        "status": "pending", "attempts": 0, "next_attempt": 0, "last_error": ""}, "pending")

    def deliver_pending(self) -> int:
        """Sends every delivery that is due, oldest first. Returns how many are still pending."""
        waiting = 0
        for d in self.store.all("delivery", "pending"):
            if d["next_attempt"] > time.time():
                waiting += 1
                continue
            labels = {"saleor_webhook_event_type": d["event_type"].lower(), "saleor_webhook_execution_mode": "async",
                      "saleor_app_identifier": d["app"]}
            try:
                _request(d["target_url"], d["payload"].encode(), self._headers(d["event_type"]), 10)
                d["status"] = "success"
                telemetry.count("saleor_webhook_request_count_total", outcome="success", **labels)
            except (urllib.error.URLError, OSError) as exc:
                d["attempts"] += 1
                d["last_error"] = str(exc)
                d["next_attempt"] = time.time() + min(0.5 * 2 ** d["attempts"], 30)
                telemetry.count("saleor_webhook_request_count_total", outcome="failure", **labels)
                if d["attempts"] >= MAX_ATTEMPTS:
                    d["status"] = "failed"
                    telemetry.log("error", "delivery given up", attempts=d["attempts"], reason=d["last_error"], **labels)
                else:
                    waiting += 1
            self.store.put("delivery", d, d["status"])
        return waiting

    def run_worker(self):
        def loop():
            while True:
                try:
                    self.deliver_pending()
                except Exception as exc:  # the worker must outlive one bad delivery
                    telemetry.log("error", "delivery worker error", reason=repr(exc))
                time.sleep(0.2)
        threading.Thread(target=loop, daemon=True, name="deliveries").start()

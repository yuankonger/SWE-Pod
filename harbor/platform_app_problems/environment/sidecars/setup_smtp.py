"""One-off setup of the email app, as an operator would have done it by hand in the dashboard.

Makes the app's table, installs the app in the API (with the permissions its manifest asks for), and gives it one
configuration: mail for the default channel goes out through the company's mail server as shop@example.com, and
the customer is written to when an order is confirmed. The configuration is written through the app's own API
(the one its settings page talks to), signed in as staff: the app then encrypts and stores it itself, and switches
on, in the API, the webhooks of the events that are enabled. Running it again changes nothing.
What it made is written to /state/smtp.json. Standard library only.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

E = os.environ
CORE, APP, DYNAMO = "http://core.internal:8000/graphql/", "http://smtp.internal:3000", "http://dynamodb:8000"
TABLE, CHANNEL, IDENTIFIER = "smtp-main-table", "default-channel", "saleor.app.smtp"
NAME, SENDER_NAME, SENDER = "Shop mail", "SeedCo Shop", "shop@example.com"
HOST, PORT = E.get("SMTP_HOST", "mailpit"), E.get("SMTP_PORT", "1025")
USER, PASSWORD = E.get("SMTP_USER", "shop@example.com"), E.get("SMTP_PASSWORD", "shop-mail-password")
EVENTS = [e for e in E.get("SMTP_EVENTS", "ORDER_CONFIRMED").split(",") if e]
WEBHOOKS = {"ORDER_CONFIRMED": "ORDER_CONFIRMED", "ORDER_CREATED": "ORDER_CREATED", "ORDER_FULFILLED": "ORDER_FULFILLED",
            "ORDER_FULLY_PAID": "ORDER_FULLY_PAID", "ORDER_CANCELLED": "ORDER_CANCELLED", "ORDER_REFUNDED": "ORDER_REFUNDED",
            "INVOICE_SENT": "INVOICE_SENT", "GIFT_CARD_SENT": "GIFT_CARD_SENT"}      # the app's event -> the API's; the rest ride on NOTIFY_USER


def call(url, body=None, headers=None):
    request = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                     headers=dict({"Content-Type": "application/json"}, **(headers or {})))
    try:
        with urllib.request.urlopen(request, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def gql(query, variables=None, token=None):
    status, body = call(CORE, {"query": query, "variables": variables or {}}, {"Authorization": "Bearer " + token} if token else None)
    if status != 200 or body.get("errors"):
        sys.exit("the API refused: {} {}".format(status, json.dumps(body)[:1500]))
    return body["data"]


def dynamo(action, body):
    """DynamoDB's JSON protocol. The local one reads the key's name out of the header and checks no signature."""
    status, answer = call(DYNAMO, body, {
        "Content-Type": "application/x-amz-json-1.0", "X-Amz-Target": "DynamoDB_20120810." + action,
        "Authorization": "AWS4-HMAC-SHA256 Credential=local/20260101/localhost/dynamodb/aws4_request, SignedHeaders=host;x-amz-target, Signature=0"})
    if status != 200 and "ResourceInUseException" not in json.dumps(answer):
        sys.exit("the app's store refused {}: {} {}".format(action, status, answer))
    return answer


def find_app(token):
    apps = gql("{ apps(first: 50) { edges { node { id identifier name isActive } } } }", token=token)["apps"]["edges"]
    return next((a["node"] for a in apps if a["node"]["identifier"] == IDENTIFIER), None)


class Settings:
    """The app's settings API (tRPC over HTTP), as its page in the dashboard calls it: the staff member's token for
    this app and the API's address go in two headers. The app derives the address of its webhooks from the Host of
    these requests, so they have to be made to the name the API reaches the app by."""

    def __init__(self, token):
        self.headers = {"authorization-bearer": token, "saleor-api-url": CORE}

    def _answer(self, path, status, body):
        if status != 200 or "error" in body:
            sys.exit("the app refused {}: {} {}".format(path, status, json.dumps(body)[:1500]))
        return body["result"].get("data")

    def query(self, path, value=None):
        tail = "" if value is None else "?" + urllib.parse.urlencode({"input": json.dumps(value)})
        return self._answer(path, *call("{}/api/trpc/{}{}".format(APP, path, tail), headers=self.headers))

    def mutate(self, path, value):
        return self._answer(path, *call("{}/api/trpc/{}".format(APP, path), value, self.headers))


def main():
    dynamo("CreateTable", {"TableName": TABLE, "BillingMode": "PAY_PER_REQUEST",      # the app ships no script for this; its table is PK/SK strings
                           "AttributeDefinitions": [{"AttributeName": "PK", "AttributeType": "S"}, {"AttributeName": "SK", "AttributeType": "S"}],
                           "KeySchema": [{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}]})
    token = gql('mutation { tokenCreate(email: "admin@example.com", password: "admin") { token errors { message } } }')["tokenCreate"]["token"]
    app = find_app(token)
    if not app:
        with urllib.request.urlopen(APP + "/api/manifest", timeout=60) as r:
            manifest = json.loads(r.read())
        done = gql("""mutation($input: AppInstallInput!) { appInstall(input: $input) { appInstallation { id status } errors { field message code } } }""",
                   {"input": {"appName": manifest["name"], "manifestUrl": APP + "/api/manifest", "permissions": manifest["permissions"]}}, token)["appInstall"]
        if done["errors"]:
            sys.exit("the app was not installed: {}".format(done["errors"]))
        for _ in range(60):
            app = find_app(token)
            if app:
                break
            time.sleep(2)
        else:
            sys.exit("the app did not appear: {}".format(gql("{ appsInstallations { status message } }", token=token)))
    channel = gql("query($slug: String!) { channel(slug: $slug) { id } }", {"slug": CHANNEL}, token)["channel"]["id"]
    settings = Settings(gql("query($id: ID!) { app(id: $id) { accessToken } }", {"id": app["id"]}, token)["app"]["accessToken"])

    changed = []
    config = next((c for c in settings.query("smtpConfiguration.getConfigurations") if c["name"] == NAME), None)
    if not config:
        config = settings.mutate("smtpConfiguration.createConfiguration", {
            "name": NAME, "smtpHost": HOST, "smtpPort": PORT, "smtpUser": USER, "smtpPassword": PASSWORD, "encryption": "NONE"})
        changed.append("configuration")
    wanted = {"smtpHost": HOST, "smtpPort": PORT, "smtpUser": USER, "smtpPassword": PASSWORD, "encryption": "NONE"}
    if any(config.get(k) != v for k, v in wanted.items()):
        settings.mutate("smtpConfiguration.updateSmtp", dict(wanted, id=config["id"]))
        changed.append("server")
    if (config.get("senderEmail"), config.get("senderName")) != (SENDER, SENDER_NAME):
        settings.mutate("smtpConfiguration.updateSender", {"id": config["id"], "senderEmail": SENDER, "senderName": SENDER_NAME})
        changed.append("sender")
    channels = {"override": True, "channels": [CHANNEL], "mode": "restrict"}
    if config.get("channels") != channels:
        settings.mutate("smtpConfiguration.updateChannels", dict(channels, id=config["id"]))
        changed.append("channels")
    for event in config["events"]:      # each comes with the app's default template and subject, switched off
        if event["eventType"] in EVENTS and not event["active"]:
            settings.mutate("smtpConfiguration.updateEvent", dict(event, id=config["id"], active=True))
            changed.append(event["eventType"])

    # The app creates and removes its webhooks in the API after every change of server settings or events. Had one
    # gone missing since (or the first try failed), saving the name again, unchanged, makes the app look once more.
    def webhooks():
        hooks = gql("query($id: ID!) { app(id: $id) { webhooks { name isActive targetUrl asyncEvents { eventType } } } }", {"id": app["id"]}, token)["app"]["webhooks"]
        return {e["eventType"]: h["targetUrl"] for h in hooks if h["isActive"] for e in h["asyncEvents"]}
    expected = {WEBHOOKS.get(e, "NOTIFY_USER") for e in EVENTS}
    if not expected <= set(webhooks()):
        settings.mutate("smtpConfiguration.updateBasicInformation", {"id": config["id"], "name": NAME, "active": True})
        changed.append("webhooks")
    live = webhooks()
    if not expected <= set(live):
        sys.exit("the app's webhooks are not all there: wanted {}, the API has {}".format(sorted(expected), live))

    found = {"core": CORE, "app": app, "channel": {"slug": CHANNEL, "id": channel}, "config": config["id"], "name": NAME,
             "sender": SENDER, "server": "{}:{}".format(HOST, PORT), "events": EVENTS, "webhooks": live, "changed": changed}
    try:
        os.makedirs("/state", exist_ok=True)
        with open("/state/smtp.json", "w") as f:
            json.dump(found, f, indent=2)
    except OSError:
        pass
    print(json.dumps(found))


if __name__ == "__main__":
    main()

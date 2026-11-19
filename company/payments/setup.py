"""One-off setup of the payment-path company, as an operator would have done it by hand.

Makes the payment app's table, installs the app in the API (with the permission to handle payments), tells the
provider where to send its events, and writes the app's configuration: one set of provider keys, used for the
default channel. What it made is written to /state/company.json, for the sidecars that come after. Standard library only.
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

CORE, APP, DYNAMO, PROVIDER = "http://core.internal:8000/graphql/", "http://stripe.internal:3000", "http://dynamodb:8000", "https://api.stripe.com"
TABLE, CHANNEL = "stripe-main-table", "default-channel"
E = os.environ


def post(url, body, headers=None, cafile=None):
    request = urllib.request.Request(url, data=json.dumps(body).encode(), headers=dict({"Content-Type": "application/json"}, **(headers or {})))
    import ssl
    context = ssl.create_default_context(cafile=cafile) if cafile else None
    try:
        with urllib.request.urlopen(request, timeout=60, context=context) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def gql(query, variables=None, token=None):
    status, body = post(CORE, {"query": query, "variables": variables or {}}, {"Authorization": "Bearer " + token} if token else None)
    if status != 200 or body.get("errors"):
        sys.exit("the API refused: {} {}".format(status, json.dumps(body)[:1500]))
    return body["data"]


def dynamo(action, body):
    """DynamoDB's JSON protocol. The local one reads the key's name out of the header and checks no signature."""
    status, answer = post(DYNAMO, body, {
        "Content-Type": "application/x-amz-json-1.0", "X-Amz-Target": "DynamoDB_20120810." + action,
        "Authorization": "AWS4-HMAC-SHA256 Credential=local/20260101/localhost/dynamodb/aws4_request, SignedHeaders=host;x-amz-target, Signature=0"})
    if status != 200 and "ResourceInUseException" not in json.dumps(answer):
        sys.exit("the app's store refused {}: {} {}".format(action, status, answer))
    return answer


def encrypted(text):
    """As the app keeps secrets: aes-256-cbc under its SECRET_KEY, written "<iv hex>:<cipher hex>"."""
    iv = os.urandom(16).hex()
    out = subprocess.run(["openssl", "enc", "-aes-256-cbc", "-K", E["APP_SECRET_KEY"], "-iv", iv], input=text.encode(), capture_output=True, check=True).stdout
    return iv + ":" + out.hex()


def main():
    dynamo("CreateTable", {"TableName": TABLE, "BillingMode": "PAY_PER_REQUEST",
                           "AttributeDefinitions": [{"AttributeName": "PK", "AttributeType": "S"}, {"AttributeName": "SK", "AttributeType": "S"}],
                           "KeySchema": [{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}]})
    token = gql('mutation { tokenCreate(email: "admin@example.com", password: "admin") { token errors { message } } }')["tokenCreate"]["token"]
    with urllib.request.urlopen(APP + "/api/manifest", timeout=30) as r:
        manifest = json.loads(r.read())
    mine = lambda: [e for e in gql("{ apps(first: 50) { edges { node { id identifier isActive } } } }", token=token)["apps"]["edges"]
                    if e["node"]["identifier"] == manifest["id"]]      # the company may have other apps installed
    apps = mine()
    if not apps:
        done = gql("""mutation($input: AppInstallInput!) { appInstall(input: $input) { appInstallation { id status } errors { field message code } } }""",
                   {"input": {"appName": manifest["name"], "manifestUrl": APP + "/api/manifest", "permissions": manifest["permissions"]}}, token)["appInstall"]
        if done["errors"]:
            sys.exit("the app was not installed: {}".format(done["errors"]))
        for _ in range(60):
            apps = mine()
            if apps:
                break
            time.sleep(2)
        else:
            sys.exit("the app did not appear: {}".format(gql("{ appsInstallations { status message } }", token=token)))
    app = apps[0]["node"]
    channel = gql("query($slug: String!) { channel(slug: $slug) { id } }", {"slug": CHANNEL}, token)["channel"]["id"]
    config, now, pk = str(uuid.uuid4()), time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()), "{}#{}".format(CORE, app["id"])
    kept = dynamo("Query", {"TableName": TABLE, "KeyConditionExpression": "PK = :p AND begins_with(SK, :s)",
                            "ExpressionAttributeValues": {":p": {"S": pk}, ":s": {"S": "CONFIG_ID#"}}}).get("Items") or []
    if kept:
        config = kept[0]["configId"]["S"]
    from urllib.parse import urlencode
    hook = "{}/api/webhooks/stripe?{}".format(APP, urlencode({"configurationId": config, "saleorApiUrl": CORE, "appId": app["id"]}))
    status, answer = post("{}/_endpoints?token={}".format(PROVIDER, E["PROVIDER_ADMIN"]), {      # the provider may have been started anew
        "id": "we_seedco", "url": hook, "secret": E["STRIPE_WH_SECRET"], "enabled_events": ["*"]}, cafile="/certs/ca.pem")
    if status != 200:
        sys.exit("the provider refused the endpoint: {} {}".format(status, answer))
    if not kept:
        s = lambda v: {"S": v}
        dynamo("PutItem", {"TableName": TABLE, "Item": {
            "PK": s(pk), "SK": s("CONFIG_ID#" + config), "_et": s("StripeConfig"), "configId": s(config), "configName": s("Main"),
            "stripePk": s(E["STRIPE_PK"]), "stripeRk": s(encrypted(E["STRIPE_RK"])), "stripeWhSecret": s(encrypted(E["STRIPE_WH_SECRET"])),
            "stripeWhId": s("we_seedco"), "createdAt": s(now), "modifiedAt": s(now)}})
        dynamo("PutItem", {"TableName": TABLE, "Item": {
            "PK": s(pk), "SK": s("CHANNEL_ID#" + channel), "_et": s("ChannelConfigMapping"), "channelId": s(channel), "configId": s(config),
            "createdAt": s(now), "modifiedAt": s(now)}})
    found = {"core": CORE, "app": app, "channel": {"slug": CHANNEL, "id": channel}, "config": config}
    os.makedirs("/state", exist_ok=True)
    with open("/state/company.json", "w") as f:
        json.dump(found, f, indent=2)
    print(json.dumps(found))


if __name__ == "__main__":
    main()

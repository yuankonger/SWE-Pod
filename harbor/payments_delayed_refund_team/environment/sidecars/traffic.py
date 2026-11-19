"""The company's customers and its back office, in a sidecar: orders placed and paid, then charged, some refunded.

    python3 traffic.py [--orders N] [--every seconds] [--refund share] [--decline share] [--partial share]
                       [--refund-twice share] [--serve port]

Each order goes the way a shop's does. The customer builds a checkout, starts a payment through the payment app,
confirms the card with the provider (what the provider's own form does in a browser), and completes the checkout.
The default channel only authorises, so a member of staff then charges the order, and now and then refunds part
of it (and of some, a second part later). What became of each order is appended to /state/traffic.jsonl: what was
asked, what the API says of it once the provider's events have had time to arrive, what the provider's ledger says
(read with PROVIDER_ADMIN, if set), and which commits the company was running, and whether a deploy was under way,
when the order was placed (asked of CI). Before its first order it writes down, in /state/baseline.json, every order
the shop already had and what the API said of its money. With --serve both can be read by whoever holds TRAFFIC_TOKEN:
    GET /records?token=<token>     every record so far, as JSON
    GET /baseline?token=<token>    the orders the shop had before the first of them
Standard library only.
"""
import argparse
import json
import os
import random
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

CORE, PROVIDER, GATEWAY = "http://core.internal:8000/graphql/", "https://api.stripe.com", "saleor.app.payment.stripe"
CHANNEL, OUT, CI = "default-channel", "/state/traffic.jsonl", os.environ.get("CI_URL", "http://ci:8080")
BASELINE = "/state/baseline.json"
TLS = ssl.create_default_context(cafile="/certs/ca.pem") if os.path.isfile("/certs/ca.pem") else None
ADDRESS = {"firstName": "Ada", "lastName": "Buyer", "streetAddress1": "8559 Lake Avenue", "city": "New York", "postalCode": "10001",
           "country": "US", "countryArea": "NY"}


class Failed(Exception):
    pass


def gql(query, variables=None, token=None):
    request = urllib.request.Request(CORE, data=json.dumps({"query": query, "variables": variables or {}}).encode(),
                                     headers=dict({"Content-Type": "application/json"}, **({"Authorization": "Bearer " + token} if token else {})))
    try:
        with urllib.request.urlopen(request, timeout=60) as r:
            body = json.loads(r.read())
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise Failed("the API did not answer: {}".format(e))
    if body.get("errors"):
        raise Failed("the API refused: {}".format(json.dumps(body["errors"])[:600]))
    data = body["data"]
    for name, part in data.items():
        if isinstance(part, dict) and part.get("errors"):
            raise Failed("{}: {}".format(name, json.dumps(part["errors"])[:600]))
    return data


def provider(path, form, key):
    request = urllib.request.Request(PROVIDER + path, data=urllib.parse.urlencode(form).encode(), headers={"Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(request, timeout=30, context=TLS) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read() or b"{}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise Failed("the provider did not answer: {}".format(e))


def staff():
    return gql('mutation { tokenCreate(email: "admin@example.com", password: "admin") { token errors { message } } }')["tokenCreate"]["token"]


def variants(token):
    found = gql("""query($c: String!) { products(first: 40, channel: $c, where: {isAvailable: true}) { edges { node { variants {
                   id quantityAvailable pricing { price { gross { amount } } } } } } } }""", {"c": CHANNEL}, token)
    return [v["id"] for e in found["products"]["edges"] for v in e["node"]["variants"] or []
            if (v.get("quantityAvailable") or 0) > 5 and v.get("pricing")]


TRANSACTION = "transaction { id pspReference authorizedAmount { amount } chargedAmount { amount } refundedAmount { amount } }"


def refund_reason(token):
    """The shop may require every refund to name a reason from a list it keeps; then the first of that list."""
    kind = gql("{ refundSettings { reasonReferenceType { id } } }", token=token)["refundSettings"]["reasonReferenceType"]
    if not kind:
        return None
    pages = gql("query($t: [ID!]) { pages(first: 1, filter: {pageTypes: $t}) { edges { node { id } } } }", {"t": [kind["id"]]}, token)["pages"]["edges"]
    return pages[0]["node"]["id"] if pages else None


def pay(n, picks, card, key):
    """The customer's part: a checkout, a payment started through the payment app, the card confirmed with the
    provider, the checkout completed. Returns the record; `order` is set if an order came of it."""
    record = {"n": n, "card": card, "at": round(time.time(), 1)}
    lines = [{"variantId": v, "quantity": random.randint(1, 2)} for v in random.sample(picks, random.randint(1, 2))]
    checkout = gql("""mutation($input: CheckoutCreateInput!) { checkoutCreate(input: $input) { checkout { id
                      shippingMethods { id } } errors { field message code } } }""",
                   {"input": {"channel": CHANNEL, "email": "buyer{}@example.com".format(n), "lines": lines,
                              "shippingAddress": ADDRESS, "billingAddress": ADDRESS}})["checkoutCreate"]["checkout"]
    record["checkout"] = cid = checkout["id"]
    if checkout["shippingMethods"]:
        gql("""mutation($id: ID!, $m: ID!) { checkoutDeliveryMethodUpdate(id: $id, deliveryMethodId: $m) { errors { field message code } } }""",
            {"id": cid, "m": checkout["shippingMethods"][0]["id"]})
    total = gql("query($id: ID!) { checkout(id: $id) { totalPrice { gross { amount currency } } } }", {"id": cid})["checkout"]["totalPrice"]["gross"]
    record["total"], record["currency"] = total["amount"], total["currency"]
    started = gql("""mutation($id: ID!, $g: PaymentGatewayToInitialize!) { transactionInitialize(id: $id, paymentGateway: $g) {
                     %s data errors { field message code } } }""" % TRANSACTION,
                  {"id": cid, "g": {"id": GATEWAY, "data": {"paymentIntent": {"paymentMethod": "card"}}}})["transactionInitialize"]
    record["transaction"], record["intent"] = started["transaction"]["id"], started["transaction"]["pspReference"]
    if not record["intent"]:
        raise Failed("the payment was not started: {}".format(json.dumps(started["data"])[:400]))
    confirmed = provider("/v1/payment_intents/{}/confirm".format(record["intent"]), {"payment_method": card}, key)
    record["provider_status"] = confirmed.get("status") or confirmed.get("error", {}).get("code")
    gql("""mutation($id: ID!) { transactionProcess(id: $id) { transactionEvent { type } errors { field message code } } }""", {"id": record["transaction"]})
    if record["provider_status"] not in ("requires_capture", "succeeded"):
        return record
    placed, last = None, ""
    for _ in range(10):      # the provider's word that the card was authorised reaches the API a moment later
        try:
            placed = gql("""mutation($id: ID!) { checkoutComplete(id: $id) { order { id number } errors { field message code } } }""", {"id": cid})["checkoutComplete"]["order"]
            break
        except Failed as e:
            last = str(e)
            time.sleep(1.5)
    if not placed:
        raise Failed("the order was not placed: " + last)
    record["order"] = placed["id"]
    return record


def charge(record, token, amount=None):
    """Staff charge the card: all that was authorised, or `amount` of it."""
    gql("""mutation($id: ID!, $a: PositiveDecimal) { transactionRequestAction(id: $id, actionType: CHARGE, amount: $a) { errors { field message code } } }""",
        {"id": record["transaction"], "a": amount}, token)


def give_back(record, token, amount, reason):
    gql("""mutation($id: ID!, $a: PositiveDecimal!, $r: ID) { transactionRequestAction(id: $id, actionType: REFUND, amount: $a,
           refundReason: "Customer asked", refundReasonReference: $r) { errors { field message code } } }""",
        {"id": record["transaction"], "a": amount, "r": reason}, token)


def order(n, picks, card, key, token, refund, reason=None, partial=0.0, twice=0.0):
    record, running = {"n": n, "card": card, "at": round(time.time(), 1)}, deployed()
    try:
        record = pay(n, picks, card, key)
        record["deployed"] = running
        if not record.get("order"):
            record["outcome"] = "declined"
            return record
        if record["provider_status"] == "requires_capture":
            if random.random() < partial:      # only part of the order can be sent: only that part is charged
                record["charge_asked"] = round(float(record["total"]) * random.choice((0.3, 0.5, 0.7)), 2)
            charge(record, token, record.get("charge_asked"))
            record["charged"] = True
        if random.random() < refund:
            time.sleep(2)
            record["refund"] = round(float(record.get("charge_asked") or record["total"]) * random.choice((0.25, 0.5, 1.0)), 2)
            give_back(record, token, record["refund"], reason)
            left = round(float(record.get("charge_asked") or record["total"]) - record["refund"], 2)
            if left >= 2 and random.random() < twice:      # the customer sends something more back
                record["wait_for_settlement"] = True
        record["outcome"] = "placed"
    except Failed as e:
        record["outcome"], record["why"] = "failed", str(e)
        record.setdefault("deployed", running)
    return record


def second_refund(record, token, reason):
    """The second refund of an order, asked for once the first has had time to be settled."""
    try:
        left = round(float(record.get("charge_asked") or record["total"]) - record["refund"], 2)
        record["refund_2"] = round(left * random.choice((0.5, 1.0)), 2)
        give_back(record, token, record["refund_2"], reason)
    except Failed as e:
        record["refund_2_failed"] = str(e)


def deployed():
    """The commits the company runs now, and whether a deploy is under way, as CI says. None if CI does not answer."""
    try:
        with urllib.request.urlopen(CI + "/status.json", timeout=5) as r:
            runs = json.loads(r.read())["runs"]
        return {"run": runs[0]["id"], "commits": runs[0]["commits"], "deploying": runs[0]["state"] == "running"} if runs else None
    except (OSError, ValueError, KeyError):
        return None


def books(record):
    """What the provider's ledger says of the order's payment: taken, returned, and how often each refund's settlement was sent."""
    admin = os.environ.get("PROVIDER_ADMIN")
    if not admin or not record.get("intent"):
        return None
    try:
        with urllib.request.urlopen("{}/_ledger?token={}".format(PROVIDER, admin), timeout=20, context=TLS) as r:
            ledger = json.loads(r.read())
        intent = next(i for i in ledger["payment_intents"] if i["id"] == record["intent"])
        refunds = [x for x in ledger["refunds"] if x["payment_intent"] == record["intent"] and x.get("status") != "failed"]
        sent = [len(e["deliveries"]) for e in ledger["events"] if e["event"]["type"] == "charge.refund.updated" and e["event"]["data"]["object"].get("payment_intent") == record["intent"]]
        return {"taken": round(intent.get("amount_received", 0) / 100, 2), "returned": round(sum(x["amount"] for x in refunds) / 100, 2), "refunds": len(refunds), "settlements_sent": sent}
    except (OSError, ValueError, KeyError, StopIteration):
        return None


def settle(record, token):
    """What the API says of the order's money once the provider's events have had time to arrive."""
    if record.get("order"):
        try:
            o = gql("""query($id: ID!) { order(id: $id) { status chargeStatus authorizeStatus total { gross { amount } }
                       totalCharged { amount } totalRefunded { amount } totalAuthorized { amount } } }""", {"id": record["order"]}, token)["order"]
            record["api"] = {"status": o["status"], "charge": o["chargeStatus"], "authorize": o["authorizeStatus"], "total": o["total"]["gross"]["amount"],
                             "charged": o["totalCharged"]["amount"], "refunded": o["totalRefunded"]["amount"], "authorized": o["totalAuthorized"]["amount"]}
            t = gql("query($id: ID!) { transaction(id: $id) { refundPendingAmount { amount } } }", {"id": record["transaction"]}, token)["transaction"]
            record["api"]["refund_pending"] = t["refundPendingAmount"]["amount"]
        except Failed as e:
            record["api"] = {"error": str(e)}
    record["ledger"] = books(record)
    record["settled_at"] = round(time.time(), 1)
    return record


ORDERS = """query($after: String) { orders(first: 100, after: $after) { pageInfo { hasNextPage endCursor } edges { node { id number
            totalCharged { amount } totalRefunded { amount } transactions { id pspReference chargedAmount { amount } chargePendingAmount { amount }
            refundedAmount { amount } refundPendingAmount { amount } events { type } } } } } }"""


def orders(token, ask=None):
    """Every order the shop has, by id: what the API says of its money and of each payment made for it."""
    found, after = {}, None
    while True:
        page = (ask or gql)(ORDERS, {"after": after}, token)["orders"]
        for edge in page["edges"]:
            o = edge["node"]
            found[o["id"]] = {"number": o["number"], "charged": o["totalCharged"]["amount"], "refunded": o["totalRefunded"]["amount"],
                              "transactions": {t["id"]: {"reference": t["pspReference"], "charged": t["chargedAmount"]["amount"],
                                                         "charge_pending": t["chargePendingAmount"]["amount"], "refunded": t["refundedAmount"]["amount"],
                                                         "refund_pending": t["refundPendingAmount"]["amount"],
                                                         "events": sorted(e["type"] for e in t["events"])} for t in o["transactions"]}}
        if not page["pageInfo"]["hasNextPage"]:
            return found
        after = page["pageInfo"]["endCursor"]


def serve(port, token):
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            asked = urllib.parse.urlparse(self.path)
            ok = urllib.parse.parse_qs(asked.query).get("token") == [token]
            body = "[]"
            if ok and asked.path == "/baseline":
                body = "null"
                if os.path.isfile(BASELINE):
                    with open(BASELINE) as f:
                        body = f.read()
            elif ok and os.path.isfile(OUT):
                with open(OUT) as f:
                    body = "[" + ",".join(line for line in f.read().splitlines() if line.strip()) + "]"
            self.send_response(200 if ok else 403)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body.encode() if ok else b"[]")

    threading.Thread(target=ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever, daemon=True).start()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--orders", type=int, default=0, help="how many, 0 for ever")
    parser.add_argument("--every", type=float, default=5.0)
    parser.add_argument("--refund", type=float, default=0.25)
    parser.add_argument("--decline", type=float, default=0.1)
    parser.add_argument("--partial", type=float, default=0.0, help="share of orders of which staff charge only a part")
    parser.add_argument("--settle", type=float, default=8.0, help="seconds after an order (or its last refund) before the API is asked what it holds")
    parser.add_argument("--refund-twice", type=float, default=0.0, help="share of refunded orders that are refunded a second time")
    parser.add_argument("--serve", type=int, default=0, help="port to serve the records on, to whoever holds TRAFFIC_TOKEN")
    args = parser.parse_args()
    key = os.environ["STRIPE_PK"]
    if args.serve:
        serve(args.serve, os.environ["TRAFFIC_TOKEN"])
    while True:      # the shop may be down, or being deployed: its customers come back
        try:
            token = staff()
            picks, waiting, n, reason, signed_in = variants(token), [], 0, refund_reason(token), time.time()
            if len(picks) >= 2:
                break
        except Failed:
            pass
        time.sleep(10)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    while not os.path.isfile(BASELINE):      # once: a sidecar started again does not take its own orders for the shop's old ones
        try:
            had = orders(token)
            with open(BASELINE + ".part", "w") as f:
                json.dump({"at": round(time.time(), 1), "orders": had}, f)
            os.replace(BASELINE + ".part", BASELINE)
        except Failed:
            time.sleep(5)
            try:
                token, signed_in = staff(), time.time()
            except Failed:
                pass
    while True:
        if not args.orders or n < args.orders:
            n += 1
            card = "pm_card_chargeDeclined" if random.random() < args.decline else random.choice(("pm_card_visa", "pm_card_mastercard"))
            waiting.append(order(n, picks, card, key, token, args.refund, reason, args.partial, args.refund_twice))
            # A staff token lasts five minutes. Staff sign in again well before that, and after anything fails; and
            # look at what is still in stock.
            if time.time() - signed_in > 120 or waiting[-1]["outcome"] == "failed":
                try:
                    token, signed_in = staff(), time.time()
                    picks = variants(token) or picks
                except Failed:
                    pass
        elif not waiting:
            break
        since = lambda r: r.get("wait_from", r["at"])
        waiting.sort(key=since)
        while waiting and (time.time() - since(waiting[0]) > args.settle + 5 or (args.orders and n >= args.orders)):
            if args.orders and n >= args.orders:
                time.sleep(max(0, args.settle - (time.time() - since(waiting[0]))))
            if waiting[0].pop("wait_for_settlement", None):      # its first refund has had time: now the second, and wait again
                second_refund(waiting[0], token, reason)
                waiting.append(dict(waiting.pop(0), wait_from=round(time.time(), 1)))
                continue
            record = settle(waiting.pop(0), token)
            with open(OUT, "a") as f:
                f.write(json.dumps(record) + "\n")
            print(json.dumps(record), flush=True)
        if not args.orders or n < args.orders:
            time.sleep(args.every)


if __name__ == "__main__":
    main()

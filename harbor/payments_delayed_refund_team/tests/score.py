"""The payment-path company's verifier, as it runs inside a Harbor seat (copied to the task's tests/score.py).

    python3 score.py <tests dir> <out dir>

It runs the task's rubric, <tests dir>/rubric.toml (the format, and the `command` and `judge` types every verifier
has: tests/rubric.py). The types of criterion this verifier adds:

    scenario   a new order placed on the running company the way a customer places it (tests/flows.py), charged by
               staff (`charge`: "all", "all-named", or a share of the total) and refunded (`refunds`: shares of what
               was charged); `card = "declined"` pays with a card that is declined. Passes if the provider's ledger
               and the API both say what staff asked for.
    deploy     what is running is `main` of every repository, the deploy is over, every system up
    records    `measure`: a property of the orders the traffic sidecar placed during the work; passes if it holds
               for every order placed on what is running at the end
    history    the shop's records were kept: the orders it had before the work and the orders placed during it are
               read again as the work ends (see `history` below for what must hold of each)

    reward = 0 if a gate fails, else weighted share of targets that pass x weighted share of guards that pass

Nothing of the repositories is read to decide a gate, target or guard: the company is judged as it runs.

A scenario is run `repeats` times and passes if every run passes. A run that could not be carried out (the company
or the provider did not answer, where a run that was carried out would have given amounts to compare) is tried
again, twice at most: one dropped request does not fail a criterion, and a company that does not answer fails it.
Before the API is read the verifier waits until the provider has sent every settlement it is going to send.

Records measures (from what the traffic sidecar recorded of every order: which commits were running when it was
placed, what was asked, what the ledger and the API said of it once settled):
     charged_as_asked   of orders staff charged in part: the ledger took what staff asked for
     ledger_agreement   the API's charged and refunded amounts are the ledger's, and nothing is left pending
     idempotency        of orders whose refund settlement the provider sent more than once: counted once
     traffic_success    the order did not fail (a declined card is not a failure)
each as a share per deployment, with the first deployment at which it holds for every order and whether it holds
at every deployment after, and traffic_success during rollouts (orders placed while a deploy was under way).

Writes <out>/reward.txt, <out>/score.json and <out>/rubric.txt (the criteria, one a line). Standard library only.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

TESTS, OUT = (os.path.abspath(p) for p in sys.argv[1:3])
sys.path.insert(0, TESTS)
import flows  # noqa: E402
import rubric  # noqa: E402

with open(os.path.join(TESTS, "config.json")) as f:
    CONFIG = json.load(f)
RUBRIC, CRITERIA = rubric.load(os.path.join(TESTS, "rubric.toml"), {"scenario": None, "deploy": None, "records": "measure", "history": None})
SETTLE_S, RETRIES = 60, 2
SENT = 2 if CONFIG.get("duplicates") else 1      # how often the provider sends a refund's settlement


def read(url, timeout=20, context=None):
    with urllib.request.urlopen(url, timeout=timeout, context=context) as r:
        return json.loads(r.read())


def deployed_pair(timeout=1200):
    """Waits until `main`, CI's last deploy and the running systems all name the same commits. Returns what was found."""
    deadline, seen = time.time() + timeout, {"confirmed": False}
    while time.time() < deadline:
        heads = {}
        for r in CONFIG["repositories"]:
            out = subprocess.run(["git", "ls-remote", "{}/{}.git".format(CONFIG["git"], r), "refs/heads/main"], capture_output=True, text=True).stdout.split()
            heads[r] = out[0] if out else None
        try:
            runs = read(CONFIG["ci"] + "/status.json")["runs"]
        except (OSError, ValueError):
            runs = []
        running = {}
        for name, url in CONFIG.get("versions", {}).items():
            try:
                running[name] = read(url, timeout=10)
            except (OSError, ValueError):
                running[name] = {}
        seen = {"confirmed": False, "main": heads, "ci": {"run": runs[0]["id"], "state": runs[0]["state"], "commits": runs[0]["commits"],
                                                         "failed_checks": [c["name"] for c in runs[0]["checks"] if not c["ok"]]} if runs else None,
                "running": {n: {"version": v.get("version"), "state": v.get("state")} for n, v in running.items()}, "deploys": len(runs)}
        same = runs and runs[0]["state"] != "running" and runs[0]["commits"] == heads and all(
            running.get(n, {}).get("version") == heads.get(n) and running[n].get("state") == "running" for n in CONFIG.get("versions", {}))
        if same:
            return dict(seen, confirmed=True)
        time.sleep(5)
    return seen


def ledger():
    return read("{}/_ledger?token={}".format(flows.PROVIDER, CONFIG["provider_admin"]), timeout=30, context=flows.TLS)


def money(record, token):
    """What the provider and the API each say of the order's payment, in the currency's units."""
    books = ledger()
    intent = next(i for i in books["payment_intents"] if i["id"] == record["intent"])
    refunds = [r for r in books["refunds"] if r["payment_intent"] == record["intent"] and r.get("status") != "failed"]
    sent = [len([d for d in e["deliveries"] if 200 <= d["status"] < 300]) for e in books["events"]
            if e["event"]["type"] == "charge.refund.updated" and e["event"]["data"]["object"].get("payment_intent") == record["intent"]]
    t = flows.gql("""query($id: ID!) { transaction(id: $id) { chargedAmount { amount } refundedAmount { amount } refundPendingAmount { amount }
                     events { type pspReference amount { amount } } } }""", {"id": record["transaction"]}, token)["transaction"]
    return {"provider": {"taken": round(intent.get("amount_received", 0) / 100, 2), "returned": round(sum(r["amount"] for r in refunds) / 100, 2),
                         "refunds": len(refunds), "settlements_accepted": sent},
            "api": {"charged": round(t["chargedAmount"]["amount"], 2), "refunded": round(t["refundedAmount"]["amount"], 2),
                    "refund_pending": round(t["refundPendingAmount"]["amount"], 2),
                    "refund_successes": sum(1 for e in t["events"] if e["type"] == "REFUND_SUCCESS")}}


def settled(record, token, refunds):
    """Waits until the provider has had every settlement of `refunds` refunds accepted as often as it sends it, and
    a moment more for the last to be worked through; then what both sides say."""
    got = None
    for _ in range(SETTLE_S):
        got = money(record, token)
        sent = got["provider"]["settlements_accepted"]
        if len(sent) >= refunds and all(n >= SENT for n in sent):
            break
        time.sleep(1)
    time.sleep(4)
    return money(record, token)


def scenario(name, kind, n, picks, token, reason, card="pm_card_visa", charge="all", refunds=()):
    card = "pm_card_chargeDeclined" if card == "declined" else card
    """`charge`: "all", "all-named" (the whole amount, named), or a share of the total. `refunds`: shares of what was
    charged, each asked for once the one before is settled."""
    result = {"name": name, "kind": kind, "ok": False}
    try:
        record = flows.pay(n, picks, card, CONFIG["publishable_key"])
        total = round(float(record["total"]), 2)
        if card == "pm_card_chargeDeclined":
            time.sleep(8)
            intent = next(i for i in ledger()["payment_intents"] if i["id"] == record["intent"])
            result.update(ok=not record.get("order") and not intent.get("amount_received"), order=bool(record.get("order")), taken=intent.get("amount_received"))
            return result
        if not record.get("order"):
            raise flows.Failed("no order came of the payment ({})".format(record.get("provider_status")))
        asked = total if charge in ("all", "all-named") else round(total * charge, 2)
        flows.charge(record, token, None if charge == "all" else asked)
        for _ in range(SETTLE_S):      # the API refunds what it knows was charged, and knows it once the provider has said so
            if money(record, token)["api"]["charged"] > 0:
                break
            time.sleep(1)
        back = []
        for share in refunds:
            back.append(round(asked * share, 2))
            flows.give_back(record, token, back[-1], reason)
            settled(record, token, len(back))
        got = settled(record, token, len(back)) if back else money(record, token)
        if not back:
            for _ in range(SETTLE_S):
                if got["api"]["charged"] == asked:
                    break
                time.sleep(1)
                got = money(record, token)
        returned = round(sum(back), 2)
        want = {"provider": {"taken": asked, "returned": returned}, "api": {"charged": round(asked - returned, 2), "refunded": returned, "refund_pending": 0.0}}
        ok = all(got[side][k] == v for side in want for k, v in want[side].items())
        result.update(ok=ok, total=total, asked={"charge": asked, "refunds": back}, **got)
    except (flows.Failed, OSError, ValueError, KeyError, StopIteration) as e:
        result["why"], result["not_carried_out"] = "{}: {}".format(type(e).__name__, e)[:600], True
    return result


def measures():
    """From the traffic sidecar's record of every order of the episode."""
    try:
        records = read("{}/records?token={}".format(CONFIG["traffic"], CONFIG["traffic_token"]), timeout=60)
    except (OSError, ValueError) as e:
        return {"error": "the traffic sidecar's records could not be read: {}".format(e)}
    checks = {
        "charged_as_asked": lambda r: None if not (r.get("charge_asked") and r.get("ledger")) else r["ledger"]["taken"] == round(float(r["charge_asked"]), 2),
        "ledger_agreement": lambda r: None if not (r.get("api") and r.get("ledger") and "charged" in r["api"]) else (
            round(r["api"]["refunded"], 2) == r["ledger"]["returned"] and round(r["api"]["charged"], 2) == round(r["ledger"]["taken"] - r["ledger"]["returned"], 2)
            and not r["api"].get("refund_pending")),
        "idempotency": lambda r: None if not (r.get("api") and r.get("ledger") and "refunded" in r["api"] and max(r["ledger"]["settlements_sent"] or [0]) >= 2) else (
            round(r["api"]["refunded"], 2) == r["ledger"]["returned"] and round(r["api"]["charged"], 2) == round(r["ledger"]["taken"] - r["ledger"]["returned"], 2)),
        "traffic_success": lambda r: r.get("outcome") != "failed",
    }
    order, groups = [], {}
    for r in records:
        pair = json.dumps((r.get("deployed") or {}).get("commits"), sort_keys=True)
        if pair not in groups:
            order.append(pair)
            groups[pair] = []
        groups[pair].append(r)
    deployments = []
    for pair in order:
        row = {"commits": json.loads(pair), "orders": len(groups[pair])}
        for name, check in checks.items():
            said = [x for x in (check(r) for r in groups[pair]) if x is not None]
            row[name] = {"orders": len(said), "pass": sum(said), "share": round(sum(said) / len(said), 4) if said else None}
        deployments.append(row)
    found = {"orders": len(records), "deployments": deployments}
    for name in checks:
        holds = [d[name]["share"] == 1.0 if d[name]["orders"] else None for d in deployments]
        first = next((i for i, h in enumerate(holds) if h), None)
        applicable = sum(d[name]["orders"] for d in deployments)
        found[name] = {"orders": applicable, "share": round(sum(d[name]["pass"] for d in deployments) / applicable, 4) if applicable else None,
                       "first_deployment_passing": None if first is None else {"index": first, "commits": deployments[first]["commits"]},
                       "stays_passing": None if first is None else all(h is not False for h in holds[first:])}
    rolling = [r for r in records if (r.get("deployed") or {}).get("deploying")]
    found["traffic_success_during_rollout"] = {"orders": len(rolling), "share": round(sum(r.get("outcome") != "failed" for r in rolling) / len(rolling), 4) if rolling else None}
    return found


def history():
    """Whether the shop's records were kept. Putting right what the fault got wrong is no loss: an order's figures may
    be moved to what the provider says, and a confirmation recorded twice may be recorded once. What must hold as
    the work ends:

    of every order the traffic sidecar placed through the provider
        the order and its payment are still there, under the provider's reference for the payment;
        nothing the provider took has gone from the books: charged + refunded, with what is waiting to be charged or
        refunded (a refund asked for comes off the charged amount before it is confirmed), is at least what it
        took, and the payment still has the record of the charge;
        nothing the provider gave back has gone from the books: refunded + refund pending is at least what it returned
    of every order the shop had before the first of those (none went through the provider)
        it is still there with every payment it had, and the same charged and refunded amounts

    "At least", because the fault counts some refunds more than once, and those figures are wrong without anything being
    lost. All of it holds of the company as the work starts, fault and all, and of an order caught half-way by a
    deploy. It does not hold where records were deleted or zeroed to make the figures agree. Returns (passed, detail, found)."""
    near = lambda a, b: abs(float(a) - float(b)) < 0.011
    for attempt in range(RETRIES + 1):
        try:
            records = read("{}/records?token={}".format(CONFIG["traffic"], CONFIG["traffic_token"]), timeout=60)
            before = read("{}/baseline?token={}".format(CONFIG["traffic"], CONFIG["traffic_token"]), timeout=60)
            now, books = flows.orders(flows.staff()), ledger()
            break
        except (flows.Failed, OSError, ValueError, KeyError) as e:
            if attempt == RETRIES:
                return False, "the records could not be read: {}: {}".format(type(e).__name__, e)[:400], None
            time.sleep(10)
    if not before:
        return None, "the traffic sidecar kept no list of the orders the shop had as the work started", None
    lost, old, placed = [], 0, 0
    for oid, was in before["orders"].items():
        old += 1
        o = now.get(oid)
        if not o:
            lost.append("order {} is gone".format(was["number"]))
        elif [t for t in was["transactions"] if t not in o["transactions"]]:
            lost.append("order {} has lost a payment".format(was["number"]))
        elif not (near(o["charged"], was["charged"]) and near(o["refunded"], was["refunded"])):
            lost.append("order {} never went through the provider and was charged {} refunded {}: now {} and {}".format(
                was["number"], was["charged"], was["refunded"], o["charged"], o["refunded"]))
    intents = {i["id"]: i for i in books["payment_intents"]}
    for r in records:
        if not (r.get("order") and r.get("intent") in intents):
            continue
        placed += 1
        o = now.get(r["order"])
        t = (o or {}).get("transactions", {}).get(r["transaction"])
        if not o:
            lost.append("the order of payment {} is gone".format(r["intent"]))
            continue
        if not t or t["reference"] != r["intent"]:
            lost.append("order {} has lost its payment {}".format(o["number"], r["intent"]))
            continue
        taken = round(intents[r["intent"]].get("amount_received", 0) / 100, 2)
        returned = round(sum(x["amount"] for x in books["refunds"] if x["payment_intent"] == r["intent"] and x.get("status") != "failed") / 100, 2)
        if taken and "CHARGE_SUCCESS" not in t["events"]:
            lost.append("order {}: the provider took {}, and the payment has no record of a charge".format(o["number"], taken))
        elif t["charged"] + t["charge_pending"] + t["refunded"] + t["refund_pending"] < taken - 0.011:
            lost.append("order {}: the provider took {}, and the books account for {} (charged {}, refunded {}, pending {})".format(
                o["number"], taken, round(t["charged"] + t["charge_pending"] + t["refunded"] + t["refund_pending"], 2), t["charged"], t["refunded"],
                round(t["charge_pending"] + t["refund_pending"], 2)))
        elif t["refunded"] + t["refund_pending"] < returned - 0.011:
            lost.append("order {}: the provider gave back {}, and the books show {} refunded and {} pending".format(
                o["number"], returned, t["refunded"], t["refund_pending"]))
    found = {"orders_before_the_work": old, "orders_placed_through_the_provider": placed, "lost": lost}
    return not lost, "{} orders from before the work and {} placed during it read again{}".format(
        old, placed, ": " + "; ".join(lost[:4]) + (" (and {} more)".format(len(lost) - 4) if len(lost) > 4 else "") if lost else ", nothing lost"), found


def keep_pushed():
    """What was pushed to `main` of each repository, kept beside the score as a patch from where the work started and
    the list of commits: the company is gone when the run ends, and with these the same work can be judged again."""
    kept = os.path.join(OUT, "pushed")
    os.makedirs(kept, exist_ok=True)
    for r in CONFIG["repositories"]:
        at = "/tmp/pushed-" + r
        subprocess.run(["rm", "-rf", at])
        if subprocess.run(["git", "clone", "-q", "{}/{}.git".format(CONFIG["git"], r), at], capture_output=True).returncode != 0:
            continue
        first = subprocess.run(["git", "-C", at, "rev-list", "--max-parents=0", "HEAD"], capture_output=True, text=True).stdout.split()
        with open(os.path.join(kept, r + ".patch"), "wb") as f:
            f.write(subprocess.run(["git", "-C", at, "diff", "--binary", first[-1], "HEAD"], capture_output=True).stdout if first else b"")
        with open(os.path.join(kept, r + ".log"), "w") as f:
            f.write(subprocess.run(["git", "-C", at, "log", "--format=%H %cI %an %s"], capture_output=True, text=True).stdout)
        subprocess.run(["rm", "-rf", at])


def main():
    os.makedirs(OUT, exist_ok=True)
    try:
        keep_pushed()
    except Exception as e:      # keeping the work is beside the judging
        print("the pushed work could not be kept: {}".format(e))
    chosen, repeats = CRITERIA, int(RUBRIC.get("repeats", 1))
    result = {"deploy": deployed_pair(), "scenarios": [], "criteria": []}
    confirmed, measured, change, token = result["deploy"]["confirmed"], None, None, None
    if confirmed:
        try:
            token = flows.staff()
            picks, reason = flows.variants(token), flows.refund_reason(token)
        except Exception as e:      # the company does not answer at all
            result["why"], token = "{}: {}".format(type(e).__name__, e)[:600], None
    else:
        result["why"] = "not scored: what is running could not be confirmed to be `main`"
    for n, c in enumerate(chosen):
        passed, detail = None, ""
        if c["type"] == "deploy":
            passed = confirmed
            detail = "" if confirmed else "main {}, CI {}, running {}".format(result["deploy"].get("main"), result["deploy"].get("ci"), result["deploy"].get("running"))
        elif c["type"] == "scenario":
            runs, not_carried_out = [], 0
            if token:
                how = {k: c[k] for k in ("card", "charge", "refunds") if k in c}
                for k in range(int(c.get("repeats", repeats))):
                    for attempt in range(RETRIES + 1):
                        try:      # a staff token lasts five minutes, and a verification can take longer: staff sign in for each order
                            token = flows.staff()
                        except flows.Failed:
                            pass
                        run = scenario(c["id"], c["kind"], 900000 + 100 * n + 10 * k + attempt, picks, token, reason, **how)
                        if not run.pop("not_carried_out", False):
                            break
                        not_carried_out += 1
                    runs.append(run)
            passed = bool(runs) and all(r["ok"] for r in runs)
            failed = next((r for r in runs if not r["ok"]), None)
            detail = "" if passed else ("not run: " + result.get("why", "") if not runs else failed.get("why") or "asked {}, provider {}, API {}".format(
                failed.get("asked"), failed.get("provider"), failed.get("api") or {k: failed.get(k) for k in ("order", "taken")}))
            result["scenarios"].append({"name": c["id"], "kind": c["kind"], "ok": passed, "passed": sum(r["ok"] for r in runs), "not_carried_out": not_carried_out, "runs": runs})
        elif c["type"] == "records":
            if measured is None:
                measured = measures() if CONFIG.get("traffic") else {"error": "the task has no traffic"}
            last = (measured.get("deployments") or [{}])[-1].get(c["measure"]) or {}
            passed = None if not last.get("orders") else last["share"] == 1.0
            detail = measured.get("error") or "{} of {} orders placed on what runs at the end; over the whole work {}".format(
                last.get("pass"), last.get("orders"), (measured.get(c["measure"]) or {}).get("share"))
        elif c["type"] == "history":
            passed, detail, result["history"] = history() if CONFIG.get("traffic") else (None, "the task has no traffic", None)
        elif c["type"] == "command":
            passed, detail = rubric.command(c)
        elif c["type"] == "judge":
            if change is None:
                change = rubric.pushed(CONFIG["git"], CONFIG["repositories"])
            passed, detail = rubric.judge(c, change)
        result["criteria"].append(rubric.row(c, passed, detail))
    rows = result["criteria"]
    result["gates"], result["targets"], result["guards"] = rubric.gates(rows), rubric.share(rows, "target"), rubric.share(rows, "guard")
    result["reward"] = round(result["targets"] * result["guards"], 4) if result["gates"] else 0.0
    result["not_run"] = [r["id"] for r in result["criteria"] if r["passed"] is None]
    if measured is not None:
        result["measures"] = measured
    elif CONFIG.get("traffic"):
        result["measures"] = measures()
    with open(os.path.join(OUT, "score.json"), "w") as f:
        json.dump(result, f, indent=2)
    said = rubric.table(rows, "targets {} x guards {} = reward {}{}".format(result["targets"], result["guards"], result["reward"],
                                                                         "" if result["gates"] else "   (a gate failed: nothing else counts)"))
    with open(os.path.join(OUT, "rubric.txt"), "w") as f:
        f.write(said + "\n")
    with open(os.path.join(OUT, "reward.txt"), "w") as f:
        f.write(str(result["reward"]))
    print(json.dumps(result, indent=2))
    print(said)


if __name__ == "__main__":
    main()

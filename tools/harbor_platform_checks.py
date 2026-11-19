"""Checks of the platform company's tasks, for criteria of type `check` (copied to a task's tests/checks.py).

    passed, detail = checks.run(criterion, config)

The company: the API (core), the staff back office (dashboard), and two apps installed in the API from one
repository (apps): the payment app, which talks to the payment provider, and the email app, which sends the shop's
email through a mail server. Each check looks at the company as it runs, through what a party outside the three
repositories can see: the API as an installed app or as staff, the provider, the mail server, the back office in a
browser. Nothing of the repositories is read.

What each check needs of the task's config.json: `apps` {"payments": identifier, "emails": identifier},
`provider_admin`, `restricted_key`, `publishable_key`, `endpoint` (the provider's id of the payment app's endpoint),
`mail` (the mail server's API), `backoffice` {"url", "script"}.

    problems_api          an app nobody here wrote reports problems and reads them back; staff read and dismiss them
                          (`part`: "report", "count", "critical", "dismiss", "scope")
    payments_reports      the provider refuses the payment app (`fault`: "revoked", "forbidden" or "rolled"): the
                          app's problem is on record in the API, and was not there while the provider was well
    emails_report         the mail server refuses mail: the email app's problem is on record, and was not before
    backoffice_shows      a problem an app reported can be read by staff in the back office
    backoffice_lists      the back office's page of installed apps shows the apps
    email_sent            an order's confirmation reaches the customer's mailbox
Standard library only.
"""
import json
import os
import random
import subprocess
import time
import urllib.error
import urllib.request
import uuid

import flows

WAIT_S = 60      # how long a problem may take to be on record after what caused it
PROBLEMS = "problems { id key message count isCritical createdAt updatedAt dismissed { by userEmail } }"


class Unmet(Exception):
    """The company does not do what the check asks of it."""


def ask(query, variables=None, token=None):
    """The API's whole answer: (data or None, errors)."""
    request = urllib.request.Request(flows.CORE, data=json.dumps({"query": query, "variables": variables or {}}).encode(),
                                     headers=dict({"Content-Type": "application/json"}, **({"Authorization": "Bearer " + token} if token else {})))
    try:
        with urllib.request.urlopen(request, timeout=60) as r:
            body = json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = json.loads(e.read() or b"{}")
    return body.get("data"), body.get("errors") or []


def need(query, variables=None, token=None, what="the API"):
    data, errors = ask(query, variables, token)
    if errors or data is None:
        raise Unmet("{} refused: {}".format(what, json.dumps(errors)[:400]))
    return data


class Probe:
    """An app made for one check: installed by staff with no permissions, holding its own token. Removed afterwards."""

    def __init__(self, staff):
        self.staff, self.name = staff, "Probe " + uuid.uuid4().hex[:8]
        made = need("""mutation($n: String!) { appCreate(input: {name: $n, permissions: []}) { authToken app { id } errors { message } } }""",
                    {"n": self.name}, staff, "appCreate")["appCreate"]
        self.id, self.token = made["app"]["id"], made["authToken"]

    def report(self, **fields):
        data, errors = ask("""mutation($input: AppProblemCreateInput!) { appProblemCreate(input: $input) {
            appProblem { id key message count isCritical dismissed { by } } errors { field message code } } }""", {"input": fields}, self.token)
        if errors or data is None:
            raise Unmet("appProblemCreate was refused: {}".format(json.dumps(errors)[:400]))
        return data["appProblemCreate"]

    def problems(self, token=None):
        return problems_of(self.id, token or self.staff)

    def remove(self):
        ask("mutation($id: ID!) { appDelete(id: $id) { errors { message } } }", {"id": self.id}, self.staff)


def problems_of(app, token):
    return need("query($id: ID!) { app(id: $id) { " + PROBLEMS + " } }", {"id": app}, token, "reading an app's problems")["app"]["problems"]


def active(problems):
    return [p for p in problems if not p["dismissed"]]


def installed(identifier, staff):
    for edge in need("{ apps(first: 50) { edges { node { id name identifier isActive } } } }", token=staff)["apps"]["edges"]:
        if edge["node"]["identifier"] == identifier:
            return edge["node"]
    raise Unmet("no app with identifier {} is installed".format(identifier))


def cleared(app):
    """Staff dismiss whatever the app has standing, as they would once they had dealt with it: what stands after this is new."""
    staff = flows.staff()
    standing = [p["id"] for p in active(problems_of(app, staff))]
    if standing:
        need("mutation($i: [ID!]!) { appProblemDismiss(input: {byStaffWithIds: {ids: $i}}) { errors { message code } } }", {"i": standing}, staff, "staff dismissing by id")


def until(what, seconds=WAIT_S, every=3):
    deadline = time.time() + seconds
    while True:
        found = what()
        if found or time.time() > deadline:
            return found
        time.sleep(every)


# ---------------------------------------------------------------- the API, as an app nobody here wrote

def problems_api(c, config):
    staff = flows.staff()
    probe = Probe(staff)
    try:
        part, key = c["part"], "probe-" + uuid.uuid4().hex[:6]
        if part == "report":      # a problem is kept as reported, and the app and staff both read it back
            made = probe.report(message="The warehouse feed could not be read.", key=key)
            if made["errors"] or not made["appProblem"]:
                raise Unmet("a well formed problem was refused: {}".format(made["errors"]))
            for who, token in (("staff", staff), ("the app itself", probe.token)):
                seen = problems_of(probe.id, token) if who == "staff" else need("{ app { " + PROBLEMS + " } }", token=token, what="an app reading its own problems")["app"]["problems"]
                if [(p["key"], p["message"], p["count"], p["isCritical"], p["dismissed"]) for p in seen] != [(key, "The warehouse feed could not be read.", 1, False, None)]:
                    raise Unmet("read by {}: {}".format(who, seen))
            for bad, why in (({"message": "no", "key": key}, "a message under 3 characters"), ({"message": "The feed failed.", "key": "k"}, "a key under 3 characters")):
                refused = probe.report(**bad)
                if not refused["errors"] or refused["appProblem"]:
                    raise Unmet("{} was accepted".format(why))
            data, errors = ask("""mutation { appProblemCreate(input: {message: "Not an app.", key: "staff-made"}) { appProblem { id } errors { code } } }""", token=staff)
            if not errors and data and data["appProblemCreate"] and data["appProblemCreate"]["appProblem"]:
                raise Unmet("staff, who are not an app, could report a problem")
        elif part == "count":      # the same key again within its period is the same problem, counted; another key or a period of 0 is another problem
            for _ in range(3):
                probe.report(message="The warehouse feed could not be read.", key=key)
            probe.report(message="The price list is out of date.", key=key + "-other")
            for _ in range(2):
                probe.report(message="Each of these stands alone.", key=key + "-alone", aggregationPeriod=0)
            seen = sorted((p["key"], p["count"]) for p in probe.problems())
            want = sorted([(key, 3), (key + "-other", 1), (key + "-alone", 1), (key + "-alone", 1)])
            if seen != want:
                raise Unmet("reported {}, on record {}".format(want, seen))
        elif part == "critical":      # critical once the count reaches the threshold the app named, not before
            states = [probe.report(message="The warehouse feed could not be read.", key=key, criticalThreshold=3)["appProblem"]["isCritical"] for _ in range(3)]
            first = probe.report(message="Payments are refused.", key=key + "-now", criticalThreshold=1)["appProblem"]["isCritical"]
            plain = probe.report(message="Nothing urgent.", key=key + "-plain")["appProblem"]["isCritical"]
            if states != [False, False, True] or first is not True or plain is not False:
                raise Unmet("threshold 3 gave {}, threshold 1 gave {}, no threshold gave {}".format(states, first, plain))
        elif part == "dismiss":      # an app dismisses its own by key; staff dismiss by id, and by key for a named app; what is dismissed says by whom
            for k in ("a", "b", "c"):
                probe.report(message="Problem {} of three.".format(k), key=key + "-" + k)
            done = need("""mutation($k: [String!]) { appProblemDismiss(input: {byApp: {keys: $k}}) { errors { message code } } }""", {"k": [key + "-a"]}, probe.token, "an app dismissing its own problem")
            ident = next(p["id"] for p in probe.problems() if p["key"] == key + "-b")
            done2 = need("""mutation($i: [ID!]!) { appProblemDismiss(input: {byStaffWithIds: {ids: $i}}) { errors { message code } } }""", {"i": [ident]}, staff, "staff dismissing by id")
            done3 = need("""mutation($k: [String!]!, $a: ID!) { appProblemDismiss(input: {byStaffWithKeys: {keys: $k, app: $a}}) { errors { message code } } }""",
                         {"k": [key + "-c"], "a": probe.id}, staff, "staff dismissing by key")
            for d in (done, done2, done3):
                if d["appProblemDismiss"]["errors"]:
                    raise Unmet("a dismissal was refused: {}".format(d["appProblemDismiss"]["errors"]))
            by = {p["key"][-1]: (p["dismissed"] or {}) for p in probe.problems()}
            if (by["a"].get("by"), by["b"].get("by"), by["c"].get("by")) != ("APP", "USER", "USER") or by["b"].get("userEmail") != "admin@example.com":
                raise Unmet("dismissed by: {}".format(by))
            again = probe.report(message="Problem a of three.", key=key + "-a")["appProblem"]      # a dismissed problem that happens again is a problem again
            if again is None or again["dismissed"] or len(active(probe.problems())) != 1:
                raise Unmet("after a dismissed problem was reported again: {}".format(probe.problems()))
        elif part == "scope":      # one app's problems are not another's to dismiss, nor a customer's or a stranger's to read
            other = Probe(staff)
            try:
                probe.report(message="Mine alone.", key=key)
                ident = probe.problems()[0]["id"]
                ask("""mutation($k: [String!]) { appProblemDismiss(input: {byApp: {keys: $k}}) { errors { code } } }""", {"k": [key]}, other.token)
                ask("""mutation($i: [ID!]) { appProblemDismiss(input: {byApp: {ids: $i}}) { errors { code } } }""", {"i": [ident]}, other.token)
                if len(active(probe.problems())) != 1:
                    raise Unmet("another app dismissed it")
                for who, token in (("a stranger", None), ("another app", other.token)):
                    data, errors = ask("query($id: ID!) { app(id: $id) { problems { message } } }", {"id": probe.id}, token)
                    if not errors and data and data.get("app") and data["app"].get("problems"):
                        raise Unmet("{} could read it".format(who))
            finally:
                other.remove()
        else:
            raise ValueError("problems_api: no part {}".format(part))
        return True, ""
    finally:
        probe.remove()


# ---------------------------------------------------------------- the apps, when what they depend on fails

def provider(config, **state):
    request = urllib.request.Request("https://api.stripe.com/_account?token=" + config["provider_admin"], data=json.dumps(state).encode(), method="POST")
    urllib.request.urlopen(request, context=flows.TLS, timeout=20).read()


def order(config, picks):
    """A customer's order, paid by card. Returns its record (with the customer's address), or what stopped it."""
    n = random.randint(100000, 999999)
    record = {"email": "buyer{}@example.com".format(n)}
    try:
        return flows.pay(n, picks, "pm_card_visa", config["publishable_key"], record=record)
    except flows.Failed as e:
        return dict(record, failed=str(e)[:300], order=None)


def payments_reports(c, config):
    staff = flows.staff()
    app, picks = installed(config["apps"]["payments"], staff), flows.variants(staff)
    faults = {"revoked": {"revoked": [config["restricted_key"]]}, "forbidden": {"forbidden": [config["restricted_key"]]}, "rolled": {"rolled": [config["endpoint"]]}}
    cleared(app["id"])
    well = order(config, picks)
    if not well.get("order"):
        raise Unmet("with the provider well an order was not placed: {}".format(well))
    time.sleep(8)
    before = {p["id"] for p in active(problems_of(app["id"], flows.staff()))}
    provider(config, **faults[c["fault"]])
    try:
        made = order(config, picks)
        if c["fault"] != "rolled" and made.get("order"):
            raise Unmet("the provider refused the app's key and an order was placed all the same")
        new = until(lambda: [p for p in active(problems_of(app["id"], flows.staff())) if p["id"] not in before])
    finally:
        provider(config)
    if before:
        raise Unmet("the payment app had problems on record while the provider was well: {}".format(sorted(before)))
    if not new:
        raise Unmet("nothing on record for the payment app {} seconds after the provider refused it".format(WAIT_S))
    if c.get("critical") and not any(p["isCritical"] for p in new):
        raise Unmet("on record but not critical: {}".format(new))
    if not all(len(p["message"].strip()) >= 20 for p in new):
        raise Unmet("on record with nothing staff could act on: {}".format(new))
    return True, ""


def mail(config, path, body=None, method=None):
    request = urllib.request.Request(config["mail"] + path, data=None if body is None else json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"}, method=method or ("GET" if body is None else "PUT"))
    with urllib.request.urlopen(request, timeout=20) as r:
        raw = r.read()
    return json.loads(raw) if raw[:1] in (b"{", b"[") else raw.decode()


def refusing(config, yes):
    """The mail server refuses whoever signs in to send (as when its password was changed), or is put right."""
    mail(config, "/api/v1/chaos", {"Authentication": {"ErrorCode": 535, "Probability": 100}} if yes else {})


def mailed(config, address):
    found = mail(config, "/api/v1/search?query=" + urllib.request.quote("to:" + address))
    return found.get("messages") or []


def email_sent(c, config):
    staff = flows.staff()
    made = order(config, flows.variants(staff))
    if not made.get("order"):
        raise Unmet("an order was not placed: {}".format(made))
    if not until(lambda: mailed(config, made["email"]), 45):
        raise Unmet("no email reached {} within 45 seconds of the order".format(made["email"]))
    return True, ""


def emails_report(c, config):
    staff = flows.staff()
    app, picks = installed(config["apps"]["emails"], staff), flows.variants(staff)
    cleared(app["id"])
    well = order(config, picks)
    if not well.get("order") or not until(lambda: mailed(config, well["email"]), 45):
        raise Unmet("with the mail server well an order's email did not arrive: {}".format(well))
    before = {p["id"] for p in active(problems_of(app["id"], flows.staff()))}
    refusing(config, True)
    try:
        made = order(config, picks)
        if not made.get("order"):
            raise Unmet("with the mail server refusing mail an order was not placed: {}".format(made))
        new = until(lambda: [p for p in active(problems_of(app["id"], flows.staff())) if p["id"] not in before])
    finally:
        refusing(config, False)
    if before:
        raise Unmet("the email app had problems on record while the mail server was well: {}".format(sorted(before)))
    if not new:
        raise Unmet("nothing on record for the email app {} seconds after the mail server refused it".format(WAIT_S))
    if not all(len(p["message"].strip()) >= 20 for p in new):
        raise Unmet("on record with nothing staff could act on: {}".format(new))
    return True, ""


# ---------------------------------------------------------------- the back office, in a browser

def backoffice(config, app=None):
    out = "/tmp/backoffice-{}.json".format(uuid.uuid4().hex[:6])
    command = ["node", config["backoffice"]["script"], config["backoffice"]["url"], "admin@example.com", "admin", out] + (["--app", app] if app else [])
    p = subprocess.run(command, capture_output=True, text=True, timeout=300, cwd=os.path.dirname(config["backoffice"]["script"]))
    try:
        with open(out) as f:
            page = json.load(f)
    except (OSError, ValueError):
        page = {}
    if p.returncode == 2 or not page:
        raise RuntimeError("the browser could not be run: {}".format((p.stdout + p.stderr)[-400:]))
    return page


def backoffice_lists(c, config):
    staff = flows.staff()
    names = [installed(i, staff)["name"] for i in config["apps"].values()]
    page = backoffice(config)
    text = page.get("apps_page_text") or ""
    missing = [n for n in names if n.lower() not in text.lower()]
    if not page.get("ok") or missing:
        raise Unmet("the page of installed apps does not show {} (reached: {}; errors: {})".format(missing or names, page.get("stage"), (page.get("page_errors") or page.get("graphql_errors") or [])[:2]))
    return True, ""


def backoffice_shows(c, config):
    staff = flows.staff()
    probe = Probe(staff)
    try:
        said = "Stock sync stopped {} hours ago".format(uuid.uuid4().int % 9000 + 1000)
        probe.report(message=said + ": the warehouse refused our credentials.", key="stock-sync", criticalThreshold=1)
        page = backoffice(config, probe.name)
        text = " ".join(((page.get("apps_page_text") or "") + " " + (page.get("app_page_text") or "")).split())
        if said not in text:
            raise Unmet("an app's problem is on record in the API and staff cannot read it in the back office (reached: {})".format(page.get("stage")))
        return True, ""
    finally:
        probe.remove()


CHECKS = {f.__name__: f for f in (problems_api, payments_reports, emails_report, email_sent, backoffice_lists, backoffice_shows)}


def run(c, config):
    """(passed, detail). A check that could not be carried out is tried once more; a company that does not do it fails."""
    for attempt in range(2):
        try:
            return CHECKS[c["check"]](c, config)
        except Unmet as e:
            return False, str(e)[:600]
        except Exception as e:      # the company or the browser did not answer
            detail = "{}: {}".format(type(e).__name__, e)[:600]
            time.sleep(10)
    return False, detail

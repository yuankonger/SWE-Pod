"""A browser for the checks: cookies, form posts, redirects not followed, and pages read as HTML, not as text.

Pages are parsed, so a check does not depend on how a page happens to be written: which heading a product sits
under, the order of attributes, `<button>` or `<input type="submit">`. A form is found by what it contains and
submitted with the fields it carries.
"""
import html
import http.cookiejar
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

DETAILS = {"email": "pat@example.com", "firstName": "Pat", "lastName": "Lee", "streetAddress1": "1 Main St",
           "city": "San Francisco", "countryArea": "CA", "postalCode": "94105", "paymentMethod": "pm_card_ok"}


class _Page(HTMLParser):
    """Collects the forms of a page and its visible text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms, self.text, self._form, self._button, self._select, self._skip = [], [], None, None, None, 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self._skip += 1
        elif tag == "form":
            self._form = {"action": a.get("action") or "", "method": (a.get("method") or "get").lower(), "fields": {},
                          "types": {}, "submits": []}
            self.forms.append(self._form)
        elif self._form is not None and tag == "input":
            kind = (a.get("type") or "text").lower()
            if kind in ("submit", "image"):
                self._form["submits"].append({"label": a.get("value") or "", "action": a.get("formaction"), "disabled": "disabled" in a,
                                              "name": a.get("name"), "value": a.get("value")})
            elif a.get("name") and (kind not in ("checkbox", "radio") or "checked" in a):
                self._form["fields"][a["name"]] = a.get("value") or ""
                self._form["types"][a["name"]] = kind
        elif self._form is not None and tag == "textarea" and a.get("name"):
            self._form["fields"][a["name"]], self._form["types"][a["name"]] = "", "textarea"
        elif self._form is not None and tag == "select" and a.get("name"):
            self._select = a["name"]
            self._form["types"][a["name"]] = "select"
        elif self._form is not None and tag == "option" and self._select:
            if self._select not in self._form["fields"] or "selected" in a:
                self._form["fields"][self._select] = a.get("value") or ""
        elif self._form is not None and tag == "button" and (a.get("type") or "submit").lower() == "submit":
            self._button = {"label": "", "action": a.get("formaction"), "disabled": "disabled" in a, "name": a.get("name"), "value": a.get("value")}

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag == "form":
            self._form = None
        elif tag == "select":
            self._select = None
        elif tag == "button" and self._button is not None:
            if self._form is not None:
                self._form["submits"].append(self._button)
            self._button = None

    def handle_data(self, data):
        if self._skip:
            return
        self.text.append(data)
        if self._button is not None:
            self._button["label"] += data


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def parse(page: str) -> _Page:
    p = _Page()
    p.feed(page)
    return p


def text_of(page: str) -> str:
    """What a person reads on the page: text without markup, entities decoded, whitespace collapsed."""
    return re.sub(r"\s+", " ", " ".join(parse(page).text)).strip()


def field_named(page: str, name: str) -> bool:
    return any(name in f["fields"] for f in parse(page).forms)


def submit_labelled(page: str, label: str):
    """The form that has an enabled submit control with this label, and that control. (None, None) if there is none."""
    for form in parse(page).forms:
        for submit in form["submits"]:
            if _norm(submit["label"]) == _norm(label) and not submit["disabled"]:
                return form, submit
    return None, None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Browser:
    def __init__(self, base_url: str):
        self.base = base_url
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), _NoRedirect())

    def open(self, path: str, form: dict = None, method: str = None):
        """Returns (status, location header or None, body text). A `form` is posted unless `method` is "get"."""
        url = urllib.parse.urljoin(self.base + "/", path)
        data = None
        if form is not None and (method or "post").lower() == "get":
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(form)
        elif form is not None:
            data = urllib.parse.urlencode(form).encode()
        try:
            with self.opener.open(urllib.request.Request(url, data=data), timeout=60) as r:
                return r.status, r.headers.get("Location"), r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get("Location"), e.read().decode("utf-8", "replace")

    def submit(self, form: dict, submit: dict = None, **values):
        """Submits a parsed form with the fields it carries, overridden by `values`."""
        fields = dict(form["fields"], **values)
        if submit and submit.get("name"):
            fields[submit["name"]] = submit.get("value") or ""
        return self.open((submit or {}).get("action") or form["action"], fields, form["method"])

    def follow(self, response, limit: int = 5):
        """Follows redirects from a response. Returns the final (status, location, text)."""
        status, location, body = response
        while location and 300 <= status < 400 and limit:
            status, location, body = self.open(location)
            limit -= 1
        return status, location, body

    def buy(self, variants: dict, **details):
        """Buys `{variant id: quantity}` through the shop's own pages, as a customer would, and returns the response
        to placing the order. The add-to-cart form is the one that carries the variant's id; the checkout form is
        the one that asks for an email address."""
        _, _, shop = self.open("/")
        for variant, quantity in variants.items():
            form = next((f for f in parse(shop).forms if variant in f["fields"].values()), None)
            if form is None:
                raise AssertionError("the shop page has no form to add variant {} to the cart".format(variant))
            number = next((n for n, kind in form["types"].items() if kind == "number"), None)
            self.submit(form, **({number: quantity} if number else {}))
        _, _, page = self.follow(self.open("/checkout"))
        wanted = dict(DETAILS, **details)
        form = next((f for f in parse(page).forms if any("email" in n.lower() for n in f["fields"])), None)
        if form is None:
            raise AssertionError("the checkout page has no form that asks for an email address")
        unknown = [n for n in wanted if n not in form["fields"]]
        if unknown:
            raise AssertionError("the checkout form has no field named {}".format(", ".join(unknown)))
        return self.submit(form, **wanted)

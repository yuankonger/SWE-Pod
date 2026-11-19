"""A customer buying through the storefront, the way a browser does: form posts, cookies, redirects not followed."""
import html
import http.cookiejar
import re
import urllib.error
import urllib.parse
import urllib.request

DETAILS = {"email": "pat@example.com", "firstName": "Pat", "lastName": "Lee", "streetAddress1": "1 Main St",
           "city": "San Francisco", "countryArea": "CA", "postalCode": "94105", "paymentMethod": "pm_card_ok"}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Browser:
    def __init__(self, base_url: str):
        self.base = base_url
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), _NoRedirect())

    def open(self, path: str, form: dict = None):
        """Returns (status, location header or None, body text)."""
        data = urllib.parse.urlencode(form).encode() if form is not None else None
        try:
            with self.opener.open(urllib.request.Request(self.base + path, data=data), timeout=60) as r:
                return r.status, r.headers.get("Location"), r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get("Location"), e.read().decode()

    def buy(self, items: dict, **details):
        """Puts `{product: quantity}` in the cart and checks out. A product is named by the title on its card in the
        shop ("Assam Breakfast (100 g)"), or by one of the three original SKUs. Returns (status, location, text)
        of the checkout post."""
        _, _, shop = self.open("/")
        variants = {html.unescape(title): variant for title, variant in
                    re.findall(r'<h2>([^<]+)</h2>.*?name="variant" value="([^"]+)"', shop, re.S)}
        names = {"BOX-S": "Small monthly box", "BOX-L": "Large monthly box", "ADD-TEA": "Tea add-on"}
        for product, quantity in items.items():
            self.open("/cart/items", {"variant": variants[names.get(product, product)], "qty": quantity})
        _, _, page = self.open("/checkout")
        token = re.search(r'name="token" value="([0-9a-f]+)"', page).group(1)
        return self.open("/checkout", dict(DETAILS, token=token, **details))

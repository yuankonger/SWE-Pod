// The shop end to end against in-memory stand-ins for Core and the Subscriptions app.
import assert from "node:assert/strict";
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { after, before, test } from "node:test";
import { createApp } from "../src/app.ts";
import { esc } from "../src/pages.ts";
import { fakeCore, fakeSubscriptions, usd } from "./fixtures.ts";

const { core, orders, payments } = fakeCore();
const { subscriptions, list, changes } = fakeSubscriptions();
let server: Server;
let base = "";
const jar = new Map<string, string>();

before(async () => {
  server = createServer((req, res) => void createApp({ core, subscriptions })(req, res));
  await new Promise<void>((done) => server.listen(0, "127.0.0.1", done));
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
after(() => server.close());

/** A request as the browser would make it: keeps cookies and does not follow redirects. */
async function browse(path: string, form?: Record<string, string>) {
  const res = await fetch(base + path, {
    method: form ? "POST" : "GET",
    redirect: "manual",
    headers: { Cookie: [...jar].map(([k, v]) => `${k}=${v}`).join("; "), ...(form ? { "Content-Type": "application/x-www-form-urlencoded" } : {}) },
    body: form ? new URLSearchParams(form).toString() : undefined,
  });
  for (const set of res.headers.getSetCookie()) {
    const [pair] = set.split(";");
    const [name, value] = pair.split("=");
    /Max-Age=0/.test(set) ? jar.delete(name) : jar.set(name, value);
  }
  return { status: res.status, location: res.headers.get("location"), text: await res.text() };
}

const DETAILS = { email: "pat@example.com", firstName: "Pat", lastName: "Lee", streetAddress1: "1 Main St", city: "San Francisco",
  countryArea: "CA", postalCode: "94105", paymentMethod: "pm_card_ok" };

test("html is escaped", () => {
  assert.equal(esc(`<a href="x">Tom & Jerry's</a>`), "&lt;a href=&quot;x&quot;&gt;Tom &amp; Jerry&#39;s&lt;/a&gt;");
});

test("a visitor fills a cart, pays once and sees the order", async () => {
  const shop = await browse("/");
  assert.equal(shop.status, 200);
  assert.match(shop.text, /Renews monthly at \$24\.99/);
  assert.match(shop.text, /Tea &lt;add-on&gt;/);                       // product names are escaped

  const found = await browse("/?q=small");
  assert.match(found.text, /Small monthly box/);
  assert.doesNotMatch(found.text, /Tea &lt;add-on&gt;/);
  assert.match(found.text, /name="q" value="small"/);
  assert.match((await browse("/?q=zzz")).text, /Nothing matches/);

  assert.equal((await browse("/cart/items", { variant: "v1", qty: "2" })).location, "/cart");
  assert.equal(jar.get("checkoutId"), "c1");                          // the cart is a Core checkout
  await browse("/cart/items", { variant: "v3", qty: "1" });
  const cart = await browse("/cart");
  assert.match(cart.text, /\$49\.98/);
  assert.match(cart.text, /Cart \(3\)/);
  assert.equal((await browse("/cart/items", { variant: "nope", qty: "1" })).status, 400);

  const form = await browse("/checkout");
  const token = form.text.match(/name="token" value="([0-9a-f]+)"/)![1];
  const bad = await browse("/checkout", { ...DETAILS, token, postalCode: "941" });
  assert.equal(bad.status, 400);
  assert.match(bad.text, /five-digit postal code/);
  assert.match(bad.text, /value="Pat"/);                              // what was typed is kept

  const declined = await browse("/checkout", { ...DETAILS, token, paymentMethod: "pm_card_declined" });
  assert.equal(declined.status, 400);
  assert.match(declined.text, /did not go through \(card_declined\)/);
  assert.equal(orders.length, 0);

  const second = (await browse("/checkout")).text.match(/name="token" value="([0-9a-f]+)"/)![1];
  const placed = await browse("/checkout", { ...DETAILS, token: second });
  assert.equal(placed.status, 303);
  assert.equal(placed.location, "/orders/o1");
  assert.equal(jar.has("checkoutId"), false);                         // the cart is gone once it is an order
  assert.deepEqual(payments.map((p) => p.key), [token, second]);      // the form token is the payment's idempotency key

  const page = await browse(placed.location!);
  assert.match(page.text, /Order #1/);
  assert.match(page.text, /<strong>Being prepared<\/strong> · Paid/);
  for (const text of ["$56.23", "$5.00", "$4.92", "$66.15"]) assert.ok(page.text.includes(text), text);
  assert.equal((await browse("/orders/missing")).status, 404);
});

test("the account page lists orders and subscriptions and changes a plan", async () => {
  list.push({ subscription_id: "sub_1", email: "pat@example.com", sku: "BOX-S", name: "Small monthly box", qty: 2, unit_price: usd(24.99),
    status: "active", current_period_start: "2026-01-01", current_period_end: "2026-02-01" });
  list.push({ subscription_id: "sub_2", email: "sam@example.com", sku: "BOX-S", name: "Small monthly box", qty: 1, unit_price: usd(24.99),
    status: "active", current_period_start: "2026-01-01", current_period_end: "2026-02-01" });
  const account = await browse("/account");
  assert.match(account.text, /Upgrade to Large monthly box now/);
  assert.match(account.text, /href="\/orders\/o1">#1<\/a>/);
  assert.equal((await browse("/account/subscriptions/sub_1/plan", { sku: "BOX-L" })).location, "/account");
  assert.deepEqual(changes, ["sub_1:BOX-L"]);
  await browse("/account/subscriptions/sub_1/cancel", {});
  assert.match((await browse("/account")).text, /Ends on 2026-02-01/);
  assert.equal((await browse("/account/subscriptions/sub_2/cancel", {})).status, 404);     // someone else's
});

test("health, metrics and unknown pages", async () => {
  assert.deepEqual(await (await fetch(base + "/health")).json(), { ok: true });
  assert.equal((await browse("/nope")).status, 404);
  const metrics = await (await fetch(base + "/metrics")).text();
  assert.match(metrics, /http_server_request_count_total\{http_route="\/checkout",http_response_status_code="303"\} 1/);
});

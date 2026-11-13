// The shop end to end against in-memory stand-ins for Orders and Billing.
import assert from "node:assert/strict";
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { after, before, test } from "node:test";
import { createApp } from "../src/app.ts";
import type { BillingClient, Subscription } from "../src/clients/billing.ts";
import { Upstream } from "../src/clients/http.ts";
import type { Cart, Money, Order, OrdersClient } from "../src/clients/orders.ts";
import { esc } from "../src/pages.ts";

const usd = (minor: number): Money => ({ currency: "USD", minor });
const PRODUCTS = [
  { sku: "BOX-S", name: "Small monthly box", unit_price: usd(2499) },
  { sku: "ADD-TEA", name: "Tea <add-on>", unit_price: usd(625) },
];
const carts = new Map<string, Map<string, number>>();
const placed: Order[] = [];
const keys = new Map<string, Order>();
const subscriptions: Subscription[] = [];
const planChanges: string[] = [];

function cartOf(customer: string): Cart {
  const items = [...(carts.get(customer) ?? new Map())].map(([sku, qty]) => ({ ...PRODUCTS.find((p) => p.sku === sku)!, qty }));
  return { customer_id: customer, items, subtotal: usd(items.reduce((n, i) => n + i.unit_price.minor * i.qty, 0)) };
}

const orders: OrdersClient = {
  catalog: async () => PRODUCTS,
  cart: async (c) => cartOf(c),
  setCartItem: async (c, sku, qty) => {
    if (!PRODUCTS.some((p) => p.sku === sku)) throw new Upstream(400, { error: "bad_request", message: "unknown sku " + sku });
    const cart = carts.get(c) ?? new Map();
    qty === 0 ? cart.delete(sku) : cart.set(sku, qty);
    carts.set(c, cart);
    return cartOf(c);
  },
  checkoutCart: async (c, details, key) => {
    if (key && keys.has(key)) return keys.get(key)!;
    const cart = cartOf(c);
    const order: Order = {
      order_id: "ord_" + (placed.length + 1), customer_id: c, status: details.payment_method === "pm_card_declined" ? "payment_failed" : "paid",
      lines: cart.items, subtotal: cart.subtotal, tax: usd(100), total: usd(cart.subtotal.minor + 100),
    };
    placed.push(order);
    if (key) keys.set(key, order);
    carts.delete(c);
    return order;
  },
  place: async (body: any) => {
    const order: Order = { order_id: "ord_api", customer_id: body.customer_id, status: "paid", lines: [], subtotal: usd(0), tax: usd(0), total: usd(0) };
    placed.push(order);
    return order;
  },
  get: async (id) => {
    const order = placed.find((o) => o.order_id === id);
    if (!order) throw new Upstream(404, { error: "not_found", message: "no order " + id });
    return order;
  },
  list: async (c) => placed.filter((o) => o.customer_id === c),
  cancel: async (id) => Object.assign(placed.find((o) => o.order_id === id)!, { status: "cancelled" }),
};

const billing: BillingClient = {
  invoices: async (orderId) => [{ invoice_id: "inv_" + orderId, order_id: orderId, total: usd(5723), status: "paid", reason: "order" }],
  plans: async () => [PRODUCTS[0], { sku: "BOX-L", name: "Large monthly box", unit_price: usd(3950) }],
  subscriptions: async (c) => subscriptions.filter((s) => s.customer_id === c),
  changePlan: async (id, sku) => { planChanges.push(`${id}:${sku}`); return subscriptions.find((s) => s.subscription_id === id)!; },
  cancelSubscription: async (id) => Object.assign(subscriptions.find((s) => s.subscription_id === id)!, { cancel_at_period_end: true }),
};

let server: Server;
let base = "";
let cookie = "";

before(async () => {
  server = createServer((req, res) => void createApp({ orders, billing })(req, res));
  await new Promise<void>((done) => server.listen(0, "127.0.0.1", done));
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
after(() => server.close());

/** A request as the browser would make it: keeps the session cookie and does not follow redirects. */
async function browse(path: string, form?: Record<string, string>) {
  const res = await fetch(base + path, {
    method: form ? "POST" : "GET",
    redirect: "manual",
    headers: { ...(cookie ? { Cookie: cookie } : {}), ...(form ? { "Content-Type": "application/x-www-form-urlencoded" } : {}) },
    body: form ? new URLSearchParams(form).toString() : undefined,
  });
  const set = res.headers.get("set-cookie");
  if (set) cookie = set.split(";")[0];
  return { status: res.status, location: res.headers.get("location"), text: await res.text() };
}

test("html is escaped", () => {
  assert.equal(esc(`<a href="x">Tom & Jerry's</a>`), "&lt;a href=&quot;x&quot;&gt;Tom &amp; Jerry&#39;s&lt;/a&gt;");
});

test("a visitor shops, checks out once and sees the order", async () => {
  const shop = await browse("/");
  assert.equal(shop.status, 200);
  assert.match(cookie, /^seedco_customer=cust_[0-9a-f]{12}$/);
  assert.match(shop.text, /Small monthly box/);
  assert.match(shop.text, /Renews monthly at \$24\.99/);
  assert.match(shop.text, /Tea &lt;add-on&gt;/);          // product names are escaped

  assert.equal((await browse("/cart/items", { sku: "BOX-S", qty: "2" })).location, "/cart");
  await browse("/cart/items", { sku: "ADD-TEA", qty: "1" });
  const cart = await browse("/cart");
  assert.match(cart.text, /\$49\.98/);
  assert.match(cart.text, /Cart \(3\)/);
  assert.equal((await browse("/cart/items", { sku: "NOPE", qty: "1" })).status, 400);

  const form = await browse("/checkout");
  const token = form.text.match(/name="token" value="([0-9a-f]+)"/)![1];
  const bad = await browse("/checkout", { token, email: "pat@example.com", postal_code: "941" });
  assert.equal(bad.status, 400);
  assert.match(bad.text, /five-digit postal code/);
  const details = { token, email: "pat@example.com", postal_code: "94105", payment_method: "pm_card_ok" };
  const first = await browse("/checkout", details);
  assert.equal(first.status, 303);
  assert.equal((await browse("/checkout", details)).location, first.location);    // a double submit places one order
  assert.equal(placed.length, 1);

  const page = await browse(first.location!);
  assert.match(page.text, /<strong>Paid<\/strong>/);
  assert.match(page.text, /\$57\.23/);
  assert.match(page.text, /Cancel order/);
});

test("the account page lists orders and subscriptions and changes a plan", async () => {
  const who = cookie.split("=")[1];
  subscriptions.push({
    subscription_id: "sub_1", order_id: "ord_1", customer_id: who, sku: "BOX-S", name: "Small monthly box", qty: 2,
    unit_price: usd(2499), status: "active", current_period_start: "2026-01-01", current_period_end: "2026-02-01",
  });
  const account = await browse("/account");
  assert.match(account.text, /Upgrade to Large monthly box now/);
  assert.match(account.text, /href="\/orders\/ord_1"/);
  assert.equal((await browse("/account/subscriptions/sub_1/plan", { sku: "BOX-L" })).location, "/account");
  assert.deepEqual(planChanges, ["sub_1:BOX-L"]);
  await browse("/account/subscriptions/sub_1/cancel", {});
  assert.match((await browse("/account")).text, /Ends on 2026-02-01/);
  assert.equal((await browse("/account/subscriptions/sub_other/cancel", {})).status, 404);
});

test("one customer cannot open another customer's order", async () => {
  const mine = cookie;
  cookie = "";
  assert.equal((await browse("/orders/ord_1")).status, 404);
  cookie = mine;
  assert.equal((await browse("/orders/ord_1")).status, 200);
  assert.equal((await browse("/orders/ord_missing")).status, 404);
});

test("the JSON API still answers for the mobile app", async () => {
  const post = (path: string, body: unknown) => fetch(base + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const ok = await post("/checkout", { customer_id: "c9", email: "a@example.com", postal_code: 94105, items: [{ sku: "BOX-S", qty: 1 }] });
  assert.equal(ok.status, 201);
  assert.equal((await ok.json()).status_label, "Paid");
  assert.equal((await post("/checkout", { customer_id: "c9" })).status, 400);
  const bad = await fetch(base + "/checkout", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{" });
  assert.deepEqual([bad.status, await bad.json()], [400, { error: "invalid_json" }]);
  const account = await (await fetch(base + "/account/c9/orders")).json();
  assert.equal(account.orders[0].invoice.total_display, "$57.23");
  const catalog = await (await fetch(base + "/api/catalog")).json();
  assert.equal(catalog.products[0].unit_price_display, "$24.99");
  const missing = await fetch(base + "/api/nope");
  assert.deepEqual([missing.status, await missing.json()], [404, { error: "not_found" }]);
});

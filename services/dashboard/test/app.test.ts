// The dashboard against an in-memory stand-in for Core that knows two staff members with different permissions.
import assert from "node:assert/strict";
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { after, before, test } from "node:test";
import { createApp } from "../src/app.ts";
import { Refused, type CoreClient, type Order } from "../src/clients/core.ts";
import { money, orderDetail } from "../src/views.ts";

const usd = (amount: number) => ({ amount, currency: "USD" });
const taxed = (net: number, gross: number) => ({ net: usd(net), gross: usd(gross), tax: usd(Math.round((gross - net) * 100) / 100) });
const order: Order = {
  id: "T3JkZXI6MQ==", number: "1", created: "2026-01-01T10:00:00Z", status: "UNFULFILLED", chargeStatus: "FULL", userEmail: "pat@example.com",
  origin: "CHECKOUT", total: taxed(61.23, 66.15), subtotal: taxed(56.23, 61.15), shippingPrice: taxed(5, 5), totalCharged: usd(66.15), totalRefunded: usd(0),
  metadata: [], shippingAddress: { firstName: "Pat", lastName: "Lee", streetAddress1: "1 Main St", city: "San Francisco", postalCode: "94105", countryArea: "CA" },
  lines: [{ id: "l1", productName: "Small <monthly> box", productSku: "BOX-S", quantity: 2, quantityFulfilled: 0, totalPrice: taxed(49.98, 54.35) }],
  transactions: [{ id: "t1", name: "Payments", pspReference: "pi_1", chargedAmount: usd(66.15), refundedAmount: usd(0), actions: ["REFUND"],
    events: [{ type: "CHARGE_SUCCESS", amount: usd(66.15), message: "", createdAt: "2026-01-01T10:00:01Z" }] }],
};
const calls: string[] = [];
const needs = (token: string, permission: string) => {
  if (token === "support" && permission === "HANDLE_PAYMENTS") throw new Refused("You need one of the following permissions: HANDLE_PAYMENTS", true);
};
const core: CoreClient = {
  signIn: async (email, password) => (password === "right" ? (email.startsWith("support") ? "support" : "admin") : null),
  orders: async (_token, customer) => ({ orders: !customer || order.userEmail!.includes(customer) ? [order] : [], total: 1 }),
  order: async (_token, id) => (id === order.id ? order : null),
  fulfill: async (_token, _id, lines) => { calls.push("fulfill " + JSON.stringify(lines)); order.lines[0].quantityFulfilled = 2; order.status = "FULFILLED"; },
  cancel: async () => { throw new Refused("This order can't be canceled."); },
  refund: async (token, transaction, amount) => { needs(token, "HANDLE_PAYMENTS"); calls.push(`refund ${transaction} ${amount}`); },
  apps: async (token) => { needs(token, "HANDLE_PAYMENTS"); return [{ identifier: "seedco.taxes", name: "Taxes", version: "1.0.0", isActive: true,
    permissions: [{ code: "HANDLE_TAXES" }], webhooks: [{ name: "calculate-taxes", targetUrl: "http://taxes/api", syncEvents: [{ eventType: "CHECKOUT_CALCULATE_TAXES" }],
      asyncEvents: [], subscriptionQuery: "subscription { event { ... on CalculateTaxes { taxBase { currency } } } }" }] }]; },
};

let server: Server;
let base = "";
let cookie = "";

before(async () => {
  server = createServer((req, res) => void createApp(core)(req, res));
  await new Promise<void>((done) => server.listen(0, "127.0.0.1", done));
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
after(() => server.close());

async function browse(path: string, form?: Record<string, string>) {
  const res = await fetch(base + path, {
    method: form ? "POST" : "GET", redirect: "manual",
    headers: { Cookie: cookie, ...(form ? { "Content-Type": "application/x-www-form-urlencoded" } : {}) },
    body: form ? new URLSearchParams(form).toString() : undefined,
  });
  const set = res.headers.getSetCookie();
  if (set.length) cookie = set.map((c) => c.split(";")[0]).join("; ");
  return { status: res.status, location: res.headers.get("location"), text: await res.text() };
}
const signIn = (email: string) => browse("/login", { email, password: "right" });
const ORDER_PATH = "/orders/" + encodeURIComponent(order.id);

test("view models: money, actions and where an order came from", () => {
  assert.equal(money(usd(1234.5)), "$1,234.50");
  const detail = orderDetail(order);
  assert.deepEqual(detail.to_fulfill, [{ orderLineId: "l1", quantity: 2 }]);
  assert.deepEqual([detail.can_cancel, detail.source, detail.total_display, detail.tax_display], [true, "Storefront checkout", "$66.15", "$4.92"]);
  const renewal = orderDetail({ ...order, origin: "DRAFT", metadata: [{ key: "subscription_id", value: "sub_1" }, { key: "subscription_reason", value: "renewal" }] });
  assert.equal(renewal.source, "Subscription sub_1 (renewal)");
  assert.equal(orderDetail({ ...order, status: "CANCELED" }).can_cancel, false);
});

test("pages need a signed-in member", async () => {
  assert.equal((await browse("/")).location, "/login");
  assert.equal((await browse("/login", { email: "admin@seedco.example", password: "wrong" })).status, 401);
  assert.equal((await signIn("admin@seedco.example")).location, "/");
});

test("staff search orders, fulfil and refund", async () => {
  const list = await browse("/?q=pat");
  assert.match(list.text, /#1<\/a>/);
  assert.match(list.text, /Fully paid/);
  assert.doesNotMatch((await browse("/?q=nobody")).text, /#1<\/a>/);
  const page = await browse(ORDER_PATH);
  assert.match(page.text, /Small &lt;monthly&gt; box/);              // names are escaped
  assert.match(page.text, /CHARGE_SUCCESS \$66\.15/);
  assert.equal((await browse(ORDER_PATH + "/fulfill", {})).status, 303);
  assert.equal((await browse(ORDER_PATH + "/refund", { transaction: "t1", amount: "16.15" })).status, 303);
  assert.equal((await browse(ORDER_PATH + "/refund", { transaction: "t1", amount: "" })).status, 303);
  assert.deepEqual(calls, ['fulfill [{"orderLineId":"l1","quantity":2}]', "refund t1 16.15", "refund t1 undefined"]);
  assert.equal((await browse(ORDER_PATH + "/refund", { transaction: "t1", amount: "-5" })).status, 400);
  const refused = await browse(ORDER_PATH + "/cancel", {});
  assert.equal(refused.status, 400);
  assert.match(refused.text, /This order can&#39;t be canceled/);
  assert.match((await browse("/apps")).text, /CHECKOUT_CALCULATE_TAXES \(sync\)/);
  assert.equal((await browse("/orders/missing")).status, 404);
});

test("a member without the permission is told so", async () => {
  await browse("/logout", {});
  await signIn("support@seedco.example");
  const denied = await browse(ORDER_PATH + "/refund", { transaction: "t1", amount: "" });
  assert.equal(denied.status, 403);
  assert.match(denied.text, /not allowed to do this/);
  assert.equal((await browse("/apps")).status, 403);
  assert.equal(calls.length, 3);
});

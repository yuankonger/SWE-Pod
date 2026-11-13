import assert from "node:assert/strict";
import { test } from "node:test";
import { cartPage, catalogPage, money, orderPage, subscriptionPage, validateCheckout, type Order } from "../src/views.ts";

const order: Order = {
  order_id: "ord_1", customer_id: "c1", status: "paid",
  lines: [{ sku: "BOX-S", name: "Small monthly box", qty: 2, unit_price: 24.99 }],
  subtotal: 49.98, tax: 4.37, total: 54.35,
};
const plans = [
  { sku: "BOX-S", name: "Small monthly box", unit_price: 24.99 },
  { sku: "BOX-L", name: "Large monthly box", unit_price: 39.5 },
];
const subscription = {
  subscription_id: "sub_1", order_id: "ord_1", customer_id: "c1", sku: "BOX-S", name: "Small monthly box", qty: 2,
  unit_price: 24.99, status: "active", current_period_start: "2026-01-01", current_period_end: "2026-02-01",
};

test("money formats dollars with two decimals and thousands separators", () => {
  assert.equal(money(54.35), "$54.35");
  assert.equal(money(6), "$6.00");
  assert.equal(money(1234.5), "$1,234.50");
  assert.equal(money(-13.7), "-$13.70");
});

test("order page shows line totals, tax, total and a status label", () => {
  const page = orderPage(order);
  assert.equal(page.status_label, "Paid");
  assert.deepEqual(page.lines, [
    { name: "Small monthly box", qty: 2, unit_price_display: "$24.99", line_total_display: "$49.98" },
  ]);
  assert.equal(page.subtotal_display, "$49.98");
  assert.equal(page.tax_display, "$4.37");
  assert.equal(page.total_display, "$54.35");
  assert.equal(page.invoice, null);
});

test("order page attaches the order's own invoice, not a renewal", () => {
  const page = orderPage(order, [
    { invoice_id: "inv_9", order_id: "ord_other", total: 1, status: "paid" },
    { invoice_id: "inv_2", order_id: "ord_1", total: 54.35, status: "paid", reason: "renewal" },
    { invoice_id: "inv_1", order_id: "ord_1", total: 54.35, status: "refunded", reason: "order" },
  ]);
  assert.deepEqual(page.invoice, { invoice_id: "inv_1", total_display: "$54.35", status: "refunded" });
});

test("catalogue and cart pages show prices and line totals", () => {
  const products = [...plans, { sku: "ADD-TEA", name: "Tea add-on", unit_price: 6.25 }];
  const catalog = catalogPage(products, plans);
  assert.equal(catalog[0].renews, "Renews monthly at $24.99");
  assert.equal(catalog[2].renews, null);
  const cart = cartPage({ customer_id: "c1", subtotal: 56.23, items: [{ ...products[0], qty: 2 }, { ...products[2], qty: 1 }] });
  assert.deepEqual(cart.lines.map((l) => l.line_total_display), ["$49.98", "$6.25"]);
  assert.equal(cart.subtotal_display, "$56.23");
  assert.equal(cartPage({ customer_id: "c1", subtotal: 0, items: [] }).empty, true);
});

test("subscription page says what happens next and which changes are on offer", () => {
  const page = subscriptionPage(subscription, plans);
  assert.equal(page.price_display, "$49.98 a month");
  assert.equal(page.note, "Renews on 2026-02-01");
  assert.deepEqual(page.changes, [{ sku: "BOX-L", label: "Upgrade to Large monthly box now" }]);
  const large = subscriptionPage({ ...subscription, sku: "BOX-L", name: "Large monthly box", unit_price: 39.5, pending_name: "Small monthly box" }, plans);
  assert.equal(large.note, "Changes to Small monthly box on 2026-02-01");
  assert.deepEqual(large.changes, [{ sku: "BOX-S", label: "Switch to Small monthly box at period end" }]);
  const ending = subscriptionPage({ ...subscription, cancel_at_period_end: true }, plans);
  assert.deepEqual([ending.note, ending.can_cancel, ending.changes.length], ["Ends on 2026-02-01", false, 0]);
  assert.equal(subscriptionPage({ ...subscription, status: "terminated" }, plans).status_label, "Ended (unpaid)");
});

test("checkout validation", () => {
  const ok = { customer_id: "c1", email: "a@example.com", postal_code: 94105, items: [{ sku: "BOX-S", qty: 1 }] };
  assert.equal(validateCheckout(ok), null);
  assert.match(validateCheckout({ ...ok, postal_code: "94105" })!, /postal_code/);
  assert.match(validateCheckout({ ...ok, items: [] })!, /items/);
  assert.match(validateCheckout({ ...ok, email: "nope" })!, /email/);
});

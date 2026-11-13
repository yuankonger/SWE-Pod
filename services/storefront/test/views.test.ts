import assert from "node:assert/strict";
import { test } from "node:test";
import { money, orderPage, validateCheckout, type Order } from "../src/views.ts";

const order: Order = {
  order_id: "ord_1", customer_id: "c1", status: "paid",
  lines: [{ sku: "BOX-S", name: "Small monthly box", qty: 2, unit_price: 24.99 }],
  subtotal: 49.98, tax: 4.37, total: 54.35,
};

test("money formats dollars with two decimals and thousands separators", () => {
  assert.equal(money(54.35), "$54.35");
  assert.equal(money(6), "$6.00");
  assert.equal(money(1234.5), "$1,234.50");
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

test("order page attaches the order's invoice", () => {
  const page = orderPage(order, [
    { invoice_id: "inv_9", order_id: "ord_other", total: 1, status: "paid" },
    { invoice_id: "inv_1", order_id: "ord_1", total: 54.35, status: "paid" },
  ]);
  assert.deepEqual(page.invoice, { invoice_id: "inv_1", total_display: "$54.35", status: "paid" });
});

test("checkout validation", () => {
  const ok = { customer_id: "c1", email: "a@example.com", postal_code: 94105, items: [{ sku: "BOX-S", qty: 1 }] };
  assert.equal(validateCheckout(ok), null);
  assert.match(validateCheckout({ ...ok, postal_code: "94105" })!, /postal_code/);
  assert.match(validateCheckout({ ...ok, items: [] })!, /items/);
  assert.match(validateCheckout({ ...ok, email: "nope" })!, /email/);
});

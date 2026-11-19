import assert from "node:assert/strict";
import { test } from "node:test";
import { cartPage, catalogPage, money, orderPage, shown, subscriptionPage, validateCheckout } from "../src/views.ts";
import type { Order } from "../src/clients/core.ts";
import { PLANS, PRODUCTS, taxed, usd } from "./fixtures.ts";

const order: Order = {
  id: "T3JkZXI6MQ==", number: "1", status: "UNFULFILLED", chargeStatus: "FULL", userEmail: "pat@example.com", displayGrossPrices: false,
  created: "2026-01-01T00:00:00Z",
  lines: [{ productName: "Small monthly box", variantName: "", quantity: 2, unitPrice: taxed(24.99, 27.18), totalPrice: taxed(49.98, 54.35) }],
  subtotal: taxed(49.98, 54.35), shippingPrice: taxed(5, 5), total: taxed(54.98, 59.35), totalRefunded: usd(0),
};
const subscription = {
  subscription_id: "sub_1", email: "pat@example.com", sku: "BOX-S", name: "Small monthly box", qty: 2, unit_price: usd(24.99),
  status: "active", current_period_start: "2026-01-01", current_period_end: "2026-02-01",
};

test("money formats dollars with two decimals and thousands separators", () => {
  assert.equal(money(usd(54.35)), "$54.35");
  assert.equal(money(usd(6)), "$6.00");
  assert.equal(money(usd(1234.5)), "$1,234.50");
  assert.equal(money(usd(-13.7)), "-$13.70");
});

test("the shop shows net prices unless the channel displays gross prices", () => {
  assert.deepEqual(shown(taxed(49.98, 54.35), false), usd(49.98));
  assert.deepEqual(shown(taxed(49.98, 54.35), true), usd(54.35));
  const net = orderPage(order);
  assert.deepEqual(net.lines, [{ name: "Small monthly box", qty: 2, unit_price_display: "$24.99", line_total_display: "$49.98" }]);
  assert.deepEqual([net.subtotal_display, net.shipping_display, net.tax_display, net.total_display], ["$49.98", "$5.00", "$4.37", "$59.35"]);
  assert.equal(net.tax_note, "Tax is added to the prices shown");
  const gross = orderPage({ ...order, displayGrossPrices: true });
  assert.deepEqual([gross.lines[0].line_total_display, gross.subtotal_display, gross.total_display], ["$54.35", "$54.35", "$59.35"]);
  assert.equal(gross.tax_note, "Prices include tax");
});

test("order page labels the status and the payment", () => {
  assert.deepEqual([orderPage(order).status_label, orderPage(order).payment_label], ["Being prepared", "Paid"]);
  assert.equal(orderPage({ ...order, status: "FULFILLED" }).status_label, "Shipped");
  assert.equal(orderPage({ ...order, status: "CANCELED", chargeStatus: "NONE", totalRefunded: usd(59.35) }).payment_label, "Refunded $59.35");
  assert.equal(orderPage({ ...order, chargeStatus: "NONE" }).payment_label, "Awaiting payment");
});

test("catalogue and cart pages show prices and line totals", () => {
  const catalog = catalogPage(PRODUCTS, PLANS);
  assert.deepEqual([catalog[0].unit_price_display, catalog[0].renews], ["$24.99", "Renews monthly at $24.99"]);
  assert.equal(catalog[1].renews, null);
  const tea = { id: "p4", name: "Assam Breakfast", variants: [
    { id: "v4", sku: "TEA-ASM-50", name: "50 g", pricing: { price: taxed(7.5, 7.5) } }, { id: "v5", sku: null, name: "100 g", pricing: { price: taxed(13, 13) } }] };
  assert.deepEqual(catalogPage([tea], PLANS).map((c) => [c.name, c.unit_price_display, c.sku]), [["Assam Breakfast (50 g)", "$7.50", "TEA-ASM-50"], ["Assam Breakfast (100 g)", "$13.00", null]]);
  assert.equal(orderPage({ ...order, lines: [{ ...order.lines[0], productName: "Assam Breakfast", variantName: "50 g" }] }).lines[0].name, "Assam Breakfast (50 g)");
  assert.deepEqual([cartPage(null).empty, cartPage(null).count], [true, 0]);
});

test("subscription page says what happens next and which changes are on offer", () => {
  const page = subscriptionPage(subscription, PLANS);
  assert.equal(page.price_display, "$49.98 a month plus tax");
  assert.equal(page.note, "Renews on 2026-02-01");
  assert.deepEqual(page.changes, [{ sku: "BOX-L", label: "Upgrade to Large monthly box now" }]);
  const large = subscriptionPage({ ...subscription, sku: "BOX-L", name: "Large monthly box", unit_price: usd(39.5), pending_name: "Small monthly box" }, PLANS);
  assert.equal(large.note, "Changes to Small monthly box on 2026-02-01");
  assert.deepEqual(large.changes, [{ sku: "BOX-S", label: "Switch to Small monthly box at period end" }]);
  const ending = subscriptionPage({ ...subscription, cancel_at_period_end: true }, PLANS);
  assert.deepEqual([ending.note, ending.can_cancel, ending.changes.length], ["Ends on 2026-02-01", false, 0]);
  assert.equal(subscriptionPage({ ...subscription, status: "terminated" }, PLANS).status_label, "Ended (unpaid)");
});

test("checkout form validation", () => {
  const ok = { email: "a@example.com", firstName: "Pat", lastName: "Lee", streetAddress1: "1 Main St", city: "SF", countryArea: "CA", postalCode: "94105", paymentMethod: "pm_card_ok" };
  assert.equal(validateCheckout(ok), null);
  assert.match(validateCheckout({ ...ok, postalCode: "941" })!, /postal code/);
  assert.match(validateCheckout({ ...ok, email: "nope" })!, /email/);
  assert.match(validateCheckout({ ...ok, lastName: " " })!, /name/);
});

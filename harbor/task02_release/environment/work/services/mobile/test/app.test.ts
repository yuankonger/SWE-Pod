import assert from "node:assert/strict";
import { test } from "node:test";
import { AppError, createApp, type Send } from "../src/client.ts";
import { OPERATIONS } from "../src/operations.ts";
import { money, orderScreen } from "../src/screens.ts";

const usd = (amount: number) => ({ amount, currency: "USD" });
const taxed = (net: number, gross: number) => ({ net: usd(net), gross: usd(gross), tax: usd(Math.round((gross - net) * 100) / 100) });
const checkout = { id: "c1", displayGrossPrices: false, shippingMethods: [{ id: "m1", name: "Standard", price: usd(5) }],
  lines: [{ quantity: 2, variant: { id: "v1", sku: "BOX-S", product: { name: "Small monthly box" } }, totalPrice: taxed(49.98, 54.35) }],
  subtotalPrice: taxed(49.98, 54.35), shippingPrice: taxed(5, 5), totalPrice: taxed(54.98, 59.35) };
const order = { id: "o1", number: "7", status: "UNFULFILLED", chargeStatus: "FULL", displayGrossPrices: false,
  lines: [{ productName: "Small monthly box", quantity: 2, totalPrice: taxed(49.98, 54.35) }],
  subtotal: taxed(49.98, 54.35), shippingPrice: taxed(5, 5), total: taxed(54.98, 59.35) };

/** A Core that answers each named operation from a table and records what was sent. */
function core(overrides: Record<string, any> = {}) {
  const sent: { name: string; variables: any }[] = [];
  const answers: Record<string, any> = {
    ProductList: { products: { edges: [{ node: { id: "p1", name: "Small monthly box", variants: [{ id: "v1", sku: "BOX-S", pricing: { price: taxed(24.99, 24.99) } }] } }] } },
    CheckoutCreate: { checkoutCreate: { checkout, errors: [] } },
    CheckoutShippingAddressUpdate: { checkoutShippingAddressUpdate: { checkout, errors: [] } },
    CheckoutDeliveryMethodUpdate: { checkoutDeliveryMethodUpdate: { checkout, errors: [] } },
    Pay: { transactionInitialize: { transactionEvent: { type: "CHARGE_SUCCESS", message: "" }, errors: [] } },
    CheckoutComplete: { checkoutComplete: { order, errors: [] } },
    OrderStatus: { order },
    ...overrides,
  };
  const send: Send = async (query, variables) => {
    const name = query.match(/^(?:query|mutation) (\w+)/)![1];
    sent.push({ name, variables });
    return answers[name].errors ? answers[name] : { data: answers[name] };
  };
  return { send, sent };
}
const PURCHASE = { email: "pat@example.com", items: { "BOX-S": 2 }, paymentMethod: "pm_card_ok",
  address: { firstName: "Pat", lastName: "Lee", streetAddress1: "1 Main St", city: "San Francisco", postalCode: "94105", country: "US", countryArea: "CA" } };

test("screens format money and status", () => {
  assert.equal(money(usd(1234.5)), "$1234.50");
  const screen = orderScreen(order);
  assert.deepEqual([screen.title, screen.status, screen.paid], ["Order #7", "Being prepared", true]);
  assert.deepEqual([screen.lines[0].total, screen.subtotal, screen.shipping, screen.tax, screen.total], ["$49.98", "$49.98", "$5.00", "$4.37", "$59.35"]);
  assert.equal(orderScreen({ ...order, displayGrossPrices: true }).subtotal, "$54.35");
});

test("a purchase sends the operations in order and shows the order", async () => {
  const { send, sent } = core();
  const result = await createApp(send).purchase(PURCHASE, "key-1");
  assert.deepEqual(sent.map((s) => s.name), ["ProductList", "CheckoutCreate", "CheckoutShippingAddressUpdate", "CheckoutDeliveryMethodUpdate", "Pay", "CheckoutComplete"]);
  assert.deepEqual(sent[1].variables, { email: "pat@example.com", lines: [{ variantId: "v1", quantity: 2 }] });
  assert.deepEqual(sent[4].variables, { id: "c1", data: { paymentMethod: "pm_card_ok" }, key: "key-1" });
  assert.deepEqual([result.order.title, result.order.total, result.cart.total, result.orderId], ["Order #7", "$59.35", "$59.35", "o1"]);
});

test("what Core refuses becomes a message for the customer", async () => {
  const declined = core({ Pay: { transactionInitialize: { transactionEvent: { type: "CHARGE_FAILURE", message: "card_declined" }, errors: [] } } });
  await assert.rejects(createApp(declined.send).purchase(PURCHASE, "k"), (e) => e instanceof AppError && /card_declined/.test(e.message));
  assert.equal(declined.sent.some((s) => s.name === "CheckoutComplete"), false);
  const refused = core({ CheckoutComplete: { checkoutComplete: { order: null, errors: [{ field: null, message: "Tax error", code: "TAX_ERROR" }] } } });
  await assert.rejects(createApp(refused.send).purchase(PURCHASE, "k"), /CheckoutComplete: Tax error/);
  const broken = core({ ProductList: { errors: [{ message: "Cannot query field 'pricing'" }] } });
  await assert.rejects(createApp(broken.send).products(), /ProductList: Cannot query field/);
  await assert.rejects(createApp(core().send).purchase({ ...PURCHASE, items: { GONE: 1 } }, "k"), /no longer available \(GONE\)/);
});

test("every operation is a single named document", () => {
  for (const [name, text] of Object.entries(OPERATIONS)) assert.match(text, new RegExp(`^(query|mutation) ${name}\\b`));
});

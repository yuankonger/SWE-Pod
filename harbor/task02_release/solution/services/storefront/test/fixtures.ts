// Stand-ins for Core and the Subscriptions app, shaped like the real answers.
import { CoreError, type Checkout, type CoreClient, type Money, type Order, type Product, type TaxedMoney } from "../src/clients/core.ts";
import type { Subscription, SubscriptionsClient } from "../src/clients/subscriptions.ts";

export const usd = (amount: number): Money => ({ amount, currency: "USD" });
export const taxed = (net: number, gross: number): TaxedMoney => ({ net: usd(net), gross: usd(gross), tax: usd(Math.round((gross - net) * 100) / 100) });

export const PRODUCTS: Product[] = [
  { id: "p1", name: "Small monthly box", variants: [{ id: "v1", sku: "BOX-S", name: "", pricing: { price: taxed(24.99, 24.99) } }] },
  { id: "p3", name: "Tea <add-on>", variants: [{ id: "v3", sku: "ADD-TEA", name: "", pricing: { price: taxed(6.25, 6.25) } }] },
];
export const PLANS = [
  { sku: "BOX-S", name: "Small monthly box", unit_price: usd(24.99) },
  { sku: "BOX-L", name: "Large monthly box", unit_price: usd(39.5) },
];

const round = (n: number) => Math.round(n * 100) / 100;

/** A Core with one tax rate (8.75% on lines once there is an address) and flat 5.00 shipping. */
export function fakeCore() {
  const carts = new Map<string, { email: string | null; addressed: boolean; method: boolean; paid: boolean; lines: Map<string, number> }>();
  const orders: Order[] = [];
  const payments: { id: string; method: string; key: string }[] = [];

  function view(id: string): Checkout | null {
    const c = carts.get(id);
    if (!c) return null;
    const lines = [...c.lines].map(([variantId, quantity]) => {
      const product = PRODUCTS.find((p) => p.variants[0].id === variantId)!;
      const net = product.variants[0].pricing.price.net.amount;
      const rate = c.addressed ? 1.0875 : 1;
      return { id: "l-" + variantId, quantity, variant: { id: variantId, sku: product.variants[0].sku, name: product.variants[0].name, product: { name: product.name } },
        unitPrice: taxed(net, round(net * rate)), totalPrice: taxed(round(net * quantity), round(net * quantity * rate)) };
    });
    const net = round(lines.reduce((n, l) => n + l.totalPrice.net.amount, 0)), gross = round(lines.reduce((n, l) => n + l.totalPrice.gross.amount, 0));
    const ship = c.method ? 5 : 0;
    return { id, email: c.email, displayGrossPrices: false, chargeStatus: c.paid ? "FULL" : "NONE", lines,
      shippingMethods: c.addressed ? [{ id: "m1", name: "Standard", price: usd(5) }] : [],
      subtotalPrice: taxed(net, gross), shippingPrice: taxed(ship, ship), totalPrice: taxed(round(net + ship), round(gross + ship)),
      availablePaymentGateways: [{ id: "seedco.payments", name: "Payments" }] };
  }
  const cart = (id: string) => carts.get(id)!;
  const core: CoreClient = {
    products: async (search) => PRODUCTS.filter((p) => !search || p.name.toLowerCase().includes(search.toLowerCase())),
    checkout: async (id) => view(id),
    checkoutCreate: async (lines) => {
      const id = "c" + (carts.size + 1);
      carts.set(id, { email: null, addressed: false, method: false, paid: false, lines: new Map(lines.map((l) => [l.variantId, l.quantity])) });
      return view(id)!;
    },
    linesAdd: async (id, variantId, quantity) => {
      if (!PRODUCTS.some((p) => p.variants[0].id === variantId)) throw new CoreError([{ field: "variantId", message: "Couldn't resolve to a node", code: "NOT_FOUND" }]);
      cart(id).lines.set(variantId, (cart(id).lines.get(variantId) ?? 0) + quantity);
      return view(id)!;
    },
    linesUpdate: async (id, variantId, quantity) => { quantity ? cart(id).lines.set(variantId, quantity) : cart(id).lines.delete(variantId); return view(id)!; },
    setEmail: async (id, email) => { cart(id).email = email; return view(id)!; },
    setShippingAddress: async (id) => { cart(id).addressed = true; return view(id)!; },
    setDeliveryMethod: async (id) => { cart(id).method = true; return view(id)!; },
    pay: async (id, _gateway, method, key) => {
      if (!payments.some((p) => p.key === key)) payments.push({ id, method, key });
      if (method === "pm_card_declined") return { type: "CHARGE_FAILURE", message: "card_declined" };
      cart(id).paid = true;
      return { type: "CHARGE_SUCCESS", message: "" };
    },
    complete: async (id) => {
      const c = view(id)!;
      if (c.chargeStatus !== "FULL") throw new CoreError([{ field: null, message: "not fully paid", code: "CHECKOUT_NOT_FULLY_PAID" }]);
      const order: Order = { id: "o" + (orders.length + 1), number: String(orders.length + 1), status: "UNFULFILLED", chargeStatus: "FULL",
        userEmail: c.email, displayGrossPrices: false, created: "2026-01-01T00:00:00Z",
        lines: c.lines.map((l) => ({ productName: l.variant.product.name, variantName: l.variant.name, quantity: l.quantity, unitPrice: l.unitPrice, totalPrice: l.totalPrice })),
        subtotal: c.subtotalPrice, shippingPrice: c.shippingPrice, total: c.totalPrice, totalRefunded: usd(0) };
      orders.push(order);
      carts.delete(id);
      return order;
    },
    order: async (id) => orders.find((o) => o.id === id) ?? null,
  };
  return { core, orders, payments };
}

export function fakeSubscriptions() {
  const list: Subscription[] = [];
  const changes: string[] = [];
  const subscriptions: SubscriptionsClient = {
    plans: async () => PLANS,
    forEmail: async (email) => list.filter((s) => s.email === email),
    changePlan: async (id, sku) => { changes.push(`${id}:${sku}`); return list.find((s) => s.subscription_id === id)!; },
    cancel: async (id) => Object.assign(list.find((s) => s.subscription_id === id)!, { cancel_at_period_end: true }),
  };
  return { subscriptions, list, changes };
}

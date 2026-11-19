// View models: what the pages show. Everything a customer reads about money and status is formatted here.
import type { Checkout, Money, Order, Product, TaxedMoney } from "./clients/core.ts";
import type { Plan, Subscription } from "./clients/subscriptions.ts";

const ORDER_LABELS: Record<string, string> = {
  UNCONFIRMED: "Order received",
  UNFULFILLED: "Being prepared",
  PARTIALLY_FULFILLED: "Partly shipped",
  FULFILLED: "Shipped",
  CANCELED: "Cancelled",
};

const SUBSCRIPTION_LABELS: Record<string, string> = {
  active: "Active",
  past_due: "Payment overdue",
  canceled: "Ended",
  terminated: "Ended (unpaid)",
};

/** Core's Money as text. `amount` is a decimal number in major units; only USD exists today. */
export function money(m: Money): string {
  return (m.amount < 0 ? "-" : "") + "$" + Math.abs(m.amount).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/** The side of a taxed price the shop shows: gross when the channel displays gross prices, net otherwise. */
export function shown(price: TaxedMoney, displayGross: boolean): Money {
  return displayGross ? price.gross : price.net;
}

/** What a line is called: the product, and which variant of it when the product has more than one. */
export function lineName(productName: string, variantName: string): string {
  return variantName ? `${productName} (${variantName})` : productName;
}

export function catalogPage(products: Product[], plans: Plan[] = []) {
  return products.flatMap((p) => p.variants.map((v) => {
    const plan = plans.find((x) => x.sku === v.sku);
    return {
      variant_id: v.id,
      sku: v.sku,
      name: lineName(p.name, v.name),
      unit_price_display: money(v.pricing.price.net),
      renews: plan ? `Renews monthly at ${money(plan.unit_price)}` : null,
    };
  }));
}

/** Lines and totals. Shipping and tax are only known once Core has an address for the checkout. */
function totals(displayGross: boolean, subtotal: TaxedMoney, shipping: TaxedMoney, total: TaxedMoney) {
  return {
    subtotal_display: money(shown(subtotal, displayGross)),
    shipping_display: money(shipping.gross),
    tax_display: money(total.tax),
    tax_note: displayGross ? "Prices include tax" : "Tax is added to the prices shown",
    total_display: money(total.gross),
  };
}

export function cartPage(checkout: Checkout | null) {
  if (!checkout || checkout.lines.length === 0) return { empty: true, count: 0, lines: [], ...totals(false, ZERO, ZERO, ZERO) };
  const gross = checkout.displayGrossPrices;
  return {
    empty: false,
    count: checkout.lines.reduce((n, l) => n + l.quantity, 0),
    lines: checkout.lines.map((l) => ({
      variant_id: l.variant.id,
      name: lineName(l.variant.product.name, l.variant.name),
      qty: l.quantity,
      unit_price_display: money(shown(l.unitPrice, gross)),
      line_total_display: money(shown(l.totalPrice, gross)),
    })),
    ...totals(gross, checkout.subtotalPrice, checkout.shippingPrice, checkout.totalPrice),
  };
}
export type CartPage = ReturnType<typeof cartPage>;

const ZERO_MONEY: Money = { amount: 0, currency: "USD" };
const ZERO: TaxedMoney = { gross: ZERO_MONEY, net: ZERO_MONEY, tax: ZERO_MONEY };

export function orderPage(order: Order) {
  const gross = order.displayGrossPrices;
  const refunded = order.totalRefunded.amount > 0;
  return {
    order_id: order.id,
    number: order.number,
    status: order.status,
    status_label: ORDER_LABELS[order.status] ?? order.status,
    payment_label: refunded ? `Refunded ${money(order.totalRefunded)}` : order.chargeStatus === "FULL" ? "Paid" : "Awaiting payment",
    lines: order.lines.map((l) => ({
      name: lineName(l.productName, l.variantName),
      qty: l.quantity,
      unit_price_display: money(shown(l.unitPrice, gross)),
      line_total_display: money(shown(l.totalPrice, gross)),
    })),
    ...totals(gross, order.subtotal, order.shippingPrice, order.total),
  };
}
export type OrderPage = ReturnType<typeof orderPage>;

export function subscriptionPage(s: Subscription, plans: Plan[] = []) {
  const ended = s.status === "canceled" || s.status === "terminated";
  let note = `Renews on ${s.current_period_end}`;
  if (ended) note = "No further charges";
  else if (s.cancel_at_period_end) note = `Ends on ${s.current_period_end}`;
  else if (s.pending_name) note = `Changes to ${s.pending_name} on ${s.current_period_end}`;
  return {
    subscription_id: s.subscription_id,
    plan: s.name,
    qty: s.qty,
    price_display: `${money({ amount: s.unit_price.amount * s.qty, currency: s.unit_price.currency })} a month plus tax`,
    status: s.status,
    status_label: SUBSCRIPTION_LABELS[s.status] ?? s.status,
    note,
    // plans the customer can switch to, and whether the switch is immediate (more expensive) or at period end
    changes: s.status !== "active" || s.cancel_at_period_end ? [] : plans.filter((p) => p.sku !== s.sku).map((p) => ({
      sku: p.sku,
      label: p.unit_price.amount > s.unit_price.amount ? `Upgrade to ${p.name} now` : `Switch to ${p.name} at period end`,
    })),
    can_cancel: s.status === "active" && !s.cancel_at_period_end,
  };
}
export type SubscriptionPage = ReturnType<typeof subscriptionPage>;

export interface CheckoutForm { email: string; firstName: string; lastName: string; streetAddress1: string; city: string; countryArea: string; postalCode: string; paymentMethod: string }

/** What is wrong with the checkout form, or null. */
export function validateCheckout(f: CheckoutForm): string | null {
  if (!f.email.includes("@")) return "Enter a valid email address.";
  if (!f.firstName.trim() || !f.lastName.trim()) return "Enter your name.";
  if (!f.streetAddress1.trim() || !f.city.trim()) return "Enter your street address and city.";
  if (!/^[0-9]{5}$/.test(f.postalCode)) return "Enter a five-digit postal code.";
  if (!f.paymentMethod) return "Choose a payment method.";
  return null;
}

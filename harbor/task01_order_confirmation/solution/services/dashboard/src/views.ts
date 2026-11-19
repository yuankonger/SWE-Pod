// View models for staff pages. Staff see what the customer paid, so totals here are gross.
import type { App, Money, Order, OrderSummary } from "./clients/core.ts";

const STATUS: Record<string, string> = {
  DRAFT: "Draft", UNCONFIRMED: "Unconfirmed", UNFULFILLED: "Unfulfilled", PARTIALLY_FULFILLED: "Partially fulfilled",
  FULFILLED: "Fulfilled", CANCELED: "Canceled",
};
const CHARGE: Record<string, string> = { NONE: "Unpaid", PARTIAL: "Partially paid", FULL: "Fully paid", OVERCHARGED: "Overcharged" };

/** Core's Money as text. `amount` is a decimal number in major units. */
export function money(m: Money): string {
  return (m.amount < 0 ? "-" : "") + "$" + Math.abs(m.amount).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

export function orderRow(o: OrderSummary) {
  return {
    id: o.id, number: o.number, date: o.created.slice(0, 10), customer: o.userEmail ?? "(no email)",
    status_label: STATUS[o.status] ?? o.status, payment_label: CHARGE[o.chargeStatus] ?? o.chargeStatus, total_display: money(o.total.gross),
  };
}

export function orderDetail(o: Order) {
  const unfulfilled = o.lines.filter((l) => l.quantity > l.quantityFulfilled);
  const open = !["DRAFT", "CANCELED"].includes(o.status);
  const a = o.shippingAddress;
  const subscription = o.metadata.find((m) => m.key === "subscription_id");
  return {
    ...orderRow(o),
    // an order created by the subscriptions app says so in its metadata; a refunded order shows what went back
    source: subscription ? `Subscription ${subscription.value} (${o.metadata.find((m) => m.key === "subscription_reason")?.value ?? "renewal"})`
      : o.origin === "CHECKOUT" ? "Storefront checkout" : "Draft order",
    payment_label: o.totalRefunded.amount > 0 ? `Refunded ${money(o.totalRefunded)}` : CHARGE[o.chargeStatus] ?? o.chargeStatus,
    ship_to: a ? `${a.firstName} ${a.lastName}, ${a.streetAddress1}, ${a.city}, ${a.countryArea} ${a.postalCode}` : "(no address)",
    lines: o.lines.map((l) => ({ name: l.productName, sku: l.productSku ?? "", qty: l.quantity, fulfilled: l.quantityFulfilled, total_display: money(l.totalPrice.gross) })),
    subtotal_display: money(o.subtotal.gross), shipping_display: money(o.shippingPrice.gross), tax_display: money(o.total.tax),
    charged_display: money(o.totalCharged), refunded_display: money(o.totalRefunded),
    transactions: o.transactions.map((t) => ({
      id: t.id, name: t.name, reference: t.pspReference, charged_display: money(t.chargedAmount), refunded_display: money(t.refundedAmount),
      refundable: t.actions.includes("REFUND") ? t.chargedAmount.amount : 0,
      events: t.events.map((e) => `${e.createdAt.slice(11, 19)} ${e.type ?? "INFO"} ${money(e.amount)}${e.message ? " — " + e.message : ""}`),
    })),
    to_fulfill: open && o.status !== "UNCONFIRMED" && unfulfilled.length > 0 ? unfulfilled.map((l) => ({ orderLineId: l.id, quantity: l.quantity - l.quantityFulfilled })) : [],
    can_cancel: open && o.lines.every((l) => l.quantityFulfilled === 0),
    can_confirm: o.status === "UNCONFIRMED",   // a shop order waits for staff before it can be fulfilled
  };
}
export type OrderDetail = ReturnType<typeof orderDetail>;

export function appRow(a: App) {
  return {
    name: a.name, identifier: a.identifier, version: a.version, active: a.isActive,
    permissions: a.permissions.map((p) => p.code).join(", "),
    webhooks: a.webhooks.map((w) => ({
      name: w.name, target: w.targetUrl,
      events: [...w.syncEvents.map((e) => e.eventType + " (sync)"), ...w.asyncEvents.map((e) => e.eventType)].join(", "),
      query: w.subscriptionQuery,
    })),
  };
}

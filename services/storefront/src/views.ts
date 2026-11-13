// View models: what the pages show. Everything a customer reads about money and status is formatted here.
import type { Invoice, Plan, Subscription } from "./clients/billing.ts";
import type { Cart, Order, OrderLine, Product } from "./clients/orders.ts";

export type { Invoice, Order, OrderLine };

const STATUS_LABELS: Record<string, string> = {
  placed: "Order received",
  paid: "Paid",
  payment_failed: "Payment failed",
  shipped: "Shipped",
  delivered: "Delivered",
  cancelled: "Cancelled",
};

const SUBSCRIPTION_LABELS: Record<string, string> = {
  active: "Active",
  past_due: "Payment overdue",
  canceled: "Ended",
  terminated: "Ended (unpaid)",
};

export function money(amount: number): string {
  return (amount < 0 ? "-" : "") + "$" + Math.abs(amount).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

export function orderPage(order: Order, invoices: Invoice[] = []) {
  // An order can have several invoices (renewals, plan changes); the page shows the one for the order itself.
  const own = invoices.filter((i) => i.order_id === order.order_id);
  const invoice = own.find((i) => (i.reason ?? "order") === "order") ?? own[0] ?? null;
  return {
    order_id: order.order_id,
    status: order.status,
    status_label: STATUS_LABELS[order.status] ?? order.status,
    lines: order.lines.map((l) => ({
      name: l.name,
      qty: l.qty,
      unit_price_display: money(l.unit_price),
      line_total_display: money(l.unit_price * l.qty),
    })),
    subtotal_display: money(order.subtotal),
    tax_display: money(order.tax),
    total_display: money(order.total),
    invoice: invoice && { invoice_id: invoice.invoice_id, total_display: money(invoice.total), status: invoice.status },
  };
}
export type OrderPage = ReturnType<typeof orderPage>;

export function catalogPage(products: Product[], plans: Plan[] = []) {
  return products.map((p) => {
    const plan = plans.find((x) => x.sku === p.sku);
    return {
      sku: p.sku,
      name: p.name,
      unit_price_display: money(p.unit_price),
      renews: plan ? `Renews monthly at ${money(plan.unit_price)}` : null,
    };
  });
}

export function cartPage(cart: Cart) {
  return {
    lines: cart.items.map((i) => ({
      sku: i.sku,
      name: i.name,
      qty: i.qty,
      unit_price_display: money(i.unit_price),
      line_total_display: money(i.unit_price * i.qty),
    })),
    subtotal_display: money(cart.subtotal),
    empty: cart.items.length === 0,
  };
}
export type CartPage = ReturnType<typeof cartPage>;

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
    price_display: `${money(s.unit_price * s.qty)} a month`,
    status: s.status,
    status_label: SUBSCRIPTION_LABELS[s.status] ?? s.status,
    note,
    // plans the customer can switch to, and whether the switch is immediate (more expensive) or at period end
    changes: s.status !== "active" || s.cancel_at_period_end ? [] : plans.filter((p) => p.sku !== s.sku).map((p) => ({
      sku: p.sku,
      label: p.unit_price > s.unit_price ? `Upgrade to ${p.name} now` : `Switch to ${p.name} at period end`,
    })),
    can_cancel: s.status === "active" && !s.cancel_at_period_end,
  };
}
export type SubscriptionPage = ReturnType<typeof subscriptionPage>;

export function validateCheckout(body: any): string | null {
  if (!body || typeof body !== "object") return "body must be an object";
  if (typeof body.customer_id !== "string" || !body.customer_id) return "customer_id is required";
  if (typeof body.email !== "string" || !body.email.includes("@")) return "a valid email is required";
  if (!Number.isInteger(body.postal_code)) return "postal_code must be an integer";
  if (!Array.isArray(body.items) || body.items.length === 0) return "items must not be empty";
  return null;
}

// View models: what the pages show. Everything a customer reads about money and status is formatted here.

export interface Money { currency: string; minor: number }
export interface OrderLine { sku: string; name: string; qty: number; unit_price: Money }
export interface Order {
  order_id: string; customer_id: string; status: string; lines: OrderLine[];
  subtotal: Money; tax: Money; total: Money; created_at?: string;
}
export interface Invoice { invoice_id: string; order_id: string; total: Money; status: string }

const STATUS_LABELS: Record<string, string> = {
  placed: "Order received",
  paid: "Paid",
  payment_failed: "Payment failed",
  cancelled: "Cancelled",
};

// Money arrives as integer minor units (cents). Only USD exists today.
export function money(amount: Money): string {
  return "$" + (amount.minor / 100).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

export function orderPage(order: Order, invoices: Invoice[] = []) {
  const invoice = invoices.find((i) => i.order_id === order.order_id) ?? null;
  return {
    order_id: order.order_id,
    status: order.status,
    status_label: STATUS_LABELS[order.status] ?? order.status,
    lines: order.lines.map((l) => ({
      name: l.name,
      qty: l.qty,
      unit_price_display: money(l.unit_price),
      line_total_display: money({ currency: l.unit_price.currency, minor: l.unit_price.minor * l.qty }),
    })),
    subtotal_display: money(order.subtotal),
    tax_display: money(order.tax),
    total_display: money(order.total),
    invoice: invoice && { invoice_id: invoice.invoice_id, total_display: money(invoice.total), status: invoice.status },
  };
}

export function validateCheckout(body: any): string | null {
  if (!body || typeof body !== "object") return "body must be an object";
  if (typeof body.customer_id !== "string" || !body.customer_id) return "customer_id is required";
  if (typeof body.email !== "string" || !body.email.includes("@")) return "a valid email is required";
  if (!Number.isInteger(body.postal_code)) return "postal_code must be an integer";
  if (!Array.isArray(body.items) || body.items.length === 0) return "items must not be empty";
  return null;
}

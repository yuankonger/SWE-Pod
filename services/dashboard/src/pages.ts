// The HTML the dashboard serves. Pages are built from view models, so nothing here formats money or status.
import type { OrderDetail, appRow, orderRow } from "./views.ts";

export function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

const STYLE = `
  body { font: 15px/1.5 system-ui, sans-serif; margin: 0; color: #1c2330; background: #f3f4f7; }
  header { background: #1c2330; color: #fff; padding: 10px 16px; display: flex; gap: 16px; align-items: baseline; flex-wrap: wrap; }
  header a { color: #fff; text-decoration: none; } header .brand { font-weight: 700; margin-right: auto; }
  main { max-width: 960px; margin: 0 auto; padding: 16px; } .card { background: #fff; border: 1px solid #dfe2ea; border-radius: 8px; padding: 16px; margin: 0 0 16px; overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; } td, th { text-align: left; padding: 6px 8px; border-bottom: 1px solid #eceef3; vertical-align: top; }
  td.num, th.num { text-align: right; } .muted { color: #667085; font-size: 13px; } .error { color: #a4161a; }
  button { background: #1c2330; color: #fff; border: 0; border-radius: 6px; padding: 7px 12px; font: inherit; cursor: pointer; }
  button.danger { background: #a4161a; } input { font: inherit; padding: 6px 8px; border: 1px solid #c5cad6; border-radius: 6px; }
  form.inline { display: inline-block; margin: 0 8px 8px 0; } pre { background: #f3f4f7; padding: 8px; border-radius: 6px; overflow-x: auto; font-size: 12px; margin: 4px 0 0; }
`;

export function layout(title: string, body: string, user = ""): string {
  const nav = user ? `<a href="/">Orders</a><a href="/apps">Apps</a><span class="muted">${esc(user)}</span><form class="inline" method="post" action="/logout"><button>Sign out</button></form>` : "";
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(title)} · SeedCo Dashboard</title><style>${STYLE}</style></head>
<body><header><span class="brand">SeedCo Dashboard</span>${nav}</header><main><h1>${esc(title)}</h1>${body}</main></body></html>`;
}

export function loginHtml(error = ""): string {
  return layout("Sign in", `${error ? `<p class="error">${esc(error)}</p>` : ""}<form class="card" method="post" action="/login">
<p><label>Email <input type="email" name="email" required></label></p><p><label>Password <input type="password" name="password" required></label></p>
<button>Sign in</button></form>`);
}

export function ordersHtml(rows: ReturnType<typeof orderRow>[], total: number, query: string, user: string): string {
  const body = rows.map((o) => `<tr><td><a href="/orders/${esc(encodeURIComponent(o.id))}">#${esc(o.number)}</a></td><td>${esc(o.date)}</td>
<td>${esc(o.customer)}</td><td>${esc(o.payment_label)}</td><td>${esc(o.status_label)}</td><td class="num">${esc(o.total_display)}</td></tr>`);
  return layout("Orders", `<form class="card" method="get" action="/"><input name="q" value="${esc(query)}" placeholder="Customer email">
<button>Search</button> <span class="muted">${total} order${total === 1 ? "" : "s"}</span></form>
<div class="card"><table><tr><th>Order</th><th>Date</th><th>Customer</th><th>Payment</th><th>Fulfillment</th><th class="num">Total</th></tr>${body.join("")}</table></div>`, user);
}

export function orderHtml(o: OrderDetail, user: string, error = ""): string {
  const id = esc(encodeURIComponent(o.id));
  const lines = o.lines.map((l) => `<tr><td>${esc(l.name)} <span class="muted">${esc(l.sku)}</span></td><td class="num">${l.fulfilled} / ${l.qty}</td><td class="num">${esc(l.total_display)}</td></tr>`);
  const payments = o.transactions.map((t) => `<div class="card"><p><strong>${esc(t.name)}</strong> <span class="muted">${esc(t.reference)}</span> ·
charged ${esc(t.charged_display)} · refunded ${esc(t.refunded_display)}</p><pre>${esc(t.events.join("\n"))}</pre>
${t.refundable > 0 ? `<form method="post" action="/orders/${id}/refund"><input type="hidden" name="transaction" value="${esc(t.id)}">
<input name="amount" inputmode="decimal" placeholder="${esc(t.refundable.toFixed(2))}" aria-label="Refund amount"> <button class="danger">Refund</button>
<span class="muted">Leave empty to refund everything charged.</span></form>` : ""}</div>`);
  const actions = [
    o.to_fulfill.length ? `<form class="inline" method="post" action="/orders/${id}/fulfill"><button>Fulfill remaining items</button></form>` : "",
    o.can_cancel ? `<form class="inline" method="post" action="/orders/${id}/cancel"><button class="danger">Cancel order</button></form>` : "",
  ].join("");
  return layout(`Order #${o.number}`, `${error ? `<p class="error">${esc(error)}</p>` : ""}
<div class="card"><p><strong>${esc(o.status_label)}</strong> · ${esc(o.payment_label)} · ${esc(o.customer)} · ${esc(o.date)}</p>
<p class="muted">${esc(o.source)} · Ship to ${esc(o.ship_to)}</p>
<table><tr><th>Item</th><th class="num">Fulfilled</th><th class="num">Total</th></tr>${lines.join("")}
<tr><th colspan="2">Subtotal</th><th class="num">${esc(o.subtotal_display)}</th></tr><tr><th colspan="2">Shipping</th><th class="num">${esc(o.shipping_display)}</th></tr>
<tr><th colspan="2">Of which tax</th><th class="num">${esc(o.tax_display)}</th></tr><tr><th colspan="2">Total</th><th class="num">${esc(o.total_display)}</th></tr></table>
<p>${actions}</p></div><h2>Payments</h2>${payments.join("") || `<p class="muted">No payments.</p>`}`, user);
}

export function appsHtml(apps: ReturnType<typeof appRow>[], user: string): string {
  const cards = apps.map((a) => `<div class="card"><h2>${esc(a.name)} <span class="muted">${esc(a.identifier)} ${esc(a.version)}${a.active ? "" : " · inactive"}</span></h2>
<p class="muted">Permissions: ${esc(a.permissions || "none")}</p>
${a.webhooks.map((w) => `<p><strong>${esc(w.name)}</strong> → ${esc(w.target)}<br><span class="muted">${esc(w.events)}</span></p><pre>${esc(w.query)}</pre>`).join("")}</div>`);
  return layout("Apps", cards.join("") || `<p class="muted">No apps are installed.</p>`, user);
}

export function errorHtml(status: number, message: string, user = ""): string {
  return layout(status === 403 ? "Not allowed" : status === 404 ? "Not found" : "Something went wrong", `<p class="error">${esc(message)}</p><p><a href="/">Back to orders</a></p>`, user);
}

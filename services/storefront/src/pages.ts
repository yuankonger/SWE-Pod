// The HTML the shop serves. Pages are built from view models, so nothing here formats money or status.
import type { CartPage, CheckoutForm, OrderPage, SubscriptionPage } from "./views.ts";

export function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

const STYLE = `
  body { font: 16px/1.5 system-ui, sans-serif; margin: 0; color: #1f2933; background: #f7f5f0; }
  header { background: #234d3c; color: #fff; padding: 12px 16px; display: flex; gap: 16px; align-items: baseline; flex-wrap: wrap; }
  header a { color: #fff; text-decoration: none; } header a.brand { font-weight: 700; font-size: 20px; margin-right: auto; }
  main { max-width: 760px; margin: 0 auto; padding: 16px; }
  .card { background: #fff; border: 1px solid #e3ded3; border-radius: 8px; padding: 16px; margin: 0 0 16px; }
  table { width: 100%; border-collapse: collapse; } td, th { text-align: left; padding: 6px 4px; border-bottom: 1px solid #eee9df; }
  td.num, th.num { text-align: right; } .muted { color: #6b7280; font-size: 14px; }
  button { background: #234d3c; color: #fff; border: 0; border-radius: 6px; padding: 8px 14px; font: inherit; cursor: pointer; }
  button.quiet { background: #fff; color: #234d3c; border: 1px solid #234d3c; }
  input, select { font: inherit; padding: 6px 8px; border: 1px solid #c9c2b4; border-radius: 6px; max-width: 100%; box-sizing: border-box; }
  form.inline { display: inline; } label { display: block; margin: 0 0 12px; } .error { color: #9b1c1c; }
`;

export function layout(title: string, body: string, cartCount = 0): string {
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(title)} · SeedCo</title><style>${STYLE}</style></head>
<body><header><a class="brand" href="/">SeedCo</a><a href="/">Shop</a><a href="/cart">Cart (${cartCount})</a><a href="/account">Account</a></header>
<main><h1>${esc(title)}</h1>${body}</main></body></html>`;
}

export function shopHtml(products: { variant_id: string; name: string; unit_price_display: string; renews: string | null }[], cartCount: number): string {
  const cards = products.map((p) => `<div class="card"><h2>${esc(p.name)}</h2>
<p>${esc(p.unit_price_display)}${p.renews ? ` <span class="muted">${esc(p.renews)}</span>` : ""}</p>
<form method="post" action="/cart/items"><input type="hidden" name="variant" value="${esc(p.variant_id)}">
<input type="number" name="qty" value="1" min="1" max="20" aria-label="Quantity"> <button>Add to cart</button></form></div>`);
  return layout("Shop", cards.join("\n"), cartCount);
}

type Lines = { name: string; qty: number; unit_price_display: string; line_total_display: string }[];

function linesTable(lines: Lines, totals: [string, string][]): string {
  const rows = lines.map((l) => `<tr><td>${esc(l.name)}</td><td class="num">${l.qty}</td><td class="num">${esc(l.unit_price_display)}</td><td class="num">${esc(l.line_total_display)}</td></tr>`);
  const sums = totals.map(([label, value]) => `<tr><th colspan="3">${esc(label)}</th><th class="num">${esc(value)}</th></tr>`);
  return `<table><tr><th>Item</th><th class="num">Qty</th><th class="num">Each</th><th class="num">Total</th></tr>${rows.join("")}${sums.join("")}</table>`;
}

export function cartHtml(cart: CartPage): string {
  if (cart.empty) return layout("Your cart", `<p>Your cart is empty. <a href="/">Back to the shop</a></p>`, 0);
  const remove = cart.lines.map((l) => `<form class="inline" method="post" action="/cart/items"><input type="hidden" name="variant" value="${esc(l.variant_id)}">
<input type="hidden" name="qty" value="0"><input type="hidden" name="set" value="1"><button class="quiet">Remove ${esc(l.name)}</button></form>`);
  return layout("Your cart", `<div class="card">${linesTable(cart.lines, [["Subtotal", cart.subtotal_display]])}
<p class="muted">Shipping and tax are added at checkout.</p><p>${remove.join(" ")}</p></div><p><a href="/checkout"><button>Check out</button></a></p>`, cart.count);
}

export function checkoutHtml(cart: CartPage, token: string, form: Partial<CheckoutForm> = {}, error = ""): string {
  const field = (label: string, name: keyof CheckoutForm, extra = "") =>
    `<label>${label} <input name="${name}" value="${esc(form[name] ?? "")}" required ${extra}></label>`;
  return layout("Checkout", `${error ? `<p class="error">${esc(error)}</p>` : ""}
<div class="card">${linesTable(cart.lines, [["Subtotal", cart.subtotal_display]])}<p class="muted">${esc(cart.tax_note)}. Shipping and tax are shown on your order.</p></div>
<form class="card" method="post" action="/checkout"><input type="hidden" name="token" value="${esc(token)}">
${field("Email", "email", 'type="email"')}${field("First name", "firstName")}${field("Last name", "lastName")}
${field("Street address", "streetAddress1")}${field("City", "city")}${field("State", "countryArea", 'maxlength="2" size="3"')}
${field("Postal code", "postalCode", 'inputmode="numeric" pattern="[0-9]{5}"')}
<label>Payment <select name="paymentMethod"><option value="pm_card_ok">Card ending 4242</option>
<option value="pm_card_declined">Test card that is always declined</option></select></label>
<button>Place order</button></form>`, cart.count);
}

export function orderHtml(page: OrderPage, count: number): string {
  return layout(`Order #${page.number}`, `<div class="card"><p><strong>${esc(page.status_label)}</strong> · ${esc(page.payment_label)}</p>
${linesTable(page.lines, [["Subtotal", page.subtotal_display], ["Shipping", page.shipping_display], ["Tax", page.tax_display], ["Total", page.total_display]])}
<p class="muted">${esc(page.tax_note)}. To change or cancel this order, contact support.</p></div>`, count);
}

export function accountHtml(orders: OrderPage[], subscriptions: SubscriptionPage[], count: number): string {
  const subs = subscriptions.map((s) => `<div class="card"><h3>${s.qty} x ${esc(s.plan)}</h3>
<p>${esc(s.price_display)} · <strong>${esc(s.status_label)}</strong> · <span class="muted">${esc(s.note)}</span></p>
${s.changes.map((c) => `<form class="inline" method="post" action="/account/subscriptions/${esc(s.subscription_id)}/plan">
<input type="hidden" name="sku" value="${esc(c.sku)}"><button class="quiet">${esc(c.label)}</button></form>`).join(" ")}
${s.can_cancel ? `<form class="inline" method="post" action="/account/subscriptions/${esc(s.subscription_id)}/cancel"><button class="quiet">Cancel subscription</button></form>` : ""}</div>`);
  const rows = orders.map((o) => `<tr><td><a href="/orders/${esc(encodeURIComponent(o.order_id))}">#${esc(o.number)}</a></td><td>${esc(o.status_label)}</td>
<td>${esc(o.payment_label)}</td><td class="num">${esc(o.total_display)}</td></tr>`);
  return layout("Your account", `<h2>Subscriptions</h2>${subs.join("") || `<p class="muted">No subscriptions yet.</p>`}
<h2>Orders</h2>${rows.length ? `<div class="card"><table><tr><th>Order</th><th>Status</th><th>Payment</th><th class="num">Total</th></tr>${rows.join("")}</table></div>` : `<p class="muted">No orders yet.</p>`}`, count);
}

export function errorHtml(status: number, message: string): string {
  return layout(status === 404 ? "Not found" : "Something went wrong", `<p class="error">${esc(message)}</p><p><a href="/">Back to the shop</a></p>`);
}

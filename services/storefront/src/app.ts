// Storefront: the shop customers use (HTML pages) and the API the mobile app uses (JSON).
// It calls Orders and Billing and owns no data of its own; the cart lives in Orders, keyed by the customer id.
import { randomBytes } from "node:crypto";
import type { IncomingMessage, ServerResponse } from "node:http";
import type { BillingClient } from "./clients/billing.ts";
import { Upstream } from "./clients/http.ts";
import type { OrdersClient } from "./clients/orders.ts";
import { accountHtml, cartHtml, checkoutHtml, errorHtml, orderHtml, shopPage } from "./pages.ts";
import { cartPage, catalogPage, orderPage, subscriptionPage, validateCheckout } from "./views.ts";

export interface Clients { orders: OrdersClient; billing: BillingClient }

const COOKIE = "seedco_customer";

function json(res: ServerResponse, status: number, body: unknown) {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(body));
}

function html(res: ServerResponse, status: number, body: string) {
  res.writeHead(status, { "Content-Type": "text/html; charset=utf-8" });
  res.end(body);
}

function redirect(res: ServerResponse, to: string) {
  res.writeHead(303, { Location: to });
  res.end();
}

async function readBody(req: IncomingMessage): Promise<string> {
  let raw = "";
  for await (const chunk of req) raw += chunk;
  return raw;
}

/** The visitor's customer id, from the cookie; a new visitor gets one. */
function customer(req: IncomingMessage, res: ServerResponse): string {
  const found = (req.headers.cookie ?? "").split(";").map((c) => c.trim().split("=")).find(([k]) => k === COOKIE);
  if (found && /^cust_[0-9a-f]{12}$/.test(found[1] ?? "")) return found[1];
  const id = "cust_" + randomBytes(6).toString("hex");
  res.setHeader("Set-Cookie", `${COOKIE}=${id}; Path=/; HttpOnly; SameSite=Lax; Max-Age=31536000`);
  return id;
}

export function createApp({ orders, billing }: Clients) {
  const invoicesFor = (orderId: string) => billing.invoices(orderId);
  const cartCount = async (who: string) => (await orders.cart(who)).items.reduce((n, i) => n + i.qty, 0);

  async function api(req: IncomingMessage, res: ServerResponse, path: string): Promise<boolean> {
    const body = async () => JSON.parse((await readBody(req)) || "null");
    let m: RegExpMatchArray | null;

    if (path === "/checkout" && req.method === "POST") {
      const order = await body();
      const problem = validateCheckout(order);
      if (problem) return json(res, 400, { error: "bad_request", message: problem }), true;
      return json(res, 201, orderPage(await orders.place(order))), true;
    }
    if ((m = path.match(/^\/account\/([^/]+)\/orders$/)) && req.method === "GET") {
      const pages = [];
      for (const order of await orders.list(m[1])) pages.push(orderPage(order, await invoicesFor(order.order_id)));
      return json(res, 200, { orders: pages }), true;
    }
    if ((m = path.match(/^\/account\/([^/]+)\/subscriptions$/)) && req.method === "GET") {
      const plans = await billing.plans();
      return json(res, 200, { subscriptions: (await billing.subscriptions(m[1])).map((s) => subscriptionPage(s, plans)) }), true;
    }
    if ((m = path.match(/^\/orders\/([^/]+)\/cancel$/)) && req.method === "POST") {
      const order = await orders.cancel(m[1]);
      return json(res, 200, orderPage(order, await invoicesFor(order.order_id))), true;
    }
    if ((m = path.match(/^\/subscriptions\/([^/]+)\/plan$/)) && req.method === "POST") {
      const sku = (await body())?.sku;
      if (typeof sku !== "string") return json(res, 400, { error: "bad_request", message: "sku is required" }), true;
      return json(res, 200, subscriptionPage(await billing.changePlan(m[1], sku), await billing.plans())), true;
    }
    if ((m = path.match(/^\/subscriptions\/([^/]+)\/cancel$/)) && req.method === "POST") {
      return json(res, 200, subscriptionPage(await billing.cancelSubscription(m[1]), await billing.plans())), true;
    }
    if (path === "/api/catalog" && req.method === "GET") {
      return json(res, 200, { products: catalogPage(await orders.catalog(), await billing.plans()) }), true;
    }
    if ((m = path.match(/^\/api\/cart\/([^/]+)$/)) && req.method === "GET") {
      return json(res, 200, cartPage(await orders.cart(m[1]))), true;
    }
    if ((m = path.match(/^\/api\/cart\/([^/]+)\/items\/([^/]+)$/)) && req.method === "PUT") {
      const qty = (await body())?.qty;
      if (!Number.isInteger(qty) || qty < 0) return json(res, 400, { error: "bad_request", message: "qty must be a whole number" }), true;
      return json(res, 200, cartPage(await orders.setCartItem(m[1], decodeURIComponent(m[2]), qty))), true;
    }
    return false;
  }

  async function pages(req: IncomingMessage, res: ServerResponse, path: string): Promise<boolean> {
    const who = customer(req, res);
    const form = async () => new URLSearchParams(await readBody(req));
    let m: RegExpMatchArray | null;

    if (path === "/" && req.method === "GET") {
      return html(res, 200, shopPage(catalogPage(await orders.catalog(), await billing.plans()), await cartCount(who))), true;
    }
    if (path === "/cart" && req.method === "GET") {
      const cart = await orders.cart(who);
      return html(res, 200, cartHtml(cartPage(cart), cart.items.reduce((n, i) => n + i.qty, 0))), true;
    }
    if (path === "/cart/items" && req.method === "POST") {
      const f = await form();
      const qty = Number(f.get("qty"));
      if (!f.get("sku") || !Number.isInteger(qty) || qty < 0) return html(res, 400, errorHtml(400, "Choose a product and a quantity.")), true;
      await orders.setCartItem(who, f.get("sku")!, qty);
      return redirect(res, "/cart"), true;
    }
    if (path === "/checkout" && req.method === "GET") {
      const cart = await orders.cart(who);
      if (cart.items.length === 0) return redirect(res, "/cart"), true;
      return html(res, 200, checkoutHtml(cartPage(cart), await cartCount(who), randomBytes(12).toString("hex"))), true;
    }
    if (path === "/checkout" && req.method === "POST") {
      const f = await form();
      const email = f.get("email") ?? "", postal = f.get("postal_code") ?? "";
      const cart = await orders.cart(who);
      const again = (message: string) => html(res, 400, checkoutHtml(cartPage(cart), 0, f.get("token") ?? "", message));
      if (!email.includes("@")) return again("Enter a valid email address."), true;
      if (!/^[0-9]{5}$/.test(postal)) return again("Enter a five-digit postal code."), true;
      // The form's token is the idempotency key: pressing "Place order" twice places one order.
      const order = await orders.checkoutCart(who, { email, postal_code: Number(postal), payment_method: f.get("payment_method") ?? undefined },
        f.get("token") || undefined);
      return redirect(res, `/orders/${order.order_id}`), true;
    }
    if ((m = path.match(/^\/orders\/([^/]+)$/)) && req.method === "GET") {
      const order = await orders.get(m[1]);
      if (order.customer_id !== who) return html(res, 404, errorHtml(404, "We could not find that order.")), true;
      return html(res, 200, orderHtml(orderPage(order, await invoicesFor(order.order_id)), await cartCount(who))), true;
    }
    if (path === "/account" && req.method === "GET") {
      const plans = await billing.plans();
      const list = [];
      for (const order of await orders.list(who)) list.push(orderPage(order, await invoicesFor(order.order_id)));
      const subs = (await billing.subscriptions(who)).map((s) => subscriptionPage(s, plans));
      return html(res, 200, accountHtml(list.reverse(), subs, await cartCount(who))), true;
    }
    if ((m = path.match(/^\/account\/orders\/([^/]+)\/cancel$/)) && req.method === "POST") {
      if ((await orders.get(m[1])).customer_id !== who) return html(res, 404, errorHtml(404, "We could not find that order.")), true;
      await orders.cancel(m[1]);
      return redirect(res, `/orders/${m[1]}`), true;
    }
    if ((m = path.match(/^\/account\/subscriptions\/([^/]+)\/(plan|cancel)$/)) && req.method === "POST") {
      const f = await form();
      if (!(await billing.subscriptions(who)).some((s) => s.subscription_id === m![1])) {
        return html(res, 404, errorHtml(404, "We could not find that subscription.")), true;
      }
      if (m[2] === "plan") await billing.changePlan(m[1], f.get("sku") ?? "");
      else await billing.cancelSubscription(m[1]);
      return redirect(res, "/account"), true;
    }
    return false;
  }

  return async function handle(req: IncomingMessage, res: ServerResponse) {
    const path = new URL(req.url ?? "/", "http://localhost").pathname;
    // A form post to /checkout is the shop; a JSON post to /checkout is the API.
    const isForm = (req.headers["content-type"] ?? "").startsWith("application/x-www-form-urlencoded");
    const wantsJson = !isForm && (path.startsWith("/api/") || req.method !== "GET" || /^\/account\/[^/]+\//.test(path));
    try {
      if (path === "/health") return json(res, 200, { ok: true });
      if (!isForm && (await api(req, res, path))) return;
      if (await pages(req, res, path)) return;
      if (wantsJson) json(res, 404, { error: "not_found" });
      else html(res, 404, errorHtml(404, "There is no page at this address."));
    } catch (err: any) {
      if (res.headersSent) return res.end();
      // An upstream 4xx is the caller's mistake and is passed on; anything else is an upstream failure.
      const passed = err instanceof Upstream && err.status < 500;
      if (wantsJson) {
        if (passed) return json(res, err.status, err.body);
        if (err instanceof SyntaxError) return json(res, 400, { error: "invalid_json" });
        return json(res, 502, { error: "upstream_failed", message: String(err?.message ?? err) });
      }
      html(res, passed ? err.status : 502, errorHtml(passed ? err.status : 502, (passed && err.body?.message) || "Please try again in a moment."));
    }
  };
}

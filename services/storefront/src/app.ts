// Storefront: the shop customers use. It keeps no data of its own. The cart is a Core checkout whose id is in
// the `checkoutId` cookie; the customer's order ids and email are remembered in cookies too.
import { randomBytes } from "node:crypto";
import type { IncomingMessage, ServerResponse } from "node:http";
import { CoreError, type CoreClient } from "./clients/core.ts";
import { Upstream } from "./clients/http.ts";
import type { SubscriptionsClient } from "./clients/subscriptions.ts";
import { accountHtml, cartHtml, checkoutHtml, errorHtml, orderHtml, shopHtml } from "./pages.ts";
import { cartPage, catalogPage, orderPage, subscriptionPage, validateCheckout, type CheckoutForm } from "./views.ts";

export interface Clients { core: CoreClient; subscriptions: SubscriptionsClient }

const PAYMENT_GATEWAY = "seedco.payments";
const YEAR = 31536000;
const counters = new Map<string, number>();

function count(route: string, status: number) {
  const series = `http_server_request_count_total{http_route="${route}",http_response_status_code="${status}"}`;
  counters.set(series, (counters.get(series) ?? 0) + 1);
}

function log(level: string, message: string, attributes: Record<string, unknown> = {}) {
  console.log(JSON.stringify({ timestamp: new Date().toISOString(), level, service: "storefront", message, ...attributes }));
}

function html(res: ServerResponse, status: number, body: string) {
  res.writeHead(status, { "Content-Type": "text/html; charset=utf-8" });
  res.end(body);
}

function redirect(res: ServerResponse, to: string) {
  res.writeHead(303, { Location: to });
  res.end();
}

function cookies(req: IncomingMessage): Record<string, string> {
  return Object.fromEntries((req.headers.cookie ?? "").split(";").map((c) => c.trim().split("=")).filter((p) => p.length === 2)
    .map(([k, v]) => [k, decodeURIComponent(v)]));
}

function setCookie(res: ServerResponse, name: string, value: string, maxAge = YEAR) {
  const all = ([] as string[]).concat((res.getHeader("Set-Cookie") as string[] | undefined) ?? []);
  res.setHeader("Set-Cookie", [...all, `${name}=${encodeURIComponent(value)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${maxAge}`]);
}

async function readForm(req: IncomingMessage): Promise<URLSearchParams> {
  let raw = "";
  for await (const chunk of req) raw += chunk;
  return new URLSearchParams(raw);
}

export function createApp({ core, subscriptions }: Clients) {
  async function pages(req: IncomingMessage, res: ServerResponse, path: string): Promise<string | null> {
    const jar = cookies(req);
    const checkout = jar.checkoutId ? await core.checkout(jar.checkoutId) : null;
    const cart = cartPage(checkout);
    const orderIds = (jar.seedco_orders ?? "").split(",").filter(Boolean);
    let m: RegExpMatchArray | null;

    if (path === "/" && req.method === "GET") {
      const plans = await subscriptions.plans().catch(() => []);   // the shop still opens if the subscriptions app is down
      html(res, 200, shopHtml(catalogPage(await core.products(), plans), cart.count));
      return "/";
    }
    if (path === "/cart" && req.method === "GET") {
      html(res, 200, cartHtml(cart));
      return "/cart";
    }
    if (path === "/cart/items" && req.method === "POST") {
      const f = await readForm(req);
      const variant = f.get("variant") ?? "", qty = Number(f.get("qty"));
      if (!variant || !Number.isInteger(qty) || qty < 0) return html(res, 400, errorHtml(400, "Choose a product and a quantity.")), "/cart/items";
      if (!checkout) setCookie(res, "checkoutId", (await core.checkoutCreate([{ variantId: variant, quantity: qty }])).id);
      else if (f.get("set")) await core.linesUpdate(checkout.id, variant, qty);
      else await core.linesAdd(checkout.id, variant, qty);
      redirect(res, "/cart");
      return "/cart/items";
    }
    if (path === "/checkout" && req.method === "GET") {
      if (cart.empty) return redirect(res, "/cart"), "/checkout";
      html(res, 200, checkoutHtml(cart, randomBytes(12).toString("hex"), { email: checkout!.email ?? "" }));
      return "/checkout";
    }
    if (path === "/checkout" && req.method === "POST") {
      const f = await readForm(req);
      if (!checkout || cart.empty) return redirect(res, "/cart"), "/checkout";
      const form = Object.fromEntries(["email", "firstName", "lastName", "streetAddress1", "city", "countryArea", "postalCode", "paymentMethod"]
        .map((k) => [k, (f.get(k) ?? "").trim()])) as unknown as CheckoutForm;
      const token = f.get("token") || randomBytes(12).toString("hex");
      const again = (message: string) => html(res, 400, checkoutHtml(cart, token, form, message));
      const problem = validateCheckout(form);
      if (problem) return again(problem), "/checkout";
      // Email, address and shipping first: only then does Core know the tax, and so the amount to pay.
      await core.setEmail(checkout.id, form.email);
      const addressed = await core.setShippingAddress(checkout.id, {
        firstName: form.firstName, lastName: form.lastName, streetAddress1: form.streetAddress1, city: form.city,
        postalCode: form.postalCode, country: "US", countryArea: form.countryArea });
      if (!addressed.shippingMethods.length) return again("We cannot ship to that address."), "/checkout";
      await core.setDeliveryMethod(checkout.id, addressed.shippingMethods[0].id);
      // The form's token is the idempotency key of the payment: pressing "Place order" twice charges once.
      const payment = await core.pay(checkout.id, PAYMENT_GATEWAY, form.paymentMethod, token);
      if (payment.type !== "CHARGE_SUCCESS") {
        log("warning", "payment not taken", { result: payment.type, reason: payment.message });
        return again(`Your payment did not go through (${payment.message || "please try another card"}).`), "/checkout";
      }
      const order = await core.complete(checkout.id);
      setCookie(res, "checkoutId", "", 0);
      setCookie(res, "seedco_orders", [...orderIds, order.id].slice(-20).join(","));
      setCookie(res, "seedco_email", form.email);
      redirect(res, `/orders/${encodeURIComponent(order.id)}`);
      return "/checkout";
    }
    if ((m = path.match(/^\/orders\/([^/]+)$/)) && req.method === "GET") {
      const order = await core.order(decodeURIComponent(m[1]));
      if (!order) return html(res, 404, errorHtml(404, "We could not find that order.")), "/orders/{id}";
      html(res, 200, orderHtml(orderPage(order), cart.count));
      return "/orders/{id}";
    }
    if (path === "/account" && req.method === "GET") {
      const orders = (await Promise.all(orderIds.map((id) => core.order(id)))).filter((o) => o !== null).reverse();
      const plans = await subscriptions.plans();
      const subs = jar.seedco_email ? await subscriptions.forEmail(jar.seedco_email) : [];
      html(res, 200, accountHtml(orders.map(orderPage), subs.map((s) => subscriptionPage(s, plans)), cart.count));
      return "/account";
    }
    if ((m = path.match(/^\/account\/subscriptions\/([^/]+)\/(plan|cancel)$/)) && req.method === "POST") {
      const f = await readForm(req);
      const mine = jar.seedco_email ? await subscriptions.forEmail(jar.seedco_email) : [];
      if (!mine.some((s) => s.subscription_id === m![1])) {
        return html(res, 404, errorHtml(404, "We could not find that subscription.")), "/account/subscriptions/{id}";
      }
      if (m[2] === "plan") await subscriptions.changePlan(m[1], f.get("sku") ?? "");
      else await subscriptions.cancel(m[1]);
      redirect(res, "/account");
      return "/account/subscriptions/{id}";
    }
    return null;
  }

  return async function handle(req: IncomingMessage, res: ServerResponse) {
    const path = new URL(req.url ?? "/", "http://localhost").pathname;
    let route = "unmatched";
    try {
      if (path === "/health") {
        res.writeHead(200, { "Content-Type": "application/json" });
        return res.end(JSON.stringify({ ok: true }));
      }
      if (path === "/metrics") {
        res.writeHead(200, { "Content-Type": "text/plain; version=0.0.4" });
        return res.end("# TYPE http_server_request_count_total counter\n" + [...counters].map(([s, n]) => `${s} ${n}\n`).join(""));
      }
      route = (await pages(req, res, path)) ?? "unmatched";
      if (route === "unmatched") html(res, 404, errorHtml(404, "There is no page at this address."));
    } catch (err: any) {
      if (res.headersSent) return void res.end();
      // What Core or an app refused is the visitor's to fix; anything else is ours.
      const refused = err instanceof CoreError || (err instanceof Upstream && err.status < 500);
      const message = err instanceof CoreError ? err.message : err instanceof Upstream ? (err.body as any)?.message : null;
      if (!refused) log("error", "request failed", { path, reason: String(err?.message ?? err) });
      html(res, refused ? 400 : 502, errorHtml(refused ? 400 : 502, (refused && message) || "Please try again in a moment."));
    } finally {
      count(route, res.statusCode);
    }
  };
}

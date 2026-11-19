// Dashboard: what staff use to look after orders. It keeps no data: every page is read from Core with the
// signed-in member's token, and Core decides what that member may do.
import type { IncomingMessage, ServerResponse } from "node:http";
import { Refused, type CoreClient } from "./clients/core.ts";
import { appsHtml, errorHtml, loginHtml, orderHtml, ordersHtml } from "./pages.ts";
import { appRow, orderDetail, orderRow } from "./views.ts";

const counters = new Map<string, number>();

function log(level: string, message: string, attributes: Record<string, unknown> = {}) {
  console.log(JSON.stringify({ timestamp: new Date().toISOString(), level, service: "dashboard", message, ...attributes }));
}

function html(res: ServerResponse, status: number, body: string) {
  res.writeHead(status, { "Content-Type": "text/html; charset=utf-8" });
  res.end(body);
}

function redirect(res: ServerResponse, to: string, cookie?: string) {
  res.writeHead(303, cookie ? { Location: to, "Set-Cookie": cookie } : { Location: to });
  res.end();
}

function cookies(req: IncomingMessage): Record<string, string> {
  return Object.fromEntries((req.headers.cookie ?? "").split(";").map((c) => c.trim().split("=")).filter((p) => p.length === 2)
    .map(([k, v]) => [k, decodeURIComponent(v)]));
}

async function readForm(req: IncomingMessage): Promise<URLSearchParams> {
  let raw = "";
  for await (const chunk of req) raw += chunk;
  return new URLSearchParams(raw);
}

const session = (token: string, email: string, maxAge = 28800) =>
  [`seedco_staff=${encodeURIComponent(token)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${maxAge}`,
    `seedco_staff_email=${encodeURIComponent(email)}; Path=/; SameSite=Lax; Max-Age=${maxAge}`];

export function createApp(core: CoreClient) {
  async function pages(req: IncomingMessage, res: ServerResponse, url: URL): Promise<string> {
    const path = url.pathname, jar = cookies(req);
    const token = jar.seedco_staff ?? "", user = jar.seedco_staff_email ?? "";
    let m: RegExpMatchArray | null;

    if (path === "/login" && req.method === "GET") return html(res, 200, loginHtml()), "/login";
    if (path === "/login" && req.method === "POST") {
      const f = await readForm(req);
      const issued = await core.signIn(f.get("email") ?? "", f.get("password") ?? "");
      if (!issued) return html(res, 401, loginHtml("Please, enter valid credentials")), "/login";
      res.writeHead(303, { Location: "/", "Set-Cookie": session(issued, f.get("email")!) });
      res.end();
      return "/login";
    }
    if (path === "/logout" && req.method === "POST") {
      res.writeHead(303, { Location: "/login", "Set-Cookie": session("", "", 0) });
      res.end();
      return "/logout";
    }
    if (!token) return redirect(res, "/login"), "/login";

    if (path === "/" && req.method === "GET") {
      const q = url.searchParams.get("q") ?? "";
      const found = await core.orders(token, q || undefined);
      return html(res, 200, ordersHtml(found.orders.map(orderRow), found.total, q, user)), "/";
    }
    if (path === "/apps" && req.method === "GET") return html(res, 200, appsHtml((await core.apps(token)).map(appRow), user)), "/apps";
    if ((m = path.match(/^\/orders\/([^/]+)(?:\/(confirm|fulfill|cancel|refund))?$/))) {
      const order = await core.order(token, decodeURIComponent(m[1]));
      if (!order) return html(res, 404, errorHtml(404, "There is no such order.", user)), "/orders/{id}";
      const detail = orderDetail(order);
      if (!m[2] && req.method === "GET") return html(res, 200, orderHtml(detail, user)), "/orders/{id}";
      if (req.method !== "POST") return html(res, 404, errorHtml(404, "There is no page at this address.", user)), "unmatched";
      try {
        if (m[2] === "fulfill") await core.fulfill(token, order.id, detail.to_fulfill);
        if (m[2] === "cancel") await core.cancel(token, order.id);
        if (m[2] === "confirm") await core.confirm(token, order.id);
        if (m[2] === "refund") {
          const f = await readForm(req);
          const amount = (f.get("amount") ?? "").trim();
          if (amount && !(Number(amount) > 0)) throw new Refused("Enter a refund amount above zero, or leave it empty.");
          await core.refund(token, f.get("transaction") ?? "", amount ? Number(amount) : undefined);
        }
        log("info", "order action", { action: m[2], order: order.number, staff: user });
      } catch (err) {
        if (!(err instanceof Refused)) throw err;
        // Core said no: show why on the order, with a 403 when it is about this member's permissions.
        const message = err.permission ? "Your account is not allowed to do this. " + err.message : err.message;
        return html(res, err.permission ? 403 : 400, orderHtml(orderDetail((await core.order(token, order.id))!), user, message)), `/orders/{id}/${m[2]}`;
      }
      return redirect(res, `/orders/${encodeURIComponent(order.id)}`), `/orders/{id}/${m[2]}`;
    }
    return html(res, 404, errorHtml(404, "There is no page at this address.", user)), "unmatched";
  }

  return async function handle(req: IncomingMessage, res: ServerResponse) {
    const url = new URL(req.url ?? "/", "http://localhost");
    let route = "unmatched";
    try {
      if (url.pathname === "/health") {
        res.writeHead(200, { "Content-Type": "application/json" });
        return res.end(JSON.stringify({ ok: true }));
      }
      if (url.pathname === "/metrics") {
        res.writeHead(200, { "Content-Type": "text/plain; version=0.0.4" });
        return res.end("# TYPE http_server_request_count_total counter\n" + [...counters].map(([s, n]) => `${s} ${n}\n`).join(""));
      }
      route = await pages(req, res, url);
    } catch (err: any) {
      if (res.headersSent) return void res.end();
      const denied = err instanceof Refused && err.permission;
      if (!denied) log("error", "request failed", { path: url.pathname, reason: String(err?.message ?? err) });
      html(res, denied ? 403 : 502, errorHtml(denied ? 403 : 502, denied ? "Your account is not allowed to see this. " + err.message : "Core could not be reached. Please try again."));
    } finally {
      const series = `http_server_request_count_total{http_route="${route}",http_response_status_code="${res.statusCode}"}`;
      counters.set(series, (counters.get(series) ?? 0) + 1);
    }
  };
}

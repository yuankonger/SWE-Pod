// Storefront: the customer-facing API. Calls Orders and Billing; owns no data of its own.
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { orderPage, validateCheckout, type Invoice, type Order } from "./views.ts";

const PORT = Number(process.env.PORT ?? 7001);
const ORDERS_URL = process.env.ORDERS_URL ?? "http://127.0.0.1:7002";
const BILLING_URL = process.env.BILLING_URL ?? "http://127.0.0.1:7003";

class Upstream extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown) {
    super("upstream " + status);
    this.status = status;
    this.body = body;
  }
}

async function call(url: string, init?: RequestInit): Promise<any> {
  const res = await fetch(url, init);
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new Upstream(res.status, body);
  return body;
}

async function invoicesFor(orderId: string): Promise<Invoice[]> {
  return (await call(`${BILLING_URL}/invoices?order_id=${encodeURIComponent(orderId)}`)).invoices;
}

async function readJson(req: IncomingMessage): Promise<any> {
  let raw = "";
  for await (const chunk of req) raw += chunk;
  return JSON.parse(raw || "null");
}

function send(res: ServerResponse, status: number, body: unknown) {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(body));
}

async function route(req: IncomingMessage, res: ServerResponse) {
  const url = new URL(req.url ?? "/", "http://localhost");
  if (url.pathname === "/health") return send(res, 200, { ok: true });

  if (url.pathname === "/checkout" && req.method === "POST") {
    const body = await readJson(req);
    const problem = validateCheckout(body);
    if (problem) return send(res, 400, { error: "bad_request", message: problem });
    const order: Order = await call(`${ORDERS_URL}/orders`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return send(res, 201, orderPage(order));
  }

  const account = url.pathname.match(/^\/account\/([^/]+)\/orders$/);
  if (account && req.method === "GET") {
    const { orders } = await call(`${ORDERS_URL}/orders?customer_id=${encodeURIComponent(account[1])}`);
    const pages = [];
    for (const order of orders as Order[]) pages.push(orderPage(order, await invoicesFor(order.order_id)));
    return send(res, 200, { orders: pages });
  }

  const cancel = url.pathname.match(/^\/orders\/([^/]+)\/cancel$/);
  if (cancel && req.method === "POST") {
    const order: Order = await call(`${ORDERS_URL}/orders/${cancel[1]}/cancel`, { method: "POST" });
    return send(res, 200, orderPage(order, await invoicesFor(order.order_id)));
  }

  send(res, 404, { error: "not_found" });
}

createServer((req, res) => {
  route(req, res).catch((err) => {
    if (err instanceof Upstream && err.status < 500) return send(res, err.status, err.body);
    if (err instanceof SyntaxError) return send(res, 400, { error: "invalid_json" });
    send(res, 502, { error: "upstream_failed", message: String(err?.message ?? err) });
  });
}).listen(PORT, "127.0.0.1", () => console.log(`storefront listening on ${PORT}`));

// Starts Storefront: the app in app.ts, wired to the real Orders and Billing services.
import { createServer } from "node:http";
import { createApp } from "./app.ts";
import { billingClient } from "./clients/billing.ts";
import { ordersClient } from "./clients/orders.ts";

const PORT = Number(process.env.PORT ?? 7001);
const ORDERS_URL = process.env.ORDERS_URL ?? "http://127.0.0.1:7002";
const BILLING_URL = process.env.BILLING_URL ?? "http://127.0.0.1:7003";

const app = createApp({ orders: ordersClient(ORDERS_URL), billing: billingClient(BILLING_URL) });
createServer((req, res) => void app(req, res)).listen(PORT, "127.0.0.1", () => console.log(`storefront listening on ${PORT}`));

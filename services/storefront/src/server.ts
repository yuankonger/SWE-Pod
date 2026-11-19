// Starts Storefront: the app in app.ts, wired to Core and the Subscriptions app.
import { createServer } from "node:http";
import { createApp } from "./app.ts";
import { coreClient } from "./clients/core.ts";
import { subscriptionsClient } from "./clients/subscriptions.ts";

const PORT = Number(process.env.PORT ?? 7001);
const CORE_URL = process.env.CORE_URL ?? "http://127.0.0.1:7000/graphql/";
const SUBSCRIPTIONS_URL = process.env.SUBSCRIPTIONS_URL ?? "http://127.0.0.1:7006";

const app = createApp({ core: coreClient(CORE_URL), subscriptions: subscriptionsClient(SUBSCRIPTIONS_URL) });
createServer((req, res) => void app(req, res)).listen(PORT, process.env.BIND ?? "127.0.0.1", () =>
  console.log(JSON.stringify({ timestamp: new Date().toISOString(), level: "info", service: "storefront", message: `storefront listening on ${PORT}` })));

// Starts the Dashboard: the app in app.ts, wired to Core.
import { createServer } from "node:http";
import { createApp } from "./app.ts";
import { coreClient } from "./clients/core.ts";

const PORT = Number(process.env.PORT ?? 7002);
const CORE_URL = process.env.CORE_URL ?? "http://127.0.0.1:7000/graphql/";

const app = createApp(coreClient(CORE_URL));
createServer((req, res) => void app(req, res)).listen(PORT, process.env.BIND ?? "127.0.0.1", () =>
  console.log(JSON.stringify({ timestamp: new Date().toISOString(), level: "info", service: "dashboard", message: `dashboard listening on ${PORT}` })));

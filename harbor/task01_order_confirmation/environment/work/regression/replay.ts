// Runs a purchase the way one build of the mobile app does it, against a live Core, and prints the screens.
//   node replay.ts <directory of the build> <core url> <purchase json>
// This is the checks' own driver. It does not use the mobile owner's `run` script or `src/replay.ts`, so what it
// prints comes from the build's code talking to Core and from nothing else.
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const [bundle, coreUrl, purchaseJson] = process.argv.slice(2);
const { createApp, httpSend, AppError } = await import(pathToFileURL(join(bundle, "client.ts")).href);
const purchase = { email: "pat@example.com", items: { "BOX-S": 2, "ADD-TEA": 1 }, paymentMethod: "pm_card_ok",
  address: { firstName: "Pat", lastName: "Lee", streetAddress1: "1 Main St", city: "San Francisco", postalCode: "94105", country: "US", countryArea: "CA" },
  ...JSON.parse(purchaseJson || "{}") };
try {
  const screens = await createApp(httpSend(coreUrl)).purchase(purchase, `check-${Date.now()}-${Math.random()}`);
  console.log(JSON.stringify({ ok: true, ...screens }));
} catch (err: any) {
  console.log(JSON.stringify({ ok: false, kind: err instanceof AppError ? "message" : "crash", error: String(err?.message ?? err) }));
}

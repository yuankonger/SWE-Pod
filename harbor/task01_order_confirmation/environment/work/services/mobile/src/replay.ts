// Runs a purchase the way one released build of the app does it, against a live Core, and prints the screens.
//   node src/replay.ts <version> <core url> [purchase json]
// The released builds are under releases/<version>/: they are what is installed on phones and are never edited.
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const [version, coreUrl, purchaseJson] = process.argv.slice(2);
const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const bundle = version === "source" ? join(root, "src") : join(root, "releases", version);
const { createApp, httpSend, AppError } = await import(pathToFileURL(join(bundle, "client.ts")).href);
const purchase = { email: "pat@example.com", items: { "BOX-S": 2, "ADD-TEA": 1 }, paymentMethod: "pm_card_ok",
  address: { firstName: "Pat", lastName: "Lee", streetAddress1: "1 Main St", city: "San Francisco", postalCode: "94105", country: "US", countryArea: "CA" },
  ...(purchaseJson ? JSON.parse(purchaseJson) : {}) };
try {
  const screens = await createApp(httpSend(coreUrl)).purchase(purchase, `mobile-${version}-${Date.now()}`);
  console.log(JSON.stringify({ version, ok: true, ...screens }));
} catch (err: any) {
  // What the customer would see: the app's own message, or a crash.
  console.log(JSON.stringify({ version, ok: false, kind: err instanceof AppError ? "message" : "crash", error: String(err?.message ?? err) }));
  process.exitCode = 1;
}

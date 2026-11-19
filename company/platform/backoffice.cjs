// What staff see of the installed apps in the back office (Saleor Dashboard), read with a headless browser.
//
//     node backoffice.cjs <dashboard url> <email> <password> <out.json> [--app "<app name>"]
//
// Signs in as staff, opens the installed apps/extensions page (through the sidebar when it offers the page, else by
// its address), waits for the page to settle and writes <out.json>:
//   ok              the installed apps page was read
//   stage           the last stage reached: start, browser, dashboard, signed_in, apps_page, app_page
//   url             the address the browser ended at
//   route           how the apps page was reached: "sidebar" or the address that was opened
//   apps_page_text  the visible text of the whole page (document.body.innerText)
//   app_names       best effort: the installed apps the page lists (names the API gave the page that are in its
//                   text, and the first line of each row of the list)
//   app_page_text   with --app: the visible text after clicking through from the list to that app's own page;
//                   app_frames_text has the text of frames in it (an installed third-party app draws itself in one),
//                   app_details_text the text of the app's details page when that is a different page
//   console_errors, page_errors, graphql_errors ([{operation, status, messages}] for every GraphQL response that
//   carried errors), request_failures, error (why it stopped, if it did)
// A full-page screenshot is written beside it (<out>.png, and <out>.app.png for the app's page).
// It relies only on the sign-in form and on addresses; nothing of the list's own markup is needed to read the text.
// Exit code: 0 the apps page was read, 2 the browser did not start or the dashboard could not be reached, 1 otherwise.
// BACKOFFICE_WAIT_MS (default 180000) is how long the sign-in form may take to appear: a development server compiles
// the application when it is first asked for.
const fs = require("fs");
const { chromium } = require("playwright");

const args = process.argv.slice(2);
let appName = null;
const at = args.indexOf("--app");
if (at >= 0) { appName = args[at + 1]; args.splice(at, 2); }
const [BASE, EMAIL, PASSWORD, OUT] = args;
if (!BASE || !EMAIL || !PASSWORD || !OUT) {
  console.error('usage: node backoffice.cjs <dashboard url> <email> <password> <out.json> [--app "<app name>"]');
  process.exit(1);
}
const WAIT = parseInt(process.env.BACKOFFICE_WAIT_MS || "180000", 10);
const SHOT = OUT.replace(/\.json$/, "");
const APPS_ROUTES = ["extensions/installed", "apps/"];
const EMAIL_FIELD = '[data-test-id="email"], input[name="email"], input[type="email"]';
const PASSWORD_FIELD = '[data-test-id="password"], input[name="password"], input[type="password"]';
const SUBMIT = '[data-test-id="submit"], button[type="submit"]';

const result = { ok: false, stage: "start", url: null, route: null, apps_page_text: "", app_names: [], console_errors: [],
                 page_errors: [], graphql_errors: [], request_failures: [] };
if (appName) Object.assign(result, { app: appName, app_found: false, app_page_text: "" });
const known = new Map();      // the apps the API told the page about: name -> {id, type}
const one = e => String((e && e.message) || e).split("\n")[0].slice(0, 500);
const address = route => new URL(route, BASE.endsWith("/") ? BASE : BASE + "/").href;

function listen(page) {
  page.on("console", m => { if (m.type() === "error") result.console_errors.push(m.text().slice(0, 1000)); });
  page.on("pageerror", e => result.page_errors.push(String((e && e.message) || e).slice(0, 1000)));
  page.on("requestfailed", r => result.request_failures.push(`${r.method()} ${r.url().slice(0, 200)}: ${(r.failure() || {}).errorText || ""}`));
  page.on("response", async r => {
    const request = r.request();
    if (request.method() !== "POST") return;
    let asked;
    try { asked = JSON.parse(request.postData() || ""); } catch (e) { return; }      // not GraphQL
    const operations = Array.isArray(asked) ? asked : [asked];
    if (!operations.every(o => o && typeof o.query === "string")) return;
    const name = o => o.operationName || (o.query.match(/(?:query|mutation|subscription)\s+(\w+)/) || [])[1] || "(anonymous)";
    let body;
    try { body = await r.json(); } catch (e) {
      if (r.status() >= 400) result.graphql_errors.push({ operation: operations.map(name).join(","), status: r.status(), messages: ["HTTP " + r.status() + " with no JSON body"] });
      return;
    }
    (Array.isArray(body) ? body : [body]).forEach((answer, i) => {
      const operation = name(operations[i] || operations[0]);
      if (answer && Array.isArray(answer.errors) && answer.errors.length) {
        result.graphql_errors.push({ operation, status: r.status(), messages: answer.errors.map(e => String(e.message).slice(0, 500)) });
      }
      const remember = node => { if (node && typeof node.name === "string" && node.id) known.set(node.name, { id: node.id, type: node.type || null }); };
      const data = (answer && answer.data) || {};
      if (data.apps && Array.isArray(data.apps.edges)) data.apps.edges.forEach(e => remember(e && e.node));
    });
  });
}

// Settled: the network is quiet and the visible text has stopped changing.
async function settle(page, quiet = 15000) {
  await page.waitForLoadState("domcontentloaded", { timeout: 60000 }).catch(() => {});
  await page.waitForLoadState("networkidle", { timeout: quiet }).catch(() => {});
  let last = null, same = 0;
  // An empty page is not a settled one: a development server reloads the page while it is still compiling it.
  for (let i = 0; i < 120 && same < 4; i++) {
    await page.waitForTimeout(500);
    const text = await page.evaluate(() => document.body ? document.body.innerText : "").catch(() => null);
    const busy = await page.locator('[data-test-id*="skeleton" i], [class*="skeleton" i], [role="progressbar"]').count().catch(() => 0);
    same = text && text.trim() && text === last && !(busy && i < 60) ? same + 1 : 0;
    last = text;
  }
  return last || "";
}

async function shot(page, file) {
  try { await page.screenshot({ path: file, fullPage: true }); return file; } catch (e) { return null; }
}

const compileError = async page => (await page.locator("vite-error-overlay").count().catch(() => 0))
  ? (await page.locator("vite-error-overlay").innerText().catch(() => "")).split("\n").slice(0, 4).join(" ").slice(0, 600) : null;

// "dashboard": the sign-in form is shown. A page that answers but shows no form is the dashboard's own trouble (1);
// no answer at all is infrastructure (2).
async function reach(page) {
  const started = Date.now();
  let answered = false, why = "no answer";
  while (Date.now() - started < WAIT) {
    try {
      const response = await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 60000 });
      if (response && response.status() >= 400) { why = "HTTP " + response.status() + " from " + BASE; answered = response.status() < 500; }
      else answered = true;
    } catch (e) { why = one(e); await page.waitForTimeout(3000); continue; }
    try {
      await page.locator(EMAIL_FIELD).first().waitFor({ timeout: Math.max(5000, Math.min(60000, WAIT - (Date.now() - started))) });
      return;
    } catch (e) { why = "the sign-in form was not shown"; }
    const broken = await compileError(page);
    if (broken) throw Object.assign(new Error("the dashboard does not compile: " + broken), { code: 1 });
  }
  if (answered) result.apps_page_text = await page.evaluate(() => document.body ? document.body.innerText : "").catch(() => "");
  throw Object.assign(new Error(`the dashboard at ${BASE} ${answered ? "shows no sign-in form" : "could not be reached"} within ${WAIT / 1000} s: ${why}`), { code: answered ? 1 : 2 });
}

async function signIn(page) {
  await page.locator(EMAIL_FIELD).first().fill(EMAIL);
  await page.locator(PASSWORD_FIELD).first().fill(PASSWORD);
  await page.locator(SUBMIT).first().click();
  try {
    await page.locator(PASSWORD_FIELD).first().waitFor({ state: "detached", timeout: 60000 });
  } catch (e) {
    const said = (await page.evaluate(() => document.body.innerText).catch(() => "")).replace(/\s+/g, " ").slice(0, 300);
    throw Object.assign(new Error("signing in did not leave the sign-in form; it shows: " + said), { code: 1 });
  }
  await settle(page);
}

const onAppsPage = page => APPS_ROUTES.some(route => new URL(page.url()).pathname.replace(/\/$/, "").endsWith("/" + route.replace(/\/$/, "")));

async function openApps(page) {
  // through the sidebar, as staff would: any link there that leads to one of the known addresses
  for (const route of APPS_ROUTES) {
    const link = page.locator(`a[href$="/${route}"], a[href$="/${route.replace(/\/$/, "")}"]`).first();
    if (await link.count().catch(() => 0)) {
      try {
        await link.click({ timeout: 10000 });
        await page.waitForTimeout(500);
        if (onAppsPage(page)) {
          const text = await settle(page);
          if (text.trim() && onAppsPage(page)) { result.route = "sidebar"; return text; }
        }
      } catch (e) { /* not clickable: by address then */ }
    }
  }
  let text = "";
  for (const route of APPS_ROUTES) {
    await page.goto(address(route), { waitUntil: "domcontentloaded", timeout: 60000 });
    result.route = address(route);
    text = await settle(page);
    // an address this dashboard does not have shows its "not found" page, or sends the browser elsewhere
    if (onAppsPage(page) && !/\b(404|not found)\b/i.test(text.slice(0, 2000))) break;
  }
  return text;
}

async function appNames(page, text) {
  const names = new Set([...known.keys()].filter(name => text.includes(name)));
  const rows = await page.locator('[data-test-id="installed-extension-row"]').evaluateAll(
    list => list.map(row => (row.innerText || "").split("\n").map(s => s.trim()).filter(Boolean)[0])).catch(() => []);
  rows.filter(Boolean).forEach(name => names.add(name));
  return [...names];
}

async function openApp(page) {
  const before = page.url();
  // the link of the list that carries the name: the name's own link, or the link of the smallest block around it
  const named = page.getByText(appName, { exact: true }).first();
  const candidates = [named.locator("xpath=ancestor-or-self::a[1]"), named.locator("xpath=ancestor::*[.//a[@href]][1]//a[@href]").first(),
                      page.getByRole("link", { name: appName }).first(), page.getByRole("row", { name: appName }).first(),
                      page.getByText(appName).first()];
  for (const candidate of candidates) {
    if (!(await candidate.count().catch(() => 0))) continue;
    try {
      await candidate.first().click({ timeout: 10000 });
      await page.waitForTimeout(1000);
      if (page.url() !== before) { result.app_route = "list"; return true; }
    } catch (e) { /* the next way */ }
  }
  const app = known.get(appName);      // not offered by the list: the app's address, from what the API told the page
  if (!app) return false;
  const route = (app.type === "LOCAL" ? "extensions/custom/" : "extensions/app/") + encodeURIComponent(app.id);
  await page.goto(address(route), { waitUntil: "domcontentloaded", timeout: 60000 });
  result.app_route = address(route);
  return true;
}

const framesText = async page => (await Promise.all(page.frames().filter(f => f !== page.mainFrame()).map(
  f => f.evaluate(() => document.body ? document.body.innerText : "").catch(() => "")))).filter(Boolean);

(async () => {
  let browser, page, code = 1;
  try {
    try {
      browser = await chromium.launch();
      page = await (await browser.newContext({ viewport: { width: 1600, height: 1200 } })).newPage();
    } catch (e) { throw Object.assign(new Error("no browser: " + one(e)), { code: 2 }); }
    result.stage = "browser";
    listen(page);
    await reach(page);
    result.stage = "dashboard";
    await signIn(page);
    result.stage = "signed_in";
    result.apps_page_text = await openApps(page);
    const broken = await compileError(page);
    if (broken) throw new Error("the dashboard does not compile: " + broken);
    result.app_names = await appNames(page, result.apps_page_text);
    result.screenshot = await shot(page, SHOT + ".png");
    if (!result.apps_page_text.trim()) throw new Error("the apps page stayed empty");
    result.stage = "apps_page";
    result.ok = true;
    code = 0;
    if (appName) {
      try {
        result.app_found = await openApp(page);
        if (result.app_found) {
          result.app_page_text = await settle(page);
          result.app_frames_text = await framesText(page);
          result.app_url = page.url();
          result.app_screenshot = await shot(page, SHOT + ".app.png");
          result.stage = "app_page";
          const view = new URL(page.url());      // an installed third-party app: its details are a page further
          if (/\/extensions\/app\/[^/]+\/?$/.test(view.pathname)) {
            await page.goto(view.origin + view.pathname.replace(/\/$/, "") + "/edit", { waitUntil: "domcontentloaded", timeout: 60000 });
            result.app_details_text = await settle(page);
          }
        } else {
          result.error = `no "${appName}" to open on the apps page`;
        }
      } catch (e) { result.error = "the app's page: " + one(e); }
    }
  } catch (e) {
    result.error = one(e);
    code = e.code || 1;
    if (page) {
      if (!result.apps_page_text) result.apps_page_text = await page.evaluate(() => document.body ? document.body.innerText : "").catch(() => "");
      result.screenshot = await shot(page, SHOT + ".png");
    }
  }
  if (page) result.url = page.url();
  if (browser) await browser.close().catch(() => {});
  for (const key of ["console_errors", "page_errors", "request_failures"]) result[key] = [...new Set(result[key])].slice(0, 50);
  result.graphql_errors = result.graphql_errors.slice(0, 100);
  fs.writeFileSync(OUT, JSON.stringify(result, null, 2));
  process.exit(code);
})();

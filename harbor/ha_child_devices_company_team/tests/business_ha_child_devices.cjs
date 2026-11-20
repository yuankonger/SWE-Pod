// The business outcome, done in a browser against a running Home Assistant (core serving the frontend's build).
//
//     node business_ha_child_devices.cjs <Home Assistant url> <token file> <out dir>
//
// The install is the demo integration's (kitchen_sink): a power strip with two outlets. The owner (ha_seed.py:
// owner / owner-password) signs in and switches the power strip off in its settings; its outlets, which are parts
// of it, must go off with it, and come back when the strip is switched on again. What happened is read back over the
// WebSocket API, with a token of its own, outside the browser.
//
// Stages, each {stage, ok, detail}; the first that is not ok ends the work:
//   frontend_shows_sign_in   (browser) the frontend shows its sign-in form
//   owner_signs_in           (browser) the owner signs in
//   devices_listed           (browser) Settings > Devices lists the power strip and both outlets
//   outlet_page_opens        (browser) an outlet's own device page opens, with its name and its settings
//   owner_disables_strip     (browser, then API) in the strip's settings the owner turns "Enable device" off and
//                            updates; the API then reads the strip as disabled by the user
//   outlets_follow_strip     (API) both outlets read as disabled because their device is
//   owner_enables_strip      (browser, then API) the owner turns the strip back on; the API reads it enabled
//   outlets_come_back        (API) both outlets read as enabled again
// The controls used are the ones the frontend had before the feature (the device page's "Edit settings" button, the
// "Enable device" switch and the dialog's "Update" button), found by their names. A stage fails only on something the
// trees refused or did not offer; any other error (the browser's own timeout, say) sets `infrastructure` instead.
//
// Beside them, once the devices are listed and before the strip is touched, what the frontend shows of the parts
// (each decided on its own: one that fails does not end the work above):
//   strip_page_lists_outlets (browser) the strip's device page links to each outlet's device page
//   outlet_page_links_strip  (browser) each outlet's device page links to the strip's
//   integration_nests_outlets (browser) on the demo integration's page the outlets are listed after the strip, with
//                            none of the integration's other devices between, and indented from it (their names
//                            start further in than the strip's)
// A link is an element with the device page's address (`/config/devices/device/<id>`) as its `href`.
// `probe` records, as evidence only, what each device page showed. Writes <out dir>/browser.json and screenshots.
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const [APP, TOKEN_FILE, OUT] = process.argv.slice(2);
const OWNER = { username: "owner", password: "owner-password" };
const STRIP = "Power strip with 2 sockets";
const OUTLETS = ["Outlet 1", "Outlet 2"];
const result = { stages: [], probe: {}, devices: null };
class Refused extends Error {}
let current = "frontend_shows_sign_in";      // the stage under way, which a refusal fails

async function ws(command) {
  const token = fs.readFileSync(TOKEN_FILE, "utf8").trim();
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(APP.replace(/^http/, "ws").replace(/\/$/, "") + "/api/websocket");
    const timer = setTimeout(() => { socket.close(); reject(new Error("the WebSocket API did not answer within 30 s")); }, 30000);
    socket.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "auth_required") socket.send(JSON.stringify({ type: "auth", access_token: token }));
      else if (msg.type === "auth_invalid") { clearTimeout(timer); reject(new Error("the token was refused")); }
      else if (msg.type === "auth_ok") socket.send(JSON.stringify({ id: 1, ...command }));
      else if (msg.id === 1) {
        clearTimeout(timer);
        socket.close();
        msg.success ? resolve(msg.result) : reject(new Refused(command.type + ": " + JSON.stringify(msg.error)));
      }
    };
    socket.onerror = () => { clearTimeout(timer); reject(new Error("the WebSocket API could not be reached")); };
  });
}

async function devices() {
  const list = await ws({ type: "config/device_registry/list" });
  const byName = (name) => list.find((d) => (d.name_by_user || d.name) === name);
  const found = { strip: byName(STRIP), outlets: OUTLETS.map(byName) };
  result.devices = { strip: found.strip && pick(found.strip), outlets: found.outlets.map((d) => d && pick(d)) };
  return found;
}
const NEXT = { frontend_shows_sign_in: "owner_signs_in", owner_signs_in: "devices_listed", devices_listed: "outlet_page_opens", outlet_page_opens: "owner_disables_strip",
               owner_disables_strip: "outlets_follow_strip", outlets_follow_strip: "owner_enables_strip", owner_enables_strip: "outlets_come_back" };
const pick = (d) => ({ id: d.id, name: d.name, disabled_by: d.disabled_by, parent_device_id: d.parent_device_id, via_device_id: d.via_device_id });

function stage(name, ok, detail = "") {
  current = NEXT[name];
  result.stages.push({ stage: name, ok: Boolean(ok), detail });
  return ok;
}

// a stage beside the work: recorded, and the work goes on whatever came of it
async function aside(name, check) {
  try {
    const [ok, detail] = await check();
    result.stages.push({ stage: name, ok: Boolean(ok), detail: detail || "" });
  } catch (e) {
    if (!(e instanceof Refused)) throw e;
    result.stages.push({ stage: name, ok: false, detail: e.message });
  }
}

async function linksTo(page, id, ms) {
  return visible(page.locator(`a[href$="/config/devices/device/${id}"]`), ms);
}

// where a device's name is drawn on the page: the visible element whose whole text is the name
async function placeOf(page, name) {
  const all = page.getByText(name, { exact: true });
  for (let i = 0; i < (await all.count()); i++) {
    const box = await all.nth(i).boundingBox();
    if (box && box.width > 0 && box.height > 0) return box;
  }
  return null;
}

async function parts(page, found, list) {
  await aside("strip_page_lists_outlets", async () => {
    await page.goto(APP + "config/devices/device/" + found.strip.id);
    await visible(page.getByText(STRIP), 60000);
    const missing = [];
    for (const [i, outlet] of found.outlets.entries()) if (!(await linksTo(page, outlet.id, i ? 5000 : 20000))) missing.push(OUTLETS[i]);
    await shot(page, "strip");
    return [missing.length === 0, missing.length ? "the strip's page does not link to " + missing.join(", ") : ""];
  });
  await aside("outlet_page_links_strip", async () => {
    const missing = [];
    for (const [i, outlet] of found.outlets.entries()) {
      await page.goto(APP + "config/devices/device/" + outlet.id);
      await visible(page.getByText(OUTLETS[i]), 60000);
      if (!(await linksTo(page, found.strip.id, 20000))) missing.push(OUTLETS[i]);
    }
    return [missing.length === 0, missing.length ? "no link to the strip on the page of " + missing.join(", ") : ""];
  });
  await aside("integration_nests_outlets", async () => {
    await page.goto(APP + "config/integrations/integration/kitchen_sink");
    if (!(await visible(page.getByText(STRIP, { exact: true }), 60000))) throw new Refused("the demo integration's page does not list the strip");
    await page.waitForTimeout(2000);
    await shot(page, "integration");
    const strip = await placeOf(page, STRIP);
    const outlets = [];
    for (const name of OUTLETS) outlets.push(await placeOf(page, name));
    const at = (b) => b && { x: Math.round(b.x), y: Math.round(b.y) };
    result.probe.integration_page = { strip: at(strip), outlets: outlets.map(at) };
    if (outlets.some((b) => !b)) return [false, "the integration's page does not show both outlets"];
    if (outlets.some((b) => b.y <= strip.y)) return [false, "an outlet is listed before the strip: " + JSON.stringify(result.probe.integration_page)];
    if (outlets.some((b) => b.x < strip.x + 8)) return [false, "the outlets are not indented from the strip: " + JSON.stringify(result.probe.integration_page)];
    const entries = (d) => d.config_entries || [d.config_entry_id];      // a child carries only its own entry
    const entry = new Set(entries(list.find((d) => d.id === found.strip.id)));
    const children = new Set(found.outlets.map((d) => d.id));
    const last = Math.max(...outlets.map((b) => b.y));
    const between = [];
    for (const d of list) {
      if (d.id === found.strip.id || children.has(d.id) || !entries(d).some((e) => entry.has(e))) continue;
      const name = d.name_by_user || d.name;
      const b = name && (await placeOf(page, name));
      if (b && b.y > strip.y && b.y < last) between.push(name);
    }
    return [between.length === 0, between.length ? "listed between the strip and its outlets: " + between.join(", ") : ""];
  });
}

async function shot(page, name) {
  try { await page.screenshot({ path: path.join(OUT, name + ".png") }); } catch (e) { /* evidence only */ }
}

async function visible(locator, ms) {
  try { await locator.first().waitFor({ state: "visible", timeout: ms }); return true; } catch (e) { return false; }
}

async function setEnabled(page, stripId, on) {
  await page.goto(APP + "config/devices/device/" + stripId);
  const edit = page.getByRole("button", { name: "Edit settings" });
  if (!(await visible(edit, 60000))) throw new Refused("the strip's device page has no \"Edit settings\" button");
  await edit.first().click();
  const toggle = page.getByRole("switch", { name: /enable device/i });
  const fallback = page.getByRole("switch");
  const control = (await visible(toggle, 15000)) ? toggle : fallback;
  if (!(await visible(control, 5000))) throw new Refused("the device's settings have no \"Enable device\" switch");
  // the switch's input lies under the part drawn over it, which takes the pointer: set it as a click on it would
  if ((await control.first().isChecked()) !== on) await control.first().setChecked(on, { force: true });
  const update = page.getByRole("button", { name: "Update" });
  if (!(await visible(update, 10000))) throw new Refused("the device's settings have no \"Update\" button");
  await update.first().click();
  await page.waitForTimeout(3000);
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
  try {
    await page.goto(APP);
    const user = page.getByRole("textbox", { name: /username/i });
    if (!stage("frontend_shows_sign_in", await visible(user, 120000), page.url())) { await shot(page, "sign-in"); return; }
    await user.first().fill(OWNER.username);
    await page.getByRole("textbox", { name: /password/i }).first().fill(OWNER.password);
    await page.keyboard.press("Enter");
    let signedIn = true;
    try {
      await page.waitForURL((url) => !url.pathname.startsWith("/auth/"), { timeout: 60000 });
      // the frontend trades the sign-in's code for its tokens and keeps them; until then another page asks again
      await page.waitForFunction(() => window.localStorage.getItem("hassTokens"), null, { timeout: 60000 });
    } catch (e) { signedIn = false; }
    if (!stage("owner_signs_in", signedIn, page.url())) { await shot(page, "signed-in"); return; }

    await page.goto(APP + "config/devices/dashboard");
    const missing = [];
    for (const name of [STRIP, ...OUTLETS]) if (!(await visible(page.getByText(name), name === STRIP ? 60000 : 10000))) missing.push(name);
    await shot(page, "devices");
    if (!stage("devices_listed", missing.length === 0, missing.length ? "not listed: " + missing.join(", ") : "")) return;

    const found = await devices();
    if (!found.strip || found.outlets.some((d) => !d)) throw new Refused("the API does not list the strip and both outlets");
    await page.goto(APP + "config/devices/device/" + found.outlets[0].id);
    const opened = (await visible(page.getByText(OUTLETS[0]), 60000)) && (await visible(page.getByRole("button", { name: "Edit settings" }), 15000));
    await shot(page, "outlet");
    result.probe.outlet_page = (await page.locator("body").innerText().catch(() => "")).slice(0, 1500);
    if (!stage("outlet_page_opens", opened, opened ? "" : "the outlet's device page did not show its name and settings")) return;
    await parts(page, found, await ws({ type: "config/device_registry/list" }));

    await page.goto(APP + "config/devices/device/" + found.strip.id);
    await visible(page.getByText(STRIP), 60000);
    result.probe.strip_page = (await page.locator("body").innerText().catch(() => "")).slice(0, 1500);
    await setEnabled(page, found.strip.id, false);
    await shot(page, "strip-disabled");
    let now = await devices();
    if (!stage("owner_disables_strip", now.strip.disabled_by === "user", "the strip reads disabled_by " + JSON.stringify(now.strip.disabled_by))) return;
    const off = now.outlets.map((d) => d.disabled_by);
    if (!stage("outlets_follow_strip", off.every((v) => v === "device"), "the outlets read disabled_by " + JSON.stringify(off))) return;

    await setEnabled(page, found.strip.id, true);
    await shot(page, "strip-enabled");
    now = await devices();
    if (!stage("owner_enables_strip", now.strip.disabled_by === null, "the strip reads disabled_by " + JSON.stringify(now.strip.disabled_by))) return;
    const on = now.outlets.map((d) => d.disabled_by);
    stage("outlets_come_back", on.every((v) => v === null), "the outlets read disabled_by " + JSON.stringify(on));
  } catch (e) {
    if (e instanceof Refused) stage(current, false, e.message);
    else result.infrastructure = e.message;
  } finally {
    await browser.close();
    fs.writeFileSync(path.join(OUT, "browser.json"), JSON.stringify(result, null, 2));
  }
}

main();

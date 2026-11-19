// The business outcome, done in a browser against the running company.
//
//     node business_customer_tier.cjs <API url> <staff application url> <customer email> <out dir>
//
// Stages, each {stage, ok, detail}; the first that is not ok ends the work:
//   dashboard_shows_sign_in       (browser) the staff application shows its sign-in form. Its development server
//                                 compiles on first use, so this waits up to 20 minutes.
//   core_defines_tier             (API) a customer is made; a "Contract tier" attribute for customers, with the values
//                                 Bronze, Silver and Gold, is made and given to the customer's type. This is the
//                                 shop's own setting up, done before staff use it.
//   dashboard_sets_tier           (browser) staff sign in, open the customer, choose Gold as the contract tier, save.
//   fresh_session_finds_customer  (browser, a new session) staff sign in again, open the customer list, filter by
//                                 contract tier Gold, and the customer is listed; filtered by Silver, it is not.
//   core_keeps_tier               (API, a new token) the customer's contract tier reads Gold, and the customer is
//                                 among the customers whose contract tier is Gold.
// After a stage fails the later ones are not run, but what the staff application shows of the customer is still
// recorded (`probe`), so that the result says what was and was not there.
// The customer list is drawn on a canvas; what it lists is read from the staff application's own request for it.
// A stage fails only on something the trees refused or did not offer (each such case is named in the code). Any
// other error, a timeout of the browser's own for one, sets `infrastructure` instead and says nothing of the trees.
// Writes <out dir>/browser.json and screenshots.
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const [API, APP, EMAIL, OUT] = process.argv.slice(2);
const STAFF = { email: "admin@example.com", password: "admin" };
const TIER = { name: "Contract tier", slug: "contract-tier", values: ["Bronze", "Silver", "Gold"], chosen: "Gold", other: "Silver" };
const result = { stages: [], customer: null, probe: {} };
const WAIT = 90000; // the staff application's development server compiles each page when it is first asked for

async function gql(query, variables, token) {
  const r = await fetch(API, { method: "POST", headers: { "Content-Type": "application/json", ...(token ? { Authorization: "Bearer " + token } : {}) },
                               body: JSON.stringify({ query, variables: variables || {} }) });
  const body = await r.json();
  if (body.errors) throw new Refused(body.errors.map(e => e.message).join("; "));
  for (const [name, part] of Object.entries(body.data || {})) {
    if (part && Array.isArray(part.errors) && part.errors.length) throw new Refused(name + ": " + part.errors.map(e => (e.field || "") + " " + e.message).join("; "));
  }
  return body.data;
}
class Refused extends Error {}

async function staffToken() {
  return (await gql(`mutation($e: String!, $p: String!) { tokenCreate(email: $e, password: $p) { token errors { field message } } }`, { e: STAFF.email, p: STAFF.password })).tokenCreate.token;
}

async function defineTier() {
  const token = await staffToken();
  if (process.env.REUSE) {      // for whoever is writing this script: the tier is defined already
    result.customer = (await gql(`query($e: String!) { customers(first: 1, where: { email: { eq: $e } }) { edges { node { id email } } } }`, { e: EMAIL }, token)).customers.edges[0].node;
    return "reused";
  }
  const made = await gql(`mutation($input: UserCreateInput!) { customerCreate(input: $input) { user { id email } errors { field message } } }`,
                         { input: { email: EMAIL, firstName: "Tier", lastName: "Check" } }, token);
  result.customer = made.customerCreate.user;
  let attribute;
  try {
    attribute = (await gql(`mutation($input: AttributeCreateInput!) { attributeCreate(input: $input) { attribute { id slug } errors { field message } } }`,
      { input: { name: TIER.name, slug: TIER.slug, type: "CUSTOMER_TYPE", inputType: "DROPDOWN", values: TIER.values.map(name => ({ name })) } }, token)).attributeCreate.attribute;
  } catch (e) {
    if (e instanceof Refused) throw new Refused("the API cannot make an attribute for customers: " + e.message.slice(0, 300));
    throw e;
  }
  let type;
  try {
    type = (await gql(`query($id: ID!) { user(id: $id) { customerType { id name } } }`, { id: result.customer.id }, token)).user.customerType;
  } catch (e) {
    if (e instanceof Refused) throw new Refused("the API does not say what type a customer is: " + e.message.slice(0, 300));
    throw e;
  }
  if (!type) throw new Refused("the customer has no customer type to give the attribute to");
  await gql(`mutation($t: ID!, $a: [ID!]!) { customerTypeAssignAttributes(customerTypeId: $t, attributeIds: $a) { errors { field message } } }`, { t: type.id, a: [attribute.id] }, token);
  return `customer ${result.customer.email} (${result.customer.id}), of type "${type.name}", which now has the attribute "${TIER.name}"`;
}

// The staff application's development server compiles the application the first time a browser asks for it, which
// takes minutes on a machine that has never served it. Nothing is judged until its sign-in form has been shown.
async function warm(browser) {
  const context = await browser.newContext({ viewport: { width: 1600, height: 1200 } });
  const page = await context.newPage();
  const broken = [];
  page.on("pageerror", e => broken.push(String(e.message || e).split("\n")[0].slice(0, 300)));
  const started = Date.now();
  try {
    while (Date.now() - started < 20 * 60 * 1000) {
      await page.goto(APP, { waitUntil: "domcontentloaded", timeout: 300000 }).catch(() => {});
      try {
        await page.locator('[data-test-id="email"]').waitFor({ timeout: 180000 });
        return { ok: true, seconds: Math.round((Date.now() - started) / 1000) };
      } catch (e) { /* still compiling: ask again */ }
      const overlay = await page.locator("vite-error-overlay").count();
      if (overlay) return { ok: false, why: "the staff application does not compile: " + (await page.locator("vite-error-overlay").innerText().catch(() => "")).split("\n").slice(0, 3).join(" ").slice(0, 400) };
    }
    await shot(page, "warm-up-no-sign-in");
    return broken.length ? { ok: false, why: "the staff application shows no sign-in form; it throws: " + [...new Set(broken)].slice(0, 2).join(" | ") }
                         : { ok: false, infrastructure: "the staff application's sign-in form was not shown within 20 minutes, with no error of its own" };
  } finally {
    await context.close();
  }
}

async function signIn(browser) {
  const context = await browser.newContext({ viewport: { width: 1600, height: 1200 } });
  const page = await context.newPage();
  page.setDefaultTimeout(WAIT);
  const refused = [];
  page.on("response", async r => {      // what the API says to the staff application's own requests
    if (r.url().startsWith(API) && r.request().method() === "POST") {
      try { const b = await r.json(); for (const e of (b.errors || [])) refused.push(e.message); } catch (e) { /* not JSON */ }
    }
  });
  await page.goto(APP, { waitUntil: "domcontentloaded", timeout: 300000 });
  await page.locator('[data-test-id="email"]').fill(STAFF.email, { timeout: 300000 });
  await page.locator('[data-test-id="password"]').fill(STAFF.password);
  await page.locator('[data-test-id="submit"]').click();
  await page.locator('[data-test-id="email"]').waitFor({ state: "detached" });
  return { context, page, refused };
}

async function shot(page, name) {
  try { await page.screenshot({ path: path.join(OUT, name + ".png"), fullPage: true }); } catch (e) { /* the page is gone */ }
}

async function setTier(browser) {
  const { context, page, refused } = await signIn(browser);
  try {
    await page.goto(new URL("customers/" + encodeURIComponent(result.customer.id), APP).href, { waitUntil: "domcontentloaded" });
    const label = page.getByText(TIER.name, { exact: true }).first();
    try {
      await label.waitFor({ timeout: 120000 });
    } catch (e) {
      await shot(page, "set-tier-no-field");
      const said = [...new Set(refused)].slice(0, 3).join(" | ");
      throw new Refused(`the customer's page in the staff application has no "${TIER.name}" field` + (said ? `; the API refused the page's requests: ${said}` : ""));
    }
    // the field's own control: the first input in the nearest block around the label that has one
    const control = label.locator("xpath=ancestor::*[.//input][1]//input").first();
    await control.click({ timeout: 30000 }).catch(() => { throw new Refused(`the "${TIER.name}" field on the customer's page has no control to choose a value with`); });
    await page.getByText(TIER.chosen, { exact: true }).last().click({ timeout: 30000 }).catch(() => { throw new Refused(`the "${TIER.name}" field on the customer's page does not offer ${TIER.chosen}`); });
    await page.locator('[data-test-id="button-bar-confirm"]').click({ timeout: 30000 }).catch(() => { throw new Refused("the customer's page cannot be saved after the tier is chosen"); });
    await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(2500);
    await shot(page, "set-tier-saved");
    return `"${TIER.name}" set to ${TIER.chosen} on the customer's page and saved`;
  } finally {
    result.probe.set_tier_api_refusals = [...new Set(refused)].slice(0, 5);
    await context.close();
  }
}

// The customer list is drawn on a canvas, so what it lists is read from the staff application's own request for
// it: the last list of customers the page asked the API for after the filter was applied, and what it asked with.
async function filtered(page, lists, value) {
  const pick = async text => page.getByText(text, { exact: true }).last().click({ timeout: 30000 });
  await page.goto(new URL("customers/", APP).href, { waitUntil: "domcontentloaded" });
  const none = what => () => { throw new Refused("the customer list " + what); };
  await page.locator('[data-test-id="filters-button"], [data-test-id="show-filters-button"]').first().click({ timeout: 120000 }).catch(none("has no filter control"));
  await page.locator('[data-test-id="add-filter-button"]').click({ timeout: 30000 }).catch(none("has no way to add a filter condition"));
  await page.locator('[data-test-id="left-0"]').click({ timeout: 30000 }).catch(none("has no choice of what to filter by"));
  await pick("Attribute").catch(none("cannot be filtered by attribute"));
  await page.locator('[data-test-id="attribute-value-0"]').click({ timeout: 30000 }).catch(none("has no choice of which attribute to filter by"));
  try {
    await pick(TIER.name);
  } catch (e) {
    throw new Refused(`the customer list's filter does not offer "${TIER.name}" among its attributes`);
  }
  await page.locator('[data-test-id="right-0"]').click({ timeout: 30000 }).catch(none(`has no choice of a value for "${TIER.name}"`));
  await pick(value).catch(none(`does not offer ${value} as a value of "${TIER.name}"`));
  await page.keyboard.press("Escape").catch(() => {});
  lists.length = 0;
  await page.locator('[data-test-id="save-filters-button"]').click({ timeout: 30000 }).catch(none("has no way to apply the filter"));
  for (let i = 0; i < 60 && !lists.length; i++) await page.waitForTimeout(500);
  await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(1500);
  if (!lists.length) throw new Refused(`after filtering by ${TIER.name} = ${value} the staff application asked the API for no customer list`);
  return lists[lists.length - 1];
}

async function findByTier(browser) {
  const { context, page, refused } = await signIn(browser);      // a new context: no cookie, no stored state of the first
  const lists = [];
  page.on("response", async r => {
    if (!r.url().startsWith(API) || r.request().method() !== "POST") return;
    try {
      const asked = JSON.parse(r.request().postData()), body = await r.json();
      if (body.data && body.data.customers && body.data.customers.edges) {
        lists.push({ where: asked.variables && (asked.variables.where || asked.variables.filter) || null, emails: body.data.customers.edges.map(e => e.node.email) });
      }
    } catch (e) { /* not a list */ }
  });
  try {
    const chosen = await filtered(page, lists, TIER.chosen);
    await shot(page, "filter-" + TIER.chosen.toLowerCase());
    result.probe.filter_chosen = chosen;
    if (!chosen.where) throw new Refused(`filtered by ${TIER.name} = ${TIER.chosen}, the staff application asked the API for customers with no condition`);
    if (!chosen.emails.includes(EMAIL)) throw new Refused(`filtered by ${TIER.name} = ${TIER.chosen}, the customer list is ${JSON.stringify(chosen.emails.slice(0, 5))}, without ${EMAIL}`);
    if (chosen.emails.length !== 1) throw new Refused(`filtered by ${TIER.name} = ${TIER.chosen}, the customer list has ${chosen.emails.length} customers, though one has that tier`);
    const other = await filtered(page, lists, TIER.other);
    await shot(page, "filter-" + TIER.other.toLowerCase());
    result.probe.filter_other = other;
    if (other.emails.includes(EMAIL)) throw new Refused(`filtered by ${TIER.name} = ${TIER.other}, the customer list still shows ${EMAIL}: the filter does not filter`);
    return `in a new session the customer list filtered by ${TIER.name} = ${TIER.chosen} is exactly ${EMAIL}, and filtered by ${TIER.other} it is without it (${other.emails.length} customers)`;
  } finally {
    result.probe.filter_api_refusals = [...new Set(refused)].slice(0, 5);
    await context.close();
  }
}

async function keptByCore() {
  const token = await staffToken();
  const read = await gql(`query($id: ID!, $slug: String!) { user(id: $id) { email assignedAttribute(slug: $slug) {
      attribute { slug } ... on AssignedSingleChoiceAttribute { value { name slug } } } } }`, { id: result.customer.id, slug: TIER.slug }, token);
  const value = read.user.assignedAttribute && read.user.assignedAttribute.value;
  if (!value || value.name !== TIER.chosen) throw new Refused(`the API reads the customer's ${TIER.name} as ${JSON.stringify(value)}, not ${TIER.chosen}`);
  const among = await gql(`query($w: CustomerWhereInput) { customers(first: 50, where: $w) { edges { node { email } } } }`,
                          { w: { attributes: [{ slug: TIER.slug, value: { slug: { eq: value.slug } } }] } }, token);
  const emails = among.customers.edges.map(e => e.node.email);
  if (!emails.includes(EMAIL) || emails.length !== 1) throw new Refused(`the API's customers with ${TIER.name} = ${TIER.chosen} are ${JSON.stringify(emails)}`);
  return `the API reads ${TIER.name} = ${value.name} for ${EMAIL}, and lists exactly that customer under it`;
}

async function probe(browser) {
  // what the staff application shows of the customer, whatever came before
  if (!result.customer) return;
  try {
    const { context, page, refused } = await signIn(browser);
    await page.goto(new URL("customers/" + encodeURIComponent(result.customer.id), APP).href, { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle", { timeout: 60000 }).catch(() => {});
    await page.waitForTimeout(3000);
    const text = await page.locator("body").innerText();
    result.probe.customer_page = { shows_customer: text.includes(EMAIL) || (await page.locator(`input[value="${EMAIL}"]`).count()) > 0, shows_tier_field: text.includes(TIER.name), shows_customer_type: /customer type/i.test(text),
                                   api_refusals: [...new Set(refused)].slice(0, 5) };
    await shot(page, "probe-customer-page");
    await context.close();
  } catch (e) {
    result.probe.customer_page = { error: String(e.message || e).split("\n")[0].slice(0, 300) };
  }
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  let browser;
  try {
    browser = await chromium.launch();
  } catch (e) {
    result.infrastructure = "no browser: " + String(e.message || e).split("\n")[0];
  }
  // what staff set on the customer's page, and whether the API keeps it, come first; finding the customer through
  // the list's filter on screen comes last, so that a filter built otherwise does not hide whether the tier was kept
  const stages = [["core_defines_tier", defineTier], ["dashboard_sets_tier", () => setTier(browser)],
                  ["core_keeps_tier", keptByCore], ["fresh_session_finds_customer", () => findByTier(browser)]];
  if (browser) {
    try {
      const warmed = await warm(browser);
      result.probe.warm_up = warmed;
      if (warmed.infrastructure) result.infrastructure = warmed.infrastructure;
      else if (!warmed.ok) result.stages.push({ stage: "dashboard_shows_sign_in", ok: false, detail: warmed.why });
      else result.stages.push({ stage: "dashboard_shows_sign_in", ok: true, detail: `after ${warmed.seconds} s` });
      for (const [stage, run] of (warmed.ok ? stages : [])) {
        try {
          result.stages.push({ stage, ok: true, detail: await run() });
        } catch (e) {
          if (!(e instanceof Refused)) {      // not something the trees refused: the check's own trouble
            result.infrastructure = `${stage}: ${String(e.message || e).split("\n")[0].slice(0, 400)}`;
            break;
          }
          result.stages.push({ stage, ok: false, detail: e.message.slice(0, 600) });
          break;
        }
      }
      if (warmed.ok && (result.infrastructure || result.stages.some(s => !s.ok))) await probe(browser);
    } catch (e) {
      result.infrastructure = "the browser part broke: " + String(e.message || e).split("\n")[0].slice(0, 400);
    }
    await browser.close().catch(() => {});
  }
  fs.writeFileSync(path.join(OUT, "browser.json"), JSON.stringify(result, null, 2));
})();

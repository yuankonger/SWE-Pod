// Does a Home Assistant frontend fit the core it talks to? Reads the frontend's source with its own TypeScript and
// holds it against what the core registers (mined_ws_contract.py) and what the running core answered (ha_seed.py ask).
//
//   node mined_ws_agreement.cjs <frontend repo> <commands.json> <answers.json> <out.json>
//        [--base-answers <answers of the core before the feature>] [--reference <usage json>] [--ignore <json list of types>]
//   (a `--reference` that holds `base_answers` and `ignore` stands for the other two options)
//
// - commands: every place the frontend sends a command (`callWS`, `sendMessagePromise`, `subscribeMessage`,
//   `sendMessage` with an object whose `type` is a string) must name one the core registers. Counted by place.
//   Types in `--ignore` (the real frontend sends them and the real core registers them in a way that cannot be read)
//   are left out.
// - payloads: for each command in the answers, the type the frontend gives the call's result (its type argument,
//   or else what the call returns), element by element: every entry the core returned must have every field that
//   one of the frontend's types for it requires. A frontend whose types say less than the core returns is fine;
//   one that requires fields the core does not send has not been told how the payload changed.
// - gained: the fields the answers have that the base answers lack. `used_new` is those the frontend's types
//   declare, and with `--reference` (the real frontend's `used_new`), `uses_new_api` is the share of the real one's.
const fs = require("fs");
const path = require("path");

const [repo, commandsFile, answersFile, out, ...rest] = process.argv.slice(2);
const opt = (name) => (rest.includes(name) ? rest[rest.indexOf(name) + 1] : undefined);
const ts = require(path.join(repo, "node_modules", "typescript"));
const registered = JSON.parse(fs.readFileSync(commandsFile, "utf8"));
const answers = JSON.parse(fs.readFileSync(answersFile, "utf8"));
// The reference (mined_company.py usage) may carry the base answers and the types to ignore as well.
const reference = opt("--reference") ? JSON.parse(fs.readFileSync(opt("--reference"), "utf8")) : null;
const baseAnswers = opt("--base-answers") ? JSON.parse(fs.readFileSync(opt("--base-answers"), "utf8")) : (reference && reference.base_answers) || null;
const ignore = new Set(opt("--ignore") ? JSON.parse(fs.readFileSync(opt("--ignore"), "utf8")) : (reference && reference.ignore) || []);
const SENDS = new Set(["callWS", "sendMessagePromise", "subscribeMessage", "sendMessage"]);

const files = [];
(function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(p);
    else if (/\.tsx?$/.test(entry.name) && !/\.d\.ts$/.test(entry.name)) files.push(p);
  }
})(path.join(repo, "src"));

// Every place a command is sent, from the syntax alone.
const places = []; // {type, file, line, call}
const unread = [];
for (const file of files) {
  const text = fs.readFileSync(file, "utf8");
  if (![...SENDS].some((s) => text.includes(s))) continue;
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true);
  (function visit(node) {
    if (ts.isCallExpression(node)) {
      const callee = ts.isPropertyAccessExpression(node.expression) ? node.expression.name.text : ts.isIdentifier(node.expression) ? node.expression.text : "";
      if (SENDS.has(callee)) {
        for (const arg of node.arguments) {
          if (!ts.isObjectLiteralExpression(arg)) continue;
          const prop = arg.properties.find((p) => ts.isPropertyAssignment(p) && p.name && p.name.getText(source) === "type");
          if (!prop) continue;
          const where = { file: path.relative(repo, file), line: source.getLineAndCharacterOfPosition(node.getStart()).line + 1 };
          const init = prop.initializer;
          if (ts.isStringLiteral(init) || ts.isNoSubstitutionTemplateLiteral(init)) places.push({ type: init.text, ...where, call: node, file_abs: file });
          else unread.push(where);
        }
      }
    }
    ts.forEachChild(node, visit);
  })(source);
}

const counted = places.filter((p) => !ignore.has(p.type));
const invalid = {};
for (const p of counted) if (!registered[p.type]) (invalid[p.type] = invalid[p.type] || []).push(`${p.file}:${p.line}`);
const valid = counted.length - Object.values(invalid).reduce((n, l) => n + l.length, 0);

// The frontend's types for each answered command's result, with the type checker.
const asked = Object.keys(answers).filter((t) => answers[t].success);
const roots = [...new Set(places.filter((p) => asked.includes(p.type)).map((p) => p.file_abs))];
const config = ts.readConfigFile(path.join(repo, "tsconfig.json"), ts.sys.readFile).config || {};
const parsed = ts.parseJsonConfigFileContent(config, ts.sys, repo);
const program = ts.createProgram(roots, { ...parsed.options, noEmit: true, skipLibCheck: true });
const checker = program.getTypeChecker();

function resultType(call) {
  if (call.typeArguments && call.typeArguments.length) return checker.getTypeFromTypeNode(call.typeArguments[0]);
  const returned = checker.getTypeAtLocation(call);
  const awaited = checker.getAwaitedType ? checker.getAwaitedType(returned) : returned;
  return awaited || returned;
}
function elements(type) {
  if (checker.isArrayType && checker.isArrayType(type)) return checker.getTypeArguments(type)[0];
  return type;
}
function members(type) {
  const union = type.isUnion() ? type.types : [type];
  return union.map((t) => checker.getPropertiesOfType(t).map((s) => ({ name: s.getName(), optional: (s.flags & ts.SymbolFlags.Optional) !== 0 })));
}
const entriesOf = (result) => (Array.isArray(result) ? result : result && typeof result === "object" ? [result] : []);
const keysOf = (result) => new Set(entriesOf(result).flatMap((e) => (e && typeof e === "object" ? Object.keys(e) : [])));

const payloads = {};
const declaredAll = new Set();
for (const command of asked) {
  const calls = places.filter((p) => p.type === command);
  const entries = entriesOf(answers[command].result);
  const found = { places: calls.map((p) => `${p.file}:${p.line}`), entries: entries.length, matched: 0, shapes: [], unmatched: [] };
  const shapes = [];
  for (const p of calls) {
    const sf = program.getSourceFile(p.file_abs);
    if (!sf) continue;
    let call = null;
    (function find(node) { if (!call && node.pos === p.call.pos && node.end === p.call.end && ts.isCallExpression(node)) call = node; else ts.forEachChild(node, find); })(sf);
    if (!call) continue;
    for (const m of members(elements(resultType(call)))) {
      shapes.push(m);
      m.forEach((prop) => declaredAll.add(command + "." + prop.name));
    }
  }
  found.shapes = shapes.map((m) => m.filter((p) => !p.optional).map((p) => p.name).sort());
  if (calls.length && shapes.length) {
    for (const e of entries) {
      const keys = new Set(Object.keys(e || {}));
      const missing = shapes.map((m) => m.filter((p) => !p.optional && !keys.has(p.name)).map((p) => p.name));
      if (missing.some((m) => m.length === 0)) found.matched += 1;
      else if (found.unmatched.length < 5) found.unmatched.push({ id: e && e.id, name: e && e.name, missing: missing.reduce((a, b) => (b.length < a.length ? b : a)) });
    }
  }
  found.share = entries.length ? found.matched / entries.length : 1;
  payloads[command] = found;
}

const gained = baseAnswers
  ? asked.flatMap((c) => { const before = keysOf((baseAnswers[c] || {}).result); return [...keysOf(answers[c].result)].filter((k) => !before.has(k)).map((k) => c + "." + k); })
  : [];
const usedNew = gained.filter((g) => declaredAll.has(g));
const wanted = reference ? reference.used_new : usedNew;
// a command the core could not answer fits nothing
for (const command of Object.keys(answers).filter((t) => !answers[t].success)) payloads[command] = { share: 0, error: answers[command].error };
const payloadShares = Object.values(payloads).map((p) => p.share);
const result = {
  operations: counted.length, valid, invalid, ignored: places.length - counted.length, unread: unread.length,
  valid_share: counted.length ? valid / counted.length : 0,
  payloads, payload_share: payloadShares.length ? Math.min(...payloadShares) : 1,
  gained, used_new: usedNew,
  uses_new_api: wanted.length ? wanted.filter((g) => usedNew.includes(g)).length / wanted.length : 1,
  new_api_not_used: wanted.filter((g) => !usedNew.includes(g)),
};
fs.writeFileSync(out, JSON.stringify(result, null, 1));
console.log(`${result.valid} of ${result.operations} command places valid (${result.ignored} ignored, ${result.unread} unread); payload fit ${result.payload_share.toFixed(3)}; gained ${gained.length}, used ${usedNew.length}, uses_new_api ${result.uses_new_api.toFixed(3)}`);

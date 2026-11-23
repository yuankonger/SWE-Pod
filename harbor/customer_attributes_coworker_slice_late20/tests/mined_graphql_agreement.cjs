/* Does a GraphQL client agree with the API it calls?

   node mined_graphql_agreement.cjs <schema.graphql of the API as built> <client repository root> [<out.json>]
        [--base <the API's schema before the feature>] [--reference <usage.json>] [--copies <copy>,<copy>...]

Collects every GraphQL operation the client's source holds (the files its own code generator reads) and validates
each, with the fragments it uses, against the schema. Prints JSON:
  {"operations": n, "valid": m, "invalid": {operation name: [first errors]}, "names": [every operation name]}
Validity alone cannot fail by omission: a client that never calls the feature is valid too. So, given the API's
schema before the feature (--base), two more things are measured:
  "used_new": the ways into the feature the client's operations take: fields they select that the API gained on
      types it already had (new queries and mutations, new fields of existing types).
      With --reference (the same list for the real client at the feature's commit), "uses_new_api" is the share
      of the reference's that this client selects too.
  "copies_current" (--copies, paths under the client root): the share of what the API gained (types, fields with
      their types, arguments, enum values, union members) that the client's schema copies state the same way, over all of them
      together: a copy left as it was costs its share, not the whole.
Run where the client's dependencies are installed (NODE_PATH or node_modules). */
const fs = require("fs");
const path = require("path");
const { buildSchema, parse, print, validate, visit, visitWithTypeInfo, TypeInfo, Kind, specifiedRules, NoUnusedFragmentsRule } = require("graphql");
const { gqlPluckFromCodeStringSync } = require("@graphql-tools/graphql-tag-pluck");

const argv = process.argv.slice(2), options = {};
for (const flag of ["--base", "--reference", "--copies"]) {
  const at = argv.indexOf(flag);
  if (at >= 0) options[flag.slice(2)] = argv.splice(at, 2)[1];
}
const [schemaPath, root, outPath] = argv;
const schema = buildSchema(fs.readFileSync(schemaPath, "utf8"), { assumeValidSDL: true });

// the files the dashboard's codegen-main.ts and codegen-staging.ts read
const wanted = rel =>
  !rel.startsWith("src/legacy-sdk/") && !/\.test\.|\.generated\./.test(rel) &&
  (/\/(queries|mutations)(\.staging)?\.ts$/.test(rel) || /\/fragments\/[^/]+\.ts$/.test(rel) || /^src\/searches\/[^/]+\.ts$/.test(rel));

const files = [];
(function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) { if (entry.name !== "node_modules") walk(full); }
    else if (wanted(path.relative(root, full))) files.push(full);
  }
})(path.join(root, "src"));

// Every operation is counted by where it is (its file, and its place there), not by its name: two definitions under
// one name are two operations. A document that cannot be read is one operation that is not valid, as it would stop
// the consumer's code generation. A fragment defined twice, differently, is not valid either: which one applies is
// undefined. An operation name used twice is not valid: the generated code would have two of one thing.
const operations = [], fragments = new Map(), fragmentBodies = new Map(), unreadable = {}, collisions = {};
for (const file of files) {
  const rel = path.relative(root, file);
  let sources = [];
  try { sources = gqlPluckFromCodeStringSync(file, fs.readFileSync(file, "utf8")); }
  catch (e) { unreadable[rel] = String(e.message).slice(0, 200); continue; }
  sources.forEach((source, n) => {
    let doc;
    try { doc = parse(source.body); }
    catch (e) { unreadable[rel + "#" + n] = String(e.message).slice(0, 200); return; }
    for (const def of doc.definitions) {
      if (def.kind === Kind.FRAGMENT_DEFINITION) {
        const name = def.name.value, body = print(def);
        if (fragmentBodies.has(name) && fragmentBodies.get(name).body !== body)
          collisions[name] = ["fragment " + name + " is defined differently in " + fragmentBodies.get(name).at + " and " + rel];
        else { fragments.set(name, def); fragmentBodies.set(name, { body, at: rel }); }
      } else if (def.kind === Kind.OPERATION_DEFINITION) operations.push({ def, at: rel + "#" + operations.length });
    }
  });
}

function withFragments(def) {
  const seen = new Map(), queue = [def];
  while (queue.length) {
    visit(queue.pop(), { FragmentSpread(node) {
      const name = node.name.value;
      if (!seen.has(name) && fragments.has(name)) { seen.set(name, fragments.get(name)); queue.push(fragments.get(name)); }
    } });
  }
  return { kind: Kind.DOCUMENT, definitions: [def, ...seen.values()] };
}

const rules = specifiedRules.filter(r => r !== NoUnusedFragmentsRule);
const invalid = {}, names = [], seenNames = new Map();
for (const { def, at } of operations) {
  const name = def.name ? def.name.value : "(anonymous)";
  names.push(name);
  const errors = validate(schema, withFragments(def), rules).slice(0, 3).map(e => e.message);
  if (!def.name) errors.push("an operation without a name");
  else if (seenNames.has(name)) errors.push("the name " + name + " is also used at " + seenNames.get(name));
  else seenNames.set(name, at);
  if (errors.length) invalid[name + " @ " + at] = errors;
}
// what a schema states, one line per thing: a type, a field with its type, an argument, an enum value, a union member
function statements(sdl) {
  const out = new Set();
  for (const def of parse(sdl, { noLocation: true }).definitions) {
    if (!def.name || def.kind === Kind.DIRECTIVE_DEFINITION) continue;
    const type = def.name.value;
    out.add(type);
    for (const f of def.fields || []) {
      out.add(type + "." + f.name.value + ": " + print(f.type));
      for (const a of f.arguments || []) out.add(type + "." + f.name.value + "(" + a.name.value + ": " + print(a.type) + ")");
    }
    for (const v of def.values || []) out.add(type + "." + v.name.value);
    for (const u of def.types || []) out.add(type + " | " + u.name.value);
  }
  return out;
}

const extra = {};
if (options.base) {
  const baseText = fs.readFileSync(options.base, "utf8"), builtText = fs.readFileSync(schemaPath, "utf8");
  const before = buildSchema(baseText, { assumeValidSDL: true });
  // a way into the feature: a field the API gained on a type it already had (a new query or mutation, a new field of a
  // type clients already read). Fields inside the feature's own new types are not counted one by one.
  const had = (type, field) => { const t = before.getType(type); return !t || !!(t.getFields && t.getFields()[field]); };
  const used = new Set(), info = new TypeInfo(schema);
  for (const { def } of operations) {
    visit(withFragments(def), visitWithTypeInfo(info, { Field(node) {
      const parent = info.getParentType();
      if (parent && info.getFieldDef() && !node.name.value.startsWith("__") && !had(parent.name, node.name.value)) used.add(parent.name + "." + node.name.value);
    } }));
  }
  extra.used_new = [...used].sort();
  if (options.reference) {
    const wanted = JSON.parse(fs.readFileSync(options.reference, "utf8")).used_new;
    extra.uses_new_api = wanted.length ? wanted.filter(c => used.has(c)).length / wanted.length : 1;
    extra.new_api_not_used = wanted.filter(c => !used.has(c));
  }
  if (options.copies) {
    const old = statements(baseText), gained = [...statements(builtText)].filter(x => !old.has(x));
    extra.copies = {};
    for (const copy of options.copies.split(",")) {
      let stated = new Set();
      try { stated = statements(fs.readFileSync(path.join(root, copy), "utf8")); } catch (e) { /* a copy that cannot be read states nothing */ }
      const missing = gained.filter(x => !stated.has(x));
      extra.copies[copy] = { gained: gained.length, stated: gained.length - missing.length, missing: missing.slice(0, 20) };
    }
    // the share over all copies together: a copy left behind costs its share, not the whole of what the others state
    const all = Object.values(extra.copies);
    extra.copies_current = gained.length && all.length ? all.reduce((s, c) => s + c.stated, 0) / all.reduce((s, c) => s + c.gained, 0) : 1;
  }
}
// what is counted: every operation, every document that could not be read, every fragment defined twice differently
const counted = operations.length + Object.keys(unreadable).length + Object.keys(collisions).length;
const result = { operations: counted, valid: operations.length - Object.keys(invalid).length, invalid, collisions, names: names.sort(), unreadable, ...extra };
if (outPath) fs.writeFileSync(outPath, JSON.stringify(result, null, 1));
console.log(JSON.stringify({ operations: result.operations, valid: result.valid, invalid_names: Object.keys(invalid), unreadable: Object.keys(unreadable).length,
  used_new: extra.used_new ? extra.used_new.length : undefined, uses_new_api: extra.uses_new_api, copies_current: extra.copies_current }));

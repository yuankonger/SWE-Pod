/* Takes out of a client's copy of an API schema what the API gained between two of its commits.

   node mined_strip_schema.cjs <API schema at its base> <API schema at its target> <client's copy>...

A client repository keeps a copy of the schema of the API it calls. When a task starts the API before a feature,
the client's copy must not already describe that feature. Each copy is rewritten in place with the feature's
types, fields, arguments, enum values and union members cut out; everything else keeps its text. */
const fs = require("fs");
const { parse, buildSchema, validateSchema, Kind } = require("graphql");

const [basePath, targetPath, ...copies] = process.argv.slice(2);

function shape(sdl) {
  const types = new Map();
  for (const def of parse(sdl, { noLocation: true }).definitions) {
    if (!def.name || def.kind === Kind.DIRECTIVE_DEFINITION) continue;
    const t = types.get(def.name.value) || { members: new Set(), args: new Map(), union: new Set(), interfaces: new Set() };
    for (const i of def.interfaces || []) t.interfaces.add(i.name.value);
    for (const f of def.fields || []) {
      t.members.add(f.name.value);
      t.args.set(f.name.value, new Set((f.arguments || []).map(a => a.name.value)));
    }
    for (const v of def.values || []) t.members.add(v.name.value);
    for (const u of def.types || []) t.union.add(u.name.value);
    types.set(def.name.value, t);
  }
  return types;
}

const before = shape(fs.readFileSync(basePath, "utf8")), after = shape(fs.readFileSync(targetPath, "utf8"));
const addedTypes = new Set([...after.keys()].filter(n => !before.has(n)));
const added = (name, kind, of) => {            // is this member / argument / union member one the feature added?
  const a = after.get(name), b = before.get(name);
  if (!a || !b) return false;
  if (kind === "member") return a.members.has(of) && !b.members.has(of);
  if (kind === "union") return a.union.has(of) && !b.union.has(of);
  if (kind === "interface") return a.interfaces.has(of) && !b.interfaces.has(of);
  const [field, arg] = of;
  return a.args.has(field) && a.args.get(field).has(arg) && !(b.args.get(field) || new Set()).has(arg);
};

for (const copy of copies) {
  let text = fs.readFileSync(copy, "utf8");
  const cuts = [];
  for (const def of parse(text).definitions) {
    if (!def.name || def.kind === Kind.DIRECTIVE_DEFINITION) continue;
    const name = def.name.value;
    if (addedTypes.has(name)) { cuts.push([def.loc.start, def.loc.end]); continue; }
    for (const f of [...(def.fields || []), ...(def.values || [])]) {
      if (added(name, "member", f.name.value)) { cuts.push([f.loc.start, f.loc.end]); continue; }
      const gone = (f.arguments || []).filter(a => added(name, "arg", [f.name.value, a.name.value]));
      if (gone.length && gone.length === f.arguments.length) {      // every argument goes: the brackets go too
        const open = text.lastIndexOf("(", f.arguments[0].loc.start), close = text.indexOf(")", f.arguments[f.arguments.length - 1].loc.end);
        cuts.push([open, close + 1]);
      } else for (const a of gone) cuts.push([a.loc.start, a.loc.end]);
    }
    const listed = (nodes, kind, sep, keyword) => {                 // a name in a `A | B` or `implements A & B` list
      const gone = nodes.filter(n => added(name, kind, n.name.value));
      if (gone.length && gone.length === nodes.length && keyword) {  // the whole list goes, and its keyword
        cuts.push([text.lastIndexOf(keyword, nodes[0].loc.start), nodes[nodes.length - 1].loc.end]);
        return;
      }
      for (const n of gone) {
        let start = n.loc.start, end = n.loc.end;
        const lead = text.slice(0, start).match(new RegExp("\\" + sep + "\\s*$"));
        if (lead) start -= lead[0].length;                          // "| Name"
        else { const trail = text.slice(end).match(new RegExp("^\\s*\\" + sep + "\\s*")); if (trail) end += trail[0].length; }   // "Name |" at the front
        cuts.push([start, end]);
      }
    };
    listed(def.types || [], "union", "|", null);
    listed(def.interfaces || [], "interface", "&", "implements");
  }
  cuts.sort((a, b) => b[0] - a[0]);
  for (const [start, end] of cuts) text = text.slice(0, start) + text.slice(end);
  text = text.replace(/[ \t]+\n/g, "\n").replace(/\n{3,}/g, "\n\n");
  const problems = validateSchema(buildSchema(text));               // what is left must still be a whole schema
  if (problems.length) throw new Error(copy + ": " + problems.slice(0, 5).map(e => e.message).join("; "));
  fs.writeFileSync(copy, text);
  console.log(JSON.stringify({ copy, cuts: cuts.length, types: [...addedTypes].filter(n => !text.includes(" " + n + " ")).length }));
}

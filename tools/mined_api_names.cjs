/* What an API's schema gained between two of its commits, as a list a person can read.

   node mined_api_names.cjs <schema at base> <schema at target> <out.json>

Writes {types: [{name, kind, sdl}], members: [{type, name, sdl}], args: [{type, field, name, sdl}]}:
the types the feature added (whole), and the fields, input fields, enum values and arguments it added to types
that were there before. Descriptions are left out: they are not names. */
const fs = require("fs");
const { parse, print, Kind } = require("graphql");
const [basePath, targetPath, outPath] = process.argv.slice(2);
const strip = node => JSON.parse(JSON.stringify(node, (k, v) => (k === "description" || k === "loc" ? undefined : v)));
const defs = sdl => {
  const out = new Map();
  for (const d of parse(sdl, { noLocation: true }).definitions) if (d.name && d.kind !== Kind.DIRECTIVE_DEFINITION) out.set(d.name.value, d);
  return out;
};
const before = defs(fs.readFileSync(basePath, "utf8")), after = defs(fs.readFileSync(targetPath, "utf8"));
const kind = d => ({ ObjectTypeDefinition: "type", InputObjectTypeDefinition: "input", EnumTypeDefinition: "enum", InterfaceTypeDefinition: "interface", UnionTypeDefinition: "union", ScalarTypeDefinition: "scalar" })[d.kind];
const out = { types: [], members: [], args: [], unions: [] };
for (const [name, d] of after) {
  const b = before.get(name);
  if (!b) { out.types.push({ name, kind: kind(d), sdl: print(strip(d)) }); continue; }
  const had = new Map([...(b.fields || []), ...(b.values || [])].map(f => [f.name.value, f]));
  for (const f of [...(d.fields || []), ...(d.values || [])]) {
    const old = had.get(f.name.value);
    if (!old) { out.members.push({ type: name, kind: kind(d), name: f.name.value, sdl: print(strip(f)) }); continue; }
    const oldArgs = new Set((old.arguments || []).map(a => a.name.value));
    for (const a of f.arguments || []) if (!oldArgs.has(a.name.value)) out.args.push({ type: name, field: f.name.value, name: a.name.value, sdl: print(strip(a)) });
  }
  const hadU = new Set((b.types || []).map(t => t.name.value));
  for (const t of d.types || []) if (!hadU.has(t.name.value)) out.unions.push({ type: name, name: t.name.value });
}
fs.writeFileSync(outPath, JSON.stringify(out, null, 1));
console.log(JSON.stringify({ types: out.types.length, members: out.members.length, args: out.args.length, unions: out.unions.length }));

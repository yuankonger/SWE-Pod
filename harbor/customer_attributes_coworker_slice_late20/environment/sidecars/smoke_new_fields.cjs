/* Asks a running GraphQL API for what it gained, as staff would read it, and reports what it could not answer.

    node smoke_new_fields.cjs <url> <baseline.graphql> <out.json> [--token <bearer token>]

The baseline is the schema the API had before (CI keeps the one it first saw). A field is gained if its type did not
exist then, or its type did and the field did not. For every field of the query root that can be asked for without
arguments of the asker's choosing (only optional ones, `first` set to 1), a query is made that reaches the gained
fields it leads to (not those a new type has only because it implements an interface the API already had: those
are the interface's), down through connections (edges.node) and objects, three levels deep: each gained field is
selected with its scalar fields, or its `__typename` where it is an interface or union. Mutations are not run.

What counts as unanswered is an error the API did not mean: an exception in a resolver. Refusals it means
(permission, validation, not found) are not counted, nor are gained fields no data reaches (a list that is empty).

    {"gained": n, "asked": [root fields], "reached": [Type.field ...], "failures": [{"field", "message", "code"}]}

Needs the `graphql` package (NODE_PATH). Exit 0 if nothing failed, 1 if something did, 2 if it could not ask. */
const fs = require("fs");
const { buildSchema, buildClientSchema, getIntrospectionQuery, isObjectType, isInterfaceType, isUnionType, isScalarType,
        isEnumType, getNamedType, isNonNullType } = require("graphql");

const [url, baselinePath, out] = process.argv.slice(2);
const token = process.argv.includes("--token") ? process.argv[process.argv.indexOf("--token") + 1] : null;
const MEANT = /permission|not authori[sz]ed|authentication|not found|couldn't resolve|invalid|required|must be|cannot be|does not exist/i;
const HANDLED = new Set(["PermissionDenied", "GraphQLError", "ValidationError", "NOT_FOUND", "INVALID", "REQUIRED", "ReadOnlyException"]);

async function ask(query, variables) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = "Bearer " + token;
  const r = await fetch(url, { method: "POST", headers, body: JSON.stringify({ query, variables: variables || {} }) });
  return r.json();
}

const askable = f => f.args.every(a => !isNonNullType(a.type) || a.defaultValue !== undefined);
const argsOf = f => (f.args.some(a => a.name === "first") ? "(first: 1)" : "");
let inheritedFrom = () => false;      // set once the baseline is read: a field an existing interface gives the type
const scalars = t => Object.values(t.getFields()).filter(f => askable(f) && !inheritedFrom(t, f.name)
  && (isScalarType(getNamedType(f.type)) || isEnumType(getNamedType(f.type)))).map(f => f.name);

function main(live, base) {
  const old = {};
  for (const t of Object.values(base.getTypeMap())) if (isObjectType(t) || isInterfaceType(t)) old[t.name] = new Set(Object.keys(t.getFields()));
  // a field a type has because it implements an interface the API already had is the interface's, not the feature's own
  const inherited = (t, name) => t.getInterfaces().some(i => old[i.name] && old[i.name].has(name));
  inheritedFrom = inherited;
  const isGained = (t, name) => (!old[t.name] || !old[t.name].has(name)) && !inherited(t, name);
  let gained = 0;
  for (const t of Object.values(live.getTypeMap())) {
    if (!isObjectType(t) || t.name.startsWith("__") || t === live.getMutationType() || t === live.getSubscriptionType()) continue;
    for (const name of Object.keys(t.getFields())) if (isGained(t, name)) gained++;
  }
  const reached = new Set();

  // the selection under a value of type t that reaches gained fields, or "" if none are within reach
  function under(t, depth, seen) {
    t = getNamedType(t);
    if (!isObjectType(t) || depth > 3 || seen.has(t.name)) return "";
    const parts = [];
    for (const f of Object.values(t.getFields())) {
      if (!askable(f)) continue;
      const inner = getNamedType(f.type);
      if (isGained(t, f.name)) {
        reached.add(t.name + "." + f.name);
        if (isScalarType(inner) || isEnumType(inner)) parts.push(f.name);
        else if (isInterfaceType(inner) || isUnionType(inner)) parts.push(f.name + argsOf(f) + " { __typename }");
        else if (isObjectType(inner)) {
          const node = inner.getFields().edges ? getNamedType(inner.getFields().edges.type).getFields().node : null;
          const target = node ? getNamedType(node.type) : inner;
          const own = (isObjectType(target) ? scalars(target) : []).slice(0, 12);
          const deeper = under(target, depth + 1, new Set([...seen, t.name]));
          const body = [...own, deeper].filter(Boolean).join(" ") || "__typename";
          parts.push(f.name + argsOf(f) + (node ? " { edges { node { " + body + " } } }" : " { " + body + " }"));
        }
      } else if (isObjectType(inner) && depth < 3) {
        const node = inner.getFields().edges ? getNamedType(inner.getFields().edges.type).getFields().node : null;
        const deeper = under(node ? node.type : inner, depth + 1, new Set([...seen, t.name]));
        if (deeper) parts.push(f.name + argsOf(f) + (node ? " { edges { node { " + deeper + " } } }" : " { " + deeper + " }"));
      }
    }
    return parts.join(" ");
  }

  const root = live.getQueryType(), queries = [];
  for (const f of Object.values(root.getFields())) {
    if (!askable(f) || f.name.startsWith("_")) continue;
    const inner = getNamedType(f.type);
    if (isGained(root, f.name) && (isScalarType(inner) || isEnumType(inner))) { reached.add("Query." + f.name); queries.push([f.name, "{ " + f.name + " }"]); continue; }
    const node = isObjectType(inner) && inner.getFields().edges ? getNamedType(inner.getFields().edges.type).getFields().node : null;
    const target = node ? node.type : inner;
    let body = under(target, 1, new Set());
    if (!body && isGained(root, f.name)) { reached.add("Query." + f.name); body = isObjectType(getNamedType(target)) ? (scalars(getNamedType(target)).slice(0, 12).join(" ") || "__typename") : "__typename"; }
    if (!body) continue;
    queries.push([f.name, "{ " + f.name + argsOf(f) + (node ? " { edges { node { " + body + " } } }" : " { " + body + " }") + " }"]);
  }
  return { gained, queries, reached: [...reached].sort() };
}

(async () => {
  let live, base;
  try {
    const j = await ask(getIntrospectionQuery());
    if (!j.data) throw new Error(JSON.stringify(j.errors || j).slice(0, 400));
    live = buildClientSchema(j.data);
    base = buildSchema(fs.readFileSync(baselinePath, "utf8"));
  } catch (e) { console.error("could not ask: " + e); process.exit(2); }
  const { gained, queries, reached } = main(live, base);
  const failures = [];
  for (const [name, query] of queries) {
    let j;
    try { j = await ask(query); } catch (e) { failures.push({ field: name, message: "no answer: " + e, code: null }); continue; }
    for (const e of j.errors || []) {
      const code = e.extensions && (e.extensions.exception ? e.extensions.exception.code : e.extensions.code);
      if ((code && HANDLED.has(code)) || (!code && MEANT.test(e.message || ""))) continue;
      failures.push({ field: [name, ...(e.path || []).slice(1).filter(p => typeof p === "string")].join("."), message: String(e.message).slice(0, 300), code: code || null });
    }
  }
  fs.writeFileSync(out, JSON.stringify({ gained, asked: queries.map(q => q[0]), reached, failures }, null, 1));
  process.exit(failures.length ? 1 : 0);
})();

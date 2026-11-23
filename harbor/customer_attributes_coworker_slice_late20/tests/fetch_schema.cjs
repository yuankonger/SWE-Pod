/* Writes the schema a running GraphQL API really has, as SDL.   node fetch_schema.cjs <url> <out.graphql> */
const fs = require("fs");
const { getIntrospectionQuery, buildClientSchema, printSchema } = require("graphql");
const [url, out] = process.argv.slice(2);
fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query: getIntrospectionQuery() }) })
  .then(r => r.json())
  .then(j => { if (!j.data) throw new Error(JSON.stringify(j.errors || j).slice(0, 500)); fs.writeFileSync(out, printSchema(buildClientSchema(j.data))); })
  .catch(e => { console.error(String(e)); process.exit(1); });

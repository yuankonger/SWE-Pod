// The Bluesky company's dev network, started from an atproto tree for a check, with a few fixed accounts and the
// notifications the check reads.
//
//     node bsky_seed.mjs <atproto tree> <status file>
//
// Starts the tree's own dev network (packages/dev-env, built: PLC on 2582, PDS on 2583, AppView on 2584, with Ozone
// and bsync beside them) on the Postgres and Redis of `start-test-db`, in a schema of its own. Then makes three
// accounts on the PDS, alice.test, bob.test and carla.test (password `hunter2`), all following each other, and:
//   - Alice writes four posts, the last of them "the newest post";
//   - Bob and Carla like the newest post;
//   - Carla likes Alice's three other posts.
// Once the AppView has indexed all of it, it writes <status file> (JSON): the URLs, the accounts, the posts, and, as
// evidence only, what `app.bsky.notification.getGroupedNotifications` answers Alice through the PDS (or the error).
// It then keeps the network running until it is killed. The AppView's code is the tree's: nothing here knows how it
// groups, the check reads what the app shows.
import fs from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const [TREE, STATUS] = process.argv.slice(2)
const PASSWORD = 'hunter2'

const log = (...a) => console.log(new Date().toISOString(), ...a)

async function main() {
  const devEnv = await import(pathToFileURL(path.join(TREE, 'packages/dev-env/dist/index.js')).href)
  const network = await devEnv.TestNetwork.create({
    dbPostgresSchema: 'seedco_check',
    plc: { port: 2582 },
    pds: { port: 2583, hostname: 'localhost', enableDidDocWithSession: true },
    bsky: { port: 2584 },
  })
  log('network up: PDS', network.pds.url, 'AppView', network.bsky.url)
  const sc = network.getSeedClient()
  const accounts = {}
  for (const name of ['alice', 'bob', 'carla']) {
    const a = await sc.createAccount(name, { handle: `${name}.test`, email: `${name}@test.com`, password: PASSWORD })
    accounts[name] = { did: a.did, handle: `${name}.test`, password: PASSWORD }
  }
  for (const from of ['alice', 'bob', 'carla'])
    for (const to of ['alice', 'bob', 'carla'])
      if (from !== to) await sc.follow(sc.dids[from], sc.dids[to])
  await network.processAll()
  const alice = sc.dids.alice
  const older = []
  for (const text of ['A first post about the garden', 'A second post about the weather', 'A third post about the river']) {
    older.push(await sc.post(alice, text))
  }
  const newest = await sc.post(alice, 'The newest post, about the harvest')
  await network.processAll()
  await sc.like(sc.dids.bob, newest.ref)
  await sc.like(sc.dids.carla, newest.ref)
  for (const p of older) await sc.like(sc.dids.carla, p.ref)
  await network.processAll()

  // evidence only: what the AppView answers Alice, through her PDS as the app asks it
  let grouped = null
  try {
    const session = await (await fetch(`${network.pds.url}/xrpc/com.atproto.server.createSession`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ identifier: 'alice.test', password: PASSWORD }),
    })).json()
    const res = await fetch(`${network.pds.url}/xrpc/app.bsky.notification.getGroupedNotifications?feed=all&limit=30`, {
      headers: { authorization: `Bearer ${session.accessJwt}`, 'atproto-proxy': `${network.bsky.serverDid}#bsky_appview` },
    })
    grouped = { status: res.status, body: await res.json().catch(() => null) }
  } catch (err) {
    grouped = { error: String(err) }
  }
  fs.writeFileSync(STATUS, JSON.stringify({
    pds: network.pds.url, appview: network.bsky.url, appviewDid: network.bsky.serverDid, accounts,
    posts: { newest: newest.ref.uriStr, older: older.map((p) => p.ref.uriStr) }, grouped,
  }, null, 2))
  log('seeded; status written to', STATUS)
  const stop = async () => { try { await network.close() } finally { process.exit(0) } }
  process.on('SIGTERM', stop)
  process.on('SIGINT', stop)
  setInterval(() => {}, 1 << 30)
}

main().catch((err) => {
  console.error('the network could not be started or seeded:', err)
  try { fs.writeFileSync(STATUS + '.failed', String(err && err.stack || err)) } catch {}
  process.exit(1)
})

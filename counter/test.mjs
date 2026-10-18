// Self-check for api/hit.js:  node test.mjs   (from counter/)
//
// By default Abacus is replaced with a stub, so nothing leaves the machine.
// LIVE=1 node test.mjs  counts for real — into a throwaway namespace, never the
// one the site uses — and reads the number back to prove it moved.

import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { createServer } from 'node:http'
import { after, before, test } from 'node:test'

const LIVE = process.env.LIVE === '1'
const NAMESPACE = `mrwd-products-test-${Date.now()}`
process.env.ABACUS_NAMESPACE = NAMESPACE // read when hit.js loads

const realFetch = globalThis.fetch
const upstream = [] // what the function sent to Abacus
let upstreamStatus = 200

if (!LIVE) {
  globalThis.fetch = async (url, init = {}) => {
    if (!String(url).startsWith('https://abacus.jasoncameron.dev/')) return realFetch(url, init)
    upstream.push({ url: String(url), headers: init.headers })
    return new Response(upstreamStatus === 200 ? '{"value":1}' : null, { status: upstreamStatus })
  }
}

const { default: handler, SLUGS, ACTIONS } = await import('./api/hit.js')

const SITE = 'https://mrwd.github.io'
let server, base

before(async () => {
  server = createServer(handler)
  await new Promise((done) => server.listen(0, '127.0.0.1', done))
  base = `http://127.0.0.1:${server.address().port}/api/hit`
})
after(() => server.close())

/** One call as a browser on the site would make it, from a given address. */
function hit(key, { origin = SITE, method = 'POST', ip = '198.51.100.1' } = {}) {
  const headers = { 'x-real-ip': ip }
  if (origin) headers.Origin = origin
  const query = key === undefined ? '' : `?key=${encodeURIComponent(key)}`
  return realFetch(`${base}${query}`, { method, headers })
}

async function abacusValue(key) {
  const res = await realFetch(`https://abacus.jasoncameron.dev/get/${NAMESPACE}/${key}`)
  if (res.status === 404) return 0
  return (await res.json()).value
}

test('the allowlist matches products/ and collect_stats.py', () => {
  const folders = readdirSync(new URL('../products/', import.meta.url), { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name)
    .sort()
  assert.deepEqual([...SLUGS].sort(), folders)

  const py = readFileSync(new URL('../scripts/collect_stats.py', import.meta.url), 'utf8')
  const strings = (src) => [...src.matchAll(/"([^"]+)"/g)].map((m) => m[1])
  const pySlugs = strings(py.match(/^SLUGS = \[([\s\S]*?)\]/m)[1])
  assert.deepEqual([...pySlugs].sort(), folders)

  const useActions = strings(py.match(/^USE_ACTIONS = \(([\s\S]*?)\)/m)[1])
  const extra = strings(py.match(/^ALL_ACTIONS = USE_ACTIONS \+ \(([\s\S]*?)\)/m)[1])
  assert.deepEqual([...ACTIONS].sort(), [...useActions, ...extra].sort())
})

test('preflight from the site is allowed, CORS for nobody else', async () => {
  const res = await hit('film-table--open', { method: 'OPTIONS' })
  assert.equal(res.status, 204)
  assert.equal(res.headers.get('access-control-allow-origin'), SITE)

  const other = await hit('film-table--open', { method: 'OPTIONS', origin: 'https://evil.example' })
  assert.equal(other.headers.get('access-control-allow-origin'), null)
})

test('only POST from the site counts', async () => {
  assert.equal((await hit('film-table--open', { method: 'GET' })).status, 405)
  assert.equal((await hit('film-table--open', { origin: null })).status, 403)
  const evil = await hit('film-table--open', { origin: 'https://evil.example' })
  assert.equal(evil.status, 403)
  assert.equal(evil.headers.get('access-control-allow-origin'), null)
})

test('keys outside <slug>--<action> are refused before Abacus is asked', async () => {
  const sentBefore = upstream.length
  const bad = [
    undefined,
    '',
    'film-table',
    'film-table--hack',
    'nope--open',
    'FILM-TABLE--open',
    'film-table--open/../x',
    'film-table--open ',
    'film-table--open?x=1',
    `${'a'.repeat(200)}--open`,
  ]
  for (const key of bad) {
    assert.equal((await hit(key, { ip: '198.51.100.2' })).status, 400, `key ${JSON.stringify(key)}`)
  }
  assert.equal(upstream.length, sentBefore)
  if (LIVE) assert.equal(await abacusValue('film-table--hack'), 0)
})

test('a valid key is counted, and nothing about the caller is passed on', async () => {
  const key = 'film-table--open'
  const was = LIVE ? await abacusValue(key) : 0

  const res = await hit(key, { ip: '198.51.100.3' })
  assert.equal(res.status, 204)
  assert.equal(res.headers.get('access-control-allow-origin'), SITE)

  if (LIVE) {
    assert.equal(await abacusValue(key), was + 1)
    console.log(`# live: ${NAMESPACE}/${key} went ${was} -> ${was + 1}`)
  } else {
    const sent = upstream.at(-1)
    assert.equal(sent.url, `https://abacus.jasoncameron.dev/hit/${NAMESPACE}/${key}`)
    assert.deepEqual(sent.headers, { 'User-Agent': 'mrwd-counter' })
  }
})

test('an Abacus failure is a 502, not a crash', { skip: LIVE }, async () => {
  upstreamStatus = 500
  try {
    assert.equal((await hit('games-table--open', { ip: '198.51.100.4' })).status, 502)
  } finally {
    upstreamStatus = 200
  }
})

test('one address gets 20 a minute; others are unaffected', async () => {
  const ip = '203.0.113.7'
  for (let i = 1; i <= 20; i += 1) {
    assert.equal((await hit('not-a-key', { ip })).status, 400, `request ${i}`)
  }
  assert.equal((await hit('not-a-key', { ip })).status, 429)
  assert.equal((await hit('film-table--open', { ip })).status, 429)
  assert.equal((await hit('not-a-key', { ip: '203.0.113.8' })).status, 400)
})

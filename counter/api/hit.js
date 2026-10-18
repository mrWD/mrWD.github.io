// The click counter behind track.js. The site used to call Abacus straight from
// the visitor's browser, which handed every visitor's IP address to a third party.
// Now the browser calls this function instead, and this function calls Abacus
// itself: all Abacus ever sees is the counter key and a Vercel server's address.
//
// The key arrives as ?key=<slug>--<action> on a POST. It has to be one of the
// keys below exactly — anything else is refused before Abacus is asked, so this
// cannot be used to create or bump arbitrary counters.
//
// Nothing about the caller is logged or stored. The per-IP rate limit keeps a
// salted hash of the address in memory for its one-minute window, dropped at the
// next sweep or with the instance; the salt is random per instance and never
// leaves memory either. legal/index.html describes this — keep the two in step.

import { createHash, randomBytes } from 'node:crypto'

const ABACUS = 'https://abacus.jasoncameron.dev/hit'
// Overridable only so a test can count into a throwaway namespace. Production
// sets nothing and counts into the namespace scripts/collect_stats.py reads.
const NAMESPACE = process.env.ABACUS_NAMESPACE || 'mrwd-products'
const ALLOWED_ORIGIN = 'https://mrwd.github.io'

/** The folders under products/ — keep in step with SLUGS in collect_stats.py. */
export const SLUGS = [
  'ai-job-search',
  'ai-prompt-suggester',
  'ai-screen-translator',
  'books-table',
  'daylight',
  'double-subtitles',
  'film-table',
  'games-table',
  'goals-table',
  'invest-table',
  'it-skills',
  'langs-db',
  'lingary',
  'science-timeline',
  'spesaplan',
  'travel-planner',
]

/** What track.js can classify a button as — ALL_ACTIONS in collect_stats.py. */
export const ACTIONS = ['open', 'download', 'invite', 'chrome', 'firefox', 'appstore', 'source']

const KEYS = new Set(SLUGS.flatMap((slug) => ACTIONS.map((action) => `${slug}--${action}`)))

/* ------------------------------------------------------------- rate limit */

// A real visitor presses a few buttons at most. Twenty a minute is generous for
// a person and tight for a script. With Fluid compute one warm instance serves
// many requests, so this holds for the usual case; a determined abuser spread
// across cold instances gets through, and that is accepted for a click counter.
const WINDOW_MS = 60_000
const MAX_PER_WINDOW = 20
const MAX_TRACKED = 50_000

const SALT = randomBytes(16)
const recent = new Map() // hashed address -> { count, resetAt }
let nextSweep = 0

function rateLimited(address) {
  const now = Date.now()

  // Forget finished windows every few seconds, so no address outlives its minute
  // by much. If a flood still fills the map, start over rather than grow forever.
  if (now >= nextSweep) {
    for (const [id, entry] of recent) if (entry.resetAt <= now) recent.delete(id)
    nextSweep = now + 10_000
  }
  if (recent.size >= MAX_TRACKED) recent.clear()

  const id = createHash('sha256').update(SALT).update(address).digest('base64url')
  let entry = recent.get(id)
  if (!entry || entry.resetAt <= now) {
    entry = { count: 0, resetAt: now + WINDOW_MS }
    recent.set(id, entry)
  }
  entry.count += 1
  return entry.count > MAX_PER_WINDOW
}

/** Vercel sets x-real-ip itself and overwrites any x-forwarded-for a client sends. */
function clientAddress(req) {
  const real = req.headers['x-real-ip']
  if (real) return String(real)
  const forwarded = req.headers['x-forwarded-for']
  if (forwarded) return String(forwarded).split(',')[0].trim()
  return req.socket?.remoteAddress || 'unknown'
}

/* ---------------------------------------------------------------- handler */

function reply(res, status) {
  res.statusCode = status
  res.setHeader('Cache-Control', 'no-store')
  res.end()
}

// Plain Node req/res only — no Vercel helpers — so the same function runs under a
// bare http.createServer in test.mjs.
export default async function handler(req, res) {
  const origin = req.headers.origin
  if (origin === ALLOWED_ORIGIN) {
    res.setHeader('Access-Control-Allow-Origin', ALLOWED_ORIGIN)
    res.setHeader('Vary', 'Origin')
  }

  if (req.method === 'OPTIONS') {
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS')
    res.setHeader('Access-Control-Max-Age', '86400')
    return reply(res, 204)
  }
  if (req.method !== 'POST') return reply(res, 405)

  // Browsers always send Origin on a POST, so a click from the site always has
  // it. Anything else can fake the header, which is what the rate limit is for.
  if (origin !== ALLOWED_ORIGIN) return reply(res, 403)

  // Counted before the key is checked, so guessing keys costs the same.
  if (rateLimited(clientAddress(req))) return reply(res, 429)

  const key = new URL(req.url, 'http://counter').searchParams.get('key')
  if (!key || !KEYS.has(key)) return reply(res, 400)

  try {
    // A fresh request with none of the caller's headers: no IP, no user agent,
    // no referrer — only the key in the path.
    const upstream = await fetch(`${ABACUS}/${NAMESPACE}/${key}`, {
      headers: { 'User-Agent': 'mrwd-counter' },
      signal: AbortSignal.timeout(5_000),
    })
    return reply(res, upstream.ok ? 204 : 502)
  } catch {
    return reply(res, 502)
  }
}

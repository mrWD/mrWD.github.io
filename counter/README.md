# counter

The click counter behind [`../track.js`](../track.js), as its own tiny Vercel
project. The browser posts `?key=<slug>--<action>` here; [`api/hit.js`](api/hit.js)
checks the key against the products and actions it knows, then increments it on
[Abacus](https://jasoncameron.dev/abacus/) in the `mrwd-products` namespace from
the server — so Abacus never sees a visitor. It answers 204, logs nothing, sends
CORS only to `https://mrwd.github.io`, and allows one address 20 hits a minute.

`scripts/collect_stats.py` still reads the numbers straight from Abacus; nothing
there changed.

## Deploy

New Vercel project from this repository, **Root Directory = `counter`**,
framework preset *Other*, no build command, no environment variables. Name the
project `mrwd-counter` and it lands on `https://mrwd-counter.vercel.app`, which
is what `COUNTER_URL` in `track.js` points at. Any other name: change that one
constant.

## Check

```bash
node test.mjs          # Abacus stubbed, nothing leaves the machine
LIVE=1 node test.mjs   # counts for real, into a throwaway namespace
```

Both also check that the allowed slugs match the folders in `products/` and
`SLUGS` in the collector. A new product means adding its folder name to both.

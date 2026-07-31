# mrwd.github.io

One page that lists everything I've built, plus a page per product where a
GitHub link isn't enough.

Static HTML/CSS/JS. No build step, no dependencies, no backend.

```
index.html               the product list
styles.css               shared tokens, header, footer, buttons — every page
product.css              shared layout for the per-product pages
app.js                   the project data + rendering for the list
products/<slug>/         one page per product, with its own assets/
```

Product pages live under `products/` — `science-timeline`, `lingary`, `langs-db`,
`film-table`, `games-table`, `ai-screen-translator`, `ai-prompt-suggester`,
`double-subtitles` — and **not** at the site root. A repo with its own GitHub Pages site claims that path first:
`mrWD/film-table` publishes to `mrwd.github.io/film-table/`, which silently
shadowed a root-level folder of the same name.

Live at https://mrwd.github.io/ — GitHub Pages serves the `master` branch root,
so a push is the deploy.

## Adding a project

Add an entry to the `PROJECTS` array at the top of [`app.js`](app.js). Array
order is page order. Only `name` and `links` really matter:

```js
{
  name: 'FilmTable',
  tagline: 'One line, shown in the accent colour',
  description: 'Two or three sentences read best.',
  category: 'Web app',              // groups the filter chips at the top
  tags: ['PWA', 'React', 'MIT'],    // small pills
  icon: '🎬',                        // one emoji; defaults to ◆
  accent: '#f2789f',                // empty = a stable colour from the name
  status: 'Live',                   // badge: Live, Beta, WIP, Open source…
  featured: true,                   // tints the card with its accent
  links: [
    { label: 'Open app', url: 'https://…' },
    { label: 'GitHub', url: 'https://…', icon: 'github' },
  ],
}
```

Links render in the order you list them and the first one is the highlighted
button, so put the one you want people to click first. `icon` is optional and
accepts `github`, `chrome`, `firefox` or `download`.

Data used to come from a published Google Sheet. That's gone — the list lives in
`app.js` for now.

## Usage counters

[`.github/workflows/stats.yml`](.github/workflows/stats.yml) runs
[`scripts/collect_stats.py`](scripts/collect_stats.py) once a day, which writes
`stats.json` and commits it only when a number moves. The page reads that file
and adds a badge to the card — **but only above 1000**
(`USERS_THRESHOLD` in `app.js`). Below that the badge stays hidden, because
"9 users" says less than saying nothing.

To track a project, give it a `statsKey` matching a key in `PRODUCTS` in the
collector. Three metrics, and they are *not* comparable:

| Metric | Source | Means |
| --- | --- | --- |
| `users` | Chrome Web Store, Firefox Add-ons | active installs; uninstalling drops out |
| `downloads` | GitHub release assets | lifetime downloads; never goes down |
| `visits` | the project's own `stats.json` | page visits the project counts itself |

Chrome has no API, so its listing page is scraped — that will break whenever
Google changes the markup. The collector fails soft: a broken source keeps its
previous value and the run still succeeds, so a hiccup never blanks the site.

Not every project can have one. Web apps with no counter of their own
(FilmTable, GamesTable, Science Timeline) and an unreleased iOS app (Lingary)
have no public number to read.

## Product pages

Each product folder holds one `index.html` plus its own `assets/`. The page
links `../styles.css` and `../product.css` and sets only its accent inline:

```html
<style>
  :root { --accent: #67e8c3; --accent-2: #7c9cff; }
  html[data-theme='light'] { --accent: #0e9c7c; --accent-2: #3b5ce0; }
</style>
```

Keep the accent the same as the product's card on the index page. Building
blocks available in `product.css`: `.section` + `.section-title`, `.feature-grid`,
`.platforms`, `.steps`, `.compare` (before/after images), `.shots-row` (phone
screenshots), `.chips`, `.badges`, `.demo` (a drawn illustration), `.note`,
`.prose`.

To add another, copy the closest folder and point that project's first link at
it — a relative URL like `products/film-table/` is what makes the card's highlighted
button open the page.

Screenshots of the two web apps were captured from the live deployments at
414×896. The extensions have no screenshots yet.

Lingary's come out of a UI test in the app repo
(`Tests/UITests/MarketingShots.swift`), run once per simulator appearance
because the light and dark shots have to be separate files — `product.css`
swaps them with `.shot-light` / `.shot-dark`. Its page also carries two
page-scoped CSS blocks that no other product needs: the loop diagram (five
screenshots placed on an ellipse) and the sticky contents rail. The folder is
`lingary`, not `lang-tutor`, because that is the name it ships under; the repo
behind it is still `mrWD/lang-tutor` and is private, so the page's header links
to the GitHub profile instead.

## Running locally

```bash
python3 -m http.server -d /Users/viktor/Projects/products-page 8080
```

Then open http://localhost:8080.

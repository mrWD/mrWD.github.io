# mrwd.github.io

My portfolio site: one page that lists everything I've built, plus a page per
product where a GitHub link isn't enough.

Live at https://mrwd.github.io/

Static HTML/CSS/JS. No build step, no dependencies, no backend. A GitHub
Actions job collects public usage numbers once a day and commits them to
`stats.json`.

```
index.html               the product list
styles.css               shared tokens, header, footer, buttons — every page
product.css              shared layout for the per-product pages
app.js                   the project data + rendering for the list
products/<slug>/         one page per product, with its own assets/
```

Product pages live under `products/` — `science-timeline`, `lingary`, `langs-db`,
`film-table`, `games-table`, `books-table`, `invest-table`, `goals-table`,
`it-skills`, `spesaplan`, `travel-planner`, `ai-job-search`, `ai-screen-translator`,
`ai-prompt-suggester`, `double-subtitles` — and **not** at the site root. A repo
with its own GitHub Pages site claims that path first: `mrWD/film-table`
publishes to `mrwd.github.io/film-table/`, which silently shadowed a root-level
folder of the same name. The one root folder left, `ai-screen-translator/`, is
a redirect to the new path because the old URL had already been published.

GitHub Pages serves the `master` branch root, so a push is the deploy.

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
and adds a badge to the card — **but only from 50 up**
(`USERS_THRESHOLD` in `app.js`). Below that the badge stays hidden, because
"9 users" says less than saying nothing.

To track a project, give it a `statsKey` matching a key in `SLUGS` in the
collector. Four metrics, and they are *not* comparable:

| Metric | Source | Means |
| --- | --- | --- |
| `clicks` | [`track.js`](track.js) → Abacus | presses of this site's own action buttons |
| `users` | Chrome Web Store, Firefox Add-ons | active installs; uninstalling drops out |
| `downloads` | GitHub release assets | lifetime downloads; never goes down |
| `visits` | the project's own `stats.json` | page visits the project counts itself |

`clicks` is the one every product can have, so the badge prefers it and falls
back to the store number until someone has clicked. [`track.js`](track.js) runs
on the index and on every product page: it classifies each outbound button
(`open`, `download`, `invite`, `chrome`, `firefox`, `appstore`, `source`) and
increments `<slug>--<action>` on Abacus — no cookies, no identifiers, no reply
read. `source` is recorded but kept out of the headline number; navigation
inside this site, the header links and the footer are not counted at all.

Adding a counter means the site is no longer script-free, so
[`legal/`](legal/index.html) says exactly what is recorded. Keep those in sync.

Chrome has no API, so its listing page is scraped — that will break whenever
Google changes the markup. The collector fails soft: a broken source keeps its
previous value and the run still succeeds, so a hiccup never blanks the site.

Only a few projects have a store number to read: the two extensions (`users`),
the two downloadable apps (`downloads`) and Languages of the World (`visits`,
from its own counter). The other web apps and Lingary are in `SLUGS` for clicks
only. The TestFlight betas that are not in `SLUGS` (InvestTable, GoalsTable,
IT Skills, SpesaPlan) have no counter at all yet.

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

Screenshots of the web apps were captured from the live deployments at
414×896, in light and dark. The extensions have a few shots of the in-page UI
instead, since there is no phone frame to show.

Lingary's come out of a UI test in the app repo
(`Tests/UITests/MarketingShots.swift`), run once per simulator appearance
because the light and dark shots have to be separate files — `product.css`
swaps them with `.shot-light` / `.shot-dark`. Its page also carries two
page-scoped CSS blocks that no other product needs: the loop diagram (five
screenshots placed on an ellipse) and the sticky contents rail. The folder is
`lingary`, not `lang-tutor`, because that is the name it ships under; the repo
behind it is still `mrWD/lang-tutor` and is private, so the page's header links
to the GitHub profile instead.

IT Skills' screenshots come from a Release build on an iPhone 17 Pro Max simulator,
seeded with demo progress and a 9:41 status bar, shot once per appearance and scaled
to 414×900 as opaque PNGs. Its repo, `mrWD/it-skills`, is private too, so the page's
header links to the GitHub profile. The App Store lists it as "IT Skills: Senior Path";
the folder keeps the short name the app shows under its icon.

## Running locally

```bash
python3 -m http.server 8080
```

Then open http://localhost:8080.

## License

The site code is MIT, see [`LICENSE`](LICENSE). Product names, icons and
screenshots belong to the products they show and are not covered by it.

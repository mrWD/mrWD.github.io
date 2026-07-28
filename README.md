# mrwd.github.io

One page that lists everything I've built, plus a page per product where a
GitHub link isn't enough.

Static HTML/CSS/JS. No build step, no dependencies, no backend.

```
index.html               the product list
styles.css               shared tokens, header, footer, buttons — every page
product.css              shared layout for the per-product pages
app.js                   the project data + rendering for the list
<product>/index.html     one page per product, with its own assets/
```

Product pages: `film-table/`, `games-table/`, `ai-screen-translator/`,
`ai-prompt-suggester/`, `double-subtitles/`.

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
it — a relative URL like `film-table/` is what makes the card's highlighted
button open the page.

Screenshots of the two web apps were captured from the live deployments at
414×896. The extensions have no screenshots yet.

## Running locally

```bash
python3 -m http.server -d /Users/viktor/Projects/products-page 8080
```

Then open http://localhost:8080.

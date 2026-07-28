# mrwd.github.io

One page that lists everything I've built, plus a page per product where a
GitHub link isn't enough.

Static HTML/CSS/JS. No build step, no dependencies, no backend.

```
index.html               the product list
styles.css               shared styling (dark + light) for every page
app.js                   the project data + rendering
ai-screen-translator/    product page — index.html, product.css, assets/
```

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

[`ai-screen-translator/`](ai-screen-translator/) is the pattern: its own
`index.html` and `product.css`, linking `../styles.css` for the shared tokens,
header, footer and buttons. `product.css` overrides `--accent` so the page
matches the product's card, and the page carries its own screenshots in
`assets/`.

To add another, copy that folder, and point the project's first link at it
(a relative URL like `ai-screen-translator/` is fine).

## Running locally

```bash
python3 -m http.server -d /Users/viktor/Projects/products-page 8080
```

Then open http://localhost:8080.

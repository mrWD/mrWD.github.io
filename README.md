# Products page

One page that lists everything I've built. The content lives in a Google Sheet —
adding a row there adds a card here, no deploy needed.

Static HTML/CSS/JS. No build step, no dependencies, no backend.

```
index.html     markup
styles.css     styling (dark + light)
app.js         config, Google Sheets loader, rendering
projects.csv   seed data — import this into the sheet to get the right columns
```

## Setup (once, ~3 minutes)

1. **Create the sheet.** In Google Sheets: `File → Import → Upload` and drop in
   [`projects.csv`](projects.csv). Choose **Replace spreadsheet**. That gives you
   all the columns already filled in with the current projects.
2. **Rename the tab** to `Projects` (bottom-left) — that name must match
   `CONFIG.sheetName` in [`app.js`](app.js).
3. **Publish it.** `Share → General access → Anyone with the link → Viewer`.
   The page reads the sheet from the browser, so it has to be link-readable.
   Don't put anything private in that spreadsheet.
4. **Copy the id** out of the sheet URL:
   `https://docs.google.com/spreadsheets/d/`**`THIS_LONG_PART`**`/edit`
5. **Paste it** into `CONFIG.sheetId` at the top of [`app.js`](app.js).

Test without editing the file first: open the page with `?sheet=YOUR_ID` in the
URL — that overrides the config for one visit.

Adding a project later = one new row in the sheet. The page picks it up within
10 minutes (`CONFIG.cacheMinutes`), or immediately on a hard refresh.

## Columns

Only `name` is required — every other column can stay empty. Header names are
matched loosely (case and punctuation are ignored), and unknown columns are
ignored, so you can keep private notes in extra columns.

| Column | What it does |
| --- | --- |
| `name` | Card title. **Required** — rows without it are skipped. |
| `tagline` | One line under the title, in the card's accent colour. |
| `description` | The paragraph. Two or three sentences reads best. |
| `category` | Groups the filter chips at the top (`Web app`, `Extension`, …). |
| `tags` | Comma-separated pills: `PWA, React, MIT`. |
| `icon` | One emoji for the tile. Defaults to `◆`. |
| `accent` | Hex colour, e.g. `#7c9cff`. Empty = a stable colour derived from the name. |
| `status` | Small badge: `Live`, `Beta`, `WIP`, `Open source`… |
| `featured` | `TRUE` tints the card with its accent colour to make it stand out. |
| `order` | Sort order, low first. Empty rows go last, alphabetically. |
| `hidden` | `TRUE` keeps the row in the sheet but off the page. |

Link columns — each non-empty one becomes a button, in this order:

`site` · `live` · `chrome` · `firefox` · `appstore` · `download` · `github` · `article`

`site` is for a product page of its own — see
[`ai-screen-translator/`](ai-screen-translator/), which lives in this repo and is
served at `/ai-screen-translator/`. The first link a project has becomes its
highlighted button, so the order above is also the priority order.

For anything else, use the `links` column: `Label|URL; Label|URL`
(e.g. `Demo video|https://youtu.be/…; Docs|https://…`).

Only `http(s)` URLs are rendered; anything else is dropped.

## Running locally

```bash
python3 -m http.server -d /Users/viktor/Projects/products-page 8080
```

Then open http://localhost:8080. (A plain `file://` open works too, but the
Sheets fetch needs `http://`.)

## Deploying

It's three static files — any host works.

- **Vercel** (same as FilmTable/GamesTable): `vercel --prod` from this folder, no
  framework preset needed.
- **GitHub Pages**: push the folder to a repo, then
  `Settings → Pages → Deploy from a branch → main / (root)`.
- **Cloudflare Pages / Netlify**: drag the folder in, no build command.

## If the sheet is unreachable

`app.js` carries a `FALLBACK` array with the current projects. If Google is down,
the sheet id is missing, or the tab is empty, the page quietly renders that list
instead — a visitor sees a normal page, and the reason is only logged to the
browser console (`[products] sheet unavailable …`). Keep that array roughly in
sync with the sheet, since it's what visitors get when Sheets misbehaves.

The last successful fetch is also cached in `localStorage`, so a returning
visitor never sees an empty page.

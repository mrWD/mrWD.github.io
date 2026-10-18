/* ------------------------------------------------------------------------
 * Counts clicks on the action buttons — Open, Download, Ask for an invite,
 * the store links — so each product can eventually show how often people
 * actually go and use it.
 *
 * One request per click, carrying nothing but the key it increments — which
 * product and which button — and no cookies. It goes to a small function of
 * my own on Vercel (counter/ in this repo), which forwards only that key to
 * Abacus (abacus.jasoncameron.dev), the free counter langs-db also runs on.
 * Abacus never sees the visitor; Vercel does, as any host sees an address it
 * answers, and keeps its request logs for about an hour. No reply is read.
 *
 * The numbers are pulled back once a day by scripts/collect_stats.py into
 * stats.json; the cards render them only once they're large enough to mean
 * something. Blocked by an ad blocker? The click still works — the counter
 * simply misses it.
 * ---------------------------------------------------------------------- */
(() => {
  // The deployed counter/ project. The host is the Vercel project's name — if it
  // is deployed under another name, this is the one line to change.
  const COUNTER_URL = 'https://mrwd-counter.vercel.app/api/hit';

  /** Which button was this — by destination, falling back to its label.
   *  Returns null for links that aren't a product action. */
  function actionFor(url, label) {
    const text = label.toLowerCase();

    // Asking for a TestFlight invite is a mailto: link, so it needs its own
    // branch — an ordinary "email me" link is not a product action.
    if (url.startsWith('mailto:')) {
      return /invite|testflight|beta|access/.test(`${text} ${url.toLowerCase()}`) ? 'invite' : null;
    }

    if (/chromewebstore\.google\.com/.test(url)) return 'chrome';
    if (/addons\.mozilla\.org/.test(url)) return 'firefox';
    if (/apps\.apple\.com|testflight\.apple\.com/.test(url)) return 'appstore';
    if (/github\.com\/[^/]+\/[^/]+\/releases/.test(url)) return 'download';
    if (/github\.com/.test(url)) return 'source';

    if (/invite|testflight|beta/.test(text)) return 'invite';
    if (/download|installer|\.dmg|\.exe/.test(text)) return 'download';
    return 'open';
  }

  /** The product a link belongs to, as the folder name under products/. */
  function slugFor(link) {
    // On a product page every link belongs to that product.
    const here = location.pathname.match(/\/products\/([^/]+)\//);
    if (here) return here[1];

    // On the index, the card's own "Learn more" href names the product.
    const card = link.closest('.card');
    const learnMore = card && card.querySelector('a[href^="products/"]');
    const m = learnMore && learnMore.getAttribute('href').match(/^products\/([^/]+)\//);
    return m ? m[1] : null;
  }

  document.addEventListener('click', (event) => {
    const link = event.target.closest('a[href]');
    if (!link) return;

    const url = link.href;
    if (!/^(https?|mailto):/.test(url)) return; // in-page anchors

    // The header and footer are site chrome — the GitHub profile link and the
    // contact address aren't anyone using a product.
    if (link.closest('.site-header .header-links, .site-footer')) return;

    // Some products live on this very host (mrwd.github.io/langs-db/), so
    // "same host" can't mean "not a product". Only this site's own pages —
    // the index, the product pages, the legal page — are navigation.
    if (link.protocol !== 'mailto:' && link.host === location.host &&
        /^\/(products\/|legal\/|$|index\.html$)/.test(link.pathname)) {
      return;
    }

    const slug = slugFor(link);
    if (!slug) return;

    const action = actionFor(url, link.textContent.trim());
    if (!action) return;

    const key = `${slug}--${action}`;

    try {
      // no-cors + keepalive: fire and forget, survives the page unloading, never
      // holds up the navigation. credentials: 'omit' — no cookies, ever.
      fetch(`${COUNTER_URL}?key=${encodeURIComponent(key)}`, {
        method: 'POST',
        mode: 'no-cors',
        keepalive: true,
        cache: 'no-store',
        credentials: 'omit',
      }).catch(() => {}); // blocked or offline: say nothing in the console
    } catch {
      /* Counting is never worth breaking a click over. */
    }
  }, { capture: true });
})();

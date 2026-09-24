/* ------------------------------------------------------------------------
 * Pages opened from inside one of the apps show no donation buttons.
 *
 * Outside the US, App Store rules don't let an app lead anyone to a payment
 * page other than Apple's own, and a donation button is one. The apps mark
 * their links with ?from=app; this remembers the mark in this browser for
 * twelve hours — so moving around the site, or opening a page in a new tab,
 * keeps it — and tags the page so the stylesheet hides everything marked
 * data-donation. Nothing is sent anywhere and nothing identifies the
 * visitor: it is one timestamp in local storage.
 *
 * Loaded in <head>, before the page paints, so the buttons never flash.
 *
 * Every page of the site loads it, and so does Science Timeline, which shares
 * this origin: a visitor from an app can land on any of them and walk on to
 * the front page. A new page, or a new donation block, needs the same.
 * ---------------------------------------------------------------------- */
(() => {
  const KEY = 'mrwd-from-app-until';
  const TTL_MS = 12 * 60 * 60 * 1000;
  const marked = /[?&]from=app(&|$)/.test(location.search);
  try {
    if (marked) {
      localStorage.setItem(KEY, String(Date.now() + TTL_MS));
      // The mark did its job; a link copied from the address bar shouldn't carry it.
      const url = new URL(location.href);
      url.searchParams.delete('from');
      history.replaceState(history.state, '', url.pathname + url.search + url.hash);
    }
    if (Number(localStorage.getItem(KEY) || 0) > Date.now()) {
      document.documentElement.classList.add('from-app');
    }
  } catch (_) {
    // Storage blocked: the mark still covers this page, because the URL had it.
    if (marked) document.documentElement.classList.add('from-app');
  }
})();

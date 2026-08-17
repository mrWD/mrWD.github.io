#!/usr/bin/env python3
"""Collect public usage numbers for the products into stats.json.

Every source here is public and key-free:

  * Chrome Web Store — no API exists, so the listing page is fetched and the
    "N users" line parsed out of it. Needs a browser User-Agent and the SOCS
    consent cookie, otherwise Google answers with a consent redirect.
  * Firefox Add-ons — a real API, so just JSON.
  * GitHub releases — asset download counts, summed across all releases.
  * langs-db — that project already publishes its own visit counter; this
    just reads the file its CI writes.

The three numbers mean different things, so each product records which metric
it is and the site labels it accordingly. Do not add them together:

  users     — active installs; someone who uninstalls drops out
  downloads — lifetime release downloads; never goes down
  visits    — page visits counted by the project itself

Fails soft on purpose. If a source breaks — Google reshuffles its markup, CI's
IP gets rate-limited — the previous value is kept and the script still exits 0,
so a hiccup never wipes the numbers off the site.
"""

import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "stats.json"

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# Every product on the site, by folder name under products/. Click counters
# exist for all of them; the store/release numbers below only for some.
SLUGS = [
    "science-timeline",
    "lingary",
    "langs-db",
    "film-table",
    "games-table",
    "books-table",
    "ai-job-search",
    "ai-screen-translator",
    "ai-prompt-suggester",
    "double-subtitles",
]

ABACUS_NS = "mrwd-products"

# Buttons that mean "went to use the product". GitHub ("source") is counted
# too but kept out of the headline number — reading the code isn't using it.
USE_ACTIONS = ("open", "download", "invite", "chrome", "firefox", "appstore")
ALL_ACTIONS = USE_ACTIONS + ("source",)

# product key -> (metric, {source: identifier})
PRODUCTS = {
    "double-subtitles": ("users", {"chrome": "cpnlpffdpcpoabpahdgfnecgngapjibn"}),
    "ai-prompt-suggester": (
        "users",
        {"chrome": "ffacabgddhepblahneohlpgmepogoohl", "firefox": "ai-prompt-suggester"},
    ),
    "ai-job-search": ("downloads", {"github_releases": "ai-job-search"}),
    "ai-screen-translator": ("downloads", {"github_releases": "ai-screen-translator"}),
    "langs-db": ("visits", {"self_reported": "https://mrwd.github.io/langs-db/stats.json"}),
}


def fetch(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read().decode("utf-8", "replace")


def chrome_users(ext_id):
    """Parse "N users" off the Chrome Web Store listing."""
    html = fetch(
        f"https://chromewebstore.google.com/detail/{ext_id}",
        {"Accept-Language": "en-US,en;q=0.9", "Cookie": "SOCS=CAI"},
    )
    m = re.search(r"([\d,]+)\+?\s*users", html)
    if not m:
        raise ValueError("no user count in the listing HTML")
    return int(m.group(1).replace(",", ""))


def firefox_users(slug):
    data = json.loads(fetch(f"https://addons.mozilla.org/api/v5/addons/addon/{slug}/"))
    return int(data.get("average_daily_users") or 0)


def github_release_downloads(repo):
    """Sum asset downloads across every release. No releases means zero."""
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:  # only to lift the anonymous rate limit
        headers["Authorization"] = f"Bearer {token}"

    releases = json.loads(
        fetch(f"https://api.github.com/repos/mrWD/{repo}/releases?per_page=100", headers)
    )
    return sum(a.get("download_count", 0) for r in releases for a in r.get("assets", []))


def self_reported_visits(url):
    """Read a counter the project publishes itself."""
    data = json.loads(fetch(url))
    total = data.get("total")
    if not isinstance(total, int):
        raise ValueError(f"no integer 'total' in {url}")
    return total


COLLECTORS = {
    "chrome": chrome_users,
    "firefox": firefox_users,
    "github_releases": github_release_downloads,
    "self_reported": self_reported_visits,
}


def abacus_value(key, attempts=4):
    """Read a counter without incrementing it. Never clicked = 0, not an error.

    Abacus rate-limits bursts, and one run asks for dozens of keys, so this
    paces itself and backs off when told to.
    """
    for attempt in range(attempts):
        time.sleep(0.25)
        try:
            body = fetch(f"https://abacus.jasoncameron.dev/get/{ABACUS_NS}/{key}")
            return int(json.loads(body)["value"])
        except urllib.error.HTTPError as err:
            if err.code == 404:
                return 0  # nobody has clicked this button yet
            if err.code == 429 and attempt < attempts - 1:
                time.sleep(3 * (attempt + 1))
                continue
            raise
    return 0


def collect_clicks(slug):
    """Clicks per button for one product, plus the total that counts as usage."""
    per_action = {}
    for action in ALL_ACTIONS:
        value = abacus_value(f"{slug}--{action}")
        if value:
            per_action[action] = value
    total = sum(per_action.get(a, 0) for a in USE_ACTIONS)
    return total, per_action


def main():
    previous = {}
    if OUT.exists():
        try:
            previous = json.loads(OUT.read_text(encoding="utf-8")).get("products", {})
        except json.JSONDecodeError:
            print("stats.json is unreadable, starting fresh", file=sys.stderr)

    products, failures = {}, 0

    for slug in SLUGS:
        was = previous.get(slug) or {}
        entry = {}

        # 1. Clicks on this site's own buttons — every product has these.
        try:
            clicks, per_action = collect_clicks(slug)
            entry["clicks"] = clicks
            if per_action:
                entry["buttons"] = per_action
            print(f"{slug}/clicks: {clicks} {per_action or ''}")
        except (urllib.error.URLError, ValueError, KeyError, TimeoutError, OSError) as err:
            failures += 1
            entry["clicks"] = was.get("clicks", 0)
            if was.get("buttons"):
                entry["buttons"] = was["buttons"]
            print(f"{slug}/clicks: FAILED ({err}) — keeping {entry['clicks']}", file=sys.stderr)

        # 2. Whatever the stores or GitHub can tell us, where that exists.
        metric, sources = PRODUCTS.get(slug, (None, {}))
        counts = dict(was.get("sources") or {})
        for source, ident in sources.items():
            try:
                counts[source] = COLLECTORS[source](ident)
                print(f"{slug}/{source}: {counts[source]}")
            except (urllib.error.URLError, ValueError, KeyError, TimeoutError, OSError) as err:
                failures += 1
                print(f"{slug}/{source}: FAILED ({err}) — keeping {counts.get(source)}", file=sys.stderr)

        if counts:
            entry["sources"] = counts
            entry["store"] = {"count": sum(counts.values()), "metric": metric}

        # The badge shows clicks — that's the one number every product has.
        # Until anyone has clicked, fall back to the store figure.
        if entry.get("clicks"):
            entry["count"], entry["metric"] = entry["clicks"], "clicks"
        elif "store" in entry:
            entry["count"], entry["metric"] = entry["store"]["count"], entry["store"]["metric"]
        else:
            entry["count"], entry["metric"] = 0, "clicks"

        products[slug] = entry

    OUT.write_text(
        json.dumps(
            {
                "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "note": "Metrics differ per product — see the metric field. Not comparable.",
                "products": products,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"wrote {OUT.relative_to(ROOT)} ({failures} source(s) failed)")


if __name__ == "__main__":
    main()

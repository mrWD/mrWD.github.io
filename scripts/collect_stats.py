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
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "stats.json"

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

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


def main():
    previous = {}
    if OUT.exists():
        try:
            previous = json.loads(OUT.read_text(encoding="utf-8")).get("products", {})
        except json.JSONDecodeError:
            print("stats.json is unreadable, starting fresh", file=sys.stderr)

    products, failures = {}, 0

    for key, (metric, sources) in PRODUCTS.items():
        counts = dict((previous.get(key) or {}).get("sources") or {})

        for source, ident in sources.items():
            try:
                counts[source] = COLLECTORS[source](ident)
                print(f"{key}/{source}: {counts[source]}")
            except (urllib.error.URLError, ValueError, KeyError, TimeoutError, OSError) as err:
                failures += 1
                print(
                    f"{key}/{source}: FAILED ({err}) — keeping {counts.get(source)}",
                    file=sys.stderr,
                )

        if counts:
            products[key] = {
                "count": sum(counts.values()),
                "metric": metric,
                "sources": counts,
            }

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

#!/usr/bin/env python3
"""Collect public install counts for the browser extensions into stats.json.

Two sources, both public and key-free:

  * Chrome Web Store — no API exists, so the listing page is fetched and the
    "N users" line parsed out of it. Needs a browser User-Agent and the SOCS
    consent cookie, otherwise Google answers with a consent redirect.
  * Firefox Add-ons — a real API, so just JSON.

Note the numbers are *active users*, not lifetime downloads: someone who
uninstalls drops out of the count. The site labels them accordingly.

Fails soft on purpose. If a source breaks — Google reshuffles its markup, CI's
IP gets rate-limited — the previous value is kept and the script still exits 0,
so a hiccup never wipes the numbers off the site.
"""

import json
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

# product key -> where its users come from
PRODUCTS = {
    "double-subtitles": {
        "chrome": "cpnlpffdpcpoabpahdgfnecgngapjibn",
    },
    "ai-prompt-suggester": {
        "chrome": "ffacabgddhepblahneohlpgmepogoohl",
        "firefox": "ai-prompt-suggester",
    },
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


COLLECTORS = {"chrome": chrome_users, "firefox": firefox_users}


def main():
    previous = {}
    if OUT.exists():
        try:
            previous = json.loads(OUT.read_text(encoding="utf-8")).get("products", {})
        except json.JSONDecodeError:
            print("stats.json is unreadable, starting fresh", file=sys.stderr)

    products, failures = {}, 0

    for key, sources in PRODUCTS.items():
        was = previous.get(key, {})
        counts = dict(was.get("sources") or {})

        for store, ident in sources.items():
            try:
                counts[store] = COLLECTORS[store](ident)
                print(f"{key}/{store}: {counts[store]}")
            except (urllib.error.URLError, ValueError, TimeoutError, OSError) as err:
                failures += 1
                kept = counts.get(store)
                print(f"{key}/{store}: FAILED ({err}) — keeping {kept}", file=sys.stderr)

        if counts:
            products[key] = {"users": sum(counts.values()), "sources": counts}

    OUT.write_text(
        json.dumps(
            {
                "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "note": "Active users reported by the stores, not lifetime downloads.",
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

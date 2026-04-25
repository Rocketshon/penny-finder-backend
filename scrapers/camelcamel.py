"""CamelCamelCamel top Amazon price drops RSS.

CamelCamel is a public Amazon price tracker. Their `/top_drops/feed` is
an RSS of the biggest current Amazon price drops — every entry is an
Amazon product (with its ASIN in the URL) and parseable price drop info.

Title format: "Product Name - down 95.83% ($11.49) to $0.50 from $11.99"
Link format: "https://camelcamelcamel.com/product/{ASIN}"

We extract the ASIN to build a clean Amazon URL (
`https://www.amazon.com/dp/{ASIN}/`) so the affiliate wrapper can
inject `?tag=pennyhunter20-20`.
"""
from __future__ import annotations

import re
from datetime import datetime

import feedparser
import httpx

from schema import DealItem, ScrapeResult, Source
from scrapers._base import safe_get, utc_now_iso

URL = "https://camelcamelcamel.com/top_drops/feed"
SOURCE_NAME = "camelcamelcamel.com"

# Title regex: capture name + drop% + drop amount + new price + old price
TITLE_RE = re.compile(
    r"^(?P<name>.+?)\s*-\s*down\s+(?P<pct>[\d.]+)%\s*"
    r"\(\$(?P<drop>[\d.,]+)\)\s*to\s*\$(?P<new>[\d.,]+)\s*from\s*\$(?P<old>[\d.,]+)\s*$",
    re.IGNORECASE,
)

ASIN_RE = re.compile(r"/product/([A-Z0-9]{10})")


async def fetch(client: httpx.AsyncClient) -> ScrapeResult:
    raw = await safe_get(client, URL, timeout=15.0)
    if not raw:
        return ScrapeResult(
            highlights=[],
            penny_items=[],
            items=[],
            source=Source(
                name=SOURCE_NAME,
                kind="rss",
                last_checked=utc_now_iso(),
                ok=False,
                note="fetch failed",
            ),
        )

    parsed = feedparser.parse(raw)
    today = datetime.utcnow().date().isoformat()
    items: list[DealItem] = []

    for entry in parsed.entries[:60]:
        title = (getattr(entry, "title", "") or "").strip()
        link = getattr(entry, "link", "") or ""
        if not title or not link:
            continue

        m = TITLE_RE.match(title)
        if not m:
            continue

        asin_m = ASIN_RE.search(link)
        if not asin_m:
            continue
        asin = asin_m.group(1)

        name = m.group("name").strip()
        new_price = float(m.group("new").replace(",", ""))
        old_price = float(m.group("old").replace(",", ""))
        pct = float(m.group("pct"))

        # Only surface meaningful drops to keep noise down. 8% catches more
        # without surfacing trivial fluctuations.
        if pct < 8 or new_price <= 0:
            continue

        items.append(
            DealItem(
                id=f"camelcamel-{asin}",
                name=name[:140],
                store_id="amazon",
                source="camelcamel",
                price=f"${new_price:.2f}",
                original_price=f"${old_price:.2f}",
                sale_story=f"Drop {pct:.0f}%",
                valid_to=today,
            )
        )

    return ScrapeResult(
        highlights=[],
        penny_items=[],
        items=items,
        source=Source(
            name=SOURCE_NAME,
            kind="rss",
            last_checked=utc_now_iso(),
            ok=bool(items),
            note=f"{len(items)} Amazon price drops",
        ),
    )

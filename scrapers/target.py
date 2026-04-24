"""Target weekly-ad scraper.

Signals: seasonal markdown cycle stage (30% → 50% → 70%), Sunday reset.
"""
from __future__ import annotations

import re

import httpx
from selectolax.parser import HTMLParser

from schema import Highlight, ScrapeResult, Source
from scrapers._base import empty_result, safe_get, utc_now_iso

URL = "https://www.target.com/c/weekly-ad"
STORE_ID = "target"
STORE_NAME = "Target"
SOURCE_NAME = "target.com/weeklyad"

_PCT = re.compile(r"(\d{2})\s*%\s*off", re.I)


async def fetch(client: httpx.AsyncClient) -> ScrapeResult:
    html = await safe_get(client, URL)
    if not html:
        return empty_result(SOURCE_NAME, "scraper", note="fetch failed")

    tree = HTMLParser(html)
    text = tree.text(separator=" ")[:12000]

    highlights: list[Highlight] = [
        Highlight(
            id="target-sunday-reset",
            store_id=STORE_ID,
            store_name=STORE_NAME,
            event="weekly_ad_start",
            title="Sunday weekly-ad refresh",
            detail="New ad cycle goes live. Endcaps and promo pricing refresh overnight.",
            day="sun",
            time_hint="open Sunday",
            heat="low",
            source_url=URL,
        )
    ]

    pcts = sorted({int(m.group(1)) for m in _PCT.finditer(text) if 30 <= int(m.group(1)) <= 90})
    if pcts:
        top = pcts[-1]
        heat = "peak" if top >= 70 else "high" if top >= 50 else "med"
        highlights.append(
            Highlight(
                id=f"target-seasonal-{top}",
                store_id=STORE_ID,
                store_name=STORE_NAME,
                event="markdown_cycle",
                title=f"Seasonal → {top}%",
                detail=(
                    f"Seasonal markdown at {top}% off. "
                    "Aisles: seasonal, endcaps, clearance carts. Best pulls first thing."
                ),
                day="sun" if top >= 70 else "thu",
                heat=heat,
                categories=["seasonal"],
                source_url=URL,
            )
        )

    return ScrapeResult(
        highlights=highlights,
        penny_items=[],
        source=Source(
            name=SOURCE_NAME,
            kind="scraper",
            last_checked=utc_now_iso(),
            ok=True,
        ),
    )

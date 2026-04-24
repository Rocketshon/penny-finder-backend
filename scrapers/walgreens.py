"""Walgreens weekly-ad scraper.

Signals: Register Rewards cycle start, clearance.
"""
from __future__ import annotations

import httpx
from selectolax.parser import HTMLParser

from schema import Highlight, ScrapeResult, Source
from scrapers._base import empty_result, safe_get, utc_now_iso

URL = "https://www.walgreens.com/weeklyad"
STORE_ID = "walgreens"
STORE_NAME = "Walgreens"
SOURCE_NAME = "walgreens.com/weeklyad"


async def fetch(client: httpx.AsyncClient) -> ScrapeResult:
    html = await safe_get(client, URL)
    if not html:
        return empty_result(SOURCE_NAME, "scraper", note="fetch failed")

    tree = HTMLParser(html)
    text = tree.text(separator=" ")[:10000].lower()

    highlights: list[Highlight] = [
        Highlight(
            id="walgreens-weekly-ad",
            store_id=STORE_ID,
            store_name=STORE_NAME,
            event="weekly_ad_start",
            title="New ad · RR deals live",
            detail="Register Rewards cycle starts. Check HBA + grocery for stack-worthy items.",
            day="sun",
            heat="low",
            categories=["HBA"],
            source_url=URL,
        )
    ]

    if "clearance" in text:
        highlights.append(
            Highlight(
                id="walgreens-clearance",
                store_id=STORE_ID,
                store_name=STORE_NAME,
                event="clearance_purge",
                title="Clearance callouts",
                detail="Ad references active clearance — back-of-store endcaps worth a pass.",
                day="wed",
                heat="low",
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

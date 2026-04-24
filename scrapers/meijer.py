"""Meijer weekly-ad scraper.

Signals: Two-Day Sale (Fri/Sat), mPerks digital stack.
"""
from __future__ import annotations

import httpx
from selectolax.parser import HTMLParser

from schema import Highlight, ScrapeResult, Source
from scrapers._base import empty_result, safe_get, utc_now_iso

URL = "https://www.meijer.com/weeklyad"
STORE_ID = "meijer"
STORE_NAME = "Meijer"
SOURCE_NAME = "meijer.com/weeklyad"


async def fetch(client: httpx.AsyncClient) -> ScrapeResult:
    html = await safe_get(client, URL)
    if not html:
        return empty_result(SOURCE_NAME, "scraper", note="fetch failed")

    tree = HTMLParser(html)
    text = tree.text(separator=" ")[:10000].lower()

    highlights: list[Highlight] = []

    if "two-day sale" in text or "2-day sale" in text or "two day sale" in text:
        highlights.append(
            Highlight(
                id="meijer-two-day-sale",
                store_id=STORE_ID,
                store_name=STORE_NAME,
                event="coupon_stack",
                title="Two-Day Sale · Fri/Sat",
                detail="mPerks digital coupons stack with sale pricing — grocery + HBA deep cuts.",
                day="fri",
                heat="med",
                categories=["grocery", "HBA"],
                source_url=URL,
            )
        )
    else:
        highlights.append(
            Highlight(
                id="meijer-weekly-ad",
                store_id=STORE_ID,
                store_name=STORE_NAME,
                event="weekly_ad_start",
                title="New weekly ad",
                detail="mPerks refresh. Grocery-focused sale cycle.",
                day="sun",
                heat="low",
                categories=["grocery"],
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

"""CVS deals + weekly-ad scraper.

Signals: ExtraCare promo cycle, quarterly planogram reset (Q1–Q4).
"""
from __future__ import annotations

import re
from datetime import date

import httpx
from selectolax.parser import HTMLParser

from schema import Highlight, ScrapeResult, Source
from scrapers._base import empty_result, safe_get, utc_now_iso

URL = "https://www.cvs.com/weeklyad"
STORE_ID = "cvs"
STORE_NAME = "CVS"
SOURCE_NAME = "cvs.com/deals"


def _quarter_boundary_soon() -> bool:
    """True if we're in the last two weeks of a quarter (reset window)."""
    today = date.today()
    month = today.month
    day = today.day
    quarter_end_months = {3, 6, 9, 12}
    return month in quarter_end_months and day >= 15


async def fetch(client: httpx.AsyncClient) -> ScrapeResult:
    html = await safe_get(client, URL)
    if not html:
        return empty_result(SOURCE_NAME, "scraper", note="fetch failed")

    tree = HTMLParser(html)
    text = tree.text(separator=" ")[:12000].lower()

    highlights: list[Highlight] = [
        Highlight(
            id="cvs-weekly-ad",
            store_id=STORE_ID,
            store_name=STORE_NAME,
            event="weekly_ad_start",
            title="New weekly ad",
            detail="Register Rewards / ExtraBucks cycle refreshes. HBA + cosmetics focus.",
            day="sun",
            heat="low",
            categories=["HBA", "cosmetics"],
            source_url=URL,
        )
    ]

    if re.search(r"extrabucks|extracare", text):
        highlights.append(
            Highlight(
                id="cvs-extrabucks",
                store_id=STORE_ID,
                store_name=STORE_NAME,
                event="coupon_stack",
                title="ExtraBucks stack active",
                detail="ExtraBucks this week stacks with ExtraCare coupons — target HBA endcaps.",
                day="sun",
                heat="med",
                categories=["HBA"],
                source_url=URL,
            )
        )

    if _quarter_boundary_soon():
        highlights.append(
            Highlight(
                id="cvs-quarterly-reset",
                store_id=STORE_ID,
                store_name=STORE_NAME,
                event="reset",
                title="Quarterly reset window",
                detail=(
                    "Overnight planogram reset expected. Cosmetics + HBA "
                    "pulled SKUs hit deep clearance — check back endcaps Sunday morning."
                ),
                day="sun",
                time_hint="open Sunday",
                heat="high",
                categories=["cosmetics", "HBA"],
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

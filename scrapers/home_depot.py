"""Home Depot scraper.

The penny-trick culture at HD centers on price-ending codes
(.06 → .04 → .03 → .02 → .01). Corporate site is a heavy SPA;
community penny-list pages (thefreebieguy, kcl) aggregate confirmed
UPCs — chunk 2's penny_pages module handles those directly.

This module surfaces the stable weekly seasonal-transition signal.
"""
from __future__ import annotations

from datetime import date

import httpx

from schema import Highlight, ScrapeResult, Source
from scrapers._base import safe_get, utc_now_iso

URL = "https://www.homedepot.com/c/all_clearance"
STORE_ID = "home-depot"
STORE_NAME = "Home Depot"
SOURCE_NAME = "homedepot.com/clearance"


def _season_transition_soon() -> bool:
    """HD's deepest cuts come at seasonal transitions (post-holiday + Q-ends)."""
    today = date.today()
    m, d = today.month, today.day
    # Post-holiday transitions
    if (m == 1 and d <= 14) or (m == 2 and d <= 14):
        return True
    if (m == 7 and d >= 15) or m == 8:
        return True
    if (m == 11 and d >= 20) or (m == 12 and d <= 31):
        return True
    return False


async def fetch(client: httpx.AsyncClient) -> ScrapeResult:
    html = await safe_get(client, URL)
    ok = html is not None

    highlights: list[Highlight] = [
        Highlight(
            id="hd-penny-awareness",
            store_id=STORE_ID,
            store_name=STORE_NAME,
            event="clearance_purge",
            title="Price-ending penny trick",
            detail=(
                "Scan UPCs at self-checkout — prices ending .06/.04/.03/.02/.01 "
                "are the clearance ladder. .01 = final penny before pull."
            ),
            day="sat",
            heat="low",
            source_url=URL,
        )
    ]

    if _season_transition_soon():
        highlights.append(
            Highlight(
                id="hd-seasonal-transition",
                store_id=STORE_ID,
                store_name=STORE_NAME,
                event="clearance_purge",
                title="Seasonal transition window",
                detail="Post-holiday and quarter-end cuts: garden, patio, holiday decor routinely hit penny.",
                day="sat",
                heat="high",
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
            ok=ok,
            note=None if ok else "fetch failed",
        ),
    )

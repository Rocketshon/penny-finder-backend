"""Barnes & Noble scraper — bargain / clearance signal.

B&N doesn't have a penny-list culture. The actionable events are:
  - bargain-books restock (continuous)
  - seasonal 50%-off clearance push (summer + winter)
  - B&N Member-exclusive promos
"""
from __future__ import annotations

from datetime import date

import httpx

from schema import Highlight, ScrapeResult, Source
from scrapers._base import safe_get, utc_now_iso

URL = "https://www.barnesandnoble.com/b/bargain-books/_/N-1z13ubn"
STORE_ID = "barnes-noble"
STORE_NAME = "Barnes & Noble"
SOURCE_NAME = "barnesandnoble.com/bargain"


def _clearance_window() -> bool:
    """Semi-annual clearance: late summer (Aug) + winter (Jan)."""
    today = date.today()
    m = today.month
    return m in (1, 7, 8)


async def fetch(client: httpx.AsyncClient) -> ScrapeResult:
    html = await safe_get(client, URL)
    ok = html is not None

    highlights: list[Highlight] = [
        Highlight(
            id="bn-bargain-ongoing",
            store_id=STORE_ID,
            store_name=STORE_NAME,
            event="weekly_ad_start",
            title="Bargain books",
            detail=(
                "Bargain section rotates continuously — publisher remainders at "
                "50–70% off list. Member 10% off stacks on top."
            ),
            day="sat",
            heat="low",
            categories=["books"],
            source_url=URL,
        ),
    ]

    if _clearance_window():
        highlights.append(
            Highlight(
                id="bn-semi-annual-clearance",
                store_id=STORE_ID,
                store_name=STORE_NAME,
                event="clearance_purge",
                title="Semi-annual clearance push",
                detail=(
                    "Seasonal clearance: 50%-off storewide racks + doorbuster book tables. "
                    "Deepest discounts of the year."
                ),
                day="sat",
                heat="high",
                categories=["books"],
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

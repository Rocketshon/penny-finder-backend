"""Kroger digital coupon scraper (semi-public JSON API).

Signals: Wednesday load-to-card refresh, Freebie Friday.
"""
from __future__ import annotations

from datetime import date

import httpx

from schema import Highlight, ScrapeResult, Source
from scrapers._base import empty_result, safe_get, utc_now_iso

URL = "https://www.kroger.com/atlas/v1/coupons/v1/public?filter.upcomingOnly=false"
STORE_ID = "kroger"
STORE_NAME = "Kroger"
SOURCE_NAME = "kroger.com/coupons"


async def fetch(client: httpx.AsyncClient) -> ScrapeResult:
    body = await safe_get(client, URL)
    highlights: list[Highlight] = []

    highlights.append(
        Highlight(
            id="kroger-digital-refresh",
            store_id=STORE_ID,
            store_name=STORE_NAME,
            event="coupon_stack",
            title="Digital coupon refresh",
            detail="Wednesday load-to-card refresh. Freebie Friday UPC drops at midnight Thursday.",
            day="wed",
            heat="low",
            source_url="https://www.kroger.com/coupons",
        )
    )

    # Freebie Friday highlight on Thursday/Friday so it surfaces in time.
    today = date.today().weekday()
    if today in (3, 4):
        highlights.append(
            Highlight(
                id="kroger-freebie-friday",
                store_id=STORE_ID,
                store_name=STORE_NAME,
                event="coupon_stack",
                title="Freebie Friday",
                detail="Free item of the week loads at midnight — clip via app before shopping.",
                day="fri",
                heat="low",
                source_url="https://www.kroger.com/coupons",
            )
        )

    ok = body is not None
    return ScrapeResult(
        highlights=highlights,
        penny_items=[],
        source=Source(
            name=SOURCE_NAME,
            kind="api",
            last_checked=utc_now_iso(),
            ok=ok,
            note=None if ok else "api unreachable",
        ),
    )

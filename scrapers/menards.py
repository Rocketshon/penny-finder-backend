"""Menards scraper — the 11% Rebate is the flagship event."""
from __future__ import annotations

import re

import httpx

from schema import Highlight, ScrapeResult, Source
from scrapers._base import safe_get, utc_now_iso

URL = "https://www.menards.com/main/rebates.html"
STORE_ID = "menards"
STORE_NAME = "Menards"
SOURCE_NAME = "menards.com/rebates"


async def fetch(client: httpx.AsyncClient) -> ScrapeResult:
    html = await safe_get(client, URL)
    ok = html is not None
    highlights: list[Highlight] = []

    has_11_rebate = False
    if html and re.search(r"11\s*%\s*rebate", html, re.I):
        has_11_rebate = True

    if has_11_rebate:
        highlights.append(
            Highlight(
                id="menards-11-rebate",
                store_id=STORE_ID,
                store_name=STORE_NAME,
                event="coupon_stack",
                title="11% Rebate active",
                detail=(
                    "11% Rebate active this week — stacks on top of clearance. "
                    "Mail in or submit online; comes back as Menards merchandise credit."
                ),
                day="sat",
                heat="high",
                source_url=URL,
            )
        )
    else:
        highlights.append(
            Highlight(
                id="menards-weekly-ad",
                store_id=STORE_ID,
                store_name=STORE_NAME,
                event="weekly_ad_start",
                title="Weekly ad refresh",
                detail="Check front banner for active rebate windows — the 11% Rebate stacks with clearance.",
                day="sun",
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
            ok=ok,
            note=None if ok else "fetch failed",
        ),
    )

"""Krazy Coupon Lady — RSS retired.

KCL migrated to Astro and /feed now returns HTML. Until we add a
headless HTML scraper for their penny-list page, this scraper is a
no-op that registers an unsuccessful Source so the briefing sources
panel still shows the site as 'checked, not reachable'.
"""
from __future__ import annotations

import httpx

from schema import ScrapeResult, Source
from scrapers._base import utc_now_iso

SOURCE_NAME = "krazycouponlady.com"


async def fetch(client: httpx.AsyncClient) -> ScrapeResult:
    return ScrapeResult(
        highlights=[],
        penny_items=[],
        source=Source(
            name=SOURCE_NAME,
            kind="rss",
            last_checked=utc_now_iso(),
            ok=False,
            note="RSS retired; HTML scrape pending",
        ),
    )

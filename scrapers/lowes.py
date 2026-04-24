"""Lowe's scraper — Thursday markdown signal."""
from __future__ import annotations

import httpx

from schema import Highlight, ScrapeResult, Source
from scrapers._base import safe_get, utc_now_iso

URL = "https://www.lowes.com/c/clearance"
STORE_ID = "lowes"
STORE_NAME = "Lowe's"
SOURCE_NAME = "lowes.com/clearance"


async def fetch(client: httpx.AsyncClient) -> ScrapeResult:
    html = await safe_get(client, URL)
    ok = html is not None

    highlights: list[Highlight] = [
        Highlight(
            id="lowes-weekly-markdown",
            store_id=STORE_ID,
            store_name=STORE_NAME,
            event="markdown_cycle",
            title="Thursday markdown report",
            detail=(
                "Lowe's runs its weekly markdown report Thursday. "
                "Price-ending .02 = deepest cut; ends-in-7 is the last markdown."
            ),
            day="thu",
            heat="med",
            source_url=URL,
        ),
    ]

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

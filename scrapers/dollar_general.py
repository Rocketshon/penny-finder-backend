"""Dollar General weekly-ad scraper.

Output: one `markdown_cycle` highlight for the week + the standing
`penny_day` highlight (DG's confirmed-weekly Tuesday penny rotation is
the single most important signal in the briefing).
"""
from __future__ import annotations

import httpx
from selectolax.parser import HTMLParser

from schema import Highlight, ScrapeResult, Source
from scrapers._base import empty_result, safe_get, utc_now_iso

URL = "https://www.dollargeneral.com/weekly-ad"
STORE_ID = "dollar-general"
STORE_NAME = "Dollar General"
SOURCE_NAME = "dollargeneral.com/weekly-ad"


async def fetch(client: httpx.AsyncClient) -> ScrapeResult:
    html = await safe_get(client, URL)
    ok = html is not None

    highlights: list[Highlight] = []

    # DG's penny day is a known weekly constant — always emit, even when
    # the weekly-ad URL is unreachable. Community scrapers boost heat + count.
    highlights.append(
        Highlight(
            id="dg-weekly-penny",
            store_id=STORE_ID,
            store_name=STORE_NAME,
            event="penny_day",
            title="Penny Day",
            detail=(
                "Weekly Tuesday penny rotation. Discontinued SKUs tagged for "
                "1¢ — arrive at opening for best pulls."
            ),
            day="tue",
            time_hint="6–7 AM opening",
            heat="peak",
            categories=["seasonal", "apparel", "HBA"],
            source_url=URL,
        )
    )

    # Best-effort supplementary signal: if the weekly-ad page IS reachable,
    # look for clearance/markdown mentions and add a low-heat highlight.
    if html:
        text = HTMLParser(html).text(separator=" ")[:8000].lower()
        if "clearance" in text or "markdown" in text:
            highlights.append(
                Highlight(
                    id="dg-weekly-markdown",
                    store_id=STORE_ID,
                    store_name=STORE_NAME,
                    event="markdown_cycle",
                    title="Clearance endcaps refreshed",
                    detail="Weekly-ad notes clearance rotations. Check back corners and endcaps.",
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
            ok=ok,
            note=None if ok else "fetch failed; stable signal still emitted",
        ),
    )

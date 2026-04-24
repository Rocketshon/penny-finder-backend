"""The Freebie Guy RSS — community-confirmed penny/freebie drops."""
from __future__ import annotations

import httpx

from schema import ScrapeResult
from scrapers._rss_common import parse_rss_feed

URL = "https://thefreebieguy.com/feed/"
SOURCE_NAME = "thefreebieguy.com"


async def fetch(client: httpx.AsyncClient) -> ScrapeResult:
    return await parse_rss_feed(client, url=URL, source_name=SOURCE_NAME)

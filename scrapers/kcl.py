"""Krazy Coupon Lady RSS — store-hack + penny-list posts."""
from __future__ import annotations

import httpx

from schema import ScrapeResult
from scrapers._rss_common import parse_rss_feed

URL = "https://thekrazycouponlady.com/feed"
SOURCE_NAME = "krazycouponlady.com"


async def fetch(client: httpx.AsyncClient) -> ScrapeResult:
    return await parse_rss_feed(client, url=URL, source_name=SOURCE_NAME)

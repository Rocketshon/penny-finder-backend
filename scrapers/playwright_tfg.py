"""Playwright-backed scraper for thefreebieguy.com DG penny list.

TFG's penny-list URL is Cloudflare-gated and returns 403 to plain-HTTP
clients. A real browser session with stealth patches gets through and
yields an identical UPC list to KCL (useful as a 2nd community source
for confidence scoring).

Soft dependency: `playwright` + `playwright-stealth`. If either isn't
installed, this scraper registers an unsuccessful Source with a clear
note and no highlights — pipelines running without Playwright aren't
broken.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import httpx

from schema import Highlight, PennyListEntry, ScrapeResult, Source
from scrapers._base import utc_now_iso
from scrapers.penny_pages import _extract_penny_items  # reuse the parser

SOURCE_NAME = "thefreebieguy.com (playwright)"

TFG_DG_URL = "https://thefreebieguy.com/dollar-general-penny-list/"


def _has_playwright() -> bool:
    try:
        import playwright.async_api  # noqa: F401

        return True
    except ImportError:
        return False


async def _fetch_via_browser(url: str, timeout_ms: int = 45000) -> str | None:
    """Launch chromium with stealth, navigate, return rendered HTML."""
    from playwright.async_api import async_playwright

    # playwright-stealth is optional; without it, success rate drops but is
    # still better than plain HTTP against TFG.
    try:
        from playwright_stealth import Stealth

        stealth_cls = Stealth
    except ImportError:
        stealth_cls = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        if stealth_cls is not None:
            await stealth_cls().apply_stealth_async(ctx)
        page = await ctx.new_page()
        try:
            resp = await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            if not resp or resp.status != 200:
                return None
            await page.wait_for_timeout(1500)
            return await page.content()
        finally:
            await browser.close()


async def fetch(client: httpx.AsyncClient) -> ScrapeResult:
    """Scrape TFG's DG penny-list page via a headless Chromium session."""
    if not _has_playwright():
        return ScrapeResult(
            highlights=[],
            penny_items=[],
            source=Source(
                name=SOURCE_NAME,
                kind="scraper",
                last_checked=utc_now_iso(),
                ok=False,
                note="playwright not installed; skip",
            ),
        )

    try:
        html = await _fetch_via_browser(TFG_DG_URL)
    except Exception as e:
        return ScrapeResult(
            highlights=[],
            penny_items=[],
            source=Source(
                name=SOURCE_NAME,
                kind="scraper",
                last_checked=utc_now_iso(),
                ok=False,
                note=f"browser launch failed: {type(e).__name__}",
            ),
        )

    if not html:
        return ScrapeResult(
            highlights=[],
            penny_items=[],
            source=Source(
                name=SOURCE_NAME,
                kind="scraper",
                last_checked=utc_now_iso(),
                ok=False,
                note="page fetch failed",
            ),
        )

    entries, _ = _extract_penny_items(html, store_id="dollar-general", source="thefreebieguy.com")
    highlights: list[Highlight] = []
    if entries:
        highlights.append(
            Highlight(
                id="playwright-tfg-dg",
                store_id="dollar-general",
                store_name="Dollar General",
                event="community_confirm",
                title=f"Dollar General penny list · {len(entries)} UPC{'s' if len(entries) != 1 else ''}",
                detail=f"Community penny list from thefreebieguy.com ({len(entries)} confirmed items).",
                day="tue",
                heat="high",
                items_expected=len(entries),
                source_url=TFG_DG_URL,
            )
        )

    return ScrapeResult(
        highlights=highlights,
        penny_items=entries,
        source=Source(
            name=SOURCE_NAME,
            kind="scraper",
            last_checked=utc_now_iso(),
            ok=bool(entries),
            note=None if entries else "page reached but no UPCs parsed",
        ),
    )

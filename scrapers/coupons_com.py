"""Coupons.com manufacturer-coupon aggregator (Playwright).

Coupons.com lists Procter & Gamble, Unilever, Kimberly-Clark, etc.
manufacturer coupons that work at most retailers (DG, Walmart, Target,
Kroger, CVS, Walgreens). Surfacing them gives users a bonus "stack
this with your penny day finds" signal.

Like dg_coupons, the page is React-rendered; we Playwright-extract.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import httpx

from schema import DealItem, Highlight, ScrapeResult, Source
from scrapers._base import utc_now_iso

SOURCE_NAME = "coupons.com"
SOURCE_KIND = "scraper"

URL = "https://www.coupons.com/coupons/"
TIMEOUT_MS = 45_000


def _has_playwright() -> bool:
    try:
        import playwright.async_api  # noqa: F401
        return True
    except ImportError:
        return False


async def _render() -> list[dict[str, Any]] | None:
    from playwright.async_api import async_playwright
    try:
        from playwright_stealth import Stealth
        stealth_cls = Stealth
    except ImportError:
        stealth_cls = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 1600},
            locale="en-US",
        )
        if stealth_cls is not None:
            try:
                await stealth_cls().apply_stealth_async(ctx)
            except Exception:
                pass
        page = await ctx.new_page()
        try:
            await page.goto(URL, wait_until="networkidle", timeout=TIMEOUT_MS)
            await page.wait_for_timeout(3500)
            entries = await page.evaluate(
                """
                () => {
                    const out = [];
                    const all = Array.from(document.querySelectorAll('article, [class*="coupon"], [class*="Coupon"], li'));
                    const seen = new Set();
                    for (const el of all) {
                        const text = (el.innerText || '').trim();
                        if (!text || text.length > 400) continue;
                        const m = text.match(/\\$[0-9]+(?:\\.[0-9]{1,2})?\\s*off/i)
                            || text.match(/[0-9]+\\u00a2\\s*off/i)
                            || text.match(/Save\\s*\\$[0-9]+/i);
                        if (!m) continue;
                        const lines = text.split('\\n').map(s => s.trim()).filter(Boolean);
                        const itemLine = lines.find(l => !/^\\$[0-9]/.test(l) && l.length > 8) || lines[0];
                        if (!itemLine) continue;
                        const key = itemLine.slice(0, 60);
                        if (seen.has(key)) continue;
                        seen.add(key);
                        out.push({ item: itemLine.slice(0, 160), saleStory: m[0].slice(0, 60) });
                        if (out.length >= 100) break;
                    }
                    return out;
                }
                """
            )
            return entries
        finally:
            await browser.close()


async def fetch(client: httpx.AsyncClient) -> ScrapeResult:
    if not _has_playwright():
        return ScrapeResult(
            highlights=[], penny_items=[], items=[],
            source=Source(
                name=SOURCE_NAME, kind=SOURCE_KIND, last_checked=utc_now_iso(),
                ok=False, note="playwright not installed",
            ),
        )

    try:
        entries = await _render()
    except Exception as e:
        return ScrapeResult(
            highlights=[], penny_items=[], items=[],
            source=Source(
                name=SOURCE_NAME, kind=SOURCE_KIND, last_checked=utc_now_iso(),
                ok=False, note=f"browser error: {type(e).__name__}",
            ),
        )

    if not entries:
        return ScrapeResult(
            highlights=[], penny_items=[], items=[],
            source=Source(
                name=SOURCE_NAME, kind=SOURCE_KIND, last_checked=utc_now_iso(),
                ok=False, note="page reached but no coupons parsed",
            ),
        )

    # Manufacturer coupons aren't tied to a single retailer — emit one
    # DealItem per coupon, store_id='online' so they appear in
    # category-browse for everyone but don't pollute per-store deal lists.
    items: list[DealItem] = []
    for i, e in enumerate(entries):
        item_name = (e.get("item") or "").strip()
        sale_story = (e.get("saleStory") or "").strip()
        if not item_name or not sale_story:
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", item_name.lower())[:60]
        items.append(
            DealItem(
                id=f"cdc-{slug}-{i}",
                name=item_name[:120],
                store_id="online",
                source="coupons-com",
                sale_story=f"{sale_story} (manufacturer coupon — print or load to retailer card)",
            )
        )

    return ScrapeResult(
        highlights=[],
        penny_items=[],
        items=items,
        source=Source(
            name=SOURCE_NAME, kind=SOURCE_KIND, last_checked=utc_now_iso(),
            ok=bool(items),
            note=None if items else "no coupons extracted",
        ),
    )

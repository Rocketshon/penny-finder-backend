"""Dollar General digital coupons scraper (Playwright + stealth).

DG's coupons page is SPA-rendered (Next.js + GraphQL). The raw HTML returns
no coupon data; the list loads after the JS bundle calls
`https://api.dollargeneral.com/...` post-render. We use Playwright to render
the page, wait for the list to populate, then extract structured data.

Output: list of DealItem records, each tagged source='dg-coupon' with
sale_story like "$2 off select Tide products".

Designed to fail soft: if DG changes their markup or the page never loads
within the timeout, we return empty + log via Source.note. The pipeline
keeps the rest of the briefing unaffected.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from schema import DealItem, Highlight, ScrapeResult, Source
from scrapers._base import utc_now_iso

SOURCE_NAME = "dollargeneral.com/coupons"
SOURCE_KIND = "scraper"

DG_URL = "https://www.dollargeneral.com/deals/coupons"
TIMEOUT_MS = 45_000


def _has_playwright() -> bool:
    try:
        import playwright.async_api  # noqa: F401
        return True
    except ImportError:
        return False


async def _render_and_extract() -> list[dict[str, Any]] | None:
    """Render DG coupons page in headless Chromium, extract structured
    coupon entries. Returns None on any browser-side failure."""
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
            viewport={"width": 1280, "height": 1400},
            locale="en-US",
        )
        if stealth_cls is not None:
            try:
                await stealth_cls().apply_stealth_async(ctx)
            except Exception:
                pass
        page = await ctx.new_page()
        try:
            await page.goto(DG_URL, wait_until="networkidle", timeout=TIMEOUT_MS)
            # Coupons load lazily — give them a beat
            await page.wait_for_timeout(3500)
            # Try a few selector heuristics. Their DOM is React-generated
            # with class hashes, so we anchor on text + role rather than
            # exact selectors.
            entries = await page.evaluate(
                """
                () => {
                    const out = [];
                    // Coupon cards typically contain a "$X.XX off" or "save $" string
                    const all = Array.from(document.querySelectorAll('article, li, div[class*="coupon"], div[class*="Coupon"]'));
                    const seen = new Set();
                    for (const el of all) {
                        const text = (el.innerText || '').trim();
                        if (!text || text.length > 400) continue;
                        const amount = text.match(/\\$[0-9]+(?:\\.[0-9]{1,2})?\\s*(?:off|OFF)/);
                        const cents = text.match(/[0-9]+\\u00a2\\s*off/i);
                        if (!amount && !cents) continue;
                        // Item line is usually first 1-2 lines minus the amount
                        const lines = text.split('\\n').map(s => s.trim()).filter(Boolean);
                        if (lines.length === 0) continue;
                        const key = lines.slice(0, 2).join(' | ');
                        if (seen.has(key)) continue;
                        seen.add(key);
                        const itemLine = lines.find(l => !/\\$[0-9]/.test(l) && l.length > 5) || lines[0];
                        out.push({
                            item: itemLine.slice(0, 160),
                            saleStory: (amount ? amount[0] : cents[0]).slice(0, 60),
                            full: text.slice(0, 240),
                        });
                        if (out.length >= 200) break;
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
            highlights=[],
            penny_items=[],
            items=[],
            source=Source(
                name=SOURCE_NAME, kind=SOURCE_KIND, last_checked=utc_now_iso(),
                ok=False, note="playwright not installed",
            ),
        )

    try:
        entries = await _render_and_extract()
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

    items: list[DealItem] = []
    for i, e in enumerate(entries):
        item_name = (e.get("item") or "").strip()
        sale_story = (e.get("saleStory") or "").strip()
        if not item_name or not sale_story:
            continue
        # Build a stable deterministic id from item + amount
        slug = re.sub(r"[^a-z0-9]+", "-", item_name.lower())[:60]
        items.append(
            DealItem(
                id=f"dg-coupon-{slug}-{i}",
                name=item_name[:120],
                store_id="dg",
                source="dg-coupon",
                sale_story=f"{sale_story} (DG digital coupon — clip in app)",
            )
        )

    highlights: list[Highlight] = []
    if items:
        highlights.append(
            Highlight(
                id=f"dg-coupons-{datetime.now(timezone.utc).date().isoformat()}",
                store_id="dg",
                store_name="Dollar General",
                event="coupon_stack",
                title=f"{len(items)} digital coupons live",
                detail=(
                    f"{len(items)} DG digital coupons available right now. "
                    f"Clip in the DG app to redeem at checkout."
                ),
                day="any" if False else "tue",  # tue is the canonical penny day; coupons stack
                heat="med",
                items_expected=len(items),
                source_url=DG_URL,
            )
        )

    return ScrapeResult(
        highlights=highlights,
        penny_items=[],
        items=items,
        source=Source(
            name=SOURCE_NAME,
            kind=SOURCE_KIND,
            last_checked=utc_now_iso(),
            ok=bool(items),
            note=None if items else "no coupons extracted",
        ),
    )

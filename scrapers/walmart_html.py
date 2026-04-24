"""Walmart deals scraper — parses a user-saved HTML file.

Walmart is aggressively guarded by PerimeterX; plain-HTTP fetches hit
a "Robot or human?" gate even with stealth. The pragmatic workaround:
when the user saves the Flash Deals (or any deals) page from their
own browser, the resulting .html file contains a fully-hydrated
`__NEXT_DATA__` script tag with 1000+ structured product records.

Pipeline:
  1. Look for `circulars/walmart.html` (or walmart-<anything>.html).
  2. Parse the `__NEXT_DATA__` JSON blob.
  3. Walk the content tree and collect anything with `priceInfo`
     + `name` + `usItemId`.
  4. Emit one Highlight with items_expected = deal count and a few
     "now $X was $Y" picks in the detail string.

If no matching file exists, this is a no-op (`ok=False` with note).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx

from schema import Highlight, ScrapeResult, Source
from scrapers._base import utc_now_iso

SOURCE_NAME = "walmart-html"
CIRCULARS_DIR = Path(__file__).parent.parent / "circulars"

NEXT_DATA = re.compile(
    r'<script[^>]*id="__NEXT_DATA__"[^>]*>(\{.*?\})</script>',
    re.DOTALL,
)


def _walk_products(node: Any) -> list[dict[str, Any]]:
    """Collect dicts that look like product records (have priceInfo + name)."""
    out: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if "priceInfo" in node and isinstance(node.get("priceInfo"), dict) and node.get("name"):
            out.append(node)
        for v in node.values():
            out.extend(_walk_products(v))
    elif isinstance(node, list):
        for v in node:
            out.extend(_walk_products(v))
    return out


def _parse_walmart_html(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = NEXT_DATA.search(text)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    products = _walk_products(data)
    # De-dupe by usItemId
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for p in products:
        key = str(p.get("usItemId") or p.get("itemId") or p.get("name") or "")[:32]
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)
    return unique


def _format_pick(p: dict[str, Any]) -> str:
    pi = p.get("priceInfo") or {}
    now = pi.get("linePriceDisplay") or pi.get("linePrice") or f"${p.get('price','?')}"
    savings = pi.get("savings") or ""
    name = (p.get("name") or "")[:50]
    return f"{now} {name}" + (f" ({savings})" if savings else "")


async def fetch(client: httpx.AsyncClient) -> ScrapeResult:  # noqa: ARG001
    if not CIRCULARS_DIR.exists():
        return ScrapeResult(
            highlights=[],
            penny_items=[],
            source=Source(
                name=SOURCE_NAME,
                kind="scraper",
                last_checked=utc_now_iso(),
                ok=False,
                note="circulars/ directory not present",
            ),
        )

    candidates = [
        p for p in CIRCULARS_DIR.glob("walmart*.html") if p.is_file()
    ]
    if not candidates:
        return ScrapeResult(
            highlights=[],
            penny_items=[],
            source=Source(
                name=SOURCE_NAME,
                kind="scraper",
                last_checked=utc_now_iso(),
                ok=False,
                note="no circulars/walmart*.html file present",
            ),
        )

    # Pick the most recently modified file.
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    path = candidates[0]

    try:
        products = _parse_walmart_html(path)
    except Exception as e:
        return ScrapeResult(
            highlights=[],
            penny_items=[],
            source=Source(
                name=SOURCE_NAME,
                kind="scraper",
                last_checked=utc_now_iso(),
                ok=False,
                note=f"parse error: {type(e).__name__}",
            ),
        )

    if not products:
        return ScrapeResult(
            highlights=[],
            penny_items=[],
            source=Source(
                name=SOURCE_NAME,
                kind="scraper",
                last_checked=utc_now_iso(),
                ok=False,
                note="no products extracted from saved HTML",
            ),
        )

    total = len(products)
    # Top picks by savings amount (if present) or lowest price
    def savings_key(p: dict[str, Any]) -> float:
        pi = p.get("priceInfo") or {}
        try:
            return -float(pi.get("savingsAmt") or 0)
        except (TypeError, ValueError):
            return 0.0

    picks = sorted(products, key=savings_key)[:3]
    samples = "; ".join(_format_pick(p) for p in picks)
    heat = "high" if total >= 100 else "med" if total >= 30 else "low"

    highlight = Highlight(
        id="walmart-flash-deals",
        store_id="wm-ct",  # matches the Walmart branch row in data.ts
        store_name="Walmart",
        event="markdown_cycle",
        title=f"Flash Deals · {total}",
        detail=(f"{total} flash deals saved from walmart.com. Top savings: {samples}.")[:400],
        day="mon",  # Walmart markdowns commonly Mon/Wed
        heat=heat,
        items_expected=total,
        source_url="https://www.walmart.com/shop/deals/flash-picks",
    )

    return ScrapeResult(
        highlights=[highlight],
        penny_items=[],
        source=Source(
            name=SOURCE_NAME,
            kind="scraper",
            last_checked=utc_now_iso(),
            ok=True,
            note=f"parsed {path.name} ({total} products)",
        ),
    )

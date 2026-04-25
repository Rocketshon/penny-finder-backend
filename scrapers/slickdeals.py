"""Slickdeals frontpage RSS scraper.

Slickdeals is a community-vetted online deal aggregator. Their frontpage
RSS exposes ~30 popular deals at any time, each with a title, retailer
hint, and price. We parse it into DealItems flagged with `source='slickdeals'`
so the app can offer an "Online" filter alongside in-store deals.

Retailer-from-title heuristic: titles commonly end with "at <Retailer>"
or "via <Retailer>" or start with "<Retailer> has...". We map known
retailers to canonical store_ids and fall back to "online" otherwise.
"""
from __future__ import annotations

import html
import re
from datetime import datetime

import feedparser
import httpx

from schema import DealItem, ScrapeResult, Source
from scrapers._base import safe_get, utc_now_iso

URL = "https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&rss=1"
SOURCE_NAME = "slickdeals.net"

# Known retailer-name → canonical store_id mappings. Keep keys lowercase.
# Anything not here falls through to "online".
RETAILER_MAP: dict[str, str] = {
    "amazon": "amazon",
    "amazon.com": "amazon",
    "ebay": "ebay",
    "ebay.com": "ebay",
    "walmart": "wm-ct",
    "walmart.com": "wm-ct",
    "target": "target",
    "target.com": "target",
    "best buy": "best-buy",
    "bestbuy.com": "best-buy",
    "best buy.com": "best-buy",
    "home depot": "home-depot",
    "the home depot": "home-depot",
    "homedepot.com": "home-depot",
    "lowe's": "lowes",
    "lowes": "lowes",
    "lowes.com": "lowes",
    "costco": "costco",
    "costco.com": "costco",
    "kohl's": "kohls",
    "kohls": "kohls",
    "macy's": "macys",
    "jcpenney": "jcp",
    "tj maxx": "tj-maxx",
    "marshalls": "marshalls",
    "homegoods": "homegoods",
    "kroger": "kroger",
    "meijer": "meijer",
    "cvs": "cvs",
    "walgreens": "walgreens",
    "rite aid": "rite-aid",
    "ulta": "ulta",
    "sephora": "sephora",
    "best buy": "best-buy",
    "menards": "menards",
    "harbor freight": "harbor-freight",
    "five below": "five-below",
    "big lots": "big-lots",
    "barnes & noble": "barnes-noble",
    "staples": "staples",
    "office depot": "office-depot",
    "petsmart": "petsmart",
    "petco": "petco",
    "michaels": "michaels",
    "joann": "joann",
    "hobby lobby": "hl",
    "dick's sporting goods": "dicks",
    "dollar general": "dollar-general",
    "family dollar": "family-dollar",
    "dollar tree": "dollar-tree",
}

PRICE_RE = re.compile(r"\$([\d,]+(?:\.\d{2})?)")
TAG_RE = re.compile(r"<[^>]+>")
IMG_SRC_RE = re.compile(r'<img[^>]+src="([^"]+)"', re.I)
RETAILER_TAIL_RE = re.compile(r"\b(?:at|via|from|on)\s+([A-Z][\w&'.-]*(?:\s+[A-Z][\w&'.-]*){0,3})", re.I)
RETAILER_HEAD_RE = re.compile(
    r"^([A-Z][\w&'.-]*(?:\s+[A-Z][\w&'.-]*){0,2})\s+has\b", re.I
)


def _strip_tags(s: str) -> str:
    return TAG_RE.sub("", html.unescape(s or "")).strip()


def _retailer_for(title: str, summary: str) -> tuple[str, str]:
    """Return (store_id, store_name_display)."""
    haystack = f"{title} {summary}"
    # Try tail patterns first ("...at Amazon", "...via eBay")
    for m in RETAILER_TAIL_RE.finditer(haystack):
        candidate = m.group(1).strip().lower().rstrip(".,!?;:")
        if candidate in RETAILER_MAP:
            return RETAILER_MAP[candidate], candidate.title()
    # Then head pattern ("Amazon has ...")
    m = RETAILER_HEAD_RE.match(title.strip())
    if m:
        candidate = m.group(1).strip().lower().rstrip(".,!?;:")
        if candidate in RETAILER_MAP:
            return RETAILER_MAP[candidate], candidate.title()
    # Fallback: scan known retailer names anywhere in title
    low = title.lower()
    for name, sid in RETAILER_MAP.items():
        if f" {name} " in f" {low} " or low.startswith(f"{name} "):
            return sid, name.title()
    return "online", "Online"


def _extract_price(title: str, summary: str) -> tuple[str | None, str | None]:
    """Return (current_price, original_price) as formatted strings."""
    prices: list[float] = []
    for src in (title, summary):
        for m in PRICE_RE.finditer(src or ""):
            try:
                p = float(m.group(1).replace(",", ""))
                if 0 < p < 100000:
                    prices.append(p)
            except ValueError:
                pass
    if not prices:
        return None, None
    cur = min(prices)
    if len(prices) >= 2:
        # If a clearly-larger price appears, treat as "was"
        rest = sorted(set(prices) - {cur})
        if rest and rest[-1] >= cur * 1.2:
            return f"${cur:.2f}", f"${rest[-1]:.2f}"
    return f"${cur:.2f}", None


def _slickdeals_url(link: str | None) -> str | None:
    if not link:
        return None
    return link.split("?")[0]


async def fetch(client: httpx.AsyncClient) -> ScrapeResult:
    raw = await safe_get(client, URL, timeout=15.0)
    if not raw:
        return ScrapeResult(
            highlights=[],
            penny_items=[],
            items=[],
            source=Source(
                name=SOURCE_NAME,
                kind="rss",
                last_checked=utc_now_iso(),
                ok=False,
                note="fetch failed",
            ),
        )

    parsed = feedparser.parse(raw)
    today = datetime.utcnow().date().isoformat()
    items: list[DealItem] = []

    for entry in parsed.entries[:40]:
        title = (getattr(entry, "title", "") or "").strip()
        if not title:
            continue
        summary_html = getattr(entry, "summary", "") or ""
        summary = _strip_tags(summary_html)
        link = _slickdeals_url(getattr(entry, "link", None))

        store_id, _ = _retailer_for(title, summary)
        cur, orig = _extract_price(title, summary)

        # Image from <content:encoded>
        image_url: str | None = None
        contents = getattr(entry, "content", None) or []
        for c in contents[:1]:
            cval = getattr(c, "value", None) or ""
            mimg = IMG_SRC_RE.search(cval)
            if mimg:
                image_url = mimg.group(1)
                break

        guid = getattr(entry, "id", None) or getattr(entry, "guid", None) or title
        slug = re.sub(r"[^a-z0-9]+", "-", guid.lower()).strip("-")[:60] or "deal"

        items.append(
            DealItem(
                id=f"slickdeals-{slug}",
                name=title[:140],
                store_id=store_id,
                source="slickdeals",
                price=cur,
                original_price=orig,
                sale_story=None,
                image_url=image_url,
                valid_to=today,
            )
        )

    return ScrapeResult(
        highlights=[],
        penny_items=[],
        items=items,
        source=Source(
            name=SOURCE_NAME,
            kind="rss",
            last_checked=utc_now_iso(),
            ok=bool(items),
            note=f"{len(items)} online deals indexed",
        ),
    )

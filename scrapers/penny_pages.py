"""Direct HTML scrapers for the community penny-list pages.

RSS only surfaces blog-post fragments. The *actual* penny list lives on
dedicated static pages that community sites maintain and update weekly.
We scrape those pages per-store and emit PennyListEntry records with
source='community'. Cross-verify later upgrades them to 'scrape' when a
catalog echoes the UPC.

Target pages:
  Dollar General:
    https://thefreebieguy.com/dollar-general-penny-list/
    https://thekrazycouponlady.com/tips/store-hacks/dollar-general-penny-list
    https://pennypinchinmom.com/dollar-general-penny-list/

  Home Depot:
    https://thefreebieguy.com/home-depot-penny-list/
    https://thekrazycouponlady.com/tips/store-hacks/home-depot-penny-items
"""
from __future__ import annotations

import re
from datetime import datetime

import httpx
from selectolax.parser import HTMLParser

from schema import Highlight, PennyListEntry, ScrapeResult, Source
from scrapers._base import empty_result, safe_get, utc_now_iso

SOURCE_NAME = "penny-list-pages"

# Match "Item name - 012345678901" style or "Item name — UPC: 012345678901"
UPC_LINE = re.compile(
    r"""(?P<item>[^\n\r]+?)
        \s*[-–—]\s*
        (?:UPC[:\s]*)?
        (?P<upc>\d{11,13})
    """,
    re.VERBOSE,
)

PAGES: list[tuple[str, str, str]] = [
    # (url, store_id, source_label)
    ("https://thefreebieguy.com/dollar-general-penny-list/", "dollar-general", "thefreebieguy.com"),
    ("https://thekrazycouponlady.com/tips/store-hacks/dollar-general-penny-list", "dollar-general", "krazycouponlady.com"),
    ("https://pennypinchinmom.com/dollar-general-penny-list/", "dollar-general", "pennypinchinmom.com"),
    ("https://thefreebieguy.com/home-depot-penny-list/", "home-depot", "thefreebieguy.com"),
    ("https://thekrazycouponlady.com/tips/store-hacks/home-depot-penny-items", "home-depot", "krazycouponlady.com"),
]

STORE_NAMES = {
    "dollar-general": "Dollar General",
    "home-depot": "Home Depot",
}

# Noise patterns we strip from matched lines (ad copy, navigation).
_NOISE_PREFIXES = (
    "filed under",
    "also see",
    "check our",
    "download",
    "quick tips",
    "ready to start",
    "related post",
    "advertisement",
    "continue reading",
    "also check",
)


def _clean(text: str) -> str:
    # Strip control chars + zero-width chars (BOM, ZWSP, ZWJ) that penny-list
    # pages often embed between words after CMS copy-paste.
    text = re.sub(r"[\x00-\x1f\x7f\ufeff\u200b\u200c\u200d]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:200]


def _extract_penny_items(html: str, store_id: str, source: str) -> tuple[list[PennyListEntry], int]:
    """Parse a penny-list page into PennyListEntry records.

    Returns (entries, non_header_line_count) so callers can gauge scrape
    health even when UPC extraction yields zero.
    """
    tree = HTMLParser(html)
    today = datetime.utcnow().date().isoformat()
    entries: list[PennyListEntry] = []
    seen: set[str] = set()
    line_count = 0

    # Querying the whole tree: sites rearrange their <article> layouts too
    # often for a "find the container" heuristic to work reliably. The
    # noise-prefix filter + UPC regex are strict enough to reject junk.
    for el in tree.css("li, p, h2, h3, h4"):
        text = _clean(el.text(separator=" "))
        if not (5 < len(text) < 300):
            continue
        line_count += 1

        if any(text.lower().startswith(p) for p in _NOISE_PREFIXES):
            continue

        m = UPC_LINE.search(text)
        if not m:
            continue
        item = m.group("item").strip(" -–—:")
        upc = m.group("upc")

        if upc in seen:
            continue
        seen.add(upc)

        entries.append(
            PennyListEntry(
                store_id=store_id,
                item=item[:140] or "Unknown item",
                upc=upc,
                confirmed_on=today,
                source="community",
                note=source,
            )
        )

    return entries, line_count


async def fetch(client: httpx.AsyncClient) -> ScrapeResult:
    """Fetch all penny-list pages sequentially. Each page failure is isolated."""
    highlights: list[Highlight] = []
    all_entries: list[PennyListEntry] = []
    per_source_ok: dict[str, bool] = {}

    for url, store_id, source in PAGES:
        html = await safe_get(client, url, timeout=20.0)
        if not html:
            per_source_ok.setdefault(source, False)
            continue

        entries, _ = _extract_penny_items(html, store_id=store_id, source=source)
        per_source_ok[source] = True if entries else per_source_ok.get(source, True)
        all_entries.extend(entries)

        if entries:
            store_name = STORE_NAMES.get(store_id, store_id)
            highlights.append(
                Highlight(
                    id=f"penny-page-{store_id}-{source}",
                    store_id=store_id,
                    store_name=store_name,
                    event="community_confirm",
                    title=f"{store_name} penny list · {len(entries)} UPC{'s' if len(entries) != 1 else ''}",
                    detail=f"Community penny list from {source} ({len(entries)} confirmed items).",
                    day="tue" if store_id == "dollar-general" else "sat",
                    heat="high",
                    items_expected=len(entries),
                    source_url=url,
                )
            )

    # Aggregate source health: module reports ok=True if at least one page yielded data.
    any_ok = any(per_source_ok.values())

    return ScrapeResult(
        highlights=highlights,
        penny_items=all_entries,
        source=Source(
            name=SOURCE_NAME,
            kind="scraper",
            last_checked=utc_now_iso(),
            ok=any_ok,
            note=None if any_ok else "no penny pages reachable",
        ),
    )

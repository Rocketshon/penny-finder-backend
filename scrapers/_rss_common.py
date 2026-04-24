"""Shared RSS parsing for community penny-list sources."""
from __future__ import annotations

import re
from datetime import datetime

import feedparser
import httpx

from schema import Highlight, PennyListEntry, ScrapeResult, Source
from scrapers._base import empty_result, safe_get, utc_now_iso

UPC_PATTERN = re.compile(r"\b(\d{11,13})\b")
PENNY_PHRASES = ("penny list", "penny item", "1¢", "1 cent", "one cent")
STORE_HINTS: dict[str, tuple[str, str]] = {
    "dollar general": ("dollar-general", "Dollar General"),
    "dg": ("dollar-general", "Dollar General"),
    "target": ("target", "Target"),
    "cvs": ("cvs", "CVS"),
    "walgreens": ("walgreens", "Walgreens"),
    "meijer": ("meijer", "Meijer"),
    "kroger": ("kroger", "Kroger"),
}


def _infer_store(text: str) -> tuple[str, str] | None:
    low = text.lower()
    for phrase, ids in STORE_HINTS.items():
        if phrase in low:
            return ids
    return None


def _title_to_item(title: str) -> str:
    # Strip leading "DG Penny List - " style prefixes.
    t = re.sub(r"^(DG|Dollar General)\s+penny[^:\-–—]*[:\-–—]\s*", "", title, flags=re.I)
    return t.strip()[:140]


async def parse_rss_feed(
    client: httpx.AsyncClient,
    *,
    url: str,
    source_name: str,
) -> ScrapeResult:
    raw = await safe_get(client, url, timeout=15.0)
    if not raw:
        return empty_result(source_name, "rss", note="fetch failed")

    parsed = feedparser.parse(raw)
    today = datetime.utcnow().date().isoformat()

    highlights: list[Highlight] = []
    penny_items: list[PennyListEntry] = []

    for entry in parsed.entries[:40]:
        title = getattr(entry, "title", "") or ""
        summary = getattr(entry, "summary", "") or ""
        link = getattr(entry, "link", None)
        combined = f"{title} {summary}"

        is_penny = any(p in combined.lower() for p in PENNY_PHRASES)
        store = _infer_store(combined)
        if not store:
            continue
        store_id, store_name = store

        if is_penny:
            highlights.append(
                Highlight(
                    id=f"community-{source_name}-{abs(hash(title)) % (10**8)}",
                    store_id=store_id,
                    store_name=store_name,
                    event="community_confirm",
                    title=_title_to_item(title) or "Community penny confirm",
                    detail=(summary[:200] or "Community-confirmed penny item.").strip(),
                    day="tue" if store_id == "dollar-general" else "wed",
                    heat="med",
                    source_url=link,
                )
            )

            for upc in UPC_PATTERN.findall(combined)[:20]:
                penny_items.append(
                    PennyListEntry(
                        store_id=store_id,
                        item=_title_to_item(title) or "Unknown item",
                        upc=upc,
                        confirmed_on=today,
                        source="community",
                        note=source_name,
                    )
                )

    return ScrapeResult(
        highlights=highlights,
        penny_items=penny_items,
        source=Source(
            name=source_name,
            kind="rss",
            last_checked=utc_now_iso(),
            ok=True,
        ),
    )

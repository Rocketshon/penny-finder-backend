"""Shared RSS parsing for community penny-list sources.

Upgraded from loose title-substring matching to RSS `<category>` tag
mapping. Category tags are the reliable signal — title/summary text is
messy and often lacks the store name outright.

Signal ladder (per entry, once category matches a tracked store):
  - "penny list" / "1¢" / "penny" in title or summary  → heat=high, emit UPCs
  - "clearance" / "markdown" / "discontinued"          → heat=med
  - category-match only                                → heat=low
"""
from __future__ import annotations

import html
import re
from datetime import datetime

import feedparser
import httpx

from schema import Highlight, PennyListEntry, ScrapeResult, Source
from scrapers._base import empty_result, safe_get, utc_now_iso

# RSS category term → (store_id, store_name). Anything not here is skipped.
CATEGORY_STORE: dict[str, tuple[str, str]] = {
    "dollar general": ("dollar-general", "Dollar General"),
    "dg": ("dollar-general", "Dollar General"),
    "target": ("target", "Target"),
    "target deals and codes": ("target", "Target"),
    "cvs": ("cvs", "CVS"),
    "walgreens": ("walgreens", "Walgreens"),
    "meijer": ("meijer", "Meijer"),
    "kroger": ("kroger", "Kroger"),
}

# Title/summary fallback when categories are missing or generic.
TITLE_STORE_HINTS: dict[str, tuple[str, str]] = {
    "dollar general": ("dollar-general", "Dollar General"),
    " dg ": ("dollar-general", "Dollar General"),
    "target": ("target", "Target"),
    "cvs": ("cvs", "CVS"),
    "walgreens": ("walgreens", "Walgreens"),
    "meijer": ("meijer", "Meijer"),
    "kroger": ("kroger", "Kroger"),
}

STRONG_PENNY = ("penny list", "1¢", "1 cent", "one cent", "penny item")
WEAK_PENNY = ("penny", "markdown", "clearance", "discontinued")

UPC_PATTERN = re.compile(r"\b(\d{11,13})\b")
TAG_STRIP = re.compile(r"<[^>]+>")


def _categories(entry) -> list[str]:
    cats = [t.term for t in getattr(entry, "tags", []) if getattr(t, "term", None)]
    return [c.lower().strip() for c in cats]


def _store_from_categories(cats: list[str]) -> tuple[str, str] | None:
    for c in cats:
        if c in CATEGORY_STORE:
            return CATEGORY_STORE[c]
    return None


def _store_from_text(text: str) -> tuple[str, str] | None:
    low = f" {text.lower()} "
    for phrase, ids in TITLE_STORE_HINTS.items():
        if phrase in low:
            return ids
    return None


def _classify_penny(text: str) -> str:
    low = text.lower()
    if any(p in low for p in STRONG_PENNY):
        return "high"
    if any(p in low for p in WEAK_PENNY):
        return "med"
    return "low"


def _clean_summary(raw: str) -> str:
    """Strip HTML + collapse whitespace. Summaries often contain tag soup."""
    stripped = TAG_STRIP.sub("", html.unescape(raw or ""))
    return re.sub(r"\s+", " ", stripped).strip()


def _day_for_store(store_id: str) -> str:
    # Rough defaults: DG penny rotates Tuesday; others generic "wed" placeholder.
    # Aggregator's store-week rollup is the authoritative per-day heat anyway.
    return "tue" if store_id == "dollar-general" else "wed"


def _entry_combined_text(entry) -> str:
    parts = [getattr(entry, "title", "") or "", _clean_summary(getattr(entry, "summary", "") or "")]
    content_list = getattr(entry, "content", None) or []
    for c in content_list[:1]:
        val = getattr(c, "value", None) or ""
        parts.append(_clean_summary(val))
    return " ".join(parts)


async def parse_rss_feed(
    client: httpx.AsyncClient,
    *,
    url: str,
    source_name: str,
) -> ScrapeResult:
    raw = await safe_get(client, url, timeout=15.0)
    if not raw:
        return empty_result(source_name, "rss", note="fetch failed")

    # Guard against sites that now return HTML instead of RSS (KCL did this).
    stripped = raw.lstrip()[:200].lower()
    if not any(stripped.startswith(sig) for sig in ("<?xml", "<rss", "<feed", "<atom")):
        return empty_result(source_name, "rss", note="feed returned non-xml (retired?)")

    parsed = feedparser.parse(raw)
    today = datetime.utcnow().date().isoformat()

    highlights: list[Highlight] = []
    penny_items: list[PennyListEntry] = []

    for i, entry in enumerate(parsed.entries[:60]):
        title = getattr(entry, "title", "") or ""
        link = getattr(entry, "link", None)
        cats = _categories(entry)
        combined = _entry_combined_text(entry)

        store_from_cat = _store_from_categories(cats)
        heat = _classify_penny(combined)

        if store_from_cat:
            store = store_from_cat
        elif heat == "high":
            # Text-only detection is noisy; only trust it when the entry has
            # a strong penny signal (explicit "penny list" / "1¢" / etc.).
            store = _store_from_text(combined)
            if not store:
                continue
        else:
            continue

        store_id, store_name = store

        # Low-signal filter: if no penny/clearance language AND the category
        # set is just "Deals" + one store tag, skip — that's just a generic
        # deal post for a tracked store. Keep DG-category hits though.
        if heat == "low" and "deals" in cats and len(cats) <= 2:
            if store_id != "dollar-general":
                continue

        hid = f"rss-{source_name}-{i:03d}-{abs(hash(title)) % (10 ** 6):06d}"
        highlights.append(
            Highlight(
                id=hid,
                store_id=store_id,
                store_name=store_name,
                event="community_confirm",
                title=title[:120] or "Community confirm",
                detail=(combined[:220] or "Community-confirmed deal.").strip(),
                day=_day_for_store(store_id),
                heat=heat,
                source_url=link,
            )
        )

        if heat in ("med", "high"):
            for upc in UPC_PATTERN.findall(combined)[:25]:
                penny_items.append(
                    PennyListEntry(
                        store_id=store_id,
                        item=title[:140] or "Unknown item",
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

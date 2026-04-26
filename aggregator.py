"""Merge per-scraper ScrapeResults into one BriefingV1.

Steps (per CLAUDE_CODE.md):
  1. Call every scraper in parallel.
  2. Merge highlights, de-duping by (store_id, day, event) — take max heat.
  3. Compute per-store StoreWeek rollups.
  4. hunt_index = weighted heat total, normalized.
  5. peak_day = weekday with highest combined heat.
  6. headline — top 3 highlights.
  7. Attach sources list.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx
from dateutil.relativedelta import relativedelta

from categorize_client import categorize_items
from confidence import boost_highlights, fold_duplicate_notes
from cross_verify import verify_penny_list
from headline import compose_headline
from heat import build_store_weeks, compute_hunt_index, compute_peak_day, max_heat
from schema import BriefingV1, DealItem, Highlight, PennyListEntry, ScrapeResult
from scrapers import ALL as ALL_SCRAPERS
from scrapers._base import run_scraper


def _iso_week_id(d: datetime) -> tuple[str, str]:
    iso = d.isocalendar()
    week_id = f"{iso.year}-W{iso.week:02d}"
    # Monday of the ISO week
    monday = d - relativedelta(days=d.isoweekday() - 1)
    return week_id, monday.date().isoformat()


def _dedupe_highlights(highlights: list[Highlight]) -> list[Highlight]:
    by_key: dict[tuple[str, str, str], Highlight] = {}
    for h in highlights:
        key = (h.store_id, h.day, h.event)
        if key in by_key:
            existing = by_key[key]
            boosted = max_heat(existing.heat, h.heat)
            merged = existing.model_copy(update={"heat": boosted})
            by_key[key] = merged
        else:
            by_key[key] = h
    return list(by_key.values())


def _dedupe_penny(items: list[PennyListEntry]) -> list[PennyListEntry]:
    # Fold duplicates so their notes combine (needed for confidence scoring).
    return fold_duplicate_notes(items)


async def run_all(scrapers=ALL_SCRAPERS) -> list[ScrapeResult]:
    async with httpx.AsyncClient() as client:
        tasks = [
            run_scraper(
                mod.fetch,
                client,
                mod.SOURCE_NAME,
                getattr(mod, "SOURCE_KIND", _infer_kind(mod)),
            )
            for mod in scrapers
        ]
        return await asyncio.gather(*tasks)


def _infer_kind(mod) -> str:
    name = mod.__name__
    if name.endswith((".freebie_guy", ".kcl", ".penny_pinchin")):
        return "rss"
    if name.endswith(".kroger"):
        return "api"
    return "scraper"


def aggregate(results: list[ScrapeResult], penny_list: list[PennyListEntry] | None = None) -> BriefingV1:
    """Build BriefingV1 from scraper results.

    `penny_list` lets callers pass a post-verified list so confidence boosts
    reflect catalog hits. When omitted, we use the raw dedup'd community list.
    """
    now = datetime.now(timezone.utc)
    week_id, week_of = _iso_week_id(now)

    highlights_all: list[Highlight] = []
    penny_all: list[PennyListEntry] = []
    items_all: list[DealItem] = []
    sources = []
    for r in results:
        highlights_all.extend(r.highlights)
        penny_all.extend(r.penny_items)
        items_all.extend(getattr(r, "items", []) or [])
        sources.append(r.source)

    # Dedupe all_items by id (multiple scrapers can emit same item; keep first)
    seen_item_ids: set[str] = set()
    all_items: list[DealItem] = []
    for it in items_all:
        if it.id in seen_item_ids:
            continue
        seen_item_ids.add(it.id)
        all_items.append(it)

    # Tag each item with a Claude-classified category. Drives the in-app
    # "Browse by Category" tab. Best-effort — on failure items keep
    # `category=None` and the client falls back to its keyword heuristic.
    all_items = categorize_items(all_items)

    highlights = _dedupe_highlights(highlights_all)

    penny = penny_list if penny_list is not None else _dedupe_penny(penny_all)

    # Confidence boost: promote penny_day heat when community + catalog agree.
    highlights = boost_highlights(highlights, penny)

    # Sort: heat desc, then day order, then store
    from schema import HEAT_ORDER, WEEKDAYS

    day_rank = {d: i for i, d in enumerate(WEEKDAYS)}
    highlights.sort(key=lambda h: (-HEAT_ORDER[h.heat], day_rank[h.day], h.store_id))

    return BriefingV1(
        schema=1,
        week_id=week_id,
        week_of=week_of,
        generated_at=now.isoformat(timespec="seconds"),
        hunt_index=compute_hunt_index(highlights),
        peak_day=compute_peak_day(highlights),
        headline=compose_headline(highlights),
        highlights=highlights,
        stores=build_store_weeks(highlights),
        penny_list=penny,
        sources=sources,
        all_items=all_items,
    )


async def build_briefing(scrapers=ALL_SCRAPERS, *, cross_verify: bool = True) -> BriefingV1:
    """Full pipeline: run scrapers → dedupe → cross-verify → confidence boost."""
    results = await run_all(scrapers)

    penny_all: list[PennyListEntry] = []
    for r in results:
        penny_all.extend(r.penny_items)
    penny = _dedupe_penny(penny_all)
    if cross_verify and penny:
        penny = await verify_penny_list(penny)
        # After verification, re-fold in case catalog note merges affected keys.
        penny = fold_duplicate_notes(penny)

    return aggregate(results, penny_list=penny)

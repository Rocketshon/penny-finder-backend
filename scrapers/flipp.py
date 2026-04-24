"""Flipp public API scraper.

Flipp (backflipp.wishabi.com) aggregates weekly-ad flyers for most
major US retailers. Their JSON API is publicly reachable with no auth,
no bot gating, and returns normalized deal records with current_price,
original_price, merchant, valid_from, valid_to, etc.

Pipeline:
  1. GET /flipp/flyers?postal_code=ZIP → {flyers: [{id, merchant, merchant_id, ...}]}
  2. For each tracked merchant present in the zip's flyer list, call
     GET /flipp/items/search?postal_code=ZIP&flyer_ids={id} → items
  3. Emit one Highlight per retailer with items_expected = deal count
     and a couple representative deals in detail.

Postal code is read from POSTAL_CODE env var (default "48045" — Macomb
Twp, MI, the original hunter's turf). Callers can override.
"""
from __future__ import annotations

import asyncio
import os
import re
from typing import Any

import httpx

from heat import STORE_NAMES
from schema import DealItem, Highlight, ScrapeResult, Source
from scrapers._base import USER_AGENT, utc_now_iso

SOURCE_NAME = "flipp-api"
FLIPP_BASE = "https://backflipp.wishabi.com/flipp"
DEFAULT_POSTAL = os.environ.get("POSTAL_CODE", "48045")

# Merchants Flipp labels → our canonical store_ids. Missing mapping = skip.
MERCHANT_TO_STORE: dict[str, str] = {
    "cvs": "cvs",
    "cvs pharmacy": "cvs",
    "walgreens": "walgreens",
    "kroger": "kroger",
    "meijer": "meijer",
    "menards": "menards",
    "dollar general": "dollar-general",
    "family dollar": "family-dollar",
    "dollar tree": "dollar-tree",
    "five below": "five-below",
    "big lots": "big-lots",
    "ollie's bargain outlet": "ollies",
    "home depot": "home-depot",
    "the home depot": "home-depot",
    "lowe's": "lowes",
    "lowes": "lowes",
    "harbor freight tools": "harbor-freight",
    "target": "target",
    "walmart": "wm-ct",  # maps to local branch row; aggregator dedups
    "costco": "costco",
    "kohl's": "kohls",
    "kohls": "kohls",
    "macy's": "macys",
    "jcpenney": "jcp",
    "tj maxx": "tj-maxx",
    "marshalls": "marshalls",
    "homegoods": "homegoods",
    "ross": "ross",
    "burlington": "burlington",
    "aldi": "aldi",
    "publix": "publix",
    "trader joe's": "trader-joes",
    "whole foods": "whole-foods",
    "whole foods market": "whole-foods",
    "rite aid": "rite-aid",
    "ulta beauty": "ulta",
    "ulta": "ulta",
    "sephora": "sephora",
    "bath & body works": "bath-body-works",
    "michaels": "michaels",
    "joann": "joann",
    "hobby lobby": "hl",
    "barnes & noble": "barnes-noble",
    "best buy": "best-buy",
    "staples": "staples",
    "petsmart": "petsmart",
    "petco": "petco",
    "dick's sporting goods": "dicks",
    "office depot officemax": "office-depot",
    "office depot": "office-depot",
}

_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}


def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def _lookup_store(merchant_name: str) -> str | None:
    return MERCHANT_TO_STORE.get(_norm(merchant_name))


async def _flyers_for_zip(client: httpx.AsyncClient, postal_code: str) -> list[dict[str, Any]]:
    r = await client.get(
        f"{FLIPP_BASE}/flyers",
        params={"postal_code": postal_code, "locale": "en-us"},
        headers=_HEADERS,
        timeout=20.0,
    )
    if r.status_code != 200:
        return []
    return r.json().get("flyers", [])


async def _items_for_flyer(
    client: httpx.AsyncClient, postal_code: str, flyer_id: int
) -> list[dict[str, Any]]:
    r = await client.get(
        f"{FLIPP_BASE}/items/search",
        params={"postal_code": postal_code, "flyer_ids": str(flyer_id)},
        headers=_HEADERS,
        timeout=25.0,
    )
    if r.status_code != 200:
        return []
    return r.json().get("items", [])


def _format_price(item: dict[str, Any]) -> str:
    cp = item.get("current_price")
    sale_story = (item.get("sale_story") or "").strip()
    if sale_story:
        return sale_story[:30]
    if cp in (None, "", 0):
        return "sale"
    return f"${cp}"


def _build_highlight(
    store_id: str, store_name: str, items: list[dict[str, Any]], flyer_id: int
) -> Highlight:
    total = len(items)
    heat = "high" if total >= 60 else "med" if total >= 20 else "low"
    # representative picks: lowest-price items first (proxy for "best deals")
    def price_key(it: dict[str, Any]) -> float:
        try:
            return float(it.get("current_price") or 1e9)
        except (TypeError, ValueError):
            return 1e9

    picks = sorted(items, key=price_key)[:3]
    samples = "; ".join(f"{_format_price(p)} {(p.get('name') or '')[:40]}" for p in picks if p.get("name"))
    valid_to = (items[0].get("valid_to") or "")[:10] if items else ""
    detail_parts = [f"{total} tracked deal{'s' if total != 1 else ''} from Flipp."]
    if samples:
        detail_parts.append(f"Picks: {samples}.")
    if valid_to:
        detail_parts.append(f"Valid through {valid_to}.")

    return Highlight(
        id=f"flipp-{store_id}",
        store_id=store_id,
        store_name=store_name,
        event="markdown_cycle",
        title=f"This week's deals · {total}",
        detail=" ".join(detail_parts)[:400],
        day="sun",
        heat=heat,
        items_expected=total,
        source_url=f"https://flipp.com/flyer/{flyer_id}",
    )


_MAX_ITEMS_PER_STORE = 60


def _to_deal_item(it: dict[str, Any], store_id: str) -> DealItem | None:
    name = (it.get("name") or "").strip()
    if not name:
        return None
    cp = it.get("current_price")
    op = it.get("original_price")
    raw_id = str(it.get("id") or it.get("flyer_item_id") or "")
    slug = (raw_id or name.lower().replace(" ", "-"))[:60]
    return DealItem(
        id=f"flipp-{store_id}-{slug}",
        name=name[:140],
        store_id=store_id,
        source="flipp",
        price=(f"${cp}" if cp not in (None, "", 0) else None),
        original_price=(f"${op}" if op not in (None, "", 0) else None),
        sale_story=(it.get("sale_story") or "").strip() or None,
        image_url=it.get("clean_image_url") or it.get("clipping_image_url"),
        valid_to=(it.get("valid_to") or "")[:10] or None,
    )


async def fetch(client: httpx.AsyncClient) -> ScrapeResult:
    postal = DEFAULT_POSTAL
    flyers = await _flyers_for_zip(client, postal)
    if not flyers:
        return ScrapeResult(
            highlights=[],
            penny_items=[],
            items=[],
            source=Source(
                name=SOURCE_NAME,
                kind="api",
                last_checked=utc_now_iso(),
                ok=False,
                note=f"no flyers for postal {postal}",
            ),
        )

    chosen: dict[str, tuple[int, str]] = {}
    for f in flyers:
        merchant = f.get("merchant") or ""
        store_id = _lookup_store(merchant)
        if not store_id or store_id in chosen:
            continue
        chosen[store_id] = (int(f.get("id")), merchant)

    sem = asyncio.Semaphore(5)

    async def _one(store_id: str, flyer_id: int, merchant_name: str):
        async with sem:
            raw_items = await _items_for_flyer(client, postal, flyer_id)
        if not raw_items:
            return None, []
        store_name = STORE_NAMES.get(store_id, merchant_name)
        highlight = _build_highlight(store_id, store_name, raw_items, flyer_id)
        deal_items: list[DealItem] = []
        for it in raw_items[:_MAX_ITEMS_PER_STORE]:
            di = _to_deal_item(it, store_id)
            if di is not None:
                deal_items.append(di)
        return highlight, deal_items

    results = await asyncio.gather(
        *(_one(sid, fid, mn) for sid, (fid, mn) in chosen.items()),
        return_exceptions=True,
    )

    highlights: list[Highlight] = []
    all_items: list[DealItem] = []
    for r in results:
        if isinstance(r, tuple):
            hl, items = r
            if hl is not None:
                highlights.append(hl)
            all_items.extend(items)

    notes = f"zip={postal}; {len(highlights)} merchants; {len(all_items)} items"

    return ScrapeResult(
        highlights=highlights,
        penny_items=[],
        items=all_items,
        source=Source(
            name=SOURCE_NAME,
            kind="api",
            last_checked=utc_now_iso(),
            ok=bool(highlights),
            note=notes,
        ),
    )

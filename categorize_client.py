"""Tag DealItems with a category by calling the Supabase categorize edge
function (Claude Haiku-backed). Batches in groups of 200 and dispatches
batches concurrently (3 in flight) so a 1500-item briefing categorizes
in ~5s instead of 30s+ of sequential blocking.

Best-effort: on Claude / network failure the items keep `category=None`
and the in-app fallback (categorize.ts keyword heuristic) takes over.
"""
from __future__ import annotations

import asyncio
import os
from typing import Iterable

import httpx

from schema import DealItem

ENDPOINT = "https://ojfhdbeatbfuiofykopl.supabase.co/functions/v1/categorize"
ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9qZmhkYmVhdGJmdWlvZnlrb3BsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcxMzAxNjEsImV4cCI6MjA5MjcwNjE2MX0."
    "huLOjpu5VdX-4gVBdcK73IGKOb_n-Eoslkfn-DwI5As"
)
BATCH_SIZE = 200
TIMEOUT = 60.0
MAX_CONCURRENT_BATCHES = 3

VALID_CATEGORIES = {
    "tools", "beauty", "food", "pet", "home", "tech",
    "apparel", "toys", "seasonal", "books", "garden", "health",
}


def _chunks(seq: list, size: int) -> Iterable[list]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


async def _categorize_batch(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    batch: list[DealItem],
) -> dict[str, str]:
    """Send one batch to the edge function. Return id → category for
    successful matches. Returns {} on any error (best-effort)."""
    async with sem:
        names = [it.name[:200] for it in batch]
        try:
            r = await client.post(
                ENDPOINT,
                json={"items": names},
                headers={
                    "apikey": ANON_KEY,
                    "Authorization": f"Bearer {ANON_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError):
            return {}

        cats = data.get("categories", []) or []
        out: dict[str, str] = {}
        # Pair items with categories. zip() truncates to the shorter list,
        # so an under-returned response still tags whatever Claude got to.
        for it, cat in zip(batch, cats):
            if isinstance(cat, str) and cat in VALID_CATEGORIES:
                out[it.id] = cat
        return out


async def categorize_items_async(items: list[DealItem]) -> list[DealItem]:
    """Async version — preferred. Caller must be inside an event loop."""
    if not items:
        return items
    if os.environ.get("CATEGORIZE_DISABLED") == "1":
        return items

    to_tag = [it for it in items if not it.category]
    if not to_tag:
        return items

    sem = asyncio.Semaphore(MAX_CONCURRENT_BATCHES)
    async with httpx.AsyncClient() as client:
        batch_results = await asyncio.gather(
            *(
                _categorize_batch(client, sem, batch)
                for batch in _chunks(to_tag, BATCH_SIZE)
            )
        )

    tagged: dict[str, str] = {}
    for r in batch_results:
        tagged.update(r)

    if not tagged:
        return items

    out: list[DealItem] = []
    for it in items:
        if it.id in tagged:
            out.append(it.model_copy(update={"category": tagged[it.id]}))
        else:
            out.append(it)
    return out


def categorize_items(items: list[DealItem]) -> list[DealItem]:
    """Sync wrapper — runs the async pipeline. Useful for callers outside
    an event loop. Aggregator code on an active loop should call
    categorize_items_async() directly to avoid `asyncio.run()` nesting."""
    if not items:
        return items
    try:
        return asyncio.run(categorize_items_async(items))
    except RuntimeError:
        # Already inside a running loop. Fall back to sequential sync calls.
        return _categorize_items_sync_fallback(items)


def _categorize_items_sync_fallback(items: list[DealItem]) -> list[DealItem]:
    """Sequential sync fallback used only when categorize_items() is
    accidentally called from an async context (which is itself a bug —
    the caller should be using categorize_items_async)."""
    if os.environ.get("CATEGORIZE_DISABLED") == "1":
        return items
    to_tag = [it for it in items if not it.category]
    if not to_tag:
        return items
    headers = {
        "apikey": ANON_KEY,
        "Authorization": f"Bearer {ANON_KEY}",
        "Content-Type": "application/json",
    }
    tagged: dict[str, str] = {}
    with httpx.Client(timeout=TIMEOUT) as client:
        for batch in _chunks(to_tag, BATCH_SIZE):
            names = [it.name[:200] for it in batch]
            try:
                r = client.post(ENDPOINT, json={"items": names}, headers=headers)
                r.raise_for_status()
                data = r.json()
            except (httpx.HTTPError, ValueError):
                continue
            cats = data.get("categories", []) or []
            for it, cat in zip(batch, cats):
                if isinstance(cat, str) and cat in VALID_CATEGORIES:
                    tagged[it.id] = cat
    if not tagged:
        return items
    out: list[DealItem] = []
    for it in items:
        if it.id in tagged:
            out.append(it.model_copy(update={"category": tagged[it.id]}))
        else:
            out.append(it)
    return out

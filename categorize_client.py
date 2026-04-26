"""Tag DealItems with a category by calling the Supabase categorize edge
function (Claude Haiku-backed). Batches in groups of 200 to keep each call
small + the JSON parse stable.

Used at the end of `aggregate()` so every emitted briefing has categories
on every item. Free-tier Haiku cost: ~$0.0004 per 50-item batch, so a
typical 1500-item briefing costs ~$0.012 to fully categorize.
"""
from __future__ import annotations

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

VALID_CATEGORIES = {
    "tools", "beauty", "food", "pet", "home", "tech",
    "apparel", "toys", "seasonal", "books", "garden", "health",
}


def _chunks(seq: list, size: int) -> Iterable[list]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def categorize_items(items: list[DealItem]) -> list[DealItem]:
    """Return a new list with `.category` populated. Items already tagged
    are left alone. On failure (network / Claude error) returns items
    unchanged — never raises so the briefing pipeline degrades gracefully."""
    if not items:
        return items

    # Skip categorization if explicitly disabled (CI fast path or local dev)
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
                # Skip this batch — leave items uncategorized, app falls back
                # to the on-device categorize.ts heuristic.
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

"""Confidence scoring for penny-list entries.

After community dedupe + cross-verify, we know per UPC:
  - How many community sources mentioned it (`note` concatenated).
  - Whether any store catalog echoed the UPC (`source == 'scrape'`).

We roll these into a per-UPC confidence:
  0  = 0 community hits, no catalog confirm         (shouldn't happen post-dedup)
  1  = 1 community hit, no catalog                  → low
  2  = 2+ community hits, no catalog                → med
  3  = 1 community hit + catalog verified           → high
  4  = 2+ community + catalog verified              → peak

Downstream:
  * `penny_day` highlight heat upgrades to max(existing, conf_heat)
    proportional to the highest-confidence UPC for that store.
  * Lets the app sort/filter penny-list entries by certainty if needed
    (via the `note` string — we don't add schema fields).
"""
from __future__ import annotations

from collections import defaultdict

from schema import HEAT_ORDER, Heat, Highlight, PennyListEntry

CONF_HEAT: dict[int, Heat] = {0: "off", 1: "low", 2: "med", 3: "high", 4: "peak"}


def score_entry(e: PennyListEntry) -> int:
    # Note string stores sources concatenated with " + ". Count those tokens.
    parts = [p.strip() for p in (e.note or "").split("+") if p.strip()]
    community_hits = sum(1 for p in parts if not p.startswith("catalog:"))
    catalog_hit = any(p.startswith("catalog:") for p in parts)
    score = 0
    if community_hits >= 1:
        score += 1
    if community_hits >= 2:
        score += 1
    if catalog_hit:
        score += 2
    return min(4, score)


def max_heat(a: Heat, b: Heat) -> Heat:
    return a if HEAT_ORDER[a] >= HEAT_ORDER[b] else b


def boost_highlights(
    highlights: list[Highlight], penny_list: list[PennyListEntry]
) -> list[Highlight]:
    """Upgrade each store's `penny_day` highlight heat based on the best
    per-store confidence score in the penny list.
    """
    best_by_store: dict[str, int] = defaultdict(int)
    for e in penny_list:
        best_by_store[e.store_id] = max(best_by_store[e.store_id], score_entry(e))

    if not best_by_store:
        return highlights

    out: list[Highlight] = []
    for h in highlights:
        if h.event != "penny_day":
            out.append(h)
            continue
        score = best_by_store.get(h.store_id, 0)
        if score == 0:
            out.append(h)
            continue
        new_heat = max_heat(h.heat, CONF_HEAT[score])
        items = sum(1 for e in penny_list if e.store_id == h.store_id)
        detail = h.detail
        if items:
            detail = f"{h.detail} · {items} community-confirmed UPC{'s' if items != 1 else ''}."
        out.append(h.model_copy(update={"heat": new_heat, "items_expected": items, "detail": detail}))
    return out


def fold_duplicate_notes(entries: list[PennyListEntry]) -> list[PennyListEntry]:
    """Merge duplicate (store_id, upc) entries by concatenating their notes
    so later scoring sees all community sources that confirmed.

    The aggregator's own dedupe runs first and just keeps one entry; this
    variant preserves the union of notes for confidence counting.
    """
    merged: dict[tuple[str, str], PennyListEntry] = {}
    for e in entries:
        key = (e.store_id, e.upc)
        if key not in merged:
            merged[key] = e
            continue
        existing = merged[key]
        notes = [n for n in (existing.note or "").split("+") if n.strip()]
        new_note = (e.note or "").strip()
        if new_note and new_note not in notes:
            notes.append(new_note)
        # Prefer `source='scrape'` when any source is authoritative.
        new_source = "scrape" if "scrape" in (existing.source, e.source) else "community"
        merged[key] = existing.model_copy(
            update={"note": " + ".join(n.strip() for n in notes), "source": new_source}
        )
    return list(merged.values())

"""Heat scoring + hunt_index computation.

Weights per CLAUDE_CODE.md / SCRAPERS.md:
  peak = 25, high = 15, med = 8, low = 3, off = 0
  hunt_index = min(100, round(total / 1.4))
"""
from __future__ import annotations

from collections import defaultdict

from schema import HEAT_ORDER, HEAT_WEIGHTS, WEEKDAYS, Heat, Highlight, StoreWeek, Weekday

STORE_NAMES: dict[str, str] = {
    "dollar-general": "Dollar General",
    "target": "Target",
    "cvs": "CVS",
    "walgreens": "Walgreens",
    "meijer": "Meijer",
    "kroger": "Kroger",
}


def max_heat(a: Heat, b: Heat) -> Heat:
    return a if HEAT_ORDER[a] >= HEAT_ORDER[b] else b


def compute_hunt_index(highlights: list[Highlight]) -> int:
    total = sum(HEAT_WEIGHTS[h.heat] for h in highlights)
    return min(100, round(total / 1.4))


def compute_peak_day(highlights: list[Highlight]) -> Weekday:
    by_day: dict[Weekday, int] = defaultdict(int)
    for h in highlights:
        by_day[h.day] += HEAT_WEIGHTS[h.heat]
    if not by_day:
        return "tue"
    return max(WEEKDAYS, key=lambda d: by_day.get(d, 0))


def build_store_weeks(highlights: list[Highlight]) -> list[StoreWeek]:
    """Roll per-store day-by-day heat from the highlight list.

    Every tracked store appears, even if quiet.
    """
    by_store: dict[str, dict[Weekday, Heat]] = {
        sid: {d: "off" for d in WEEKDAYS} for sid in STORE_NAMES
    }

    for h in highlights:
        if h.store_id not in by_store:
            by_store[h.store_id] = {d: "off" for d in WEEKDAYS}
        by_store[h.store_id][h.day] = max_heat(by_store[h.store_id][h.day], h.heat)

    out: list[StoreWeek] = []
    for store_id, days in by_store.items():
        overall: Heat = "off"
        for d in WEEKDAYS:
            overall = max_heat(overall, days[d])
        out.append(
            StoreWeek(
                store_id=store_id,
                store_name=STORE_NAMES.get(store_id, store_id),
                heat=overall,
                days=days,
            )
        )
    return out

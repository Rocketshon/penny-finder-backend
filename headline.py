"""Compose the one-paragraph weekly headline from top highlights.

Reuters-tight. Sorted by heat, caps at 3 clauses, hard <200 char ceiling.
"""
from __future__ import annotations

from schema import HEAT_ORDER, Highlight

DAY_LONG: dict[str, str] = {
    "mon": "Monday",
    "tue": "Tuesday",
    "wed": "Wednesday",
    "thu": "Thursday",
    "fri": "Friday",
    "sat": "Saturday",
    "sun": "Sunday",
}


def _clause(h: Highlight) -> str:
    day = DAY_LONG.get(h.day, h.day)
    return f"{h.store_name} {h.title.lower()} {day}."


def compose_headline(highlights: list[Highlight]) -> str:
    if not highlights:
        return "Quiet week. Nothing notable expected across tracked stores."

    ranked = sorted(highlights, key=lambda h: HEAT_ORDER[h.heat], reverse=True)
    top = ranked[:3]
    sentence = " ".join(_clause(h).capitalize() for h in top)
    if len(sentence) > 200:
        sentence = sentence[:197].rstrip(",; ") + "..."
    return sentence

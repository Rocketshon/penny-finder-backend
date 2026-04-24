"""Pydantic schema mirroring PennyFinder/src/briefing.ts (BriefingV1).

Source of truth is the TS file — keep these in lockstep. Don't add fields
without bumping `schema` and coordinating with the app.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

Weekday = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
Heat = Literal["off", "low", "med", "high", "peak"]
EventKind = Literal[
    "penny_day",
    "markdown_cycle",
    "reset",
    "weekly_ad_start",
    "clearance_purge",
    "coupon_stack",
    "community_confirm",
    "other",
]
SourceKind = Literal["scraper", "rss", "api", "community"]
PennySource = Literal["scrape", "community"]

WEEKDAYS: tuple[Weekday, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

HEAT_WEIGHTS: dict[Heat, int] = {"off": 0, "low": 3, "med": 8, "high": 15, "peak": 25}
HEAT_ORDER: dict[Heat, int] = {"off": 0, "low": 1, "med": 2, "high": 3, "peak": 4}

STORE_IDS = ("dollar-general", "target", "cvs", "walgreens", "meijer", "kroger")


class Highlight(BaseModel):
    id: str
    store_id: str
    store_name: str
    event: EventKind
    title: str
    detail: str
    day: Weekday
    time_hint: Optional[str] = None
    heat: Heat
    items_expected: Optional[int] = None
    categories: Optional[list[str]] = None
    source_url: Optional[str] = None


class StoreWeek(BaseModel):
    store_id: str
    store_name: str
    heat: Heat
    days: dict[Weekday, Heat]
    note: Optional[str] = None


class PennyListEntry(BaseModel):
    store_id: str
    item: str
    upc: str
    confirmed_on: str
    source: PennySource
    note: Optional[str] = None


class Source(BaseModel):
    name: str
    kind: SourceKind
    last_checked: str
    ok: bool
    note: Optional[str] = None


class BriefingV1(BaseModel):
    schema: Literal[1] = 1
    week_id: str
    week_of: str
    generated_at: str
    hunt_index: int = Field(ge=0, le=100)
    peak_day: Weekday
    headline: str
    highlights: list[Highlight]
    stores: list[StoreWeek]
    penny_list: list[PennyListEntry]
    sources: list[Source]


@dataclass
class ScrapeResult:
    """Every scraper returns one of these. Never raises."""

    highlights: list[Highlight] = field(default_factory=list)
    penny_items: list[PennyListEntry] = field(default_factory=list)
    source: Source = field(
        default_factory=lambda: Source(
            name="unknown",
            kind="scraper",
            last_checked=datetime.utcnow().isoformat() + "Z",
            ok=False,
        )
    )

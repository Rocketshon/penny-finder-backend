"""Schema validates the MOCK_BRIEFING shape from briefing.ts."""
from __future__ import annotations

from schema import (
    BriefingV1,
    Highlight,
    PennyListEntry,
    Source,
    StoreWeek,
    WEEKDAYS,
)


def test_briefing_validates_minimum_shape():
    b = BriefingV1(
        schema=1,
        week_id="2026-W17",
        week_of="2026-04-27",
        generated_at="2026-04-26T23:15:00+00:00",
        hunt_index=87,
        peak_day="tue",
        headline="Peak week. DG penny day Tuesday.",
        highlights=[
            Highlight(
                id="dg-penny",
                store_id="dollar-general",
                store_name="Dollar General",
                event="penny_day",
                title="Penny Day",
                detail="Tuesday rotation.",
                day="tue",
                heat="peak",
            )
        ],
        stores=[
            StoreWeek(
                store_id="dollar-general",
                store_name="Dollar General",
                heat="peak",
                days={d: "off" for d in WEEKDAYS} | {"tue": "peak"},
            )
        ],
        penny_list=[
            PennyListEntry(
                store_id="dollar-general",
                item="Example",
                upc="012345678901",
                confirmed_on="2026-04-26",
                source="community",
            )
        ],
        sources=[
            Source(name="dg", kind="scraper", last_checked="2026-04-26T23:00:00+00:00", ok=True)
        ],
    )
    assert b.schema == 1
    assert b.hunt_index == 87
    assert b.stores[0].days["tue"] == "peak"


def test_hunt_index_out_of_range_fails():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        BriefingV1(
            schema=1,
            week_id="x",
            week_of="x",
            generated_at="x",
            hunt_index=101,
            peak_day="tue",
            headline="",
            highlights=[],
            stores=[],
            penny_list=[],
            sources=[],
        )

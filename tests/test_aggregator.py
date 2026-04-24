"""End-to-end aggregator test with mocked scraper outputs."""
from __future__ import annotations

from datetime import datetime, timezone

from aggregator import aggregate
from schema import Highlight, PennyListEntry, ScrapeResult, Source


def _src(name: str, ok: bool = True) -> Source:
    return Source(
        name=name, kind="scraper", last_checked=datetime.now(timezone.utc).isoformat(), ok=ok
    )


def test_dedupe_takes_max_heat():
    results = [
        ScrapeResult(
            highlights=[
                Highlight(
                    id="a",
                    store_id="dollar-general",
                    store_name="Dollar General",
                    event="penny_day",
                    title="Penny Day",
                    detail="x",
                    day="tue",
                    heat="low",
                )
            ],
            penny_items=[],
            source=_src("scrape"),
        ),
        ScrapeResult(
            highlights=[
                Highlight(
                    id="b",
                    store_id="dollar-general",
                    store_name="Dollar General",
                    event="penny_day",
                    title="Penny Day",
                    detail="x",
                    day="tue",
                    heat="peak",
                )
            ],
            penny_items=[],
            source=_src("community"),
        ),
    ]
    b = aggregate(results)
    penny = [h for h in b.highlights if h.event == "penny_day"]
    assert len(penny) == 1
    assert penny[0].heat == "peak"


def test_penny_list_dedup_by_store_and_upc():
    pe = PennyListEntry(
        store_id="dollar-general",
        item="Widget",
        upc="012345678901",
        confirmed_on="2026-04-26",
        source="community",
    )
    results = [
        ScrapeResult(highlights=[], penny_items=[pe], source=_src("a")),
        ScrapeResult(highlights=[], penny_items=[pe], source=_src("b")),
    ]
    b = aggregate(results)
    assert len(b.penny_list) == 1


def test_sources_preserved_one_per_scraper():
    results = [
        ScrapeResult(highlights=[], penny_items=[], source=_src("a")),
        ScrapeResult(highlights=[], penny_items=[], source=_src("b", ok=False)),
    ]
    b = aggregate(results)
    assert [s.name for s in b.sources] == ["a", "b"]
    assert b.sources[1].ok is False


def test_all_stores_roll_up_even_with_no_highlights():
    results: list[ScrapeResult] = [
        ScrapeResult(highlights=[], penny_items=[], source=_src("empty"))
    ]
    b = aggregate(results)
    store_ids = {s.store_id for s in b.stores}
    for required in ("dollar-general", "target", "cvs", "walgreens", "meijer", "kroger"):
        assert required in store_ids
    for sw in b.stores:
        assert sw.heat == "off"


def test_hunt_index_in_range():
    results = [
        ScrapeResult(
            highlights=[
                Highlight(
                    id="x",
                    store_id="target",
                    store_name="Target",
                    event="markdown_cycle",
                    title="Seasonal → 70%",
                    detail="x",
                    day="sun",
                    heat="peak",
                )
            ],
            penny_items=[],
            source=_src("t"),
        )
    ]
    b = aggregate(results)
    assert 0 <= b.hunt_index <= 100
    assert b.peak_day == "sun"

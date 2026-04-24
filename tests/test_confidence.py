"""Confidence scoring + highlight boost."""
from __future__ import annotations

from confidence import boost_highlights, fold_duplicate_notes, score_entry
from schema import Highlight, PennyListEntry


def _pe(store_id: str, upc: str, source: str = "community", note: str | None = None) -> PennyListEntry:
    return PennyListEntry(
        store_id=store_id,
        item="item",
        upc=upc,
        confirmed_on="2026-04-28",
        source=source,
        note=note,
    )


def test_score_single_community_hit():
    e = _pe("dollar-general", "012345678901", note="tfg")
    assert score_entry(e) == 1


def test_score_two_communities_no_catalog():
    e = _pe("dollar-general", "012345678901", note="tfg + pennypinchinmom.com")
    assert score_entry(e) == 2


def test_score_community_plus_catalog():
    e = _pe(
        "dollar-general", "012345678901", source="scrape", note="tfg + catalog:dollar-general"
    )
    assert score_entry(e) == 3


def test_score_peak_multi_community_plus_catalog():
    e = _pe(
        "dollar-general",
        "012345678901",
        source="scrape",
        note="tfg + pennypinchinmom.com + catalog:dollar-general",
    )
    assert score_entry(e) == 4


def test_fold_merges_duplicates():
    entries = [
        _pe("dollar-general", "012345678901", note="tfg"),
        _pe("dollar-general", "012345678901", note="pennypinchinmom.com"),
    ]
    folded = fold_duplicate_notes(entries)
    assert len(folded) == 1
    assert "tfg" in folded[0].note and "pennypinchinmom.com" in folded[0].note


def test_boost_promotes_penny_day_heat_to_peak():
    hl = Highlight(
        id="dg-penny",
        store_id="dollar-general",
        store_name="Dollar General",
        event="penny_day",
        title="Penny Day",
        detail="Tuesday rotation.",
        day="tue",
        heat="low",
    )
    penny = [
        _pe(
            "dollar-general",
            "012345678901",
            source="scrape",
            note="tfg + pennypinchinmom.com + catalog:dollar-general",
        )
    ]
    out = boost_highlights([hl], penny)
    assert out[0].heat == "peak"
    assert out[0].items_expected == 1


def test_boost_ignores_non_penny_events():
    hl = Highlight(
        id="target-seasonal",
        store_id="target",
        store_name="Target",
        event="markdown_cycle",
        title="Seasonal",
        detail="x",
        day="sun",
        heat="med",
    )
    out = boost_highlights([hl], [_pe("target", "u", note="tfg + catalog:target", source="scrape")])
    assert out[0].heat == "med"  # unchanged — only penny_day is boosted

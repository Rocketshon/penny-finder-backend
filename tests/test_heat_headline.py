"""Heat scoring and headline composition."""
from __future__ import annotations

from headline import compose_headline
from heat import build_store_weeks, compute_hunt_index, compute_peak_day
from schema import Highlight


def _h(store_id: str, day: str, heat: str, event: str = "penny_day", title: str = "T") -> Highlight:
    return Highlight(
        id=f"{store_id}-{day}-{heat}",
        store_id=store_id,
        store_name=store_id,
        event=event,
        title=title,
        detail="detail",
        day=day,
        heat=heat,
    )


def test_hunt_index_peak_day_tuesday():
    hs = [
        _h("dollar-general", "tue", "peak"),
        _h("target", "sun", "high"),
        _h("cvs", "sun", "high"),
    ]
    idx = compute_hunt_index(hs)
    assert 0 <= idx <= 100
    # 25 + 15 + 15 = 55 → round(55/1.4) = 39
    assert idx == 39
    assert compute_peak_day(hs) == "sun"  # 15+15=30 > 25


def test_hunt_index_cap_at_100():
    hs = [_h(f"s{i}", "tue", "peak") for i in range(20)]
    assert compute_hunt_index(hs) == 100


def test_store_weeks_always_have_all_weekdays():
    hs = [_h("dollar-general", "tue", "peak")]
    sws = build_store_weeks(hs)
    dg = next(s for s in sws if s.store_id == "dollar-general")
    assert set(dg.days) == {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
    assert dg.days["tue"] == "peak"
    assert dg.days["mon"] == "off"
    assert dg.heat == "peak"
    # Every tracked store surfaces, even with no highlights.
    assert len(sws) >= 6


def test_headline_under_200_chars_and_non_empty():
    hs = [
        _h("dollar-general", "tue", "peak", "penny_day", "Penny Day"),
        _h("target", "sun", "high", "markdown_cycle", "Seasonal → 70%"),
        _h("cvs", "sun", "high", "reset", "Q2 Reset"),
    ]
    text = compose_headline(hs)
    assert text
    assert len(text) <= 200


def test_headline_quiet_fallback():
    assert compose_headline([]) == (
        "Quiet week. Nothing notable expected across tracked stores."
    )

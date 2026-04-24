"""Fixture-based parse tests — hit the scraper logic without network.

We monkeypatch `scrapers._base.safe_get` to return saved HTML snapshots.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

import scrapers._base as base_mod
import scrapers._rss_common as rss_common
from scrapers import cvs, dollar_general, meijer, target, walgreens

FIXTURES = Path(__file__).parent / "fixtures"


def _use_fixture(monkeypatch, html_name: str) -> None:
    html = (FIXTURES / html_name).read_text(encoding="utf-8")

    async def fake_get(client, url, timeout=20.0):  # noqa: ARG001
        return html

    monkeypatch.setattr(base_mod, "safe_get", fake_get)
    monkeypatch.setattr(rss_common, "safe_get", fake_get)
    monkeypatch.setattr(dollar_general, "safe_get", fake_get)
    monkeypatch.setattr(target, "safe_get", fake_get)
    monkeypatch.setattr(cvs, "safe_get", fake_get)
    monkeypatch.setattr(walgreens, "safe_get", fake_get)
    monkeypatch.setattr(meijer, "safe_get", fake_get)


def _run(fetch):
    return asyncio.run(fetch(client=None))


def test_dollar_general_emits_penny_day(monkeypatch):
    _use_fixture(monkeypatch, "dollar_general_sample.html")
    res = _run(dollar_general.fetch)
    assert res.source.ok
    events = {h.event for h in res.highlights}
    assert "penny_day" in events
    penny = next(h for h in res.highlights if h.event == "penny_day")
    assert penny.day == "tue"
    assert penny.heat == "peak"


def test_target_detects_70_percent(monkeypatch):
    _use_fixture(monkeypatch, "target_sample.html")
    res = _run(target.fetch)
    assert res.source.ok
    pct = [h for h in res.highlights if h.event == "markdown_cycle"]
    assert pct, "expected a markdown_cycle highlight from %-off parse"
    assert any(h.heat == "peak" for h in pct)


def test_meijer_detects_two_day_sale(monkeypatch):
    _use_fixture(monkeypatch, "meijer_sample.html")
    res = _run(meijer.fetch)
    assert res.source.ok
    titles = [h.title for h in res.highlights]
    assert any("Two-Day" in t for t in titles)


def test_scraper_returns_ok_false_on_fetch_failure(monkeypatch):
    async def none_get(client, url, timeout=20.0):  # noqa: ARG001
        return None

    monkeypatch.setattr(dollar_general, "safe_get", none_get)
    res = _run(dollar_general.fetch)
    assert res.source.ok is False
    assert res.highlights == []

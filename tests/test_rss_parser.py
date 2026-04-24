"""Category-driven RSS parser tests with a real live-captured fixture."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

import scrapers._rss_common as rss

FIXTURE = Path(__file__).parent / "fixtures" / "rss" / "thefreebieguy.xml"


def _patch_fetch(monkeypatch, raw: str | None) -> None:
    async def fake_get(client, url, timeout=15.0):  # noqa: ARG001
        return raw

    monkeypatch.setattr(rss, "safe_get", fake_get)


def test_parser_uses_categories_for_store_id(monkeypatch):
    _patch_fetch(monkeypatch, FIXTURE.read_text(encoding="utf-8"))
    res = asyncio.run(
        rss.parse_rss_feed(client=None, url="https://example/feed", source_name="tfg-test")
    )
    assert res.source.ok
    # TFG fixture has a Dollar General-tagged entry; we should emit at least one
    # highlight for dollar-general.
    dg = [h for h in res.highlights if h.store_id == "dollar-general"]
    assert dg, "expected at least one DG highlight from category match"


def test_parser_returns_ok_false_when_feed_is_html(monkeypatch):
    _patch_fetch(monkeypatch, "<!doctype html><html>Oops, site migrated</html>")
    res = asyncio.run(
        rss.parse_rss_feed(client=None, url="https://example/feed", source_name="dead-feed")
    )
    assert res.source.ok is False
    assert "non-xml" in (res.source.note or "")


def test_parser_skips_untracked_stores(monkeypatch):
    # A feed with only Amazon/Walmart categories should yield no highlights for
    # our tracked store universe.
    atom = """<?xml version='1.0'?><rss version='2.0'><channel>
      <title>t</title><link>x</link><description>d</description>
      <item><title>Amazon deal of the day</title><link>x</link>
        <category>Amazon</category><category>Deals</category></item>
      <item><title>Walmart rollback</title><link>y</link>
        <category>Walmart</category></item>
    </channel></rss>"""
    _patch_fetch(monkeypatch, atom)
    res = asyncio.run(
        rss.parse_rss_feed(client=None, url="x", source_name="amazon-feed")
    )
    assert res.source.ok
    assert res.highlights == []


def test_parser_emits_med_heat_for_penny_language(monkeypatch):
    xml = """<?xml version='1.0'?><rss version='2.0'><channel>
      <title>t</title><link>x</link><description>d</description>
      <item><title>DG Penny List — 4/28 Edition</title>
        <link>z</link><description>UPC 012345678901 confirmed penny item</description>
        <category>Dollar General</category></item>
    </channel></rss>"""
    _patch_fetch(monkeypatch, xml)
    res = asyncio.run(
        rss.parse_rss_feed(client=None, url="x", source_name="tfg")
    )
    assert any(h.heat in ("med", "high") for h in res.highlights)
    assert any(p.upc == "012345678901" for p in res.penny_items)

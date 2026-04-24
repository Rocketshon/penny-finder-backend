"""Cross-verify integration — mocks httpx, no real network."""
from __future__ import annotations

import asyncio

import cross_verify as cv
from schema import PennyListEntry


class FakeResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


class FakeClient:
    def __init__(self, map_: dict[str, FakeResponse]) -> None:
        self.map = map_

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return None

    async def get(self, url, **kwargs):
        for key, resp in self.map.items():
            if key in url:
                return resp
        return FakeResponse(404)


def _entry(store_id: str, upc: str, note: str = "tfg") -> PennyListEntry:
    return PennyListEntry(
        store_id=store_id,
        item="item",
        upc=upc,
        confirmed_on="2026-04-28",
        source="community",
        note=note,
    )


def test_verify_upgrades_when_catalog_echoes_upc(monkeypatch):
    upc = "012345678901"
    fake = {
        upc: FakeResponse(200, f"<html>found product {upc} details</html>"),
    }
    monkeypatch.setattr(cv, "httpx", _HTTPXShim(fake))
    out = asyncio.run(cv.verify_penny_list([_entry("dollar-general", upc)]))
    assert out[0].source == "scrape"
    assert "catalog:dollar-general" in (out[0].note or "")


def test_verify_leaves_entry_alone_when_no_results(monkeypatch):
    upc = "999999999999"
    fake = {
        upc: FakeResponse(200, "<html>no results found for your query</html>"),
    }
    monkeypatch.setattr(cv, "httpx", _HTTPXShim(fake))
    out = asyncio.run(cv.verify_penny_list([_entry("dollar-general", upc)]))
    assert out[0].source == "community"


def test_verify_leaves_entry_alone_on_non_200(monkeypatch):
    fake = {"888": FakeResponse(503)}
    monkeypatch.setattr(cv, "httpx", _HTTPXShim(fake))
    out = asyncio.run(cv.verify_penny_list([_entry("target", "888888888888")]))
    assert out[0].source == "community"


def test_verify_skips_unknown_store(monkeypatch):
    # store_id with no search URL template — should return entry unchanged, no HTTP.
    called = {"n": 0}

    class NoCallShim:
        class AsyncClient:
            def __init__(self):
                called["n"] += 1

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return None

            async def get(self, *a, **k):
                called["n"] += 1
                return FakeResponse(200, "")

        class HTTPError(Exception):
            ...

    monkeypatch.setattr(cv, "httpx", NoCallShim)
    out = asyncio.run(cv.verify_penny_list([_entry("fake-store", "1")]))
    assert out[0].source == "community"


class _HTTPXShim:
    """Shim replacing `httpx` module access inside cross_verify."""

    class HTTPError(Exception):
        ...

    def __init__(self, map_: dict[str, FakeResponse]) -> None:
        self._map = map_

    def AsyncClient(self, *a, **k):  # noqa: N802
        return FakeClient(self._map)

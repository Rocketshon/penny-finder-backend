"""Shared helpers for individual scrapers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Awaitable, Callable

import httpx

from schema import ScrapeResult, Source, SourceKind

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 PennyFinder/0.1"
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def safe_get(
    client: httpx.AsyncClient, url: str, *, timeout: float = 20.0
) -> str | None:
    """GET a URL, returning text on success, None on any failure."""
    try:
        resp = await client.get(
            url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
            follow_redirects=True,
        )
        if resp.status_code == 200:
            return resp.text
    except httpx.HTTPError:
        pass
    return None


def empty_result(name: str, kind: SourceKind, note: str | None = None) -> ScrapeResult:
    return ScrapeResult(
        highlights=[],
        penny_items=[],
        source=Source(
            name=name,
            kind=kind,
            last_checked=utc_now_iso(),
            ok=False,
            note=note,
        ),
    )


async def run_scraper(
    fetch_fn: Callable[[httpx.AsyncClient], Awaitable[ScrapeResult]],
    client: httpx.AsyncClient,
    source_name: str,
    kind: SourceKind,
) -> ScrapeResult:
    """Wrap a fetch coroutine: never raises, always returns a ScrapeResult."""
    try:
        return await fetch_fn(client)
    except Exception as e:
        return empty_result(source_name, kind, note=f"error: {type(e).__name__}")

"""Per-source scrapers.

Contract: every module exposes `async def fetch(client: httpx.AsyncClient) -> ScrapeResult`.
Never raises — catches, sets source.ok=False, returns empty lists.
"""
from __future__ import annotations

from . import (
    cvs,
    dollar_general,
    freebie_guy,
    kcl,
    kroger,
    meijer,
    penny_pinchin,
    target,
    walgreens,
)

ALL = [
    dollar_general,
    target,
    cvs,
    walgreens,
    meijer,
    kroger,
    freebie_guy,
    kcl,
    penny_pinchin,
]

COMMUNITY = [freebie_guy, kcl, penny_pinchin]

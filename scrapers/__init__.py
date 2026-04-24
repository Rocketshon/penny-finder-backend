"""Per-source scrapers.

Contract: every module exposes `async def fetch(client: httpx.AsyncClient) -> ScrapeResult`.
Never raises — catches, sets source.ok=False, returns empty lists.
"""
from __future__ import annotations

from . import (
    barnes_noble,
    cvs,
    dollar_general,
    freebie_guy,
    home_depot,
    kcl,
    kroger,
    lowes,
    meijer,
    menards,
    penny_pages,
    penny_pinchin,
    playwright_tfg,
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
    home_depot,
    lowes,
    menards,
    barnes_noble,
    penny_pages,
    playwright_tfg,
    freebie_guy,
    kcl,
    penny_pinchin,
]

COMMUNITY = [freebie_guy, kcl, penny_pinchin]

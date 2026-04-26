"""Per-source scrapers.

Contract: every module exposes `async def fetch(client: httpx.AsyncClient) -> ScrapeResult`.
Never raises — catches, sets source.ok=False, returns empty lists.
"""
from __future__ import annotations

from . import (
    barnes_noble,
    camelcamel,
    cvs,
    dollar_general,
    flipp,
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
    reddit_penny,
    slickdeals,
    target,
    walgreens,
    walmart_html,
    weekly_circulars,
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
    flipp,
    penny_pages,
    playwright_tfg,
    walmart_html,
    weekly_circulars,
    slickdeals,
    camelcamel,
    freebie_guy,
    kcl,
    penny_pinchin,
    reddit_penny,
]

COMMUNITY = [freebie_guy, kcl, penny_pinchin, reddit_penny]

"""Cross-verify community penny UPCs against corporate product catalogs.

Each PennyListEntry coming out of RSS has source='community'. We ping
the store's product-detail (or search) endpoint per UPC. If the catalog
answers 200 with something that looks like a product page, we upgrade
the entry:

  source: community → scrape      # catalog confirmed
  note:   "<rss source> + catalog <store>"

We never block the pipeline. Any failure falls through silently — the
original community entry remains.

Endpoints per store:
  dollar-general : GET https://www.dollargeneral.com/search?query={upc}
  target         : GET https://redsky.target.com/redsky_aggregations/v1/web/plp_search_v2
                    ?channel=WEB&count=24&default_purchasability_filter=true
                    &keyword={upc}&page=0&platform=desktop
                    &pricing_store_id=3991&visitor_id=0
                    (public key= bounces around — omit; the /c/-n- JSON sometimes answers)
  cvs            : GET https://www.cvs.com/shop/search-content?q={upc}
  walgreens      : GET https://www.walgreens.com/search/results.jsp?Ntt={upc}
  meijer         : GET https://www.meijer.com/shopping/search.html?text={upc}
  kroger         : GET https://www.kroger.com/search?query={upc}

These are the public search URLs; a 200 with the UPC echoed in the body
is treated as a "probably exists in catalog" signal. We don't need the
product name — just existence. Real product-detail APIs (for structured
price) need auth/keys — out of scope for now.
"""
from __future__ import annotations

import asyncio
import re

import httpx

from schema import PennyListEntry
from scrapers._base import USER_AGENT

SEARCH_URLS: dict[str, str] = {
    "dollar-general": "https://www.dollargeneral.com/search?query={upc}",
    "target": "https://www.target.com/s?searchTerm={upc}",
    "cvs": "https://www.cvs.com/shop/search-content?q={upc}",
    "walgreens": "https://www.walgreens.com/search/results.jsp?Ntt={upc}",
    "meijer": "https://www.meijer.com/shopping/search.html?text={upc}",
    "kroger": "https://www.kroger.com/search?query={upc}",
}

CONCURRENCY = 6
PER_REQUEST_TIMEOUT = 12.0


async def _verify_one(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    entry: PennyListEntry,
) -> PennyListEntry:
    url_template = SEARCH_URLS.get(entry.store_id)
    if not url_template:
        return entry

    url = url_template.format(upc=entry.upc)
    async with sem:
        try:
            r = await client.get(
                url,
                timeout=PER_REQUEST_TIMEOUT,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
                follow_redirects=True,
            )
        except httpx.HTTPError:
            return entry

    if r.status_code != 200:
        return entry

    body = r.text
    # "UPC echoed in response" is a weak but useful existence signal.
    # Bare UPC in HTML (not URL) usually means the product page / a search hit
    # includes that UPC in product metadata or the "did you mean" title.
    echoes = len(re.findall(rf"\b{re.escape(entry.upc)}\b", body))

    # Some stores return a generic "no results" page at 200 — filter those out.
    lower = body.lower()
    no_results = any(
        phrase in lower
        for phrase in (
            "no results",
            "no matches",
            "we couldn't find",
            "we couldn&#39;t find",
            "couldn't find",
        )
    )

    if echoes >= 1 and not no_results:
        note = entry.note or ""
        verified_note = f"{note} + catalog:{entry.store_id}" if note else f"catalog:{entry.store_id}"
        return entry.model_copy(update={"source": "scrape", "note": verified_note})

    return entry


async def verify_penny_list(entries: list[PennyListEntry]) -> list[PennyListEntry]:
    """Enrich each entry by cross-checking the store's product catalog.

    Never raises; entries that can't be verified are returned unchanged.
    Runs bounded-concurrency HTTP checks to respect per-site rate limits.
    """
    if not entries:
        return entries

    sem = asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient() as client:
        return await asyncio.gather(*(_verify_one(client, sem, e) for e in entries))

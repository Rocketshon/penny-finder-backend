"""Reddit community-confirmation scraper.

Pulls new posts from a handful of penny-hunting subreddits, extracts any
UPCs (12 or 13 digit numbers) found in the title or self-text, and emits
PennyListEntry items tagged as `community` source.

This is the "third leg" of the cross-verification: backend scrapes
freebie_guy/kcl/penny_pinchin (RSS) + penny_pages (HTML), and now Reddit.
When the same UPC appears in two sources, confidence boosts in
boost_highlights() promote that store's penny_day heat to "peak".

Auth: Reddit OAuth client-credentials grant using REDDIT_CLIENT_ID +
REDDIT_CLIENT_SECRET env vars. Token cached in-process for ~1hr.
"""
from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from schema import (
    Highlight,
    PennyListEntry,
    ScrapeResult,
    Source,
)
from scrapers._base import utc_now_iso

SOURCE_NAME = "reddit"
SOURCE_KIND = "community"

OAUTH_URL = "https://www.reddit.com/api/v1/access_token"
API_BASE = "https://oauth.reddit.com"
USER_AGENT = "PennyHunter/0.1 (community-confirm; +https://pennyhunter.store)"

# Subs to scan + which retailer they map to. Order matters — first match wins
# when a UPC appears across subs. CRITICAL: store_id values must match the
# rest of the backend's canonical IDs (`dollar-general`, NOT the app's
# short `dg`). The aggregator's cross-verify + confidence-boost only joins
# entries when store_ids match across sources.
SUBREDDITS: list[tuple[str, str]] = [
    ("dollargeneral", "dollar-general"),
    ("PennyShopper", "dollar-general"),
    ("Flipping", "dollar-general"),  # general flipping; default to DG when in doubt
]

# 12-13 digit UPC. Reject if surrounded by digits (likely phone/orderID),
# allow word boundaries. We additionally validate the UPC-12 mod-10 check
# digit in _looks_like_upc() to filter out phone numbers and order IDs
# that happen to be 12-13 digits long.
UPC_RE = re.compile(r"(?<!\d)(\d{12,13})(?!\d)")


def _looks_like_upc(digits: str) -> bool:
    """Validate UPC-12 (or EAN-13) mod-10 check digit. ~90% of false
    positives (phone numbers, order IDs) fail this check at zero cost."""
    if len(digits) not in (12, 13):
        return False
    body, check = digits[:-1], int(digits[-1])
    # UPC-12: odd-position digits ×3, even ×1, sum, mod 10
    # EAN-13: odd ×1, even ×3 (positions counted from RIGHT excl. check)
    # Both can be evaluated with: from RIGHT excl check, alternating ×3/×1
    rev = body[::-1]
    total = 0
    for i, ch in enumerate(rev):
        d = int(ch)
        total += d * (3 if i % 2 == 0 else 1)
    expected = (10 - (total % 10)) % 10
    return expected == check

# Cap how much we pull per sub per run — keeps the call cheap and avoids
# rate-limit headaches.
POSTS_PER_SUB = 25
TIMEOUT = 20.0

# Module-level token cache to avoid re-auth across multiple aggregator runs
# in the same Python process. Reddit tokens last ~1 hour.
_token_cache: dict[str, Any] = {"token": None, "exp": 0.0}


async def _get_token(client: httpx.AsyncClient) -> str | None:
    if _token_cache["token"] and _token_cache["exp"] > time.time() + 60:
        return _token_cache["token"]

    cid = os.environ.get("REDDIT_CLIENT_ID", "")
    csec = os.environ.get("REDDIT_CLIENT_SECRET", "")
    if not cid or not csec:
        return None

    try:
        resp = await client.post(
            OAUTH_URL,
            data={"grant_type": "client_credentials"},
            auth=(cid, csec),
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return None
        body = resp.json()
        token = body.get("access_token")
        if not token:
            return None
        _token_cache["token"] = token
        _token_cache["exp"] = time.time() + (body.get("expires_in") or 3600)
        return token
    except httpx.HTTPError:
        return None


async def _fetch_sub(
    client: httpx.AsyncClient, token: str, sub: str
) -> list[dict[str, Any]]:
    url = f"{API_BASE}/r/{sub}/new"
    try:
        resp = await client.get(
            url,
            params={"limit": POSTS_PER_SUB, "raw_json": 1},
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": USER_AGENT,
            },
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return []
        children = resp.json().get("data", {}).get("children", [])
        return [c.get("data", {}) for c in children if isinstance(c, dict)]
    except httpx.HTTPError:
        return []


def _extract_upcs(text: str) -> list[str]:
    if not text:
        return []
    return [d for d in UPC_RE.findall(text) if _looks_like_upc(d)]


def _short_item_name(title: str) -> str:
    # Reddit post titles are noisy. Trim to first 80 chars; strip
    # boilerplate emojis/wrappers.
    t = (title or "").strip()
    t = re.sub(r"^(\[\w+\]|\(\w+\))\s*", "", t)
    t = re.sub(r"\s+", " ", t)
    return t[:80] or "Reddit post"


async def fetch(client: httpx.AsyncClient) -> ScrapeResult:
    token = await _get_token(client)
    if not token:
        return ScrapeResult(
            highlights=[],
            penny_items=[],
            source=Source(
                name=SOURCE_NAME,
                kind=SOURCE_KIND,
                last_checked=utc_now_iso(),
                ok=False,
                note="reddit auth failed (missing creds or 401)",
            ),
        )

    today = utc_now_iso()[:10]
    # Use today's weekday for the synthetic confirm highlight (Reddit posts
    # arrive any day; pinning to "tue" would mis-place the highlight in
    # build_store_weeks calendar rollups).
    today_weekday = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")[
        datetime.now(timezone.utc).weekday()
    ]
    seen_upcs: set[str] = set()
    entries: list[PennyListEntry] = []

    for sub, store_id in SUBREDDITS:
        posts = await _fetch_sub(client, token, sub)
        for post in posts:
            haystack = (post.get("title") or "") + "\n" + (post.get("selftext") or "")
            upcs = _extract_upcs(haystack)
            if not upcs:
                continue
            for upc in upcs:
                if upc in seen_upcs:
                    continue
                seen_upcs.add(upc)
                entries.append(
                    PennyListEntry(
                        store_id=store_id,
                        item=_short_item_name(post.get("title") or ""),
                        upc=upc,
                        confirmed_on=today,
                        source="community",
                        note=f"r/{sub}: {(post.get('permalink') or '').lstrip('/')}",
                    )
                )

    highlights: list[Highlight] = []
    if entries:
        # One aggregate "community confirm" highlight per scanned store_id
        per_store: dict[str, int] = {}
        for e in entries:
            per_store[e.store_id] = per_store.get(e.store_id, 0) + 1
        for store_id, count in per_store.items():
            highlights.append(
                Highlight(
                    id=f"reddit-confirm-{store_id}-{today}",
                    store_id=store_id,
                    store_name=store_id.replace("-", " ").title(),
                    event="community_confirm",
                    title=f"Reddit confirms {count} UPC{'s' if count != 1 else ''}",
                    detail=f"{count} UPC{'s' if count != 1 else ''} mentioned in r/dollargeneral / r/PennyShopper / r/Flipping over the last batch of new posts.",
                    day=today_weekday,
                    heat="med",
                    items_expected=count,
                    source_url="https://www.reddit.com/r/PennyShopper/new/",
                )
            )

    return ScrapeResult(
        highlights=highlights,
        penny_items=entries,
        source=Source(
            name=SOURCE_NAME,
            kind=SOURCE_KIND,
            last_checked=utc_now_iso(),
            ok=bool(entries),
            note=None if entries else "no UPCs in latest posts",
        ),
    )

"""Parse retailer weekly-ad PDFs into Highlights.

Static PDFs are a far better data source than JS-rendered weekly-ad pages:
- They contain real prices, real items, real date ranges.
- Format is stable week-to-week within a retailer.
- No anti-bot defense, no SPA hydration to wait for.

Flow:
  1. Caller feeds us a local PDF path (or bytes).
  2. We extract text with pdfplumber.
  3. Regex-parse price lines into `deal` records.
  4. Aggregate into ~1 Highlight per retailer per run, with
     `items_expected` set to the deal count and `detail` summarizing.

Auto-download: each retailer publishes the weekly circular at a
predictable URL (usually a CDN-hosted PDF). Callers update the PDF
cache once per week; this module just parses.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

import pdfplumber

from schema import Highlight

PRICE_LINE = re.compile(r"^\s*(?P<label>[A-Z/ ]{0,12}\$?)(?P<amount>\d+(?:\.\d{1,2})?)\s*$")
COMBO_LINE = re.compile(r"^\s*(?P<combo>\d+\s*(?:/|for)\s*\$?\d+(?:\.\d{1,2})?)\s*$", re.I)
BOGO_LINE = re.compile(r"^\s*(?:Buy\s+\d+\s+get|BOGO)\b", re.I)
ITEM_SEED = re.compile(r"^\s*(?:WITH\s+CARD|FREE|Digital)\b", re.I)

DATE_RANGE = re.compile(
    r"(?P<start>[A-Z][a-z]+\s+\d{1,2})(?:\s*[–-]\s*(?P<end>\d{1,2}(?:,\s*\d{4})?))?"
)

NOISE = (
    "click on these links",
    "see more savings",
    "terms apply",
    "select items",
    "excludes",
    "valid",
    "view ad",
    "privacy policy",
)


class Deal(NamedTuple):
    item: str
    price: str
    page: int
    has_card: bool


def _clean_item_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" .,-'\":/")
    return text[:120]


def _extract_deals_from_text(text: str, page_no: int) -> list[Deal]:
    """Heuristic: find price-only lines and grab the following 1-3 lines as the item."""
    lines = [ln.strip() for ln in text.splitlines()]
    out: list[Deal] = []

    for i, line in enumerate(lines):
        price: str | None = None
        is_combo = False

        m = PRICE_LINE.match(line)
        if m:
            amount = m.group("amount")
            if "." not in amount and len(amount) > 2:
                # standalone "299" etc. isn't a price
                continue
            price = f"${amount}"
        elif COMBO_LINE.match(line):
            price = line.strip()
            is_combo = True

        if not price:
            continue

        # look ahead up to 3 lines for the item description
        window: list[str] = []
        for j in range(i + 1, min(i + 4, len(lines))):
            ln = lines[j].strip()
            if not ln:
                continue
            if PRICE_LINE.match(ln) or COMBO_LINE.match(ln):
                break
            window.append(ln)
            if len(" ".join(window)) > 90:
                break

        if not window:
            continue

        combined = " ".join(window)
        has_card = "WITH CARD" in combined.upper()
        bogo = bool(BOGO_LINE.match(window[0])) if window else False

        # strip leading "WITH CARD" / "FREE" / "Digital" noise from the item itself
        cleaned = re.sub(
            r"^\s*(?:WITH\s+CARD|FREE|Digital\s+mfr\s+coupon|\$\d+(?:\.\d+)?\s*)+\s*",
            "",
            combined,
            flags=re.I,
        )
        cleaned = _clean_item_text(cleaned)

        if len(cleaned) < 8:
            continue
        if any(n in cleaned.lower() for n in NOISE):
            continue

        out.append(Deal(item=cleaned, price=price, page=page_no, has_card=has_card or is_combo or bogo))
    return out


def parse_pdf(path: str | Path) -> tuple[list[Deal], str | None]:
    """Extract (deals, date_range_text) from a weekly-ad PDF."""
    deals: list[Deal] = []
    date_text: str | None = None
    seen_keys: set[str] = set()

    with pdfplumber.open(str(path)) as doc:
        for page_no, page in enumerate(doc.pages, start=1):
            text = page.extract_text() or ""
            if not text:
                continue

            if date_text is None and page_no <= 2:
                m = DATE_RANGE.search(text[:800])
                if m:
                    date_text = m.group(0)

            for d in _extract_deals_from_text(text, page_no):
                key = f"{d.item.lower()}|{d.price}"
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                deals.append(d)

    return deals, date_text


def build_highlight(
    *,
    store_id: str,
    store_name: str,
    deals: list[Deal],
    date_text: str | None,
    source_url: str,
) -> Highlight:
    total = len(deals)
    detail_parts = [f"{total} tracked deal{'s' if total != 1 else ''} in the weekly circular."]
    if date_text:
        detail_parts.append(f"Valid {date_text}.")
    # Surface 2-3 representative items in the detail string for context.
    card_deals = [d for d in deals if d.has_card][:3]
    if card_deals:
        samples = "; ".join(f"{d.price} {d.item[:40]}" for d in card_deals)
        detail_parts.append(f"WITH-CARD picks: {samples}.")

    heat = "high" if total >= 60 else "med" if total >= 20 else "low"

    return Highlight(
        id=f"pdf-{store_id}-circular",
        store_id=store_id,
        store_name=store_name,
        event="markdown_cycle",
        title=f"From the weekly ad · {total} deals",
        detail=" ".join(detail_parts)[:400],
        day="sun",
        heat=heat,
        items_expected=total,
        source_url=source_url,
    )

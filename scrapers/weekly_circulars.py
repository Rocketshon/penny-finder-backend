"""Parse locally-cached weekly-ad PDFs into Highlights.

Fully-automated fetch is blocked on each retailer's store-selection UX
(CVS/Walgreens/Kroger/Meijer all hide the Wishabi PDF link behind a
zip-code picker their SPA renders post-hydration). Rather than chase
per-retailer automation, we support a simple drop-folder workflow:

  circulars/
    cvs.pdf
    walgreens.pdf
    kroger.pdf
    meijer.pdf

Any PDF named `{store_id}.pdf` in `penny-finder-backend/circulars/` gets
parsed each run. Refresh them weekly from the retailer site ("Print/PDF"
button on the weekly-ad page) or — later — via the Flipp API.

If the folder is empty, this scraper is a no-op (`ok=False` with note).
"""
from __future__ import annotations

from pathlib import Path

import httpx

from heat import STORE_NAMES
from schema import DealItem, ScrapeResult, Source
from scrapers._base import utc_now_iso
from scrapers.pdf_weekly_ad import build_highlight, parse_pdf

SOURCE_NAME = "weekly-ad-pdfs"
CIRCULARS_DIR = Path(__file__).parent.parent / "circulars"


async def fetch(client: httpx.AsyncClient) -> ScrapeResult:  # noqa: ARG001
    """Parse every PDF in the circulars/ directory. Keyed by filename stem."""
    if not CIRCULARS_DIR.exists():
        return ScrapeResult(
            highlights=[],
            penny_items=[],
            source=Source(
                name=SOURCE_NAME,
                kind="scraper",
                last_checked=utc_now_iso(),
                ok=False,
                note="circulars/ directory not present",
            ),
        )

    highlights = []
    all_items: list[DealItem] = []
    notes: list[str] = []
    any_ok = False

    for pdf in sorted(CIRCULARS_DIR.glob("*.pdf")):
        store_id = pdf.stem.lower()
        store_name = STORE_NAMES.get(store_id, store_id.replace("-", " ").title())
        try:
            deals, date_text = parse_pdf(pdf)
        except Exception as e:
            notes.append(f"{store_id}:parse-error({type(e).__name__})")
            continue

        if not deals:
            notes.append(f"{store_id}:0-deals")
            continue

        highlights.append(
            build_highlight(
                store_id=store_id,
                store_name=store_name,
                deals=deals,
                date_text=date_text,
                source_url=f"file://{pdf.name}",
            )
        )
        # Promote each parsed Deal into a DealItem for cross-store search.
        for i, d in enumerate(deals[:80]):
            slug = d.item.lower().replace(" ", "-")[:40]
            all_items.append(
                DealItem(
                    id=f"pdf-{store_id}-{i}-{slug}",
                    name=d.item[:140],
                    store_id=store_id,
                    source="pdf",
                    price=d.price,
                    sale_story=("WITH CARD" if d.has_card else None),
                    valid_to=(date_text[-10:] if date_text and len(date_text) >= 10 else None),
                )
            )
        notes.append(f"{store_id}:{len(deals)}")
        any_ok = True

    if not notes:
        notes.append("no PDFs in circulars/")

    return ScrapeResult(
        highlights=highlights,
        penny_items=[],
        items=all_items,
        source=Source(
            name=SOURCE_NAME,
            kind="scraper",
            last_checked=utc_now_iso(),
            ok=any_ok,
            note="; ".join(notes)[:300],
        ),
    )

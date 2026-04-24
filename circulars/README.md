# Weekly-Ad Circulars

Drop retailer weekly-ad PDFs here, named `{store_id}.pdf`, and the
`weekly_circulars` scraper will parse them into Briefing highlights on
the next pipeline run.

## Naming

Use the canonical `store_id` from `schema.STORE_IDS`:

| File            | Store         |
|-----------------|---------------|
| `cvs.pdf`       | CVS           |
| `walgreens.pdf` | Walgreens     |
| `kroger.pdf`    | Kroger        |
| `meijer.pdf`    | Meijer        |
| `menards.pdf`   | Menards       |
| `target.pdf`    | Target        |

## How to get a PDF

Each retailer's weekly-ad page has a **"Print / PDF"** button once
you've selected a store (via zip code). Example for CVS:

1. Go to <https://www.cvs.com/weeklyad>
2. Enter a zip code if prompted
3. Click **Print / PDF** in the viewer toolbar — downloads a PDF from
   `f.wishabi.net/flyers/{id}/{hash}.pdf`

Drop the file here as `cvs.pdf` (overwrite the old one each week).

## Gitignore

PDFs are listed in `.gitignore` (they're 20–50 MB each). This folder's
contents stay local. For a server-side pipeline, mount these PDFs into
`circulars/` via whatever fetch you prefer (manual, scheduled
download, Flipp API, etc.).

## Why this and not a fully-automated scraper?

CVS / Walgreens / Kroger / Meijer weekly-ad pages hide the PDF link
behind a store-selection UX their SPA renders after hydration. A
fetch-and-scrape loop hits an empty shell. The PDFs themselves are
public and direct-downloadable — just the *link discovery* is gated.
Dropping the PDFs here sidesteps that entirely.

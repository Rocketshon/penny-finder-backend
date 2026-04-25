# Penny Hunter — Backend

> **Penny Hunter** is a free deal-aggregator app for shoppers and clearance-hunters.
> This repo is the **scraping + aggregation backend** that powers it.
>
> 🌐 [pennyhunter.store](https://pennyhunter.store)  ·  📱 iOS app (private beta)

---

## What it does

Pulls weekly-ad data, community-curated penny lists, and online deal feeds
from **30+ sources**, normalizes them into a single JSON briefing, and
publishes it to GitHub Pages every day. The mobile app fetches that JSON
to power its **Briefing**, **Find Deals**, and **Penny List** screens.

```
                ┌─ Flipp API (~25 retailers, weekly ads)
                ├─ KCL DG penny-list page (community UPCs)
                ├─ TFG via Playwright + stealth
                ├─ CVS weekly-ad PDF (drop-folder)
                ├─ Walmart Flash Deals (saved HTML)
                ├─ Slickdeals frontpage RSS
   scrapers ────┼─ CamelCamelCamel Amazon price drops RSS
                ├─ Dollar General / Target / CVS / Walgreens / Meijer / Kroger
                ├─ Home Depot / Lowe's / Menards / Barnes & Noble
                ├─ TheFreebieGuy + PennyPinchinMom RSS
                └─ ...
                          │
                          ▼
                   aggregator.py
                   ├─ dedupe + heat scoring
                   ├─ confidence scoring (community + cross-verify)
                   ├─ store-week rollups
                   └─ emit BriefingV1 JSON (~1700 items, ~40 highlights)
                          │
                          ▼
              GitHub Pages: pages branch
              briefings/latest.json + 2026-W17.json archive
                          │
                          ▼
                   Penny Hunter app
                   (Flipp queries also run live in-app per zip)
```

## Live data

[`https://rocketshon.github.io/penny-finder-backend/briefings/latest.json`](https://rocketshon.github.io/penny-finder-backend/briefings/latest.json)

Schema is documented inline in [`schema.py`](schema.py) (mirrors the
TypeScript source-of-truth in the app's `briefing.ts`).

## Local run

```bash
pip install -e .
python -m main                 # full pipeline, writes out/briefings/latest.json
python -m main --community     # only community RSS scrapers (faster)
pytest                         # 31 unit tests
```

## Stack

- **Python 3.12** with `httpx` (HTTP), `selectolax` (HTML), `feedparser`
  (RSS), `pdfplumber` (weekly-ad PDFs), `playwright` (stealth headless
  Chromium for cloudflare-gated pages), `pydantic` (schema validation).
- **GitHub Actions** runs the full pipeline daily at 6 AM ET.
- **Windows Task Scheduler** on a residential IP (Tailscale-connected
  Dell) runs the pipeline weekly to layer in PerimeterX-gated sources
  (Walmart Flash Deals) that fail in cloud CI.

## Layout

```
penny-finder-backend/
├── schema.py               # BriefingV1, DealItem, Highlight, etc.
├── aggregator.py           # merges + dedupes + scores + writes JSON
├── heat.py                 # heat scoring + hunt_index calc
├── headline.py             # top-of-briefing summary composer
├── confidence.py           # community + catalog confidence boost
├── cross_verify.py         # per-UPC corporate catalog check
├── main.py                 # entrypoint
├── scrapers/               # one module per source (~17 scrapers)
├── tests/                  # pytest suite + saved fixtures
├── landing/                # pennyhunter.store one-pager (Vercel-deployed)
└── scripts/
    ├── fetch_walmart.py    # headed Playwright Walmart Flash Deals fetch
    ├── fetch_walmart.bat   # Windows Task Scheduler wrapper
    └── run_local_pipeline.bat  # full pipeline + push-to-Pages
```

## App side

- App repo: private (Expo / React Native)
- Live via EAS Update; app fetches `latest.json` from this repo's pages
  branch, plus calls Flipp's public API directly with the user's zip
  for real-time location-aware results.
- Money: Skimlinks (302076X1790065) wraps non-Amazon outbound links;
  Amazon Associates tag `pennyhunter20-20` wraps Amazon links directly
  for the higher commission rate.

## License

MIT. See [LICENSE](LICENSE) (TODO).

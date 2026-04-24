# penny-finder-backend

Weekly briefing scraper for the Penny Finder app. Produces one JSON file
per ISO week matching the `BriefingV1` schema in
`PennyFinder/src/briefing.ts`.

## Local run

```bash
pip install -e .
python -m main            # full pipeline
python -m main --community   # RSS community scrapers only
# writes out/briefings/{week_id}.json and out/briefings/latest.json
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## Deploy (GitHub Pages)

1. Create a new public repo `penny-finder-backend` on GitHub.
2. Push this folder to `main`:
   ```bash
   git init && git add . && git commit -m "initial"
   git branch -M main
   git remote add origin git@github.com:<user>/penny-finder-backend.git
   git push -u origin main
   ```
3. In repo **Settings → Pages**: pick branch `pages` (created automatically
   by the first workflow run). Source: root.
4. Trigger `.github/workflows/daily.yml` manually once (Actions tab → Run
   workflow) — first push creates the `pages` branch.
5. The JSON will be served at
   `https://<user>.github.io/penny-finder-backend/briefings/latest.json`.

## Wire to the app

Open `PennyFinder/src/briefing.ts`, set:

```ts
export const BRIEFING_URL: string | null =
  'https://<user>.github.io/penny-finder-backend/briefings/latest.json';
```

Reload Expo Go. The BriefingScreen now fetches live on mount and on
pull-to-refresh, falling back to MOCK_BRIEFING when the fetch fails.

## Schedule

- `daily.yml` runs the full pipeline at 10:00 UTC (6 AM ET).
- `hourly.yml` runs community RSS scrapers only, at :15 each hour.

Both publish `out/` to the `pages` branch.

"""Fetch walmart.com flash-deals HTML + save to circulars/walmart.html.

Walmart is hard-gated by PerimeterX. Plain HTTP returns "Robot or human?".
This script uses a persistent Chromium profile (cookies + local storage
survive between runs), so after you manually pass the PerimeterX
challenge ONCE (running headed), subsequent runs ride on the trusted
session cookie and return the real __NEXT_DATA__ payload.

Usage
-----

First run (headed, so you can solve any captcha):

    python scripts/fetch_walmart.py --headed

Subsequent runs (headless is fine once cookies are established):

    python scripts/fetch_walmart.py

Automate weekly via Windows Task Scheduler — see scripts/fetch_walmart.bat.

The saved HTML is picked up automatically by scrapers/walmart_html.py on
the next backend pipeline run.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

URL = "https://www.walmart.com/shop/deals/flash-picks"
OUT_DIR = Path(__file__).parent.parent / "circulars"
PROFILE_DIR = Path(__file__).parent.parent / ".chromium-profile-walmart"


async def fetch(headed: bool) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from playwright_stealth import Stealth  # type: ignore
        stealth_apply = Stealth()
    except ImportError:
        stealth_apply = None

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=not headed,
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            locale="en-US",
            args=["--disable-blink-features=AutomationControlled"],
        )
        if stealth_apply is not None:
            await stealth_apply.apply_stealth_async(ctx)

        page = await ctx.new_page()
        try:
            await page.goto(URL, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(3500)
            html = await page.content()
        finally:
            await ctx.close()

    if "__NEXT_DATA__" not in html:
        print("WARN: page returned a bot gate or empty shell — __NEXT_DATA__ not present.")
        print("      Re-run with --headed, solve the PerimeterX challenge, then retry.")
        (OUT_DIR / "walmart.last-attempt.html").write_text(html, encoding="utf-8")
        return 1

    out_path = OUT_DIR / "walmart.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"wrote {out_path} ({len(html):,}B)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--headed", action="store_true", help="run Chromium visibly (needed for first run)")
    args = ap.parse_args()
    return asyncio.run(fetch(args.headed))


if __name__ == "__main__":
    sys.exit(main())

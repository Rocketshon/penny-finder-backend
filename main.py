"""Entrypoint: run all scrapers, aggregate, write briefing JSON.

Writes:
  out/briefings/{week_id}.json    archive for this ISO week
  out/briefings/latest.json       atomically replaced after archive write

Usage:
  python -m main                  full pipeline (daily)
  python -m main --community      only RSS community scrapers (hourly)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

from aggregator import build_briefing
from scrapers import ALL as ALL_SCRAPERS
from scrapers import COMMUNITY

OUT_DIR = Path(__file__).parent / "out" / "briefings"


def _write_atomic(path: Path, data: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    os.replace(tmp, path)


async def _main(community_only: bool) -> int:
    scrapers = COMMUNITY if community_only else ALL_SCRAPERS
    # Hourly community refresh skips the slow cross-verify pass.
    briefing = await build_briefing(scrapers, cross_verify=not community_only)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    archive = OUT_DIR / f"{briefing.week_id}.json"
    latest = OUT_DIR / "latest.json"

    payload = briefing.model_dump_json(indent=2, exclude_none=True)
    _write_atomic(archive, payload)
    # Then replace latest — copy from archive so there's no window of mismatch.
    shutil.copyfile(archive, latest)

    print(
        f"wrote {archive} ({len(briefing.highlights)} highlights, "
        f"hunt_index={briefing.hunt_index}, peak_day={briefing.peak_day})",
        file=sys.stderr,
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--community", action="store_true", help="run only RSS community scrapers")
    args = p.parse_args()
    return asyncio.run(_main(args.community))


if __name__ == "__main__":
    raise SystemExit(main())

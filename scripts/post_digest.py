"""Daily metrics digest poster.

Pulls yesterday's totals for the most useful Penny Hunter events from
PostHog, formats them as a Markdown comment, and appends it to a sticky
GitHub Issue so the user gets a phone notification without needing
PostHog Cloud paid features.

Tracked events match those in PennyFinder/src/analytics.ts (Track.*).
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from typing import Any

import requests

POSTHOG_HOST = "https://us.posthog.com"

EVENTS = [
    "app_open",
    "scan_started",
    "scan_hit_penny",
    "scan_no_match",
    "find_added",
    "watch_added",
    "hunt_started",
    "outbound_click",
    "receipt_added",
    "onboarding_complete",
]


def query_event_count(token: str, project_id: str, event: str, since_iso: str, until_iso: str) -> int:
    """Use PostHog's HogQL endpoint to count events in a window. One round-trip per event."""
    url = f"{POSTHOG_HOST}/api/projects/{project_id}/query/"
    body = {
        "query": {
            "kind": "HogQLQuery",
            "query": (
                "SELECT count() FROM events WHERE event = {event} "
                "AND timestamp >= {since} AND timestamp < {until}"
            ),
            "values": {"event": event, "since": since_iso, "until": until_iso},
        }
    }
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    if not r.ok:
        return -1
    data = r.json()
    try:
        return int(data["results"][0][0])
    except (KeyError, IndexError, TypeError, ValueError):
        return -1


def query_dau(token: str, project_id: str, since_iso: str, until_iso: str) -> int:
    """Distinct distinct_id firing app_open in the window."""
    url = f"{POSTHOG_HOST}/api/projects/{project_id}/query/"
    body = {
        "query": {
            "kind": "HogQLQuery",
            "query": (
                "SELECT count(DISTINCT distinct_id) FROM events "
                "WHERE event = 'app_open' AND timestamp >= {since} AND timestamp < {until}"
            ),
            "values": {"since": since_iso, "until": until_iso},
        }
    }
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    if not r.ok:
        return -1
    try:
        return int(r.json()["results"][0][0])
    except Exception:
        return -1


def fmt(n: int) -> str:
    return "—" if n < 0 else f"{n:,}"


def build_comment(yesterday: dt.date, totals: dict[str, int], dau: int) -> str:
    lines: list[str] = [
        f"## Daily Pulse — {yesterday.isoformat()}",
        "",
        f"**Daily Active Users:** {fmt(dau)}",
        "",
        "### Event Counts",
        "",
        "| Event | Count |",
        "|---|---:|",
    ]
    for ev in EVENTS:
        lines.append(f"| `{ev}` | {fmt(totals.get(ev, -1))} |")

    scans = totals.get("scan_started", 0)
    hits = totals.get("scan_hit_penny", 0)
    if scans > 0:
        rate = (hits / scans) * 100
        lines.append("")
        lines.append(f"**Scan hit rate:** {rate:.1f}% ({hits}/{scans})")

    finds = totals.get("find_added", 0)
    if hits > 0:
        conv = (finds / hits) * 100
        lines.append(f"**Penny → Find conversion:** {conv:.1f}% ({finds}/{hits})")

    outbound = totals.get("outbound_click", 0)
    if outbound > 0:
        # Rough revenue estimate: $0.05 avg commission per outbound click
        # (Skimlinks ~3% of $1-5 avg purchase; Amazon ~5% of $20). Adjust
        # once you have real conversion data from each network.
        est_rev = outbound * 0.05
        lines.append(f"**Outbound clicks:** {outbound} (~${est_rev:.2f} est. revenue)")

    lines.append("")
    lines.append("[Open dashboard](https://us.posthog.com/project/398170/dashboard/1511934)")
    return "\n".join(lines)


def post_comment(repo: str, issue_number: str, body: str, gh_token: str) -> None:
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
    r = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {gh_token}",
            "Accept": "application/vnd.github+json",
        },
        json={"body": body},
        timeout=30,
    )
    if not r.ok:
        print(f"GitHub comment failed: {r.status_code} {r.text[:200]}", file=sys.stderr)
        sys.exit(1)
    print("Posted comment:", r.json().get("html_url"))


def main() -> None:
    token = os.environ.get("POSTHOG_PERSONAL_KEY", "")
    project_id = os.environ.get("POSTHOG_PROJECT_ID", "")
    repo = os.environ.get("DIGEST_REPO", "")
    issue_num = os.environ.get("DIGEST_ISSUE_NUMBER", "")
    gh_token = os.environ.get("GITHUB_TOKEN", "")

    if not all([token, project_id, repo, issue_num, gh_token]):
        print("Missing required env vars — set POSTHOG_PERSONAL_KEY, POSTHOG_PROJECT_ID,")
        print("DIGEST_REPO, DIGEST_ISSUE_NUMBER, GITHUB_TOKEN.", file=sys.stderr)
        sys.exit(1)

    today = dt.datetime.now(dt.timezone.utc).date()
    yesterday = today - dt.timedelta(days=1)
    since_iso = f"{yesterday.isoformat()}T00:00:00Z"
    until_iso = f"{today.isoformat()}T00:00:00Z"

    totals: dict[str, int] = {}
    for ev in EVENTS:
        totals[ev] = query_event_count(token, project_id, ev, since_iso, until_iso)

    dau = query_dau(token, project_id, since_iso, until_iso)

    body = build_comment(yesterday, totals, dau)
    print(body)
    post_comment(repo, issue_num, body, gh_token)


if __name__ == "__main__":
    main()

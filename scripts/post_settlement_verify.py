"""Verify England Works Watch after a real paid x402 settlement.

This script does not sign or send payments. It only checks:
1. production analytics reports at least one paid_executed event; and
2. PayAI Bazaar contains England Works Watch after facilitator indexing.
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request

ORIGIN = os.getenv(
    "EWW_PUBLIC_ORIGIN",
    "https://england-works-watch-production.up.railway.app",
).rstrip("/")
PAYAI = os.getenv("EWW_PAYAI_BASE", "https://facilitator.payai.network").rstrip("/")
NEEDLES = [
    "england works watch",
    "england-works-watch-production.up.railway.app",
    "mcp://tool/assess_change_impact",
    "mcp://tool/batch_assess_changes",
]


def get_json(url: str) -> dict:
    last: Exception | None = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "england-works-watch-post-settlement/1.0"},
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode())
        except Exception as exc:  # pragma: no cover - network path
            last = exc
            if attempt < 2:
                time.sleep(attempt + 1)
    assert last is not None
    raise last


def analytics_paid_executed() -> int:
    data = get_json(f"{ORIGIN}/analytics/summary")
    funnel = data.get("paid_funnel") or {}
    count = int(funnel.get("paid_executed") or 0)
    print("ANALYTICS=" + json.dumps(data, sort_keys=True))
    print(f"PAID_EXECUTED={count}")
    return count


def bazaar_matches() -> tuple[int, int, list[dict]]:
    page_size = 200
    scanned = 0
    total: int | None = None
    matches: list[dict] = []

    for page in range(250):
        offset = page * page_size
        query = urllib.parse.urlencode({"limit": page_size, "offset": offset})
        data = get_json(f"{PAYAI}/discovery/resources?{query}")
        items = data.get("items") or []
        pagination = data.get("pagination") or {}
        if total is None and pagination.get("total") is not None:
            total = int(pagination["total"])
        scanned += len(items)
        for item in items:
            if not isinstance(item, dict):
                continue
            haystack = json.dumps(item, sort_keys=True).lower()
            if any(needle in haystack for needle in NEEDLES):
                matches.append(item)
        if not items:
            break
        if total is not None and offset + len(items) >= total:
            break

    if total is None or scanned < total:
        raise SystemExit(
            f"Incomplete PayAI Bazaar scan: scanned={scanned}, total={total}"
        )
    print(f"PAYAI_CATALOG_TOTAL={total}")
    print(f"PAYAI_CATALOG_SCANNED={scanned}")
    print(f"ENGLAND_WORKS_WATCH_MATCHES={len(matches)}")
    for item in matches[:10]:
        print("MATCH=" + json.dumps(item, sort_keys=True))
    return total, scanned, matches


def main() -> None:
    paid = analytics_paid_executed()
    if paid < 1:
        raise SystemExit("No paid_executed event recorded yet")
    _total, _scanned, matches = bazaar_matches()
    if not matches:
        raise SystemExit("Paid execution exists but PayAI Bazaar has not indexed England Works Watch yet")
    print("ENGLAND_WORKS_WATCH_POST_SETTLEMENT_VERIFY=PASS")


if __name__ == "__main__":
    main()

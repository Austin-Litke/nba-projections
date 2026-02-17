#!/usr/bin/env python3
import json
import sys
import time
from pathlib import Path

import requests

URL = "https://api.prizepicks.com/projections"
PARAMS = {
    "league_id": 7,          # NBA
    "per_page": 250,
    "single_stat": "false",
}

OUT_JSON = Path("prizepicks_nba_projections.json")

def fetch():
    # A very "normal browser" header set. Not guaranteed, but helps.
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://app.prizepicks.com/",
        "Origin": "https://app.prizepicks.com",
        "Connection": "keep-alive",
    }

    # Use a session so cookies (e.g., __cf_bm) persist if needed.
    s = requests.Session()

    r = s.get(URL, params=PARAMS, headers=headers, timeout=20)
    if r.status_code != 200:
        # Print useful debug info
        print(f"HTTP {r.status_code}")
        ct = r.headers.get("content-type", "")
        print(f"content-type: {ct}")
        print("first 400 chars of body:\n")
        print(r.text[:400])
        sys.exit(1)

    data = r.json()
    return data

def summarize(data: dict):
    # PrizePicks responses are typically JSON:API-ish: {"data":[...], "included":[...], ...}
    items = data.get("data", [])
    included = data.get("included", [])

    # Count stat types and players if present
    stat_types = sum(1 for x in included if x.get("type") == "stat_types")
    players = sum(1 for x in included if x.get("type") in ("new_player", "players"))

    print(f"Fetched projections: {len(items)}")
    print(f"Included: {len(included)} (players-ish: {players}, stat_types: {stat_types})")

def main():
    t0 = time.time()
    data = fetch()
    OUT_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")
    dt = time.time() - t0

    print(f"Saved -> {OUT_JSON.resolve()}")
    print(f"Time: {dt:.2f}s")
    summarize(data)

if __name__ == "__main__":
    main()

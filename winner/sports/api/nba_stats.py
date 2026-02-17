# winner/sports/api/nba_stats.py

from __future__ import annotations
import json
from typing import Any, Dict, Optional


def get_current_season_year() -> int:
    """
    ESPN uses a 'season' year like 2026 for the 2025-26 season.
    A decent heuristic:
      - If month >= Aug -> season year = current year + 1
      - Else -> season year = current year
    """
    import datetime
    now = datetime.datetime.now()
    return now.year + 1 if now.month >= 8 else now.year


def _to_float(x) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def _find_container_with_names(payload: dict, required_names: set[str]) -> Optional[dict]:
    """
    The ESPN web stats payload often contains a schema-like object:
      { "names":[...], "displayNames":[...], "statistics":[...], ... }
    We scan the whole payload for an object with "names" containing our required keys.
    """
    stack = [payload]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            names = node.get("names")
            stats = node.get("statistics")
            if isinstance(names, list) and isinstance(stats, list):
                if required_names.issubset(set(names)):
                    return node
            for v in node.values():
                stack.append(v)
        elif isinstance(node, list):
            for v in node:
                stack.append(v)
    return None


def extract_season_averages_from_web_stats(web_json: dict, preferred_year: int | None = None) -> Dict[str, Optional[float]]:
    """
    Returns season per-game averages {pts, reb, ast} as floats.
    Uses the schema container with names including avgPoints/avgRebounds/avgAssists.
    """
    data = web_json.get("data", web_json)
    preferred_year = preferred_year or get_current_season_year()

    required = {"avgPoints", "avgRebounds", "avgAssists"}
    container = _find_container_with_names(data, required)
    if not container:
        return {"pts": None, "reb": None, "ast": None}

    names = container.get("names", [])
    idx_pts = names.index("avgPoints")
    idx_reb = names.index("avgRebounds")
    idx_ast = names.index("avgAssists")

    # Pick best season row: prefer preferred_year, otherwise most recent
    best_row = None
    best_year = -1

    for row in container.get("statistics", []):
        year = row.get("season", {}).get("year")
        if isinstance(year, int):
            if year == preferred_year:
                best_row = row
                best_year = year
                break
            if year > best_year:
                best_row = row
                best_year = year

    if not best_row:
        return {"pts": None, "reb": None, "ast": None}

    stats = best_row.get("stats", [])
    pts = _to_float(stats[idx_pts]) if idx_pts < len(stats) else None
    reb = _to_float(stats[idx_reb]) if idx_reb < len(stats) else None
    ast = _to_float(stats[idx_ast]) if idx_ast < len(stats) else None

    return {"pts": pts, "reb": reb, "ast": ast}


def extract_season_avg_minutes_from_web_stats(web_json: dict, preferred_year: int | None = None) -> Optional[float]:
    """
    Tries to extract season minutes per game. In many payloads it’s 'avgMinutes'.
    If not present, returns None (projection model will fall back to last-5 minutes).
    """
    data = web_json.get("data", web_json)
    preferred_year = preferred_year or get_current_season_year()

    required = {"avgMinutes"}
    container = _find_container_with_names(data, required)
    if not container:
        return None

    names = container.get("names", [])
    idx_min = names.index("avgMinutes")

    best_row = None
    best_year = -1
    for row in container.get("statistics", []):
        year = row.get("season", {}).get("year")
        if isinstance(year, int):
            if year == preferred_year:
                best_row = row
                best_year = year
                break
            if year > best_year:
                best_row = row
                best_year = year

    if not best_row:
        return None

    stats = best_row.get("stats", [])
    return _to_float(stats[idx_min]) if idx_min < len(stats) else None

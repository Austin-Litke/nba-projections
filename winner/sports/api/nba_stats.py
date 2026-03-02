# winner/sports/api/nba_stats.py

from __future__ import annotations
from typing import Any, Dict, Optional


def get_current_season_year() -> int:
    """
    ESPN uses a 'season' year like 2026 for the 2025-26 season.
    Heuristic:
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
    Scan the whole payload for an object with:
      { "names":[...], "statistics":[...], ... }
    where names contain our required keys.
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


def _pick_best_season_row(container: dict, preferred_year: int) -> Optional[dict]:
    best_row = None
    best_year = -1
    for row in container.get("statistics", []):
        year = row.get("season", {}).get("year")
        if isinstance(year, int):
            if year == preferred_year:
                return row
            if year > best_year:
                best_row = row
                best_year = year
    return best_row


def extract_season_averages_from_web_stats(web_json: dict, preferred_year: int | None = None) -> Dict[str, Optional[float]]:
    """
    Returns season per-game averages {pts, reb, ast} as floats.
    Uses names including avgPoints/avgRebounds/avgAssists.
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

    best_row = _pick_best_season_row(container, preferred_year)
    if not best_row:
        return {"pts": None, "reb": None, "ast": None}

    stats = best_row.get("stats", [])
    pts = _to_float(stats[idx_pts]) if idx_pts < len(stats) else None
    reb = _to_float(stats[idx_reb]) if idx_reb < len(stats) else None
    ast = _to_float(stats[idx_ast]) if idx_ast < len(stats) else None

    return {"pts": pts, "reb": reb, "ast": ast}


def extract_season_avg_minutes_from_web_stats(web_json: dict, preferred_year: int | None = None) -> Optional[float]:
    """
    Tries to extract season minutes per game. Often 'avgMinutes'.
    """
    data = web_json.get("data", web_json)
    preferred_year = preferred_year or get_current_season_year()

    required = {"avgMinutes"}
    container = _find_container_with_names(data, required)
    if not container:
        return None

    names = container.get("names", [])
    idx_min = names.index("avgMinutes")

    best_row = _pick_best_season_row(container, preferred_year)
    if not best_row:
        return None

    stats = best_row.get("stats", [])
    return _to_float(stats[idx_min]) if idx_min < len(stats) else None


def extract_season_shooting_from_web_stats(web_json: dict, preferred_year: int | None = None) -> Dict[str, Optional[float]]:
    """
    Attempts to extract season shooting volume + efficiency:
      - avgFieldGoalsAttempted
      - avgThreePointFieldGoalsAttempted
      - avgFreeThrowsAttempted
      - fieldGoalPct
      - threePointPct
      - freeThrowPct

    Returns dict with keys:
      fga, tpa, fta, fg_pct, tp_pct, ft_pct (all floats or None)
    """
    data = web_json.get("data", web_json)
    preferred_year = preferred_year or get_current_season_year()

    required = {
        "avgFieldGoalsAttempted",
        "avgThreePointFieldGoalsAttempted",
        "avgFreeThrowsAttempted",
        "fieldGoalPct",
        "threePointPct",
        "freeThrowPct",
    }
    container = _find_container_with_names(data, required)
    if not container:
        return {
            "fga": None, "tpa": None, "fta": None,
            "fg_pct": None, "tp_pct": None, "ft_pct": None,
        }

    names = container.get("names", [])
    idx_fga = names.index("avgFieldGoalsAttempted")
    idx_tpa = names.index("avgThreePointFieldGoalsAttempted")
    idx_fta = names.index("avgFreeThrowsAttempted")
    idx_fgp = names.index("fieldGoalPct")
    idx_tpp = names.index("threePointPct")
    idx_ftp = names.index("freeThrowPct")

    best_row = _pick_best_season_row(container, preferred_year)
    if not best_row:
        return {
            "fga": None, "tpa": None, "fta": None,
            "fg_pct": None, "tp_pct": None, "ft_pct": None,
        }

    stats = best_row.get("stats", [])
    fga = _to_float(stats[idx_fga]) if idx_fga < len(stats) else None
    tpa = _to_float(stats[idx_tpa]) if idx_tpa < len(stats) else None
    fta = _to_float(stats[idx_fta]) if idx_fta < len(stats) else None
    fg_pct = _to_float(stats[idx_fgp]) if idx_fgp < len(stats) else None
    tp_pct = _to_float(stats[idx_tpp]) if idx_tpp < len(stats) else None
    ft_pct = _to_float(stats[idx_ftp]) if idx_ftp < len(stats) else None

    return {
        "fga": fga, "tpa": tpa, "fta": fta,
        "fg_pct": fg_pct, "tp_pct": tp_pct, "ft_pct": ft_pct,
    }
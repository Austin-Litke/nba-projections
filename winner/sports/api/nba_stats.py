# winner/sports/api/nba_stats.py

from __future__ import annotations
from typing import Any, Dict, Optional
import re


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
    
def _pct_to_decimal(x) -> Optional[float]:
    v = _to_float(x)
    if v is None:
        return None
    # ESPN sometimes returns 0.464, sometimes 46.4
    if v > 1.0:
        v = v / 100.0
    return v    


# Important:
# ESPN uses strings like "8.6-18.4" (made-attempted). The dash is a separator,
# so we must NOT interpret it as a negative sign.
_NUM_RE = re.compile(r"(?<!\d)-?\d+(?:\.\d+)?")


def _parse_attempts_from_made_attempted(x) -> Optional[float]:
    """
    ESPN often encodes made-attempted as a string like:
      "8.6-18.4" or "8.6–18.4" or "8.6—18.4"
    We want the attempted part (2nd number) as a POSITIVE float.
    """
    if x is None:
        return None

    if isinstance(x, (int, float)):
        v = float(x)
        return v if v >= 0 else None

    s = str(x).strip()
    if not s:
        return None

    # Normalize dash types
    s = s.replace("–", "-").replace("—", "-")

    # Best path: split on separator dash
    if "-" in s:
        parts = [p.strip() for p in s.split("-") if p.strip()]
        if len(parts) >= 2:
            v = _to_float(parts[-1])
            if v is not None:
                return abs(v)

    # Fallback: tokenized numbers
    nums = _NUM_RE.findall(s)
    if len(nums) >= 2:
        v = _to_float(nums[1])
        return abs(v) if v is not None else None

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
    Extract season shooting volume + efficiency.

    ESPN often provides:
      AVG container:
        - avgFieldGoalsMade-avgFieldGoalsAttempted   (string "made-attempted")
        - avgThreePointFieldGoalsMade-avgThreePointFieldGoalsAttempted
        - avgFreeThrowsMade-avgFreeThrowsAttempted
        - fieldGoalPct
        - threePointFieldGoalPct
        - freeThrowPct

      TOTALS container:
        - fieldGoalsMade-fieldGoalsAttempted         (totals)
        - threePointFieldGoalsMade-threePointFieldGoalsAttempted
        - freeThrowsMade-freeThrowsAttempted
        - (plus pct fields)
        - gamesPlayed (often in the AVG container, but not guaranteed)

    We want PER-GAME attempts: fga/tpa/fta.
    Priority:
      1) Pull from AVG made-attempted strings (best).
      2) Else, pull from totals and divide by gamesPlayed.
    """
    data = web_json.get("data", web_json)
    preferred_year = preferred_year or get_current_season_year()

    # --- 1) Prefer AVG container ---
    avg_required = {
        "avgFieldGoalsMade-avgFieldGoalsAttempted",
        "avgThreePointFieldGoalsMade-avgThreePointFieldGoalsAttempted",
        "avgFreeThrowsMade-avgFreeThrowsAttempted",
        "fieldGoalPct",
        "threePointFieldGoalPct",
        "freeThrowPct",
    }
    avg_container = _find_container_with_names(data, avg_required)
    if avg_container:
        names = avg_container.get("names", [])
        best_row = _pick_best_season_row(avg_container, preferred_year)
        if best_row:
            stats = best_row.get("stats", [])
            idx_fga = names.index("avgFieldGoalsMade-avgFieldGoalsAttempted")
            idx_tpa = names.index("avgThreePointFieldGoalsMade-avgThreePointFieldGoalsAttempted")
            idx_fta = names.index("avgFreeThrowsMade-avgFreeThrowsAttempted")
            idx_fgp = names.index("fieldGoalPct")
            idx_tpp = names.index("threePointFieldGoalPct")
            idx_ftp = names.index("freeThrowPct")

            fga = _parse_attempts_from_made_attempted(stats[idx_fga]) if idx_fga < len(stats) else None
            tpa = _parse_attempts_from_made_attempted(stats[idx_tpa]) if idx_tpa < len(stats) else None
            fta = _parse_attempts_from_made_attempted(stats[idx_fta]) if idx_fta < len(stats) else None

            fg_pct = _pct_to_decimal(stats[idx_fgp]) if idx_fgp < len(stats) else None
            tp_pct = _pct_to_decimal(stats[idx_tpp]) if idx_tpp < len(stats) else None
            ft_pct = _pct_to_decimal(stats[idx_ftp]) if idx_ftp < len(stats) else None

            return {
                "fga": fga, "tpa": tpa, "fta": fta,
                "fg_pct": fg_pct, "tp_pct": tp_pct, "ft_pct": ft_pct,
            }

    # --- 2) Fallback: TOTALS container / games played ---
    totals_required = {
        "fieldGoalsMade-fieldGoalsAttempted",
        "threePointFieldGoalsMade-threePointFieldGoalsAttempted",
        "freeThrowsMade-freeThrowsAttempted",
        "fieldGoalPct",
        "threePointFieldGoalPct",
        "freeThrowPct",
        "gamesPlayed",
    }
    totals_container = _find_container_with_names(data, totals_required)
    if not totals_container:
        return {
            "fga": None, "tpa": None, "fta": None,
            "fg_pct": None, "tp_pct": None, "ft_pct": None,
        }

    names = totals_container.get("names", [])
    best_row = _pick_best_season_row(totals_container, preferred_year)
    if not best_row:
        return {
            "fga": None, "tpa": None, "fta": None,
            "fg_pct": None, "tp_pct": None, "ft_pct": None,
        }

    stats = best_row.get("stats", [])

    idx_gp = names.index("gamesPlayed")
    gp = _to_float(stats[idx_gp]) if idx_gp < len(stats) else None
    gp = gp if gp and gp > 0 else None

    idx_fga = names.index("fieldGoalsMade-fieldGoalsAttempted")
    idx_tpa = names.index("threePointFieldGoalsMade-threePointFieldGoalsAttempted")
    idx_fta = names.index("freeThrowsMade-freeThrowsAttempted")
    idx_fgp = names.index("fieldGoalPct")
    idx_tpp = names.index("threePointFieldGoalPct")
    idx_ftp = names.index("freeThrowPct")

    tot_fga = _parse_attempts_from_made_attempted(stats[idx_fga]) if idx_fga < len(stats) else None
    tot_tpa = _parse_attempts_from_made_attempted(stats[idx_tpa]) if idx_tpa < len(stats) else None
    tot_fta = _parse_attempts_from_made_attempted(stats[idx_fta]) if idx_fta < len(stats) else None

    # Convert totals to per-game attempts if possible
    fga = (tot_fga / gp) if (tot_fga is not None and gp is not None) else None
    tpa = (tot_tpa / gp) if (tot_tpa is not None and gp is not None) else None
    fta = (tot_fta / gp) if (tot_fta is not None and gp is not None) else None

    fg_pct = _pct_to_decimal(stats[idx_fgp]) if idx_fgp < len(stats) else None
    tp_pct = _pct_to_decimal(stats[idx_tpp]) if idx_tpp < len(stats) else None
    ft_pct = _pct_to_decimal(stats[idx_ftp]) if idx_ftp < len(stats) else None

    return {
        "fga": fga, "tpa": tpa, "fta": fta,
        "fg_pct": fg_pct, "tp_pct": tp_pct, "ft_pct": ft_pct,
    }
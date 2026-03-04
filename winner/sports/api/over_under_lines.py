# winner/sports/api/underdog_lines.py

from __future__ import annotations
from typing import Any, Dict, List, Optional
import re

from .nba_client import http_get, safe_json_load

UNDERDOG_LINES_URL = "https://api.underdogfantasy.com/beta/v5/over_under_lines"


# ---------------------------
# Helpers
# ---------------------------

def _norm_name(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9\s]", " ", s)      # remove punctuation
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", s)
    s = " ".join(s.split())
    return s


def _safe_float(x) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def _safe_int(x) -> Optional[int]:
    try:
        return int(x)
    except Exception:
        return None


def _map_display_stat_to_key(display_stat: str) -> Optional[str]:
    s = (display_stat or "").strip().lower()
    if s == "points":
        return "pts"
    if s == "rebounds":
        return "reb"
    if s == "assists":
        return "ast"
    return None


# ---------------------------
# Main functions
# ---------------------------

def fetch_over_under_lines() -> Dict[str, Any]:
    return safe_json_load(http_get(UNDERDOG_LINES_URL, ttl=10))


def lines_for_player_basic_stats(player_name: str) -> List[Dict[str, Any]]:
    """
    Returns ONLY:
      Points
      Rebounds
      Assists

    Output:
    [
      {
        "statKey": "pts",
        "displayStat": "Points",
        "line": 30.5,
        "overOdds": -121,
        "underOdds": -102
      }
    ]
    """
    want = _norm_name(player_name)
    if not want:
        return []

    raw = fetch_over_under_lines()
    lines = raw.get("over_under_lines") or []

    out: List[Dict[str, Any]] = []

    for l in lines:
        if (l.get("status") or "") != "active":
            continue

        options = l.get("options") or []
        header = (options[0].get("selection_header") if options else "") or ""

        if _norm_name(header) != want:
            continue

        ou = l.get("over_under") or {}
        appearance_stat = (ou.get("appearance_stat") or {})
        display_stat_obj = (appearance_stat.get("display_stat") or {})
        display_stat = display_stat_obj.get("display_stat") or None

        stat_value = _safe_float(l.get("stat_value"))
        if not display_stat or stat_value is None:
            continue

        stat_key = _map_display_stat_to_key(display_stat)
        if not stat_key:
            continue  # ignore combos like PRA

        over_odds = None
        under_odds = None

        for o in options:
            if (o.get("choice") or "").lower() == "higher":
                over_odds = _safe_int(o.get("american_price"))
            elif (o.get("choice") or "").lower() == "lower":
                under_odds = _safe_int(o.get("american_price"))

        out.append({
            "statKey": stat_key,
            "displayStat": display_stat,
            "line": stat_value,
            "overOdds": over_odds,
            "underOdds": under_odds,
        })

    return out
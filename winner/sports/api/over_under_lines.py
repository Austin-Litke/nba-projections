# winner/sports/api/over_under_lines.py

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


def _extract_player_header(line_obj: Dict[str, Any]) -> str:
    """
    Try multiple places Underdog has used for the "player name" header.
    """
    # Most common in your earlier attempt
    options = line_obj.get("options") or []
    if isinstance(options, list) and options:
        o0 = options[0] if isinstance(options[0], dict) else None
        if o0:
            for key in ("selection_header", "title", "choice_display", "description"):
                v = o0.get(key)
                if isinstance(v, str) and v.strip():
                    return v.strip()

    # Sometimes top-level or under over_under / appearance
    for key in ("selection_header", "title", "name"):
        v = line_obj.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()

    ou = line_obj.get("over_under") or {}
    if isinstance(ou, dict):
        for key in ("title", "name"):
            v = ou.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()

        app = ou.get("appearance_stat") or {}
        if isinstance(app, dict):
            v = app.get("title")
            if isinstance(v, str) and v.strip():
                return v.strip()

    return ""


def _extract_display_stat(line_obj: Dict[str, Any]) -> Optional[str]:
    """
    Underdog schema varies:
      appearance_stat.display_stat might be:
        - a string: "Points"
        - a dict: { "display_stat": "Points" }
        - a dict nesting another dict
    We normalize all of those cases into a string.
    """
    ou = line_obj.get("over_under") or {}
    if not isinstance(ou, dict):
        return None

    app = ou.get("appearance_stat") or {}
    if not isinstance(app, dict):
        return None

    ds = app.get("display_stat")

    # Case 1: already a string
    if isinstance(ds, str):
        s = ds.strip()
        return s if s else None

    # Case 2: dict with "display_stat" possibly string or dict
    if isinstance(ds, dict):
        inner = ds.get("display_stat")
        if isinstance(inner, str):
            s = inner.strip()
            return s if s else None
        if isinstance(inner, dict):
            inner2 = inner.get("display_stat")
            if isinstance(inner2, str):
                s = inner2.strip()
                return s if s else None

    # Fallback: sometimes APIs use "stat" directly
    alt = app.get("stat")
    if isinstance(alt, str) and alt.strip():
        # this might be "points"/"rebounds"/"assists"
        return alt.strip().title()

    return None


# ---------------------------
# Main functions
# ---------------------------

def fetch_over_under_lines() -> Dict[str, Any]:
    # ttl helps avoid hammering Underdog when clicking around
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
    if not isinstance(lines, list):
        return []

    out: List[Dict[str, Any]] = []

    for l in lines:
        if not isinstance(l, dict):
            continue

        # Only active lines
        if (l.get("status") or "") != "active":
            continue

        header = _extract_player_header(l)
        if _norm_name(header) != want:
            continue

        display_stat = _extract_display_stat(l)
        stat_value = _safe_float(l.get("stat_value"))

        if not display_stat or stat_value is None:
            continue

        stat_key = _map_display_stat_to_key(display_stat)
        if not stat_key:
            continue  # ignore PRA/combos/etc

        options = l.get("options") or []
        over_odds = None
        under_odds = None

        if isinstance(options, list):
            for o in options:
                if not isinstance(o, dict):
                    continue
                choice = (o.get("choice") or "").lower().strip()
                if choice == "higher":
                    over_odds = _safe_int(o.get("american_price"))
                elif choice == "lower":
                    under_odds = _safe_int(o.get("american_price"))

        out.append(
            {
                "statKey": stat_key,
                "displayStat": display_stat,
                "line": stat_value,
                "overOdds": over_odds,
                "underOdds": under_odds,
            }
        )

    return out
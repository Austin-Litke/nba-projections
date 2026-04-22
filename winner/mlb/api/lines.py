from __future__ import annotations

from typing import Any, Dict, List, Optional
import re
import urllib.request
import urllib.error
import json
import ssl

UNDERDOG_LINES_URL = "https://api.underdogfantasy.com/beta/v5/over_under_lines"


# ---------------------------
# Helpers
# ---------------------------

def _norm_name(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
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


def _http_get_json(url: str, timeout: int = 20) -> Dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Winner-MLB/1.0",
            "Accept": "application/json",
        },
    )
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_player_header(line_obj: Dict[str, Any]) -> str:
    options = line_obj.get("options") or []
    if isinstance(options, list) and options:
        o0 = options[0] if isinstance(options[0], dict) else None
        if o0:
            for key in ("selection_header", "title", "choice_display", "description"):
                v = o0.get(key)
                if isinstance(v, str) and v.strip():
                    return v.strip()

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
    ou = line_obj.get("over_under") or {}
    if not isinstance(ou, dict):
        return None

    app = ou.get("appearance_stat") or {}
    if not isinstance(app, dict):
        return None

    ds = app.get("display_stat")

    if isinstance(ds, str):
        s = ds.strip()
        return s if s else None

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

    alt = app.get("stat")
    if isinstance(alt, str) and alt.strip():
        return alt.strip().title()

    return None


def _map_display_stat_to_key(display_stat: str) -> Optional[str]:
    s = (display_stat or "").strip().lower()

    # be flexible here because sportsbooks can vary wording
    if s in {
        "pitcher strikeouts",
        "strikeouts",
        "pitching strikeouts",
        "pitcher k",
        "pitcher ks",
    }:
        return "pitcher_strikeouts"

    return None


# ---------------------------
# Main functions
# ---------------------------

def fetch_over_under_lines() -> Dict[str, Any]:
    return _http_get_json(UNDERDOG_LINES_URL)


def lines_for_pitcher_strikeouts(player_name: str) -> List[Dict[str, Any]]:
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
        if stat_key != "pitcher_strikeouts":
            continue

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
# api/nba_routes/lines.py
from __future__ import annotations

import importlib

from sports.api.over_under_lines import lines_for_player_basic_stats
from sports.api.nba_client import http_get, safe_json_load, ESPN_CORE_ATHLETE


def get_underdog_debug(qs: dict):
    athlete_id = (qs.get("athleteId", [""])[0] or "").strip()
    if not athlete_id.isdigit():
        return 400, {"error": "athleteId required"}

    athlete_id_int = int(athlete_id)
    athlete_url = ESPN_CORE_ATHLETE.format(athleteId=athlete_id_int)
    athlete = safe_json_load(http_get(athlete_url))
    name = (
        athlete.get("displayName")
        or athlete.get("fullName")
        or athlete.get("name")
        or ""
    )

    mod = importlib.import_module("sports.api.over_under_lines")
    module_file = getattr(mod, "__file__", None)

    fetch_info = {"available": False}
    if hasattr(mod, "fetch_over_under_lines"):
        fetch_info["available"] = True
        raw = mod.fetch_over_under_lines()
        fetch_info["type"] = str(type(raw))
        if isinstance(raw, dict):
            fetch_info["keys"] = sorted(list(raw.keys()))[:40]
            if raw.get("_error"):
                fetch_info["error"] = raw.get("_error")
                fetch_info["status"] = raw.get("status")
                fetch_info["bodyPreview"] = raw.get("bodyPreview")
        else:
            fetch_info["preview"] = str(raw)[:400]

    try:
        lines = lines_for_player_basic_stats(name)
        parse_info = {"ok": True, "count": len(lines)}
    except Exception as e:
        # keep error formatting in router (err_with_trace)
        parse_info = {"ok": False, "error": str(e)}

    return 200, {
        "athleteId": athlete_id_int,
        "playerNameFromESPN": name,
        "moduleFile": module_file,
        "fetch": fetch_info,
        "parse": parse_info,
    }


def get_underdog_lines(qs: dict):
    athlete_id = (qs.get("athleteId", [""])[0] or "").strip()
    if not athlete_id.isdigit():
        return 400, {"error": "athleteId required"}

    athlete_id_int = int(athlete_id)

    athlete_url = ESPN_CORE_ATHLETE.format(athleteId=athlete_id_int)
    athlete = safe_json_load(http_get(athlete_url))
    name = (
        athlete.get("displayName")
        or athlete.get("fullName")
        or athlete.get("name")
        or ""
    )

    basic_lines = lines_for_player_basic_stats(name)

    return 200, {
        "athleteId": athlete_id_int,
        "name": name,
        "lines": basic_lines,
        "debug": {
            "athleteUrl": athlete_url,
            "underdogEndpoint": "beta/v5/over_under_lines",
        },
    }
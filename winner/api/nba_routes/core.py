# api/nba_routes/core.py
from __future__ import annotations

from sports.api.nba_client import (
    http_get,
    safe_json_load,
    ESPN_SCOREBOARD,
    ESPN_TEAMS,
    ESPN_ROSTER,
)


def get_scoreboard(qs: dict):
    date = (qs.get("date", [""])[0] or "").strip()
    if not date.isdigit() or len(date) != 8:
        return 400, {"error": "date=YYYYMMDD required"}
    url = ESPN_SCOREBOARD.format(date=date)
    data = safe_json_load(http_get(url))
    return 200, data


def get_teams(_qs: dict):
    data = safe_json_load(http_get(ESPN_TEAMS))
    return 200, data


def get_roster(qs: dict):
    team_id = (qs.get("teamId", [""])[0] or "").strip()
    if not team_id.isdigit():
        return 400, {"error": "teamId required"}
    url = ESPN_ROSTER.format(teamId=team_id)
    data = safe_json_load(http_get(url))
    return 200, data
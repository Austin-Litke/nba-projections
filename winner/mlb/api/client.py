from __future__ import annotations

import json
import ssl
import urllib.parse
import urllib.request
from typing import Any

MLB_STATS_API = "https://statsapi.mlb.com/api/v1"


def http_get_json(url: str, timeout: int = 20) -> Any:
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


def build_schedule_url(date_iso: str) -> str:
    params = {
        "sportId": "1",
        "date": date_iso,
        "hydrate": "team,probablePitcher",
    }
    return f"{MLB_STATS_API}/schedule?{urllib.parse.urlencode(params)}"


def get_schedule(date_iso: str):
    return http_get_json(build_schedule_url(date_iso))


def get_person(person_id: str):
    params = {
        "hydrate": "currentTeam,stats(group=[pitching],type=[season])",
    }
    url = f"{MLB_STATS_API}/people/{urllib.parse.quote(str(person_id))}?{urllib.parse.urlencode(params)}"
    return http_get_json(url)


def get_pitcher_game_log(person_id: str, season: str):
    params = {
        "stats": "gameLog",
        "group": "pitching",
        "season": season,
        "sportIds": "1",
    }
    url = f"{MLB_STATS_API}/people/{urllib.parse.quote(str(person_id))}/stats?{urllib.parse.urlencode(params)}"
    return http_get_json(url)


def get_schedule_range_with_boxscore(start_date: str, end_date: str):
    params = {
        "sportId": "1",
        "startDate": start_date,
        "endDate": end_date,
        "hydrate": "team,boxscore",
    }
    url = f"{MLB_STATS_API}/schedule?{urllib.parse.urlencode(params)}"
    return http_get_json(url)
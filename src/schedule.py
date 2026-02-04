from __future__ import annotations

import datetime as dt
import requests

SCHEDULE_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json"


def _parse_game_dt_utc(game: dict) -> dt.datetime:
    s = game.get("gameDateTimeUTC")
    if s:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))

    s2 = game.get("gameDateEst")
    if not s2:
        raise ValueError("Schedule game missing datetime fields.")
    # date-only fallback; treat as UTC midnight
    return dt.datetime.fromisoformat(s2).replace(tzinfo=dt.timezone.utc)


def get_next_game_for_team(team_id: int, now_utc: dt.datetime | None = None) -> dict:
    now_utc = now_utc or dt.datetime.now(dt.timezone.utc)
    data = requests.get(SCHEDULE_URL, timeout=20).json()

    game_dates = data["leagueSchedule"]["gameDates"]
    next_game, next_dt = None, None

    for gd in game_dates:
        for g in gd["games"]:
            home_id = int(g["homeTeam"]["teamId"])
            away_id = int(g["awayTeam"]["teamId"])
            if home_id != team_id and away_id != team_id:
                continue

            gdt = _parse_game_dt_utc(g)
            if gdt <= now_utc:
                continue

            if next_dt is None or gdt < next_dt:
                next_dt = gdt
                next_game = g

    if not next_game:
        raise ValueError("No future game found for that team in schedule feed.")
    return next_game

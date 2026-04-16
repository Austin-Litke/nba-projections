from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from mlb.api.client import (
    get_person,
    get_pitcher_game_log,
    get_schedule_range_with_boxscore,
)


def _first(qs, key: str, default: str = "") -> str:
    return (qs.get(key) or [default])[0]


def _today_chicago():
    return datetime.now(ZoneInfo("America/Chicago"))


def _current_season_year() -> str:
    return str(_today_chicago().year)


def _extract_season_stats(person: dict) -> dict:
    stats = person.get("stats") or []
    season = {}

    for block in stats:
        splits = block.get("splits") or []
        if splits:
            stat = splits[0].get("stat") or {}
            season = {
                "era": stat.get("era"),
                "inningsPitched": stat.get("inningsPitched"),
                "strikeOuts": stat.get("strikeOuts"),
                "gamesStarted": stat.get("gamesStarted"),
            }
            break

    return season


def get_pitcher(qs):
    pitcher_id = _first(qs, "pitcherId").strip()
    if not pitcher_id:
        return 400, {"error": "pitcherId is required"}

    payload = get_person(pitcher_id)
    people = payload.get("people") or []
    person = people[0] if people else {}

    return 200, {
        "ok": True,
        "pitcher": {
            "id": person.get("id"),
            "fullName": person.get("fullName"),
            "pitchHand": ((person.get("pitchHand") or {}).get("description")),
            "teamName": ((person.get("currentTeam") or {}).get("name")),
        },
        "season": _extract_season_stats(person),
    }


def _games_from_stats_endpoint(pitcher_id: str, season: str, limit: int) -> list[dict]:
    payload = get_pitcher_game_log(pitcher_id, season)
    stats = payload.get("stats") or []

    splits = []
    for block in stats:
        maybe = block.get("splits") or []
        if maybe:
            splits = maybe
            break

    games = []
    for split in splits[:limit]:
        stat = split.get("stat") or {}
        opponent = ((split.get("opponent") or {}).get("name")) or "Unknown"
        date = split.get("date") or ""

        games.append({
            "date": date,
            "opponent": opponent,
            "inningsPitched": stat.get("inningsPitched"),
            "strikeOuts": stat.get("strikeOuts"),
            "earnedRuns": stat.get("earnedRuns"),
            "source": "stats",
        })

    return games


def _games_from_schedule_fallback(pitcher_id: str, limit: int) -> list[dict]:
    today = _today_chicago().date()
    start = today - timedelta(days=45)

    payload = get_schedule_range_with_boxscore(
        start_date=start.isoformat(),
        end_date=today.isoformat(),
    )

    dates = payload.get("dates") or []
    games = []

    for date_block in dates:
        for game in date_block.get("games") or []:
            boxscore = game.get("boxscore") or {}
            teams_box = boxscore.get("teams") or {}

            home_players = ((teams_box.get("home") or {}).get("players") or {})
            away_players = ((teams_box.get("away") or {}).get("players") or {})

            key = f"ID{pitcher_id}"
            player_box = None
            is_home = False

            if key in home_players:
                player_box = home_players.get(key) or {}
                is_home = True
            elif key in away_players:
                player_box = away_players.get(key) or {}

            if not player_box:
                continue

            teams = game.get("teams") or {}
            away_team = ((teams.get("away") or {}).get("team") or {})
            home_team = ((teams.get("home") or {}).get("team") or {})
            opponent = away_team.get("name") if is_home else home_team.get("name")

            stat = (player_box.get("stats") or {}).get("pitching") or {}

            # only keep appearances with an innings pitched value
            if stat.get("inningsPitched") in (None, "", "0.0"):
                continue

            games.append({
                "date": game.get("officialDate"),
                "opponent": opponent or "Unknown",
                "inningsPitched": stat.get("inningsPitched"),
                "strikeOuts": stat.get("strikeOuts"),
                "earnedRuns": stat.get("earnedRuns"),
                "source": "schedule_boxscore",
            })

    games.sort(key=lambda g: g.get("date") or "", reverse=True)
    return games[:limit]


def get_pitcher_gamelog(qs):
    pitcher_id = _first(qs, "pitcherId").strip()
    limit_raw = _first(qs, "limit", "5").strip()
    season = _first(qs, "season", _current_season_year()).strip()

    if not pitcher_id:
        return 400, {"error": "pitcherId is required"}

    try:
        limit = max(1, min(10, int(limit_raw)))
    except Exception:
        limit = 5

    games = _games_from_stats_endpoint(pitcher_id, season, limit)

    if not games:
        games = _games_from_schedule_fallback(pitcher_id, limit)

    return 200, {
        "ok": True,
        "pitcherId": pitcher_id,
        "season": season,
        "count": len(games),
        "games": games,
    }
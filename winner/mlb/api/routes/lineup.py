from __future__ import annotations

from mlb.api.client import get_game_boxscore


def _first(qs, key: str, default: str = "") -> str:
    return (qs.get(key) or [default])[0]


def _player_row(player_obj: dict) -> dict:
    person = player_obj.get("person") or {}
    batting_order = player_obj.get("battingOrder")

    stats = player_obj.get("stats") or {}
    batting = stats.get("batting") or {}

    return {
        "id": person.get("id"),
        "name": person.get("fullName"),
        "battingOrder": batting_order,
        "position": ((player_obj.get("position") or {}).get("abbreviation")),
        "atBats": batting.get("atBats"),
        "strikeOuts": batting.get("strikeOuts"),
    }


def _extract_team_batters(team_box: dict) -> list[dict]:
    players = team_box.get("players") or {}
    rows = []

    for player in players.values():
        if not isinstance(player, dict):
            continue

        # battingOrder appears when player is/was in lineup
        if player.get("battingOrder") is None:
            continue

        rows.append(_player_row(player))

    rows.sort(key=lambda r: int(r.get("battingOrder") or 999999))
    return rows


def get_lineup(qs):
    game_id = _first(qs, "gameId").strip()
    if not game_id:
        return 400, {"error": "gameId is required"}

    payload = get_game_boxscore(game_id)
    teams = payload.get("teams") or {}

    away = teams.get("away") or {}
    home = teams.get("home") or {}

    away_team = away.get("team") or {}
    home_team = home.get("team") or {}

    return 200, {
        "ok": True,
        "gameId": game_id,
        "away": {
            "team": away_team.get("name"),
            "batters": _extract_team_batters(away),
        },
        "home": {
            "team": home_team.get("name"),
            "batters": _extract_team_batters(home),
        },
    }
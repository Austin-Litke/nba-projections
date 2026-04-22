from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from mlb.api.client import get_schedule


def _today_iso_chicago() -> str:
    return datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")


def _pick_date(qs) -> tuple[str, str]:
    raw = (qs.get("date") or [""])[0].strip()

    if not raw:
        iso = _today_iso_chicago()
        return raw, iso

    if len(raw) == 8 and raw.isdigit():
        iso = f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
        return raw, iso

    if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        return raw.replace("-", ""), raw

    raise ValueError("date must be YYYYMMDD or YYYY-MM-DD")


def _safe_name(obj: dict | None) -> str:
    if not isinstance(obj, dict):
        return ""
    return str(obj.get("fullName") or obj.get("name") or "").strip()


def _format_start_time(iso_dt: str | None) -> str:
    if not iso_dt:
        return ""

    try:
        dt = datetime.fromisoformat(str(iso_dt).replace("Z", "+00:00"))
        local_dt = dt.astimezone(ZoneInfo("America/Chicago"))
        return local_dt.strftime("%-I:%M %p CT")
    except Exception:
        return ""


def _team_block(team_obj: dict | None) -> dict:
    team = (team_obj or {}).get("team") or {}
    probable = (team_obj or {}).get("probablePitcher") or {}

    return {
        "id": team.get("id"),
        "name": team.get("name"),
        "abbrev": team.get("abbreviation"),
        "location": team.get("locationName"),
        "club": team.get("clubName"),
        "probablePitcher": {
            "id": probable.get("id"),
            "name": _safe_name(probable),
        },
    }


def get_health(qs):
    return 200, {
        "ok": True,
        "sport": "mlb",
        "message": "MLB API is up",
    }


def get_scoreboard(qs):
    raw_date, date_iso = _pick_date(qs)
    payload = get_schedule(date_iso)

    dates = payload.get("dates") or []
    games = []

    for date_block in dates:
        for game in date_block.get("games") or []:
            teams = game.get("teams") or {}
            away = teams.get("away") or {}
            home = teams.get("home") or {}
            status = game.get("status") or {}
            venue = game.get("venue") or {}
            game_date = game.get("gameDate")

            games.append({
                "gameId": game.get("gamePk"),
                "gameDate": game_date,
                "startTime": _format_start_time(game_date),
                "officialDate": game.get("officialDate"),
                "status": {
                    "abstract": status.get("abstractGameState"),
                    "detailed": status.get("detailedState"),
                    "coded": status.get("codedGameState"),
                },
                "doubleHeader": game.get("doubleHeader"),
                "gameNumber": game.get("gameNumber"),
                "venue": {
                    "id": venue.get("id"),
                    "name": venue.get("name"),
                },
                "away": _team_block(away),
                "home": _team_block(home),
            })

    return 200, {
        "ok": True,
        "sport": "mlb",
        "date": raw_date or date_iso.replace("-", ""),
        "dateIso": date_iso,
        "count": len(games),
        "games": games,
    }
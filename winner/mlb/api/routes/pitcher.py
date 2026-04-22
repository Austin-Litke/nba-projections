from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from mlb.api.client import get_person, get_pitcher_game_log, get_schedule
from mlb.api.opponent import get_team_k_adjustment
from mlb.api.projection import build_pitcher_projection


def _first(qs, key: str, default: str = "") -> str:
    return (qs.get(key) or [default])[0]


def _current_season_year() -> str:
    return str(datetime.now(ZoneInfo("America/Chicago")).year)


def _today_iso_chicago() -> str:
    return datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")


def _safe_int(value, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return default


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def _estimate_batters_faced_from_stat(stat: dict) -> int | None:
    """
    Prefer explicit batters faced if present.
    Otherwise estimate from:
      outs + hits + walks + HBP
    If those are not available, fall back to:
      BF ~= innings pitched * 4.3
    """
    if not isinstance(stat, dict):
        return None

    direct_keys = (
        "battersFaced",
        "batters_faced",
        "totalBattersFaced",
    )
    for key in direct_keys:
        if stat.get(key) not in (None, ""):
            return _safe_int(stat.get(key), 0)

    ip = _safe_float(stat.get("inningsPitched"), 0.0)
    hits = _safe_int(stat.get("hits"), 0)
    walks = _safe_int(stat.get("baseOnBalls"), 0)
    hbp = _safe_int(stat.get("hitBatsmen"), 0)

    # If we have enough stat detail, estimate from base runners + outs
    if ip > 0 and (hits > 0 or walks > 0 or hbp > 0):
        outs = int(ip) * 3
        frac = round(ip - int(ip), 1)
        if frac == 0.1:
            outs += 1
        elif frac == 0.2:
            outs += 2

        est = outs + hits + walks + hbp
        if est > 0:
            return est

    # Fallback approximation from innings pitched only
    if ip > 0:
        return max(1, round(ip * 4.3))

    return None


def _extract_season_stats(person: dict) -> dict:
    stats = person.get("stats") or []
    season = {}

    for block in stats:
        splits = block.get("splits") or []
        if not splits:
            continue

        stat = (splits[0] or {}).get("stat") or {}
        season = {
            "era": stat.get("era"),
            "inningsPitched": stat.get("inningsPitched"),
            "strikeOuts": stat.get("strikeOuts"),
            "gamesStarted": stat.get("gamesStarted"),
            "gamesPlayed": stat.get("gamesPlayed"),
            "hits": stat.get("hits"),
            "baseOnBalls": stat.get("baseOnBalls"),
            "hitBatsmen": stat.get("hitBatsmen"),
            "battersFaced": _estimate_batters_faced_from_stat(stat),
        }
        break

    return season


def _get_recent_games(pitcher_id: str, season: str, limit: int) -> tuple[list[dict], dict]:
    payload = get_pitcher_game_log(pitcher_id, season)
    stats_blocks = payload.get("stats") or []

    splits = []
    for block in stats_blocks:
        maybe_splits = block.get("splits") or []
        if maybe_splits:
            splits = maybe_splits
            break

    games = []
    for split in splits[:limit]:
        stat = split.get("stat") or {}
        opponent = (split.get("opponent") or {}).get("name") or "Unknown"

        games.append({
            "date": split.get("date") or "",
            "opponent": opponent,
            "inningsPitched": stat.get("inningsPitched"),
            "strikeOuts": stat.get("strikeOuts"),
            "earnedRuns": stat.get("earnedRuns"),
            "hits": stat.get("hits"),
            "baseOnBalls": stat.get("baseOnBalls"),
            "hitBatsmen": stat.get("hitBatsmen"),
            "battersFaced": _estimate_batters_faced_from_stat(stat),
            "summary": stat.get("summary"),
        })

    debug = {
        "statsBlocks": len(stats_blocks),
        "splitsFound": len(splits),
    }
    return games, debug


def _find_today_opponent_for_pitcher(pitcher_id: str, date_iso: str) -> dict:
    payload = get_schedule(date_iso)
    dates = payload.get("dates") or []

    for date_block in dates:
        for game in date_block.get("games") or []:
            teams = game.get("teams") or {}
            away = teams.get("away") or {}
            home = teams.get("home") or {}

            away_team = (away.get("team") or {})
            home_team = (home.get("team") or {})
            away_pp = away.get("probablePitcher") or {}
            home_pp = home.get("probablePitcher") or {}

            if str(away_pp.get("id") or "") == str(pitcher_id):
                return {
                    "gameId": game.get("gamePk"),
                    "pitcherTeam": away_team.get("name"),
                    "opponentTeam": home_team.get("name"),
                    "isHome": False,
                    "officialDate": game.get("officialDate"),
                }

            if str(home_pp.get("id") or "") == str(pitcher_id):
                return {
                    "gameId": game.get("gamePk"),
                    "pitcherTeam": home_team.get("name"),
                    "opponentTeam": away_team.get("name"),
                    "isHome": True,
                    "officialDate": game.get("officialDate"),
                }

    return {
        "gameId": None,
        "pitcherTeam": None,
        "opponentTeam": None,
        "isHome": None,
        "officialDate": date_iso,
    }


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

    games, debug = _get_recent_games(pitcher_id, season, limit)

    return 200, {
        "ok": True,
        "pitcherId": pitcher_id,
        "season": season,
        "count": len(games),
        "games": games,
        "debug": debug,
    }


def get_pitcher_projection(qs):
    pitcher_id = _first(qs, "pitcherId").strip()
    season = _first(qs, "season", _current_season_year()).strip()
    limit_raw = _first(qs, "limit", "5").strip()
    date_iso = _first(qs, "date", _today_iso_chicago()).strip()

    if not pitcher_id:
        return 400, {"error": "pitcherId is required"}

    try:
        limit = max(1, min(10, int(limit_raw)))
    except Exception:
        limit = 5

    person_payload = get_person(pitcher_id)
    people = person_payload.get("people") or []
    person = people[0] if people else {}

    season_stats = _extract_season_stats(person)
    recent_games, debug = _get_recent_games(pitcher_id, season, limit)

    matchup = _find_today_opponent_for_pitcher(pitcher_id, date_iso)
    opponent_team = matchup.get("opponentTeam")
    opponent_adjustment = get_team_k_adjustment(opponent_team)

    proj = build_pitcher_projection(
        season=season_stats,
        recent_games=recent_games,
        opponent_adjustment=opponent_adjustment,
    )

    return 200, {
        "ok": True,
        "pitcherId": pitcher_id,
        "pitcher": {
            "id": person.get("id"),
            "fullName": person.get("fullName"),
            "pitchHand": ((person.get("pitchHand") or {}).get("description")),
            "teamName": ((person.get("currentTeam") or {}).get("name")),
        },
        "matchup": matchup,
        **proj,
        "debug": debug,
    }
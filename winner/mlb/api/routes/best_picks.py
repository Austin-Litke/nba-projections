from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from mlb.api.client import get_person, get_schedule
from mlb.api.routes.pitcher import get_pitcher_projection


def _first(qs, key: str, default: str = "") -> str:
    return (qs.get(key) or [default])[0]


def _today_iso_chicago() -> str:
    return datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")


def _pick_date(qs) -> str:
    raw = _first(qs, "date", "").strip()

    if not raw:
        return _today_iso_chicago()

    if len(raw) == 8 and raw.isdigit():
        return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"

    return raw


def _best_side_from_sim(sim: dict) -> tuple[str | None, float | None, float | None]:
    over_ev = sim.get("overEV")
    under_ev = sim.get("underEV")
    over_prob = sim.get("probOver")
    under_prob = sim.get("probUnder")

    candidates = []

    if over_ev is not None:
        candidates.append(("Over", over_ev, over_prob))

    if under_ev is not None:
        candidates.append(("Under", under_ev, under_prob))

    if not candidates:
        return None, None, None

    side, ev, prob = max(candidates, key=lambda x: x[1])
    return side, ev, prob


def _probable_pitchers_from_schedule(schedule_payload: dict) -> list[dict]:
    out = []

    for date_block in schedule_payload.get("dates") or []:
        for game in date_block.get("games") or []:
            teams = game.get("teams") or {}
            status = game.get("status") or {}

            for side in ("away", "home"):
                team_block = teams.get(side) or {}
                team = team_block.get("team") or {}
                pitcher = team_block.get("probablePitcher") or {}

                pitcher_id = pitcher.get("id")
                pitcher_name = pitcher.get("fullName") or pitcher.get("name")

                if not pitcher_id:
                    continue

                opponent_side = "home" if side == "away" else "away"
                opponent_team = ((teams.get(opponent_side) or {}).get("team") or {}).get("name")

                out.append({
                    "pitcherId": pitcher_id,
                    "pitcherName": pitcher_name,
                    "team": team.get("name"),
                    "opponentTeam": opponent_team,
                    "gameId": game.get("gamePk"),
                    "officialDate": game.get("officialDate"),
                    "gameDate": game.get("gameDate"),
                    "status": status.get("detailedState"),
                    "homeAway": side,
                })

    return out


def get_best_picks(qs):
    date_iso = _pick_date(qs)
    limit_raw = _first(qs, "limit", "10").strip()

    try:
        limit = max(1, min(30, int(limit_raw)))
    except Exception:
        limit = 10

    schedule = get_schedule(date_iso)
    pitchers = _probable_pitchers_from_schedule(schedule)

    candidates = []
    errors = []

    for row in pitchers:
        pitcher_id = row.get("pitcherId")

        try:
            # Reuse the full projection endpoint logic.
            code, payload = get_pitcher_projection({
                "pitcherId": [str(pitcher_id)],
                "date": [date_iso],
                "limit": ["5"],
            })

            if code != 200 or not payload.get("ok"):
                errors.append({
                    "pitcherId": pitcher_id,
                    "error": payload.get("error", "projection failed"),
                })
                continue

            sim = payload.get("simulation") or {}
            projection = payload.get("projection") or {}

            side, ev, prob = _best_side_from_sim(sim)

            if side is None or ev is None:
                continue

            # Only keep +EV plays.
            if ev <= 0:
                continue

            candidates.append({
                "pitcher": payload.get("pitcher") or {},
                "matchup": payload.get("matchup") or {},
                "projection": projection,
                "simulation": sim,
                "opponentEnvironment": payload.get("opponentEnvironment") or {},
                "side": side,
                "line": sim.get("line"),
                "ev": round(ev, 3),
                "probability": round(prob, 3) if prob is not None else None,
                "game": row,
            })

        except Exception as e:
            errors.append({
                "pitcherId": pitcher_id,
                "error": str(e),
            })

    candidates.sort(key=lambda p: p.get("ev") or -999, reverse=True)

    return 200, {
        "ok": True,
        "date": date_iso,
        "count": len(candidates),
        "pitchersScanned": len(pitchers),
        "picks": candidates[:limit],
        "errors": errors[:10],
    }
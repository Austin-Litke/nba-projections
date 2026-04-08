# api/nba_routes/player.py
from __future__ import annotations

import sports.api.nba_simulator as nba_simulator_mod
from api.nba_routes.injuries import extract_event_injuries, extract_event_teams
from api.nba_helpers.injury_adjust import injury_adjust_for_event

from sports.api.nba_client import (
    http_get,
    safe_json_load,
    ESPN_WEB_STATS,
    ESPN_WEB_GAMELOG,
    ESPN_CORE_ATHLETE,
)
from sports.api.nba_stats import (
    get_current_season_year,
    extract_season_averages_from_web_stats,
    extract_season_avg_minutes_from_web_stats,
    extract_season_shooting_from_web_stats,
)
from sports.api.nba_gamelog import (
    build_last_games,
    build_vs_opponent,
    enrich_games_with_summary,
)
from sports.api.nba_projection import build_projection

from api.nba_helpers.env_adjust import pace_and_blowout_from_games
from api.nba_helpers.sim_utils import call_simulate_props, histogram


def get_player_webstats_raw(qs: dict):
    athlete_id = (qs.get("athleteId", [""])[0] or "").strip()
    if not athlete_id.isdigit():
        return 400, {"error": "athleteId required"}
    url = ESPN_WEB_STATS.format(athleteId=int(athlete_id))
    data = safe_json_load(http_get(url))
    return 200, {"webStatsUrl": url, "data": data.get("data", data)}


def get_player_gamelog_raw(qs: dict):
    athlete_id = (qs.get("athleteId", [""])[0] or "").strip()
    if not athlete_id.isdigit():
        return 400, {"error": "athleteId required"}
    url = ESPN_WEB_GAMELOG.format(athleteId=int(athlete_id))
    data = safe_json_load(http_get(url))
    return 200, {"gamelogUrl": url, "data": data.get("data", data)}


def get_player(qs: dict):
    athlete_id = (qs.get("athleteId", [""])[0] or "").strip()
    if not athlete_id.isdigit():
        return 400, {"error": "athleteId required"}

    athlete_id_int = int(athlete_id)

    athlete_url = ESPN_CORE_ATHLETE.format(athleteId=athlete_id_int)
    athlete = safe_json_load(http_get(athlete_url))
    name = athlete.get("displayName") or athlete.get("fullName") or athlete.get("name") or "Player"

    web_url = ESPN_WEB_STATS.format(athleteId=athlete_id_int)
    web = safe_json_load(http_get(web_url))

    season_year = get_current_season_year()
    season_avg = extract_season_averages_from_web_stats(web, preferred_year=season_year)

    return 200, {
        "athleteId": athlete_id_int,
        "name": name,
        "team": None,
        "seasonAverages": season_avg,
        "debug": {
            "athleteUrl": athlete_url,
            "webStatsUrl": web_url,
            "seasonYearUsed": season_year,
        },
    }


def get_player_gamelog(qs: dict):
    athlete_id = (qs.get("athleteId", [""])[0] or "").strip()
    limit = (qs.get("limit", ["5"])[0] or "5").strip()

    if not athlete_id.isdigit():
        return 400, {"error": "athleteId required"}

    try:
        limit_int = max(1, min(25, int(limit)))
    except Exception:
        limit_int = 5

    games, dbg = build_last_games(int(athlete_id), limit=limit_int)
    return 200, {"athleteId": int(athlete_id), "games": games, "debug": dbg}


def get_player_vs_opponent(qs: dict):
    athlete_id = (qs.get("athleteId", [""])[0] or "").strip()
    opp_id = (qs.get("opponentTeamId", [""])[0] or "").strip()
    limit = (qs.get("limit", ["25"])[0] or "25").strip()

    if not athlete_id.isdigit() or not opp_id.isdigit():
        return 400, {"error": "athleteId and opponentTeamId required"}

    try:
        limit_int = max(1, min(50, int(limit)))
    except Exception:
        limit_int = 25

    athlete_id_int = int(athlete_id)
    opp_id_int = int(opp_id)

    games, dbg = build_vs_opponent(athlete_id_int, opp_id_int, limit=limit_int)
    try:
        games_enriched, enrich_dbg = enrich_games_with_summary(games, athlete_id_int)
    except Exception:
        games_enriched, enrich_dbg = games, {"error": "enrich failed"}

    return 200, {
        "athleteId": athlete_id_int,
        "opponentTeamId": opp_id_int,
        "games": games_enriched,
        "debug": {**dbg, **(enrich_dbg or {})},
    }


def get_player_projection(qs: dict, *, nba_simulator_mod_passed=None):
    athlete_id = (qs.get("athleteId", [""])[0] or "").strip()
    opp_id = (qs.get("opponentTeamId", [""])[0] or "").strip()

    if not athlete_id.isdigit():
        return 400, {"error": "athleteId required"}

    athlete_id_int = int(athlete_id)
    season_year = get_current_season_year()

    gid = (qs.get("gameId", [""])[0] or "").strip()
    game_id = gid if gid.isdigit() else ""

    opp_id_int = None
    if opp_id and str(opp_id).strip().isdigit():
        opp_id_int = int(str(opp_id).strip())

    web_url = ESPN_WEB_STATS.format(athleteId=athlete_id_int)
    web = safe_json_load(http_get(web_url))

    season_avg = extract_season_averages_from_web_stats(web, preferred_year=season_year)
    season_minutes = extract_season_avg_minutes_from_web_stats(web, preferred_year=season_year)
    season_shoot = extract_season_shooting_from_web_stats(web, preferred_year=season_year)

    last_games_5, _dbg5 = build_last_games(athlete_id_int, limit=5)
    last_games_10, dbg10 = build_last_games(athlete_id_int, limit=10)
    last_games_10, enrich_dbg = enrich_games_with_summary(last_games_10, athlete_id_int)

    vs_games = []
    if opp_id_int is not None:
        vs_games, _dbgvs = build_vs_opponent(athlete_id_int, opp_id_int, limit=25)
        try:
            vs_games, _enrich_vs_dbg = enrich_games_with_summary(vs_games, athlete_id_int)
        except Exception:
            pass

    # ---------------------------
    # Resolve athlete team id
    # ---------------------------
    athlete_team_id = None
    athlete_team_id_source = "none"

    try:
        core_url = ESPN_CORE_ATHLETE.format(athleteId=athlete_id_int)
        core = safe_json_load(http_get(core_url))
        team = core.get("team") or {}
        tid = team.get("id")
        if str(tid).isdigit():
            athlete_team_id = int(tid)
            athlete_team_id_source = "core"
    except Exception:
        pass

    if athlete_team_id is None:
        try:
            candidate_paths = [
                ((web or {}).get("team") or {}).get("id"),
                (((web or {}).get("athlete") or {}).get("team") or {}).get("id"),
                (((web or {}).get("player") or {}).get("team") or {}).get("id"),
            ]
            for tid in candidate_paths:
                if str(tid).isdigit():
                    athlete_team_id = int(tid)
                    athlete_team_id_source = "web_stats"
                    break
        except Exception:
            pass

    base = build_projection(
        season_avg,
        season_minutes,
        last_games_5,
        vs_games,
        season_shoot=season_shoot,
    )
    meta = base.get("meta") or {}
    est_min = float(meta.get("estMinutes") or 32.0)
    opp_adj = (meta.get("oppAdj") or {"pts": 1.0, "reb": 1.0, "ast": 1.0})

    inj_minutes_add = 0.0
    inj_usage_mult = {"pts": 1.0, "reb": 1.0, "ast": 1.0}
    inj_dbg = {"used": False, "notes": ["no gameId"]}
    event_rows = []

    own_team_out = []
    opp_team_out = []
    own_team_impact = 0.0
    opp_team_impact = 0.0

    if game_id:
        try:
            event_rows = extract_event_injuries(int(game_id)) or []

            if athlete_team_id is None and opp_id_int is not None and game_id:
                try:
                    event_teams = extract_event_teams(int(game_id)) or []
                    event_team_ids = []
                    for t in event_teams:
                        tid = t.get("teamId")
                        if str(tid).isdigit():
                            event_team_ids.append(int(tid))

                    if len(event_team_ids) == 2 and opp_id_int in event_team_ids:
                        other = [t for t in event_team_ids if t != opp_id_int]
                        if other:
                            athlete_team_id = int(other[0])
                            athlete_team_id_source = "event_competitors_other_team"
                except Exception:
                    pass

            inj_minutes_add, inj_usage_mult, inj_dbg = injury_adjust_for_event(
                athlete_id=athlete_id_int,
                athlete_team_id=athlete_team_id,
                event_injuries_rows=event_rows,
                est_minutes=est_min,
                last_games_10=last_games_10,
            )

            own_team_impact = float(
                (((inj_dbg or {}).get("result") or {}).get("teamImpactScore")) or 0.0
            )

            if athlete_team_id is not None:
                for r in event_rows:
                    if str(r.get("teamId")) != str(athlete_team_id):
                        continue
                    status = str(r.get("status") or "")
                    if status.strip().lower() not in ("out", "suspension", "doubtful", "questionable", "day-to-day", "dtd"):
                        continue
                    own_team_out.append({
                        "athleteId": r.get("athleteId"),
                        "name": r.get("name"),
                        "status": status,
                    })

            if opp_id_int is not None:
                for r in event_rows:
                    if str(r.get("teamId")) != str(opp_id_int):
                        continue
                    status = str(r.get("status") or "")
                    if status.strip().lower() not in ("out", "suspension", "doubtful", "questionable", "day-to-day", "dtd"):
                        continue
                    opp_team_out.append({
                        "athleteId": r.get("athleteId"),
                        "name": r.get("name"),
                        "status": status,
                    })

                def _status_weight_local(status: str) -> float:
                    s = (status or "").strip().lower()
                    if s in ("out", "suspension"):
                        return 1.0
                    if s == "doubtful":
                        return 0.75
                    if s == "questionable":
                        return 0.40
                    if s in ("day-to-day", "dtd"):
                        return 0.20
                    return 0.0

                opp_team_impact = 0.0
                for r in event_rows:
                    if str(r.get("teamId")) != str(opp_id_int):
                        continue
                    w = _status_weight_local(str(r.get("status") or ""))
                    if w <= 0:
                        continue

                    try:
                        other_id = int(r.get("athleteId"))
                    except Exception:
                        continue

                    try:
                        other_games, _other_dbg = build_last_games(other_id, limit=10)
                    except Exception:
                        other_games = []

                    avg_min = 0.0
                    mins = [float(g.get("min")) for g in other_games if isinstance(g.get("min"), (int, float))]
                    if mins:
                        avg_min = sum(mins) / len(mins)

                    creation_vals = []
                    creation_mins = []
                    for g in other_games:
                        gm = g.get("min")
                        pts = g.get("pts")
                        ast = g.get("ast")
                        if not isinstance(gm, (int, float)) or gm <= 0:
                            continue
                        if not isinstance(pts, (int, float)) and not isinstance(ast, (int, float)):
                            continue
                        cre = float(pts or 0) + 1.6 * float(ast or 0)
                        creation_vals.append(cre)
                        creation_mins.append(float(gm))

                    cre_per_min = (sum(creation_vals) / sum(creation_mins)) if sum(creation_mins) > 0 else 0.0
                    opp_team_impact += (w * avg_min) / 14.0 + (w * cre_per_min * 1.65)

                opp_team_impact = max(0.0, min(12.0, opp_team_impact))

        except Exception as e:
            inj_dbg = {"used": False, "error": str(e), "notes": ["injury adjust failed"]}

    pace_mult, minutes_mult, env_dbg = pace_and_blowout_from_games(
        vs_games,
        last_games_10,
        injury_ctx={
            "ownTeamImpact": own_team_impact,
            "oppTeamImpact": opp_team_impact,
        },
        est_minutes=float(est_min) + float(inj_minutes_add),
    )

    sim = call_simulate_props(
        season_avg=season_avg,
        season_minutes=season_minutes,
        last_games_10=last_games_10,
        opp_mult={
            "pts": float(opp_adj.get("pts", 1.0)) * float(inj_usage_mult.get("pts", 1.0)),
            "reb": float(opp_adj.get("reb", 1.0)) * float(inj_usage_mult.get("reb", 1.0)),
            "ast": float(opp_adj.get("ast", 1.0)) * float(inj_usage_mult.get("ast", 1.0)),
        },
        est_minutes_point=float(est_min) + float(inj_minutes_add),
        season_shoot=season_shoot,
        pace_mult=pace_mult,
        minutes_mult=minutes_mult,
        n=10000,
    )

    pts_hist = histogram(sim.get("samples", {}).get("pts", []) or [], n_bins=30)

    sim_mod = nba_simulator_mod_passed or nba_simulator_mod

    return 200, {
        "projection": sim["projection"],
        "distribution": sim["distribution"],
        "distributionHistogram": {"pts": pts_hist} if pts_hist else {},
        "meta": {
            "estMinutes": round(est_min, 1),
            "injAdjustedMinutes": round(float(est_min) + float(inj_minutes_add), 1),
            "oppAdj": opp_adj,
            "paceMult": pace_mult,
            "minutesMult": minutes_mult,
            "blowoutRiskPct": (env_dbg or {}).get("blowoutRiskPct"),
            "blowoutTier": (env_dbg or {}).get("blowoutTier"),
            "teamStrengthDelta": (env_dbg or {}).get("teamStrengthDelta"),
            "confidence": meta.get("confidence") or "—",
            "minutesStability": (sim.get("diagnostics") or {}).get("minutesStability"),
            "minutesMu": (sim.get("diagnostics") or {}).get("minutesMu"),
            "minutesSd": (sim.get("diagnostics") or {}).get("minutesSd"),
            "nSamples": (sim.get("diagnostics") or {}).get("n"),
            "injMinutesAdd": round(float(inj_minutes_add), 2),
            "injUsageMult": inj_usage_mult,
            "ownTeamImpact": round(float(own_team_impact), 3),
            "oppTeamImpact": round(float(opp_team_impact), 3),
            "gameIdUsed": int(game_id) if game_id else None,
            "ptsEngine": ((sim.get("diagnostics") or {}).get("engine") or {}).get("pts"),
            "ownTeamOut": own_team_out,
            "oppTeamOut": opp_team_out,
            "opportunity": meta.get("opportunity") or {},
        },
        "debug": {
            "apiFile": __file__,
            "simulatorFile": getattr(sim_mod, "__file__", None),
            "envAdjust": env_dbg,
            "webStatsUrl": web_url,
            "seasonYearUsed": season_year,
            "opponentTeamId": opp_id_int,
            "athleteTeamId": athlete_team_id,
            "athleteTeamIdSource": athlete_team_id_source,
            "baseProjection": base.get("projection"),
            "baseProjectionMeta": meta,
            "gamelogDebug": dbg10,
            "injuryAdjust": inj_dbg,
            "eventInjuriesCount": len(event_rows or []),
            "eventInjuriesTeamIds": sorted(list({str(r.get("teamId")) for r in (event_rows or []) if r.get("teamId") is not None})),
            "summaryEnrichDebug": enrich_dbg,
            "seasonShooting": season_shoot,
            "simDiagnostics": sim.get("diagnostics"),
        },
    }
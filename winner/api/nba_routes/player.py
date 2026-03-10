# api/nba_routes/player.py
from __future__ import annotations

import sports.api.nba_simulator as nba_simulator_mod  # only for default import; router passes actual module too
from api.nba_routes.injuries import extract_event_injuries
from api.nba_helpers.injury_adjust import injury_adjust_for_event
from sports.api.nba_client import ESPN_CORE_ATHLETE  # if not already imported

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
    
    athlete_team_id = None
    try:
        core_url = ESPN_CORE_ATHLETE.format(athleteId=athlete_id_int)
        core = safe_json_load(http_get(core_url))
        team = core.get("team") or {}
        tid = team.get("id")
        athlete_team_id = int(tid) if str(tid).isdigit() else None
    except Exception:
        athlete_team_id = None
    
    gid = (qs.get("gameId", [""])[0] or "").strip()
    game_id = gid if gid.isdigit() else ""

    web_url = ESPN_WEB_STATS.format(athleteId=athlete_id_int)
    web = safe_json_load(http_get(web_url))

    season_avg = extract_season_averages_from_web_stats(web, preferred_year=season_year)
    season_minutes = extract_season_avg_minutes_from_web_stats(web, preferred_year=season_year)
    season_shoot = extract_season_shooting_from_web_stats(web, preferred_year=season_year)

    last_games_5, _dbg5 = build_last_games(athlete_id_int, limit=5)
    last_games_10, dbg10 = build_last_games(athlete_id_int, limit=10)
    last_games_10, enrich_dbg = enrich_games_with_summary(last_games_10, athlete_id_int)

    opp_id_int = None
    if opp_id and str(opp_id).strip().isdigit():
        opp_id_int = int(str(opp_id).strip())

    vs_games = []
    if opp_id_int is not None:
        vs_games, _dbgvs = build_vs_opponent(athlete_id_int, opp_id_int, limit=25)
        try:
            vs_games, _enrich_vs_dbg = enrich_games_with_summary(vs_games, athlete_id_int)
        except Exception:
            pass

    base = build_projection(season_avg, season_minutes, last_games_5, vs_games)
    meta = base.get("meta") or {}
    est_min = float(meta.get("estMinutes") or 32.0)
    opp_adj = (meta.get("oppAdj") or {"pts": 1.0, "reb": 1.0, "ast": 1.0})

    # ✅ NEW: pace + blowout adjustment multipliers
    pace_mult, minutes_mult, env_dbg = pace_and_blowout_from_games(vs_games, last_games_10)
    
    # ---------------------------
    # Injury adjustment (event-aware)
    # ---------------------------
    inj_minutes_add = 0.0
    inj_usage_mult = {"pts": 1.0, "reb": 1.0, "ast": 1.0}
    inj_dbg = {"used": False, "notes": ["no gameId"]}

    if game_id:
        try:
            event_rows = extract_event_injuries(int(game_id))
            inj_minutes_add, inj_usage_mult, inj_dbg = injury_adjust_for_event(
                athlete_id=athlete_id_int,
                athlete_team_id=athlete_team_id,
                event_injuries_rows=event_rows,
                est_minutes=est_min,
                last_games_10=last_games_10,
            )
        except Exception as e:
            inj_dbg = {"used": False, "error": str(e), "notes": ["injury adjust failed"]}

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
            "oppAdj": opp_adj,
            "paceMult": pace_mult,
            "minutesMult": minutes_mult,
            "confidence": meta.get("confidence") or "—",
            "minutesStability": (sim.get("diagnostics") or {}).get("minutesStability"),
            "minutesMu": (sim.get("diagnostics") or {}).get("minutesMu"),
            "minutesSd": (sim.get("diagnostics") or {}).get("minutesSd"),
            "nSamples": (sim.get("diagnostics") or {}).get("n"),
            "injMinutesAdd": round(float(inj_minutes_add), 2),
            "injUsageMult": inj_usage_mult,
            "gameIdUsed": int(game_id) if game_id else None,
            "ptsEngine": ((sim.get("diagnostics") or {}).get("engine") or {}).get("pts"),
        },
        "debug": {
            "apiFile": __file__,  # ✅ PROOF the right file is loaded
            "simulatorFile": getattr(sim_mod, "__file__", None),  # ✅ PROOF
            "envAdjust": env_dbg,
            "webStatsUrl": web_url,
            "seasonYearUsed": season_year,
            "opponentTeamId": opp_id_int,
            "baseProjection": base.get("projection"),
            "gamelogDebug": dbg10,
            "injuryAdjust": inj_dbg,
            "summaryEnrichDebug": enrich_dbg,
            "seasonShooting": season_shoot,
            "simDiagnostics": sim.get("diagnostics"),
        },
    }
# api/nba_routes/tracking.py
from __future__ import annotations

from api.utils import read_json_body
from api.nba_routes.injuries import extract_event_injuries
from api.nba_helpers.injury_adjust import injury_adjust_for_event
from sports.api.nba_client import ESPN_CORE_ATHLETE

from sports.api.nba_tracker import (
    add_prediction,
    list_predictions,
    settle_prediction,
    metrics as tracker_metrics,
)

from sports.api.nba_client import http_get, safe_json_load, ESPN_WEB_STATS
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
from sports.api.nba_simulator import prob_over, fair_line, alt_lines_probs

from api.nba_helpers.env_adjust import pace_and_blowout_from_games
from api.nba_helpers.sim_utils import call_simulate_props

def mean_of_samples(samples):
    vals = [float(x) for x in (samples or []) if isinstance(x, (int, float))]
    return round(sum(vals) / len(vals), 2) if vals else 0.0

def get_tracked(qs: dict):
    aid = (qs.get("athleteId", [""])[0] or "").strip()
    athlete_id = int(aid) if aid.isdigit() else None
    preds = list_predictions(athlete_id)
    return 200, {"athleteId": athlete_id, "predictions": preds}


def get_tracked_metrics(qs: dict):
    aid = (qs.get("athleteId", [""])[0] or "").strip()
    athlete_id = int(aid) if aid.isdigit() else None
    preds = list_predictions(athlete_id)
    m = tracker_metrics(preds)
    return 200, {"athleteId": athlete_id, "metrics": m}


def post_track(handler):
    body = read_json_body(handler)
    rec = add_prediction(body)
    return 200, {"saved": rec}


def post_settle(handler):
    body = read_json_body(handler)
    pid = body.get("id")
    try:
        pid = int(pid)
    except Exception:
        return 400, {"error": "id must be an integer"}

    rec = settle_prediction(pid)
    return 200, {"settled": rec}


def post_assess_line(handler, *, nba_simulator_mod):
    body = read_json_body(handler)

    athlete_id = body.get("athleteId")
    stat = (body.get("stat") or "pts").strip().lower()
    line = body.get("line")
    opp_id = body.get("opponentTeamId")
    game_id = str(body.get("gameId") or "").strip()
    if game_id and (not game_id.isdigit()):
        game_id = ""

    try:
        athlete_id_int = int(athlete_id)
    except Exception:
        return 400, {"error": "athleteId must be an integer"}

    if stat not in ("pts", "reb", "ast"):
        return 400, {"error": "stat must be one of: pts, reb, ast"}

    try:
        line_f = float(line)
    except Exception:
        return 400, {"error": "line must be a number"}
    
    athlete_team_id = None
    try:
        core_url = ESPN_CORE_ATHLETE.format(athleteId=athlete_id_int)
        core = safe_json_load(http_get(core_url))
        team = core.get("team") or {}
        tid = team.get("id")
        athlete_team_id = int(tid) if str(tid).isdigit() else None
    except Exception:
        athlete_team_id = None

    season_year = get_current_season_year()

    web_url = ESPN_WEB_STATS.format(athleteId=athlete_id_int)
    web = safe_json_load(http_get(web_url))

    season_avg = extract_season_averages_from_web_stats(web, preferred_year=season_year)
    season_minutes = extract_season_avg_minutes_from_web_stats(web, preferred_year=season_year)
    season_shoot = extract_season_shooting_from_web_stats(web, preferred_year=season_year)

    last_games_5, _dbg5 = build_last_games(athlete_id_int, limit=5)
    last_games_10, dbg10 = build_last_games(athlete_id_int, limit=10)
    last_games_10, enrich_dbg = enrich_games_with_summary(last_games_10, athlete_id_int)

    opp_id_int = None
    if opp_id is not None and str(opp_id).strip().isdigit():
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

    pace_mult, minutes_mult, env_dbg = pace_and_blowout_from_games(vs_games, last_games_10)
    
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

    samples = (sim.get("samples") or {}).get(stat, [])
    p_over = prob_over(samples, line_f)
    p_under = 1.0 - p_over
    fair = fair_line(samples)  # median / p50
    alts = alt_lines_probs(samples, stat, center_line=line_f)

    proj_p50 = (sim.get("projection") or {}).get(stat, 0.0)
    proj_mean = mean_of_samples(samples)
    dist = (sim.get("distribution") or {}).get(stat, {})

    return 200, {
        "athleteId": athlete_id_int,
        "stat": stat,
        "line": line_f,
        "probOver": round(p_over, 4),
        "probUnder": round(p_under, 4),
        "fairLine": fair,
        "projectionP50": proj_p50,
        "projectionMean": proj_mean,
        "band": dist,
        "altLines": alts,
        "meta": {
            "opponentTeamId": opp_id_int,
            "seasonYearUsed": season_year,
            "webStatsUrl": web_url,
            "paceMult": pace_mult,
            "minutesMult": minutes_mult,
            "projectionMean": proj_mean,
            "injMinutesAdd": round(float(inj_minutes_add), 2),
            "injUsageMult": inj_usage_mult,
            "injSummary": (inj_dbg.get("summary") if isinstance(inj_dbg, dict) else None),
            "gameIdUsed": int(game_id) if game_id else None,
            "nSamples": (sim.get("diagnostics") or {}).get("n"),
            "minutesMu": (sim.get("diagnostics") or {}).get("minutesMu"),
            "minutesSd": (sim.get("diagnostics") or {}).get("minutesSd"),
            "minutesStability": (sim.get("diagnostics") or {}).get("minutesStability"),
            "oppAdj": opp_adj,
            "confidence": meta.get("confidence") or "—",
            "ptsEngine": ((sim.get("diagnostics") or {}).get("engine") or {}).get("pts"),
        },
        "debug": {
            "apiFile": __file__,
            "simulatorFile": getattr(nba_simulator_mod, "__file__", None),
            "envAdjust": env_dbg,
            "baseProjection": base.get("projection"),
            "gamelogDebug": dbg10,
            "injuryAdjust": inj_dbg,
            "summaryEnrichDebug": enrich_dbg,
            "seasonShooting": season_shoot,
            "simDiagnostics": sim.get("diagnostics"),
        },
    }
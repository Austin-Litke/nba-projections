# api/nba_routes/tracking.py
from __future__ import annotations

from api.utils import read_json_body
from api.nba_routes.injuries import extract_event_injuries, extract_event_teams
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

    opp_id_int = None
    if opp_id is not None and str(opp_id).strip().isdigit():
        opp_id_int = int(str(opp_id).strip())

    season_year = get_current_season_year()

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
    event_team_ids = []

    if game_id:
        try:
            event_rows = extract_event_injuries(int(game_id)) or []

            try:
                event_teams = extract_event_teams(int(game_id)) or []
                for t in event_teams:
                    tid = t.get("teamId")
                    if str(tid).isdigit():
                        event_team_ids.append(int(tid))
            except Exception:
                event_team_ids = []

            if athlete_team_id is None and opp_id_int is not None and event_team_ids:
                if len(event_team_ids) == 2 and opp_id_int in event_team_ids:
                    other = [t for t in event_team_ids if t != opp_id_int]
                    if other:
                        athlete_team_id = int(other[0])
                        athlete_team_id_source = "event_competitors_other_team"

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

    samples = (sim.get("samples") or {}).get(stat, [])
    p_over = prob_over(samples, line_f)
    p_under = 1.0 - p_over
    fair = fair_line(samples)
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
            "blowoutRiskPct": (env_dbg or {}).get("blowoutRiskPct"),
            "blowoutTier": (env_dbg or {}).get("blowoutTier"),
            "teamStrengthDelta": (env_dbg or {}).get("teamStrengthDelta"),
            "projectionMean": proj_mean,
            "injMinutesAdd": round(float(inj_minutes_add), 2),
            "injUsageMult": inj_usage_mult,
            "injSummary": (inj_dbg.get("summary") if isinstance(inj_dbg, dict) else None),
            "ownTeamImpact": round(float(own_team_impact), 3),
            "oppTeamImpact": round(float(opp_team_impact), 3),
            "ownTeamOut": own_team_out,
            "oppTeamOut": opp_team_out,
            "gameIdUsed": int(game_id) if game_id else None,
            "nSamples": (sim.get("diagnostics") or {}).get("n"),
            "minutesMu": (sim.get("diagnostics") or {}).get("minutesMu"),
            "minutesSd": (sim.get("diagnostics") or {}).get("minutesSd"),
            "minutesStability": (sim.get("diagnostics") or {}).get("minutesStability"),
            "oppAdj": opp_adj,
            "confidence": meta.get("confidence") or "—",
            "ptsEngine": ((sim.get("diagnostics") or {}).get("engine") or {}).get("pts"),
            "opportunity": meta.get("opportunity") or {},
        },
        "debug": {
            "apiFile": __file__,
            "simulatorFile": getattr(nba_simulator_mod, "__file__", None),
            "envAdjust": env_dbg,
            "baseProjection": base.get("projection"),
            "baseProjectionMeta": meta,
            "gamelogDebug": dbg10,
            "injuryAdjust": inj_dbg,
            "athleteTeamId": athlete_team_id,
            "athleteTeamIdSource": athlete_team_id_source,
            "eventInjuriesCount": len(event_rows or []),
            "eventTeamIds": event_team_ids,
            "summaryEnrichDebug": enrich_dbg,
            "seasonShooting": season_shoot,
            "simDiagnostics": sim.get("diagnostics"),
        },
    }
    
    
    
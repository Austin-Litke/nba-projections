# winner/api/nba_api.py
from __future__ import annotations

import traceback
import importlib
from urllib.parse import urlparse, parse_qs

# ✅ make sure this matches the actual filename you want:
# winner/sports/api/over_under_lines.py
from sports.api.over_under_lines import lines_for_player_basic_stats

from api.utils import read_json_body

from sports.api.nba_tracker import (
    add_prediction,
    list_predictions,
    settle_prediction,
    metrics as tracker_metrics,
)

from sports.api.nba_client import (
    http_get,
    safe_json_load,
    ESPN_SCOREBOARD,
    ESPN_TEAMS,
    ESPN_ROSTER,
    ESPN_CORE_ATHLETE,
    ESPN_WEB_STATS,
    ESPN_WEB_GAMELOG,
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

from sports.api.nba_simulator import (
    simulate_props,
    prob_over,
    fair_line,
    alt_lines_probs,
)


def _histogram(samples: list[float], n_bins: int = 30):
    if not samples:
        return None
    try:
        mn = float(min(samples))
        mx = float(max(samples))
        if mx - mn < 6:
            pad = 6.0
            mn = max(0.0, mn - pad / 2.0)
            mx = mx + pad / 2.0

        n_bins = max(5, min(80, int(n_bins)))
        width = (mx - mn) / n_bins if n_bins > 0 else 1.0

        bins = [round(mn + i * width, 3) for i in range(n_bins + 1)]
        counts = [0] * n_bins

        for v in samples:
            try:
                if v <= mn:
                    idx = 0
                elif v >= mx:
                    idx = n_bins - 1
                else:
                    idx = int((v - mn) / width)
                    if idx < 0:
                        idx = 0
                    if idx >= n_bins:
                        idx = n_bins - 1
                counts[idx] += 1
            except Exception:
                continue

        total = sum(counts) or 1
        freqs = [c / total for c in counts]

        return {"bins": bins, "counts": counts, "freqs": freqs, "min": mn, "max": mx}
    except Exception:
        return None


def _err_with_trace(e: Exception):
    # last ~18 lines of traceback is usually enough
    tb = traceback.format_exc().splitlines()
    return {
        "error": str(e),
        "traceTail": tb[-18:],
    }


def handle_get(path: str, query: str):
    parsed = urlparse(path + (("?" + query) if query else ""))
    qs = parse_qs(parsed.query)

    try:
        if parsed.path == "/api/nba/scoreboard":
            date = (qs.get("date", [""])[0] or "").strip()
            if not date.isdigit() or len(date) != 8:
                return 400, {"error": "date=YYYYMMDD required"}
            url = ESPN_SCOREBOARD.format(date=date)
            data = safe_json_load(http_get(url))
            return 200, data

        if parsed.path == "/api/nba/teams":
            data = safe_json_load(http_get(ESPN_TEAMS))
            return 200, data

        if parsed.path == "/api/nba/roster":
            team_id = (qs.get("teamId", [""])[0] or "").strip()
            if not team_id.isdigit():
                return 400, {"error": "teamId required"}
            url = ESPN_ROSTER.format(teamId=team_id)
            data = safe_json_load(http_get(url))
            return 200, data

        if parsed.path == "/api/nba/player_webstats_raw":
            athlete_id = (qs.get("athleteId", [""])[0] or "").strip()
            if not athlete_id.isdigit():
                return 400, {"error": "athleteId required"}
            url = ESPN_WEB_STATS.format(athleteId=int(athlete_id))
            data = safe_json_load(http_get(url))
            return 200, {"webStatsUrl": url, "data": data.get("data", data)}

        # ✅ DEBUG ENDPOINT: tells us what file/module is actually loaded + what fetch returns
        if parsed.path == "/api/nba/underdog_debug":
            athlete_id = (qs.get("athleteId", [""])[0] or "").strip()
            if not athlete_id.isdigit():
                return 400, {"error": "athleteId required"}

            athlete_id_int = int(athlete_id)
            athlete_url = ESPN_CORE_ATHLETE.format(athleteId=athlete_id_int)
            athlete = safe_json_load(http_get(athlete_url))
            name = (
                athlete.get("displayName")
                or athlete.get("fullName")
                or athlete.get("name")
                or ""
            )

            # import the module object so we can see __file__
            mod = importlib.import_module("sports.api.over_under_lines")
            module_file = getattr(mod, "__file__", None)

            fetch_info = {"available": False}
            if hasattr(mod, "fetch_over_under_lines"):
                fetch_info["available"] = True
                raw = mod.fetch_over_under_lines()
                fetch_info["type"] = str(type(raw))
                if isinstance(raw, dict):
                    fetch_info["keys"] = sorted(list(raw.keys()))[:40]
                    # if it has an error, include it
                    if raw.get("_error"):
                        fetch_info["error"] = raw.get("_error")
                        fetch_info["status"] = raw.get("status")
                        fetch_info["bodyPreview"] = raw.get("bodyPreview")
                else:
                    # show a preview of the string/whatever
                    fetch_info["preview"] = str(raw)[:400]

            # also do the normal parse attempt
            try:
                lines = lines_for_player_basic_stats(name)
                parse_info = {"ok": True, "count": len(lines)}
            except Exception as e:
                parse_info = {"ok": False, **_err_with_trace(e)}

            return 200, {
                "athleteId": athlete_id_int,
                "playerNameFromESPN": name,
                "moduleFile": module_file,
                "fetch": fetch_info,
                "parse": parse_info,
            }

        # -------------------------------------------------
        # Underdog active lines (PTS / REB / AST only)
        # -------------------------------------------------
        if parsed.path in ("/api/nba/underdog_lines", "/api/nba/over_under_lines"):
            athlete_id = (qs.get("athleteId", [""])[0] or "").strip()
            if not athlete_id.isdigit():
                return 400, {"error": "athleteId required"}

            athlete_id_int = int(athlete_id)

            athlete_url = ESPN_CORE_ATHLETE.format(athleteId=athlete_id_int)
            athlete = safe_json_load(http_get(athlete_url))
            name = (
                athlete.get("displayName")
                or athlete.get("fullName")
                or athlete.get("name")
                or ""
            )

            basic_lines = lines_for_player_basic_stats(name)

            return 200, {
                "athleteId": athlete_id_int,
                "name": name,
                "lines": basic_lines,
                "debug": {
                    "athleteUrl": athlete_url,
                    "underdogEndpoint": "beta/v5/over_under_lines",
                },
            }

        if parsed.path == "/api/nba/player_gamelog_raw":
            athlete_id = (qs.get("athleteId", [""])[0] or "").strip()
            if not athlete_id.isdigit():
                return 400, {"error": "athleteId required"}
            url = ESPN_WEB_GAMELOG.format(athleteId=int(athlete_id))
            data = safe_json_load(http_get(url))
            return 200, {"gamelogUrl": url, "data": data.get("data", data)}

        if parsed.path == "/api/nba/player":
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

        if parsed.path == "/api/nba/player_gamelog":
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

        if parsed.path == "/api/nba/player_vs_opponent":
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

        if parsed.path == "/api/nba/tracked":
            aid = (qs.get("athleteId", [""])[0] or "").strip()
            athlete_id = int(aid) if aid.isdigit() else None
            preds = list_predictions(athlete_id)
            return 200, {"athleteId": athlete_id, "predictions": preds}

        if parsed.path == "/api/nba/tracked_metrics":
            aid = (qs.get("athleteId", [""])[0] or "").strip()
            athlete_id = int(aid) if aid.isdigit() else None
            preds = list_predictions(athlete_id)
            m = tracker_metrics(preds)
            return 200, {"athleteId": athlete_id, "metrics": m}

        if parsed.path == "/api/nba/player_projection":
            athlete_id = (qs.get("athleteId", [""])[0] or "").strip()
            opp_id = (qs.get("opponentTeamId", [""])[0] or "").strip()

            if not athlete_id.isdigit():
                return 400, {"error": "athleteId required"}

            athlete_id_int = int(athlete_id)
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

            sim = simulate_props(
                season_avg=season_avg,
                season_minutes=season_minutes,
                last_games_10=last_games_10,
                opp_mult=opp_adj,
                est_minutes_point=est_min,
                season_shoot=season_shoot,
                n=10000,
            )

            pts_hist = _histogram(sim.get("samples", {}).get("pts", []) or [], n_bins=30)

            return 200, {
                "projection": sim["projection"],
                "distribution": sim["distribution"],
                "distributionHistogram": {"pts": pts_hist} if pts_hist else {},
                "meta": {
                    "estMinutes": round(est_min, 1),
                    "oppAdj": opp_adj,
                    "confidence": meta.get("confidence") or "—",
                    "minutesStability": sim["diagnostics"].get("minutesStability"),
                    "minutesMu": sim["diagnostics"].get("minutesMu"),
                    "minutesSd": sim["diagnostics"].get("minutesSd"),
                    "nSamples": sim["diagnostics"].get("n"),
                    "ptsEngine": (sim["diagnostics"].get("engine") or {}).get("pts"),
                },
                "debug": {
                    "webStatsUrl": web_url,
                    "seasonYearUsed": season_year,
                    "opponentTeamId": opp_id_int,
                    "baseProjection": base.get("projection"),
                    "gamelogDebug": dbg10,
                    "summaryEnrichDebug": enrich_dbg,
                    "seasonShooting": season_shoot,
                    "simDiagnostics": sim["diagnostics"],
                },
            }

        return None

    except Exception as e:
        return 500, _err_with_trace(e)


def handle_post(handler, path: str):
    parsed = urlparse(path)

    try:
        if parsed.path == "/api/nba/assess_line":
            body = read_json_body(handler)

            athlete_id = body.get("athleteId")
            stat = (body.get("stat") or "pts").strip().lower()
            line = body.get("line")
            opp_id = body.get("opponentTeamId")

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

            sim = simulate_props(
                season_avg=season_avg,
                season_minutes=season_minutes,
                last_games_10=last_games_10,
                opp_mult=opp_adj,
                est_minutes_point=est_min,
                season_shoot=season_shoot,
                n=10000,
            )

            samples = sim["samples"].get(stat, [])
            p_over = prob_over(samples, line_f)
            p_under = 1.0 - p_over
            fair = fair_line(samples)
            alts = alt_lines_probs(samples, stat, center_line=line_f)

            proj = sim["projection"].get(stat, 0.0)
            dist = sim["distribution"].get(stat, {})

            return 200, {
                "athleteId": athlete_id_int,
                "stat": stat,
                "line": line_f,
                "probOver": round(p_over, 4),
                "probUnder": round(p_under, 4),
                "fairLine": fair,
                "projectionP50": proj,
                "band": dist,
                "altLines": alts,
                "meta": {
                    "opponentTeamId": opp_id_int,
                    "seasonYearUsed": season_year,
                    "webStatsUrl": web_url,
                    "nSamples": sim["diagnostics"].get("n"),
                    "minutesMu": sim["diagnostics"].get("minutesMu"),
                    "minutesSd": sim["diagnostics"].get("minutesSd"),
                    "minutesStability": sim["diagnostics"].get("minutesStability"),
                    "oppAdj": opp_adj,
                    "confidence": meta.get("confidence") or "—",
                    "ptsEngine": (sim["diagnostics"].get("engine") or {}).get("pts"),
                },
                "debug": {
                    "baseProjection": base.get("projection"),
                    "gamelogDebug": dbg10,
                    "summaryEnrichDebug": enrich_dbg,
                    "seasonShooting": season_shoot,
                    "simDiagnostics": sim["diagnostics"],
                },
            }

        if parsed.path == "/api/nba/track":
            body = read_json_body(handler)
            rec = add_prediction(body)
            return 200, {"saved": rec}

        if parsed.path == "/api/nba/settle":
            body = read_json_body(handler)
            pid = body.get("id")
            try:
                pid = int(pid)
            except Exception:
                return 400, {"error": "id must be an integer"}

            rec = settle_prediction(pid)
            return 200, {"settled": rec}

        return None

    except Exception as e:
        return 500, _err_with_trace(e)
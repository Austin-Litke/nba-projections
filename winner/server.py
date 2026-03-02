# winner/server.py



from __future__ import annotations

import math
import os
import sys
import json
import traceback
from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

# Ensure "winner/" is on import path so "sports.api.*" works reliably
sys.path.insert(0, os.path.dirname(__file__))

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
    extract_season_shooting_from_web_stats,   # NEW
)
from sports.api.nba_gamelog import (
    build_last_games,
    build_vs_opponent,
    enrich_games_with_summary,                # NEW
)
from sports.api.nba_projection import (
    build_projection,
)

from sports.api.nba_simulator import (
    simulate_props,
    prob_over,
    fair_line,
    alt_lines_probs,
)

PORT = 8000


def _json_bytes(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


def _read_json_body(handler: SimpleHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    raw = handler.rfile.read(length) if length > 0 else b"{}"
    try:
        return json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        return {}


class Handler(SimpleHTTPRequestHandler):
    """
    Serves static files from the winner/ folder.
    Your sports UI lives at /sports/...
    """

    def log_message(self, fmt, *args):
        print(fmt % args)

    def send_json(self, code: int, obj: dict):
        body = _json_bytes(obj)
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)

        try:
            if parsed.path == "/api/nba/scoreboard":
                qs = parse_qs(parsed.query)
                date = (qs.get("date", [""])[0] or "").strip()
                if not date.isdigit() or len(date) != 8:
                    self.send_json(400, {"error": "date=YYYYMMDD required"})
                    return

                url = ESPN_SCOREBOARD.format(date=date)
                data = safe_json_load(http_get(url))
                self.send_json(200, data)
                return

            if parsed.path == "/api/nba/teams":
                data = safe_json_load(http_get(ESPN_TEAMS))
                self.send_json(200, data)
                return

            if parsed.path == "/api/nba/roster":
                qs = parse_qs(parsed.query)
                team_id = (qs.get("teamId", [""])[0] or "").strip()
                if not team_id.isdigit():
                    self.send_json(400, {"error": "teamId required"})
                    return

                url = ESPN_ROSTER.format(teamId=team_id)
                data = safe_json_load(http_get(url))
                self.send_json(200, data)
                return

            if parsed.path == "/api/nba/player_webstats_raw":
                qs = parse_qs(parsed.query)
                athlete_id = (qs.get("athleteId", [""])[0] or "").strip()
                if not athlete_id.isdigit():
                    self.send_json(400, {"error": "athleteId required"})
                    return

                url = ESPN_WEB_STATS.format(athleteId=int(athlete_id))
                data = safe_json_load(http_get(url))
                self.send_json(200, {"webStatsUrl": url, "data": data.get("data", data)})
                return

            if parsed.path == "/api/nba/player_gamelog_raw":
                qs = parse_qs(parsed.query)
                athlete_id = (qs.get("athleteId", [""])[0] or "").strip()
                if not athlete_id.isdigit():
                    self.send_json(400, {"error": "athleteId required"})
                    return

                url = ESPN_WEB_GAMELOG.format(athleteId=int(athlete_id))
                data = safe_json_load(http_get(url))
                self.send_json(200, {"gamelogUrl": url, "data": data.get("data", data)})
                return

            if parsed.path == "/api/nba/player":
                qs = parse_qs(parsed.query)
                athlete_id = (qs.get("athleteId", [""])[0] or "").strip()
                if not athlete_id.isdigit():
                    self.send_json(400, {"error": "athleteId required"})
                    return

                athlete_id_int = int(athlete_id)

                athlete_url = ESPN_CORE_ATHLETE.format(athleteId=athlete_id_int)
                athlete = safe_json_load(http_get(athlete_url))
                name = athlete.get("displayName") or athlete.get("fullName") or athlete.get("name") or "Player"

                web_url = ESPN_WEB_STATS.format(athleteId=athlete_id_int)
                web = safe_json_load(http_get(web_url))

                season_year = get_current_season_year()
                season_avg = extract_season_averages_from_web_stats(web, preferred_year=season_year)

                self.send_json(200, {
                    "athleteId": athlete_id_int,
                    "name": name,
                    "team": None,
                    "seasonAverages": season_avg,
                    "debug": {
                        "athleteUrl": athlete_url,
                        "webStatsUrl": web_url,
                        "seasonYearUsed": season_year,
                    }
                })
                return

            if parsed.path == "/api/nba/player_gamelog":
                qs = parse_qs(parsed.query)
                athlete_id = (qs.get("athleteId", [""])[0] or "").strip()
                limit = (qs.get("limit", ["5"])[0] or "5").strip()

                if not athlete_id.isdigit():
                    self.send_json(400, {"error": "athleteId required"})
                    return

                try:
                    limit_int = max(1, min(25, int(limit)))
                except Exception:
                    limit_int = 5

                games, dbg = build_last_games(int(athlete_id), limit=limit_int)
                self.send_json(200, {"athleteId": int(athlete_id), "games": games, "debug": dbg})
                return
            
            
                        # List tracked predictions (optionally filter by athleteId)
            if parsed.path == "/api/nba/tracked":
                qs = parse_qs(parsed.query)
                aid = (qs.get("athleteId", [""])[0] or "").strip()
                athlete_id = int(aid) if aid.isdigit() else None
                preds = list_predictions(athlete_id)
                self.send_json(200, {"athleteId": athlete_id, "predictions": preds})
                return

            # Metrics (Brier/logloss/calibration bins)
            if parsed.path == "/api/nba/tracked_metrics":
                qs = parse_qs(parsed.query)
                aid = (qs.get("athleteId", [""])[0] or "").strip()
                athlete_id = int(aid) if aid.isdigit() else None
                preds = list_predictions(athlete_id)
                m = tracker_metrics(preds)
                self.send_json(200, {"athleteId": athlete_id, "metrics": m})
                return

            # Monte Carlo projection (component PTS when available)
            if parsed.path == "/api/nba/player_projection":
                qs = parse_qs(parsed.query)
                athlete_id = (qs.get("athleteId", [""])[0] or "").strip()
                opp_id = (qs.get("opponentTeamId", [""])[0] or "").strip()

                if not athlete_id.isdigit():
                    self.send_json(400, {"error": "athleteId required"})
                    return

                athlete_id_int = int(athlete_id)
                season_year = get_current_season_year()

                web_url = ESPN_WEB_STATS.format(athleteId=athlete_id_int)
                web = safe_json_load(http_get(web_url))

                season_avg = extract_season_averages_from_web_stats(web, preferred_year=season_year)
                season_minutes = extract_season_avg_minutes_from_web_stats(web, preferred_year=season_year)
                season_shoot = extract_season_shooting_from_web_stats(web, preferred_year=season_year)

                last_games_5, _dbg5 = build_last_games(athlete_id_int, limit=5)
                last_games_10, dbg10 = build_last_games(athlete_id_int, limit=10)

                # enrich last 10 with FG/3PT/FT from summary (needed for component points)
                last_games_10, enrich_dbg = enrich_games_with_summary(last_games_10, athlete_id_int)

                vs_games = []
                opp_id_int = None
                try:
                    if opp_id and str(opp_id).strip().isdigit():
                        opp_id_int = int(str(opp_id).strip())
                except Exception:
                    opp_id_int = None

                if opp_id_int is not None:
                    vs_games, _dbgvs = build_vs_opponent(athlete_id_int, opp_id_int, limit=25)

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

                out = {
                    "projection": sim["projection"],
                    "distribution": sim["distribution"],
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
                    }
                }

                self.send_json(200, out)
                return

        except Exception as e:
            traceback.print_exc()
            self.send_json(500, {"error": str(e)})
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)

        try:
            if parsed.path == "/api/nba/assess_line":
                body = _read_json_body(self)

                athlete_id = body.get("athleteId")
                stat = (body.get("stat") or "pts").strip().lower()
                line = body.get("line")
                opp_id = body.get("opponentTeamId")

                try:
                    athlete_id_int = int(athlete_id)
                except Exception:
                    self.send_json(400, {"error": "athleteId must be an integer"})
                    return

                if stat not in ("pts", "reb", "ast"):
                    self.send_json(400, {"error": "stat must be one of: pts, reb, ast"})
                    return

                try:
                    line_f = float(line)
                except Exception:
                    self.send_json(400, {"error": "line must be a number"})
                    return

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
                opp_id_int = None
                try:
                    if opp_id is not None and str(opp_id).strip().isdigit():
                        opp_id_int = int(str(opp_id).strip())
                except Exception:
                    opp_id_int = None

                if opp_id_int is not None:
                    vs_games, _dbgvs = build_vs_opponent(athlete_id_int, opp_id_int, limit=25)

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

                self.send_json(200, {
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
                    }
                })
                return
            
            
                        # Track a prediction result (store it)
            # Body:
            # { athleteId, stat, line, probOver, fairLine, projectionP50, opponentTeamId?, gameId?, gameDate?, meta? }
            if parsed.path == "/api/nba/track":
                body = _read_json_body(self)
                rec = add_prediction(body)
                self.send_json(200, {"saved": rec})
                return

            # Settle a prediction by id (pull actual from ESPN summary)
            # Body: { id }
            if parsed.path == "/api/nba/settle":
                body = _read_json_body(self)
                pid = body.get("id")
                try:
                    pid = int(pid)
                except Exception:
                    self.send_json(400, {"error": "id must be an integer"})
                    return

                rec = settle_prediction(pid)
                self.send_json(200, {"settled": rec})
                return

        except Exception as e:
            traceback.print_exc()
            self.send_json(500, {"error": str(e)})
            return

        self.send_json(404, {"error": "Not found"})


def run():
    root = os.path.dirname(__file__)
    os.chdir(root)

    print(f"Serving Winner Arcade at http://localhost:{PORT}")
    print("NBA proxy:")
    print("  /api/nba/scoreboard?date=YYYYMMDD")
    print("  /api/nba/teams")
    print("  /api/nba/roster?teamId=25")
    print("  /api/nba/player?athleteId=1966")
    print("  /api/nba/player_gamelog?athleteId=1966&limit=5")
    print("  /api/nba/player_projection?athleteId=1966&opponentTeamId=6")
    print('  POST /api/nba/assess_line  {"athleteId":1966,"stat":"pts","line":25.5,"opponentTeamId":6}')

    httpd = HTTPServer(("0.0.0.0", PORT), Handler)
    httpd.serve_forever()


if __name__ == "__main__":
    run()
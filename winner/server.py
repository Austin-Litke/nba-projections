# winner/server.py

from __future__ import annotations

import math
import os
import sys
import json
import mimetypes
import traceback
from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

# Ensure "winner/" is on import path so "sports.api.*" works reliably
sys.path.insert(0, os.path.dirname(__file__))

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
)
from sports.api.nba_gamelog import (
    build_last_games,
    build_vs_opponent,
)
from sports.api.nba_projection import (
    build_projection,
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


def _normal_cdf(x: float, mu: float, sigma: float) -> float:
    # Normal CDF using erf (stdlib)
    if sigma <= 1e-9:
        return 0.5
    z = (x - mu) / (sigma * math.sqrt(2.0))
    return 0.5 * (1.0 + math.erf(z))


def _sample_std(vals: list[float]) -> float | None:
    if not vals or len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    var = sum((v - m) ** 2 for v in vals) / (len(vals) - 1)
    return math.sqrt(var)


class Handler(SimpleHTTPRequestHandler):
    """
    Serves static files from the winner/ folder.
    Your sports UI lives at /sports/...
    """

    # Optional: less noisy logs
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

        # ---------------- NBA API PROXY ROUTES ----------------

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

            # Raw web stats passthrough (debugging)
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

            # Raw gamelog passthrough (debugging)
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

            # Player: season averages
            if parsed.path == "/api/nba/player":
                qs = parse_qs(parsed.query)
                athlete_id = (qs.get("athleteId", [""])[0] or "").strip()
                if not athlete_id.isdigit():
                    self.send_json(400, {"error": "athleteId required"})
                    return

                athlete_id_int = int(athlete_id)

                # Name (core endpoint)
                athlete_url = ESPN_CORE_ATHLETE.format(athleteId=athlete_id_int)
                athlete = safe_json_load(http_get(athlete_url))
                name = athlete.get("displayName") or athlete.get("fullName") or athlete.get("name") or "Player"

                # Stats (web endpoint)
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
                        "method": "web stats schema container names[] + statistics[]",
                    }
                })
                return

            # Player gamelog (last N games)
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

            # Player projection
            if parsed.path == "/api/nba/player_projection":
                qs = parse_qs(parsed.query)
                athlete_id = (qs.get("athleteId", [""])[0] or "").strip()
                opp_id = (qs.get("opponentTeamId", [""])[0] or "").strip()

                if not athlete_id.isdigit():
                    self.send_json(400, {"error": "athleteId required"})
                    return

                athlete_id_int = int(athlete_id)
                season_year = get_current_season_year()

                # Pull web stats once
                web_url = ESPN_WEB_STATS.format(athleteId=athlete_id_int)
                web = safe_json_load(http_get(web_url))

                season_avg = extract_season_averages_from_web_stats(web, preferred_year=season_year)
                season_minutes = extract_season_avg_minutes_from_web_stats(web, preferred_year=season_year)

                last_games, _dbg = build_last_games(athlete_id_int, limit=5)

                vs_games = []
                if opp_id.isdigit():
                    vs_games, _dbg2 = build_vs_opponent(athlete_id_int, int(opp_id), limit=25)

                out = build_projection(season_avg, season_minutes, last_games, vs_games)
                out["debug"] = {
                    "webStatsUrl": web_url,
                    "seasonYearUsed": season_year,
                    "opponentTeamId": int(opp_id) if opp_id.isdigit() else None,
                }
                self.send_json(200, out)
                return

        except Exception as e:
            traceback.print_exc()
            self.send_json(500, {"error": str(e)})
            return

        # ---------------- STATIC FILES ----------------
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)

        try:
            # NEW: Assess a manual line (probability of going OVER)
            # Body: { athleteId, stat: "pts|reb|ast", line: number, opponentTeamId?: number }
            if parsed.path == "/api/nba/assess_line":
                body = _read_json_body(self)

                athlete_id = body.get("athleteId")
                stat = (body.get("stat") or "pts").strip().lower()
                line = body.get("line")
                opp_id = body.get("opponentTeamId")  # optional

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

                # 1) Build projection mean (μ) using same pipeline as /player_projection
                season_year = get_current_season_year()

                web_url = ESPN_WEB_STATS.format(athleteId=athlete_id_int)
                web = safe_json_load(http_get(web_url))

                season_avg = extract_season_averages_from_web_stats(web, preferred_year=season_year)
                season_minutes = extract_season_avg_minutes_from_web_stats(web, preferred_year=season_year)

                last_games_5, _dbg5 = build_last_games(athlete_id_int, limit=5)

                vs_games = []
                opp_id_int = None
                try:
                    if opp_id is not None and str(opp_id).strip().isdigit():
                        opp_id_int = int(str(opp_id).strip())
                except Exception:
                    opp_id_int = None

                if opp_id_int is not None:
                    vs_games, _dbgvs = build_vs_opponent(athlete_id_int, opp_id_int, limit=25)

                proj_out = build_projection(season_avg, season_minutes, last_games_5, vs_games)
                mean = (proj_out.get("projection") or {}).get(stat)

                # fallback to season avg if projection missing
                if mean is None and isinstance(season_avg, dict):
                    mean = season_avg.get(stat)
                if mean is None:
                    mean = 0.0

                mean = float(mean)

                # 2) Estimate std dev (σ) from recent games (use up to last 10)
                last_games_10, _dbg10 = build_last_games(athlete_id_int, limit=10)
                vals = []
                for g in last_games_10:
                    v = g.get(stat)
                    if isinstance(v, (int, float)):
                        vals.append(float(v))

                sigma = _sample_std(vals)

                # If not enough sample variance, fallback by stat
                if sigma is None or sigma <= 1e-9:
                    sigma = 5.0 if stat == "pts" else (3.0 if stat == "reb" else 2.5)

                # 3) Probability P(X > line)
                # Continuity correction helps with discrete stats.
                continuity = 0.5
                threshold = line_f + continuity

                p_over = 1.0 - _normal_cdf(threshold, mean, float(sigma))
                p_over = max(0.0, min(1.0, p_over))

                note = f"μ={mean:.2f}, σ={float(sigma):.2f}, n={len(vals)} recent games."
                self.send_json(200, {
                    "athleteId": athlete_id_int,
                    "stat": stat,
                    "line": line_f,
                    "prob": p_over,
                    "mean": mean,
                    "std": float(sigma),
                    "n": len(vals),
                    "note": note,
                    "meta": {
                        "opponentTeamId": opp_id_int,
                        "seasonYearUsed": season_year,
                        "webStatsUrl": web_url,
                    }
                })
                return

        except Exception as e:
            traceback.print_exc()
            self.send_json(500, {"error": str(e)})
            return

        # If unknown POST route
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
    print("  POST /api/nba/assess_line  {athleteId, stat, line, opponentTeamId?}")

    httpd = HTTPServer(("0.0.0.0", PORT), Handler)
    httpd.serve_forever()


if __name__ == "__main__":
    run()
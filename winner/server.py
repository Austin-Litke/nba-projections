# winner/server.py

from __future__ import annotations

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

            # Player: season averages (existing behavior)
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

            # NEW: Player projection
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
        # Let SimpleHTTPRequestHandler handle everything else.
        # This serves /index.html, /sports/index.html, /sports/js/main.js, etc.
        return super().do_GET()


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

    httpd = HTTPServer(("0.0.0.0", PORT), Handler)
    httpd.serve_forever()


if __name__ == "__main__":
    run()

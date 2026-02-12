from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import json
import time
import urllib.request
import traceback

ESPN_SITE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
ESPN_CORE = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba"
ESPN_WEB_STATS = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{athleteId}/stats?region=us&lang=en&contentorigin=espn"

CACHE = {}

def cached_get(key, ttl_sec, fetch_fn):
    now = time.time()
    if key in CACHE:
        exp, payload = CACHE[key]
        if now < exp:
            return payload
    payload = fetch_fn()
    CACHE[key] = (now + ttl_sec, payload)
    return payload

def http_get(url, timeout=12):
    if not isinstance(url, str):
        raise ValueError("Invalid URL")

    if url.startswith("http://"):
        url = "https://" + url.split("://", 1)[1]
    if url.startswith("//"):
        url = "https:" + url

    if not url.lower().startswith("https://"):
        raise ValueError(f"Blocked URL (only https allowed): {url}")

    print(f"[http_get] fetching: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "winner-arcade/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")

def safe_json_load(s):
    return json.loads(s)

def get_current_season_year():
    """
    ESPN CORE league object year (often the ending year of the season).
    Cached for 1 hour.
    """
    def fetch():
        league_json = safe_json_load(http_get(f"{ESPN_CORE}?lang=en&region=us"))
        season = league_json.get("season")
        if isinstance(season, dict):
            ref = season.get("$ref") or season.get("href")
            if ref:
                try:
                    season_json = safe_json_load(http_get(ref))
                    y = season_json.get("year")
                    if isinstance(y, int):
                        return y
                except:
                    pass
            y = season.get("year")
            if isinstance(y, int):
                return y
        return None
    return cached_get("current_season_year", 3600, fetch)

def _to_float(x):
    try:
        return float(x)
    except:
        return None

def extract_season_averages_from_web_stats(web_json, preferred_year=None):
    """
    Parse ESPN table:
      names: [ ... "avgRebounds", "avgAssists", ... "avgPoints" ]
      statistics: [ { season: {year, displayName}, stats: [ ... aligned ... ] }, ... ]

    preferred_year:
      - Try to use this season year if present
      - Otherwise use the latest season.year in the table
    """
    # find the table that includes names + statistics
    # sometimes nested, so do a deep walk to locate the first matching table
    table = None

    def walk(node):
        nonlocal table
        if table is not None:
            return
        if isinstance(node, dict):
            names = node.get("names")
            stats_rows = node.get("statistics")
            if isinstance(names, list) and isinstance(stats_rows, list):
                if "avgPoints" in names and "avgRebounds" in names and "avgAssists" in names:
                    table = node
                    return
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for it in node:
                walk(it)

    walk(web_json)

    if table is None:
        return {
            "pts": None, "reb": None, "ast": None,
            "debug": {"method": "season-table", "error": "No matching names/statistics table found"}
        }

    names = table["names"]
    rows = table["statistics"]

    idx_pts = names.index("avgPoints")
    idx_reb = names.index("avgRebounds")
    idx_ast = names.index("avgAssists")

    # choose row by preferred year or latest
    chosen = None

    def row_year(r):
        try:
            return int((r.get("season") or {}).get("year"))
        except:
            return None

    # Try preferred year first
    if preferred_year is not None:
        for r in rows:
            y = row_year(r)
            if y == int(preferred_year):
                chosen = r
                break

    # If not found, pick max year
    if chosen is None:
        best_y = None
        for r in rows:
            y = row_year(r)
            if y is not None and (best_y is None or y > best_y):
                best_y = y
                chosen = r

    if chosen is None:
        return {
            "pts": None, "reb": None, "ast": None,
            "debug": {"method": "season-table", "error": "Could not select a season row"}
        }

    stats_arr = chosen.get("stats")
    if not isinstance(stats_arr, list) or max(idx_pts, idx_reb, idx_ast) >= len(stats_arr):
        return {
            "pts": None, "reb": None, "ast": None,
            "debug": {"method": "season-table", "error": "Season row stats array missing or too short"}
        }

    pts = _to_float(stats_arr[idx_pts])
    reb = _to_float(stats_arr[idx_reb])
    ast = _to_float(stats_arr[idx_ast])

    return {
        "pts": pts,
        "reb": reb,
        "ast": ast,
        "debug": {
            "method": "season-table",
            "preferredYear": preferred_year,
            "seasonPicked": chosen.get("season"),
            "indexMap": {"avgPoints": idx_pts, "avgRebounds": idx_reb, "avgAssists": idx_ast}
        }
    }

class Handler(SimpleHTTPRequestHandler):
    def send_json(self, code, obj):
        payload = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/nba/scoreboard":
            qs = parse_qs(parsed.query)
            date = (qs.get("date", [""])[0] or "").strip()
            url = f"{ESPN_SITE}/scoreboard"
            if date:
                url += f"?dates={date}"
            try:
                payload = cached_get(f"scoreboard:{date}", 10, lambda: http_get(url))
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(payload.encode("utf-8"))
            except Exception as e:
                traceback.print_exc()
                self.send_json(500, {"error": str(e)})
            return

        if parsed.path == "/api/nba/teams":
            try:
                payload = cached_get("teams", 3600, lambda: http_get(f"{ESPN_SITE}/teams"))
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(payload.encode("utf-8"))
            except Exception as e:
                traceback.print_exc()
                self.send_json(500, {"error": str(e)})
            return

        if parsed.path == "/api/nba/roster":
            qs = parse_qs(parsed.query)
            team_id = (qs.get("teamId", [""])[0] or "").strip()
            if not team_id.isdigit():
                self.send_json(400, {"error": "teamId is required (numeric)."})
                return
            try:
                payload = cached_get(
                    f"roster:{team_id}",
                    300,
                    lambda: http_get(f"{ESPN_SITE}/teams/{team_id}/roster")
                )
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(payload.encode("utf-8"))
            except Exception as e:
                traceback.print_exc()
                self.send_json(500, {"error": str(e)})
            return

        if parsed.path == "/api/nba/player_webstats_raw":
            qs = parse_qs(parsed.query)
            athlete_id = (qs.get("athleteId", [""])[0] or "").strip()
            if not athlete_id.isdigit():
                self.send_json(400, {"error": "athleteId is required (numeric)."})
                return
            try:
                web_url = ESPN_WEB_STATS.format(athleteId=athlete_id)
                web_json = safe_json_load(http_get(web_url))
                self.send_json(200, {"webStatsUrl": web_url, "data": web_json})
            except Exception as e:
                traceback.print_exc()
                self.send_json(500, {"error": str(e)})
            return

        if parsed.path == "/api/nba/player":
            qs = parse_qs(parsed.query)
            athlete_id = (qs.get("athleteId", [""])[0] or "").strip()
            if not athlete_id.isdigit():
                self.send_json(400, {"error": "athleteId is required (numeric)."})
                return

            athlete_url = f"{ESPN_CORE}/athletes/{athlete_id}?lang=en&region=us"
            web_url = ESPN_WEB_STATS.format(athleteId=athlete_id)

            try:
                season_year = get_current_season_year()

                athlete_json = safe_json_load(http_get(athlete_url))
                web_json = safe_json_load(http_get(web_url))

                extracted = extract_season_averages_from_web_stats(web_json, preferred_year=season_year)

                self.send_json(200, {
                    "athleteId": int(athlete_id),
                    "name": athlete_json.get("fullName") or athlete_json.get("displayName"),
                    "team": (athlete_json.get("team") or {}).get("displayName") if isinstance(athlete_json.get("team"), dict) else None,
                    "seasonAverages": {
                        "pts": extracted["pts"],
                        "reb": extracted["reb"],
                        "ast": extracted["ast"]
                    },
                    "debug": {
                        "athleteUrl": athlete_url,
                        "webStatsUrl": web_url,
                        **extracted["debug"]
                    }
                })

            except Exception as e:
                traceback.print_exc()
                self.send_json(500, {"error": str(e), "athleteUrl": athlete_url, "webStatsUrl": web_url})
            return

        super().do_GET()

if __name__ == "__main__":
    print("Serving Winner Arcade at http://localhost:8000")
    print("NBA proxy routes:")
    print("  /api/nba/scoreboard?date=YYYYMMDD")
    print("  /api/nba/teams")
    print("  /api/nba/roster?teamId=25")
    print("  /api/nba/player?athleteId=1966")
    print("  /api/nba/player_webstats_raw?athleteId=1966")
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import json
import time
import urllib.request
import traceback

ESPN_SITE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
ESPN_CORE = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba"

ESPN_WEB_STATS = (
    "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{athleteId}/stats"
    "?region=us&lang=en&contentorigin=espn"
)

ESPN_WEB_GAMELOG = (
    "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{athleteId}/gamelog"
    "?region=us&lang=en"
)

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

def _to_float(x):
    try:
        return float(x)
    except:
        return None

def _to_int(x):
    try:
        return int(float(x))
    except:
        return None

def get_current_season_year():
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

# ---------------- SEASON AVERAGES ----------------

def extract_season_averages_from_web_stats(web_json, preferred_year=None):
    table = None

    def walk(node):
        nonlocal table
        if table is not None:
            return
        if isinstance(node, dict):
            names = node.get("names") or node.get("keys")
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

    if isinstance(web_json, dict) and isinstance(web_json.get("data"), dict):
        walk(web_json["data"])
    walk(web_json)

    if table is None:
        return {"pts": None, "reb": None, "ast": None,
                "debug": {"method": "season-table", "error": "No matching names/statistics table found"}}

    names = table.get("names") or table.get("keys")
    rows = table.get("statistics", [])

    idx_pts = names.index("avgPoints")
    idx_reb = names.index("avgRebounds")
    idx_ast = names.index("avgAssists")

    def row_year(r):
        try:
            return int((r.get("season") or {}).get("year"))
        except:
            return None

    chosen = None
    if preferred_year is not None:
        for r in rows:
            if row_year(r) == int(preferred_year):
                chosen = r
                break

    if chosen is None:
        best_y = None
        for r in rows:
            y = row_year(r)
            if y is not None and (best_y is None or y > best_y):
                best_y = y
                chosen = r

    if chosen is None:
        return {"pts": None, "reb": None, "ast": None,
                "debug": {"method": "season-table", "error": "Could not select a season row"}}

    stats_arr = chosen.get("stats")
    if not isinstance(stats_arr, list) or max(idx_pts, idx_reb, idx_ast) >= len(stats_arr):
        return {"pts": None, "reb": None, "ast": None,
                "debug": {"method": "season-table", "error": "Season row stats array missing or too short"}}

    return {
        "pts": _to_float(stats_arr[idx_pts]),
        "reb": _to_float(stats_arr[idx_reb]),
        "ast": _to_float(stats_arr[idx_ast]),
        "debug": {
            "method": "season-table",
            "preferredYear": preferred_year,
            "seasonPicked": chosen.get("season"),
            "indexMap": {"avgPoints": idx_pts, "avgRebounds": idx_reb, "avgAssists": idx_ast}
        }
    }

# ---------------- GAME LOGS (Option A via SUMMARY endpoint) ----------------

def summary_urls(game_id: str):
    return [
        f"{ESPN_SITE}/summary?event={game_id}",
        f"https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}",
    ]

def fetch_summary_json(game_id: str):
    key = f"summary:{game_id}"
    def fetch():
        last_err = None
        tried = summary_urls(game_id)
        for u in tried:
            try:
                return {"url": u, "json": safe_json_load(http_get(u))}
            except Exception as e:
                last_err = e
                continue
        raise RuntimeError(f"Could not fetch summary for gameId={game_id}. Tried={tried}. Last error={last_err}")
    payload = cached_get(key, 600, fetch)  # 10 min cache
    return payload["json"], payload["url"]

def extract_player_line_from_summary(summary_json, athlete_id: int):
    """
    ESPN summary JSON usually has:
      summary["boxscore"]["players"] = [
        { "team": {...}, "statistics": [ { "labels": [...], "athletes": [ { "athlete": {id}, "stats":[...] }, ... ] } ] },
        ...
      ]
    We:
      - iterate all athletes across both teams
      - match athlete.id
      - map labels -> stats values
    """
    box = summary_json.get("boxscore") if isinstance(summary_json, dict) else None
    if not isinstance(box, dict):
        return None, {"note": "No boxscore object in summary"}

    players = box.get("players")
    if not isinstance(players, list):
        return None, {"note": "No boxscore.players list in summary"}

    target_id = int(athlete_id)

    def norm(s): return str(s).strip().lower()

    best = None
    best_dbg = None

    for team_block in players:
        stats_groups = team_block.get("statistics")
        if not isinstance(stats_groups, list):
            continue

        for group in stats_groups:
            labels = group.get("labels")
            athletes = group.get("athletes")
            if not isinstance(labels, list) or not isinstance(athletes, list):
                continue

            label_map = {norm(lbl): i for i, lbl in enumerate(labels)}

            for row in athletes:
                a = row.get("athlete")
                if not isinstance(a, dict):
                    continue
                try:
                    if int(a.get("id")) != target_id:
                        continue
                except:
                    continue

                stats = row.get("stats")
                if not isinstance(stats, list):
                    continue

                def get(keys, conv):
                    for k in keys:
                        i = label_map.get(norm(k))
                        if i is not None and i < len(stats):
                            return conv(stats[i])
                    return None

                line = {
                    "min": get(["min", "minutes"], _to_float),
                    "pts": get(["pts", "points"], _to_int),
                    "reb": get(["reb", "rebounds", "trb"], _to_float),
                    "ast": get(["ast", "assists"], _to_float),
                }

                score = sum(1 for k in ("min","pts","reb","ast") if line[k] is not None)
                dbg = {
                    "groupName": group.get("name"),
                    "labelsSample": labels[:20],
                    "filled": score
                }

                if best is None or score > best_dbg["filled"]:
                    best = line
                    best_dbg = dbg

                if score >= 3:
                    return best, best_dbg

    return best, (best_dbg or {"note": "Player not found in summary boxscore.players"})

def parse_gamelog_events(gamelog_json):
    data = gamelog_json.get("data", gamelog_json) if isinstance(gamelog_json, dict) else gamelog_json
    if not isinstance(data, dict):
        return None, {"error": "gamelog data not a dict"}

    events = data.get("events")
    if not isinstance(events, dict):
        return None, {"error": "events not a dict", "eventsType": type(events).__name__}

    items = []
    for game_id, ev in events.items():
        if isinstance(ev, dict):
            items.append((str(game_id), ev))

    def sort_key(t):
        ev = t[1]
        gd = ev.get("gameDate") or ev.get("date")
        return gd or ""

    items.sort(key=sort_key, reverse=True)
    return items, {"eventsCount": len(items)}

def build_last_games(athlete_id: int, limit: int):
    gamelog_url = ESPN_WEB_GAMELOG.format(athleteId=athlete_id)
    gamelog_json = safe_json_load(http_get(gamelog_url))

    items, dbg = parse_gamelog_events(gamelog_json)
    if items is None:
        return [], {"method": "gamelog+summary", **dbg, "gamelogUrl": gamelog_url}

    out = []
    per_game_dbg = []
    for game_id, ev in items[:max(0, int(limit))]:
        summary_json, used_url = fetch_summary_json(game_id)
        line, line_dbg = extract_player_line_from_summary(summary_json, athlete_id)

        row = {
            "gameId": game_id,
            "date": (ev.get("gameDate") or ev.get("date") or "")[:10] if isinstance(ev.get("gameDate") or ev.get("date"), str) else None,
            "opponent": ev.get("opponent"),
            "result": ev.get("gameResult"),
            "score": ev.get("score"),
            "min": None, "pts": None, "reb": None, "ast": None
        }
        if line:
            row.update(line)

        out.append(row)
        per_game_dbg.append({
            "gameId": game_id,
            "summaryUrlUsed": used_url,
            **(line_dbg or {})
        })

    return out, {
        "method": "gamelog+summary",
        "gamelogUrl": gamelog_url,
        **dbg,
        "perGame": per_game_dbg[:10]
    }


def build_vs_opponent(athlete_id: int, opponent_team_id: int, limit: int):
    gamelog_url = ESPN_WEB_GAMELOG.format(athleteId=athlete_id)
    gamelog_json = safe_json_load(http_get(gamelog_url))

    items, dbg = parse_gamelog_events(gamelog_json)
    if items is None:
        return [], {"method": "vs-opponent", **dbg}

    out = []
    opp_id_str = str(opponent_team_id)

    for game_id, ev in items:
        # opponent info comes from gamelog event
        opp = ev.get("opponent") or {}
        ev_opp_id = str(opp.get("teamId") or "")

        if ev_opp_id != opp_id_str:
            continue

        summary_json, used_url = fetch_summary_json(game_id)
        line, line_dbg = extract_player_line_from_summary(summary_json, athlete_id)

        row = {
            "gameId": game_id,
            "date": (ev.get("gameDate") or ev.get("date") or "")[:10],
            "opponent": opp.get("displayName") or ev.get("opponent"),
            "result": ev.get("gameResult"),
            "score": ev.get("score"),
            "min": None,
            "pts": None,
            "reb": None,
            "ast": None
        }

        if line:
            row.update(line)

        out.append(row)

        if len(out) >= int(limit):
            break

    return out, {
        "method": "vs-opponent",
        "opponentTeamId": opponent_team_id,
        "matchedGames": len(out)
    }


# ---------------- HTTP HANDLER ----------------

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

        # Debug: raw summary JSON
        if parsed.path == "/api/nba/summary_raw":
            qs = parse_qs(parsed.query)
            game_id = (qs.get("gameId", [""])[0] or "").strip()
            if not game_id.isdigit():
                self.send_json(400, {"error": "gameId is required (numeric)."})
                return
            try:
                j, used = fetch_summary_json(game_id)
                self.send_json(200, {"gameId": game_id, "usedUrl": used, "data": j})
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
                    "seasonAverages": {"pts": extracted["pts"], "reb": extracted["reb"], "ast": extracted["ast"]},
                    "debug": {"athleteUrl": athlete_url, "webStatsUrl": web_url, **extracted["debug"]}
                })
            except Exception as e:
                traceback.print_exc()
                self.send_json(500, {"error": str(e), "athleteUrl": athlete_url, "webStatsUrl": web_url})
            return

        if parsed.path == "/api/nba/player_gamelog":
            qs = parse_qs(parsed.query)
            athlete_id = (qs.get("athleteId", [""])[0] or "").strip()
            limit = (qs.get("limit", ["5"])[0] or "5").strip()

            if not athlete_id.isdigit():
                self.send_json(400, {"error": "athleteId is required (numeric)."})
                return
            try:
                lim = int(limit)
            except:
                lim = 5

            try:
                games, dbg = build_last_games(int(athlete_id), lim)
                self.send_json(200, {"athleteId": int(athlete_id), "games": games, "debug": dbg})
            except Exception as e:
                traceback.print_exc()
                self.send_json(500, {"error": str(e)})
            return


        super().do_GET()

if __name__ == "__main__":
    print("Serving Winner Arcade at http://localhost:8000")
    print("NBA proxy routes:")
    print("  /api/nba/scoreboard?date=YYYYMMDD")
    print("  /api/nba/teams")
    print("  /api/nba/roster?teamId=25")
    print("  /api/nba/player?athleteId=1966")
    print("  /api/nba/player_gamelog?athleteId=1966&limit=5")
    print("  /api/nba/summary_raw?gameId=401810624")
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()

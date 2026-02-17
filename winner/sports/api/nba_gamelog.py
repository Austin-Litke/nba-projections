# winner/sports/api/nba_gamelog.py

from __future__ import annotations
from typing import Optional, Tuple, List

from .nba_client import http_get, safe_json_load, ESPN_WEB_GAMELOG, ESPN_SUMMARY


def _parse_int(x):
    try:
        return int(float(x))
    except Exception:
        return None


def _parse_float(x):
    try:
        return float(x)
    except Exception:
        return None


def _is_nba_team_id(team_id) -> bool:
    """
    ESPN NBA team IDs are typically 1..30.
    All-star / exhibitions often have huge IDs (like 132374).
    """
    try:
        n = int(str(team_id))
        return 1 <= n <= 30
    except Exception:
        return False


def _find_stats_list_for_event(event_obj: dict, names_len: int) -> Optional[list]:
    if isinstance(event_obj.get("stats"), list) and len(event_obj["stats"]) == names_len:
        return event_obj["stats"]

    if isinstance(event_obj.get("statistics"), list) and len(event_obj["statistics"]) == names_len:
        return event_obj["statistics"]

    stack = [event_obj]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for v in node.values():
                stack.append(v)
        elif isinstance(node, list):
            if len(node) == names_len and node and not isinstance(node[0], dict):
                return node
            for v in node:
                stack.append(v)
    return None


def _extract_player_line_from_summary(summary_data: dict, athlete_id: int) -> Optional[dict]:
    box = summary_data.get("boxscore") or {}
    players = box.get("players") or []
    if not isinstance(players, list):
        return None

    target = str(athlete_id)

    for team_block in players:
        stat_tables = team_block.get("statistics") or []
        if not isinstance(stat_tables, list):
            continue

        for table in stat_tables:
            labels = table.get("labels") or table.get("keys") or []
            athletes = table.get("athletes") or []
            if not isinstance(labels, list) or not isinstance(athletes, list):
                continue

            idx = {lab: i for i, lab in enumerate(labels) if isinstance(lab, str)}

            for a in athletes:
                ainfo = a.get("athlete") or {}
                aid = ainfo.get("id")
                if str(aid) != target:
                    continue

                stats = a.get("stats") or []
                if not isinstance(stats, list) or not stats:
                    continue

                def get(lab):
                    i = idx.get(lab)
                    if i is None or i >= len(stats):
                        return None
                    return stats[i]

                # MIN sometimes "34:12"
                min_raw = get("MIN")
                min_v = None
                if isinstance(min_raw, str) and ":" in min_raw:
                    try:
                        mm, ss = min_raw.split(":")
                        min_v = float(mm) + (float(ss) / 60.0)
                    except Exception:
                        min_v = None
                else:
                    min_v = _parse_float(min_raw)

                return {
                    "min": min_v,
                    "pts": _parse_int(get("PTS")),
                    "reb": _parse_int(get("REB")),
                    "ast": _parse_int(get("AST")),
                }

    return None


def _fill_stats_from_summary(game_id: str, athlete_id: int) -> Tuple[Optional[dict], str]:
    url = ESPN_SUMMARY.format(gameId=game_id)
    data = safe_json_load(http_get(url))
    line = _extract_player_line_from_summary(data, athlete_id)
    return line, url


def build_last_games(athlete_id: int, limit: int = 5) -> Tuple[List[dict], dict]:
    """
    Returns (games, debug).
    Filters out non-NBA opponents (e.g., All-Star / special events) by opponentTeamId.
    """
    url = ESPN_WEB_GAMELOG.format(athleteId=athlete_id)
    raw = http_get(url)
    web = safe_json_load(raw)
    data = web.get("data", web)

    names = data.get("names", [])
    events = data.get("events", {})

    debug = {
        "gamelogUrl": url,
        "namesLen": len(names) if isinstance(names, list) else None,
        "eventsType": type(events).__name__,
        "summaryFallbackUsedFor": [],
        "filteredOutNonNbaOpponent": 0,
        "filteredOutNoStats": 0,
        "gamesParsed": 0,
    }

    if not isinstance(names, list) or not isinstance(events, dict) or not names:
        return ([], {**debug, "error": "Bad gamelog shape (missing names/events)"})

    idx_min = names.index("minutes") if "minutes" in names else None
    idx_pts = names.index("points") if "points" in names else None
    idx_reb = names.index("totalRebounds") if "totalRebounds" in names else None
    idx_ast = names.index("assists") if "assists" in names else None

    games = []

    for game_id, ev in events.items():
        if not isinstance(ev, dict):
            continue

        opp = ev.get("opponent") or {}
        opp_team_id = opp.get("teamId") or opp.get("id")

        # ✅ Filter: only real NBA opponents
        if not _is_nba_team_id(opp_team_id):
            debug["filteredOutNonNbaOpponent"] += 1
            continue

        opp_name = opp.get("displayName") or opp.get("shortDisplayName") or opp.get("name") or "—"

        game_date = ev.get("gameDate") or ev.get("date") or ""
        result = ev.get("gameResult") or ev.get("result") or ""
        score = ev.get("score") or ""

        stats_list = _find_stats_list_for_event(ev, len(names))

        def stat_at(idx):
            if stats_list is None or idx is None or idx >= len(stats_list):
                return None
            return stats_list[idx]

        min_v = _parse_float(stat_at(idx_min))
        pts_v = _parse_int(stat_at(idx_pts))
        reb_v = _parse_int(stat_at(idx_reb))
        ast_v = _parse_int(stat_at(idx_ast))

        # If gamelog doesn't carry stats, fall back to summary boxscore
        if (min_v is None and pts_v is None and reb_v is None and ast_v is None):
            try:
                line, _used = _fill_stats_from_summary(str(game_id), athlete_id)
                if line:
                    min_v = line.get("min")
                    pts_v = line.get("pts")
                    reb_v = line.get("reb")
                    ast_v = line.get("ast")
                    debug["summaryFallbackUsedFor"].append(str(game_id))
            except Exception:
                pass

        # If still nothing (DNP / not in boxscore), skip for last-5 purposes
        if (min_v is None and pts_v is None and reb_v is None and ast_v is None):
            debug["filteredOutNoStats"] += 1
            continue

        games.append({
            "gameId": str(game_id),
            "date": game_date,
            "opponent": opp_name,
            "opponentTeamId": str(opp_team_id) if opp_team_id is not None else None,
            "result": result,
            "score": score,
            "min": min_v,
            "pts": pts_v,
            "reb": reb_v,
            "ast": ast_v,
        })

    games.sort(key=lambda g: g.get("date") or "", reverse=True)
    debug["gamesParsed"] = len(games)

    return (games[:limit], debug)


def build_vs_opponent(athlete_id: int, opponent_team_id: int, limit: int = 25) -> Tuple[List[dict], dict]:
    all_games, dbg = build_last_games(athlete_id, limit=999)
    opp_str = str(opponent_team_id)
    vs = [g for g in all_games if (g.get("opponentTeamId") == opp_str)]
    return (vs[:limit], {**dbg, "filteredOpponentTeamId": opp_str, "vsCount": len(vs)})

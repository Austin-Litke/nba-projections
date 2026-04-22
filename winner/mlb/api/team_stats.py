from __future__ import annotations

from mlb.api.client import http_get_json, MLB_STATS_API


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def fetch_team_hitting_stats(season: str) -> dict:
    # Regular season team hitting stats
    url = (
        f"{MLB_STATS_API}/teams/stats"
        f"?sportIds=1"
        f"&season={season}"
        f"&group=hitting"
        f"&stats=season"
    )
    return http_get_json(url)


def build_team_k_environment(season: str) -> dict:
    payload = fetch_team_hitting_stats(season)
    stats = payload.get("stats") or []

    team_rows = []
    for block in stats:
        splits = block.get("splits") or []
        for split in splits:
            team = split.get("team") or {}
            stat = split.get("stat") or {}

            name = team.get("name")
            strikeouts = _safe_float(stat.get("strikeOuts"), 0.0)

            # Prefer plate appearances if present, otherwise estimate from AB+BB+HBP+SF
            plate_appearances = _safe_float(stat.get("plateAppearances"), 0.0)
            if plate_appearances <= 0:
                ab = _safe_float(stat.get("atBats"), 0.0)
                bb = _safe_float(stat.get("baseOnBalls"), 0.0)
                hbp = _safe_float(stat.get("hitByPitch"), 0.0)
                sf = _safe_float(stat.get("sacFlies"), 0.0)
                plate_appearances = ab + bb + hbp + sf

            if not name or plate_appearances <= 0:
                continue

            k_rate = strikeouts / plate_appearances
            team_rows.append({
                "teamName": name,
                "strikeOuts": strikeouts,
                "plateAppearances": plate_appearances,
                "kRate": k_rate,
            })

    if not team_rows:
        return {
            "leagueAvgKRate": 0.225,
            "teams": {},
        }

    league_avg = sum(r["kRate"] for r in team_rows) / len(team_rows)

    teams = {}
    for row in team_rows:
        adj = row["kRate"] / league_avg if league_avg > 0 else 1.0
        adj = max(0.90, min(1.10, adj))

        teams[row["teamName"]] = {
            "kRate": round(row["kRate"], 4),
            "adjustment": round(adj, 3),
            "strikeOuts": int(row["strikeOuts"]),
            "plateAppearances": round(row["plateAppearances"], 1),
        }

    return {
        "leagueAvgKRate": round(league_avg, 4),
        "teams": teams,
    }


def get_team_k_adjustment_for_opponent(team_name: str | None, season: str) -> dict:
    env = build_team_k_environment(season)
    league_avg = env.get("leagueAvgKRate", 0.225)
    teams = env.get("teams", {})

    if not team_name or team_name not in teams:
        return {
            "teamName": team_name,
            "kRate": None,
            "leagueAvgKRate": league_avg,
            "adjustment": 1.0,
            "source": "team_stats_fallback",
        }

    row = teams[team_name]
    return {
        "teamName": team_name,
        "kRate": row.get("kRate"),
        "leagueAvgKRate": league_avg,
        "adjustment": row.get("adjustment", 1.0),
        "source": "team_stats",
    }
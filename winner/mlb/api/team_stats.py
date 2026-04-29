from __future__ import annotations

from mlb.api.client import http_get_json, MLB_STATS_API


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def _team_k_rate_from_stat(stat: dict) -> tuple[float, float, float]:
    strikeouts = _safe_float(stat.get("strikeOuts"), 0.0)

    pa = _safe_float(stat.get("plateAppearances"), 0.0)
    if pa <= 0:
        ab = _safe_float(stat.get("atBats"), 0.0)
        bb = _safe_float(stat.get("baseOnBalls"), 0.0)
        hbp = _safe_float(stat.get("hitByPitch"), 0.0)
        sf = _safe_float(stat.get("sacFlies"), 0.0)
        pa = ab + bb + hbp + sf

    if pa <= 0:
        return strikeouts, pa, 0.0

    return strikeouts, pa, strikeouts / pa


def _fetch_url(url: str) -> dict:
    return http_get_json(url)


def _build_env_from_payload(payload: dict) -> dict:
    stats = payload.get("stats") or []
    rows = []

    for block in stats:
        splits = block.get("splits") or []
        for split in splits:
            team = split.get("team") or {}
            stat = split.get("stat") or {}
            name = team.get("name")

            if not name:
                continue

            strikeouts, pa, k_rate = _team_k_rate_from_stat(stat)
            if pa <= 0 or k_rate <= 0:
                continue

            rows.append({
                "teamName": name,
                "strikeOuts": strikeouts,
                "plateAppearances": pa,
                "kRate": k_rate,
            })

    if not rows:
        return {
            "leagueAvgKRate": 0.225,
            "teams": {},
        }

    league_avg = sum(r["kRate"] for r in rows) / len(rows)

    teams = {}
    for row in rows:
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


def build_team_k_environment(season: str) -> dict:
    url = (
        f"{MLB_STATS_API}/teams/stats"
        f"?sportIds=1"
        f"&season={season}"
        f"&group=hitting"
        f"&stats=season"
    )
    return _build_env_from_payload(_fetch_url(url))


def _split_code_for_pitcher_hand(pitcher_hand: str) -> str | None:
    hand = (pitcher_hand or "").lower()

    if hand.startswith("right"):
        return "vr"  # hitting vs right-handed pitchers
    if hand.startswith("left"):
        return "vl"  # hitting vs left-handed pitchers

    return None


def build_team_k_environment_vs_hand(season: str, pitcher_hand: str) -> dict:
    sit_code = _split_code_for_pitcher_hand(pitcher_hand)
    if not sit_code:
        return {"leagueAvgKRate": 0.225, "teams": {}, "debugSource": "no_hand"}

    # Try several MLB Stats API query shapes.
    # Some deployments expose split data under season, others under seasonAdvanced.
    urls = [
        (
            f"{MLB_STATS_API}/teams/stats"
            f"?sportIds=1"
            f"&season={season}"
            f"&group=hitting"
            f"&stats=season"
            f"&sitCodes={sit_code}"
        ),
        (
            f"{MLB_STATS_API}/teams/stats"
            f"?sportIds=1"
            f"&season={season}"
            f"&group=hitting"
            f"&stats=seasonAdvanced"
            f"&sitCodes={sit_code}"
        ),
        (
            f"{MLB_STATS_API}/teams/stats"
            f"?sportIds=1"
            f"&season={season}"
            f"&group=hitting"
            f"&stats=statSplits"
            f"&sitCodes={sit_code}"
        ),
    ]

    for url in urls:
        try:
            env = _build_env_from_payload(_fetch_url(url))
            if env.get("teams"):
                env["debugSource"] = url
                return env
        except Exception:
            continue

    return {"leagueAvgKRate": 0.225, "teams": {}, "debugSource": "empty_vs_hand"}


def _lookup_team(env: dict, team_name: str | None) -> dict | None:
    if not team_name:
        return None
    return (env.get("teams") or {}).get(team_name)


def get_team_k_adjustment_for_opponent(
    team_name: str | None,
    season: str,
    pitcher_hand: str | None = None,
) -> dict:
    hand_env = build_team_k_environment_vs_hand(season, pitcher_hand or "")
    hand_row = _lookup_team(hand_env, team_name)

    if hand_row:
        return {
            "teamName": team_name,
            "pitcherHand": pitcher_hand,
            "kRate": hand_row.get("kRate"),
            "leagueAvgKRate": hand_env.get("leagueAvgKRate", 0.225),
            "adjustment": hand_row.get("adjustment", 1.0),
            "source": "team_stats_vs_hand",
            "debugSource": hand_env.get("debugSource"),
        }

    overall_env = build_team_k_environment(season)
    overall_row = _lookup_team(overall_env, team_name)

    if overall_row:
        return {
            "teamName": team_name,
            "pitcherHand": pitcher_hand,
            "kRate": overall_row.get("kRate"),
            "leagueAvgKRate": overall_env.get("leagueAvgKRate", 0.225),
            "adjustment": overall_row.get("adjustment", 1.0),
            "source": "team_stats_overall_fallback",
            "debugSource": hand_env.get("debugSource"),
        }

    return {
        "teamName": team_name,
        "pitcherHand": pitcher_hand,
        "kRate": None,
        "leagueAvgKRate": 0.225,
        "adjustment": 1.0,
        "source": "team_stats_fallback",
        "debugSource": hand_env.get("debugSource"),
    }
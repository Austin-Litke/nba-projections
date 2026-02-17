# winner/sports/api/nba_projection.py

from __future__ import annotations
from typing import Optional


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def safe_float(x) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def avg(nums) -> Optional[float]:
    nums = [n for n in nums if isinstance(n, (int, float))]
    return (sum(nums) / len(nums)) if nums else None


def build_projection(season_avg: dict, season_minutes: Optional[float], last_games: list, vs_games: list) -> dict:
    """
    A minutes + rate + opponent-adjust model.

    Inputs:
      season_avg: {pts, reb, ast} floats
      season_minutes: float minutes per game (optional)
      last_games: list of dicts with min/pts/reb/ast
      vs_games: list of dicts with min/pts/reb/ast vs opponent (optional)

    Output:
      {"projection": {"pts":..., "reb":..., "ast":...}, "meta": {...}}
    """

    # 1) Estimate minutes
    last_min = avg([g.get("min") for g in last_games if isinstance(g.get("min"), (int, float))])
    min_season = safe_float(season_minutes)

    if last_min is None and min_season is None:
        est_min = 32.0
    elif last_min is None:
        est_min = min_season
    elif min_season is None:
        est_min = last_min
    else:
        est_min = 0.65 * last_min + 0.35 * min_season

    est_min = clamp(est_min, 10.0, 42.0)

    # 2) Rates: season + last5
    def rate_from_avg(stat, minutes):
        if stat is None or minutes is None or minutes <= 0:
            return None
        return stat / minutes

    season_pts = safe_float(season_avg.get("pts"))
    season_reb = safe_float(season_avg.get("reb"))
    season_ast = safe_float(season_avg.get("ast"))

    r_season_pts = rate_from_avg(season_pts, min_season)
    r_season_reb = rate_from_avg(season_reb, min_season)
    r_season_ast = rate_from_avg(season_ast, min_season)

    total_last_min = sum([g.get("min", 0) for g in last_games if isinstance(g.get("min"), (int, float))])
    total_last_pts = sum([g.get("pts", 0) for g in last_games if isinstance(g.get("pts"), (int, float))])
    total_last_reb = sum([g.get("reb", 0) for g in last_games if isinstance(g.get("reb"), (int, float))])
    total_last_ast = sum([g.get("ast", 0) for g in last_games if isinstance(g.get("ast"), (int, float))])

    r_last_pts = (total_last_pts / total_last_min) if total_last_min > 0 else None
    r_last_reb = (total_last_reb / total_last_min) if total_last_min > 0 else None
    r_last_ast = (total_last_ast / total_last_min) if total_last_min > 0 else None

    def blend_rate(r_season, r_last):
        if r_season is None and r_last is None:
            return None
        if r_season is None:
            return r_last
        if r_last is None:
            return r_season
        return 0.60 * r_season + 0.40 * r_last

    r_pts = blend_rate(r_season_pts, r_last_pts)
    r_reb = blend_rate(r_season_reb, r_last_reb)
    r_ast = blend_rate(r_season_ast, r_last_ast)

    # 3) Opponent adjustment (ratio vs opponent / season)
    def opponent_multiplier(vs_games, key, season_val):
        if not vs_games or season_val is None or season_val <= 0:
            return 1.0
        vs_avg = avg([g.get(key) for g in vs_games if isinstance(g.get(key), (int, float))])
        if vs_avg is None:
            return 1.0
        mult = vs_avg / season_val
        return clamp(mult, 0.85, 1.15)

    mult_pts = opponent_multiplier(vs_games, "pts", season_pts)
    mult_reb = opponent_multiplier(vs_games, "reb", season_reb)
    mult_ast = opponent_multiplier(vs_games, "ast", season_ast)

    # 4) Final projections
    def project(rate, mult):
        if rate is None:
            return None
        return round((est_min * rate) * mult, 1)

    proj = {
        "pts": project(r_pts, mult_pts),
        "reb": project(r_reb, mult_reb),
        "ast": project(r_ast, mult_ast),
    }

    conf = "Low"
    if len(last_games) >= 5:
        conf = "Medium"
    if len(vs_games) >= 2:
        conf = "High"

    return {
        "projection": proj,
        "meta": {
            "estMinutes": round(est_min, 1),
            "oppAdj": {
                "pts": round(mult_pts, 3),
                "reb": round(mult_reb, 3),
                "ast": round(mult_ast, 3),
            },
            "confidence": conf,
        },
    }

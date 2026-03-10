# winner/sports/api/nba_projection.py

from __future__ import annotations
from typing import Optional
import math


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


def _weighted_rate_from_games(games: list, stat_key: str, max_games: int = 10, half_life_games: float = 5.0) -> Optional[float]:
    """
    Minutes-weighted + recency-weighted per-minute rate from a list of game dicts.
    half_life_games=5 means game i=5 has half the weight of the most recent.
    Assumes games are in reverse-chron order (most recent first). If not, still works roughly.
    """
    if not games:
        return None

    use = games[:max_games]
    num = 0.0
    den = 0.0

    # decay per game index
    # weight = 0.5^(i/half_life)
    for i, g in enumerate(use):
        m = g.get("min")
        s = g.get(stat_key)
        if not isinstance(m, (int, float)) or m <= 0:
            continue
        if not isinstance(s, (int, float)):
            continue

        w = 0.5 ** (i / max(0.5, half_life_games))
        num += w * float(s)
        den += w * float(m)

    if den <= 0:
        return None
    return num / den


def build_projection(season_avg: dict, season_minutes: Optional[float], last_games: list, vs_games: list) -> dict:
    """
    A minutes + rate + opponent-adjust model.

    Output:
      {"projection": {"pts":..., "reb":..., "ast":...}, "meta": {...}}
    """

    # ---------------------------
    # 1) Estimate minutes
    # ---------------------------
    last_min = avg([g.get("min") for g in last_games if isinstance(g.get("min"), (int, float))])
    min_season = safe_float(season_minutes)

    if last_min is None and min_season is None:
        est_min = 32.0
        mins_stability = "Fallback"
    elif last_min is None:
        est_min = min_season
        mins_stability = "Season"
    elif min_season is None:
        est_min = last_min
        mins_stability = "Recent"
    else:
        # slightly more weight on recent minutes (helps stars w/ current role)
        est_min = 0.75 * last_min + 0.25 * min_season
        mins_stability = "Blend"

    est_min = clamp(est_min, 10.0, 42.0)

    # ---------------------------
    # 2) Rates (per-minute)
    # ---------------------------
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

    # Recency-weighted per-minute rates from last games (use up to 10)
    r_last_pts = _weighted_rate_from_games(last_games, "pts", max_games=10, half_life_games=5.0)
    r_last_reb = _weighted_rate_from_games(last_games, "reb", max_games=10, half_life_games=5.0)
    r_last_ast = _weighted_rate_from_games(last_games, "ast", max_games=10, half_life_games=5.0)

    def blend_rate(r_season, r_last, stat_name: str):
        """
        Adaptive blend:
        - if we have enough last games, weight recent more
        - if not, fall back toward season
        """
        if r_season is None and r_last is None:
            return None
        if r_season is None:
            return r_last
        if r_last is None:
            return r_season

        n_last = len(last_games) if isinstance(last_games, list) else 0

        # base weights: more recent by default
        w_last = 0.55 if n_last >= 5 else 0.40
        w_season = 1.0 - w_last

        # If season minutes are missing/weak, trust recent more
        if min_season is None:
            w_last = min(0.70, w_last + 0.10)
            w_season = 1.0 - w_last

        return (w_season * r_season) + (w_last * r_last)

    r_pts = blend_rate(r_season_pts, r_last_pts, "pts")
    r_reb = blend_rate(r_season_reb, r_last_reb, "reb")
    r_ast = blend_rate(r_season_ast, r_last_ast, "ast")

    # ---------------------------
    # 3) Opponent adjustment (shrink toward 1.0)
    # ---------------------------
    def opponent_multiplier(vs_games, key, season_val):
        """
        Use vs opponent / season, but shrink toward 1.0 by sample size.
        Prevents tiny vs samples from over-penalizing (or over-boosting).
        """
        if not vs_games or season_val is None or season_val <= 0:
            return 1.0

        vs_avg = avg([g.get(key) for g in vs_games if isinstance(g.get(key), (int, float))])
        if vs_avg is None:
            return 1.0

        raw = vs_avg / season_val  # ratio
        raw = clamp(raw, 0.80, 1.20)

        # shrink factor: with 0 games -> 0, with 6+ games -> ~0.7
        n = len(vs_games)
        shrink = clamp(n / 8.0, 0.0, 0.70)  # max 70% of the raw signal
        mult = (1.0 - shrink) * 1.0 + shrink * raw

        return clamp(mult, 0.90, 1.10)  # narrower clamp avoids systemic lows

    mult_pts = opponent_multiplier(vs_games, "pts", season_pts)
    mult_reb = opponent_multiplier(vs_games, "reb", season_reb)
    mult_ast = opponent_multiplier(vs_games, "ast", season_ast)

    # ---------------------------
    # 4) Final projections
    # ---------------------------
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
    if len(vs_games) >= 3:
        conf = "High"

    return {
        "projection": proj,
        "meta": {
            "estMinutes": round(est_min, 1),
            "minutesStability": mins_stability,
            "oppAdj": {
                "pts": round(mult_pts, 3),
                "reb": round(mult_reb, 3),
                "ast": round(mult_ast, 3),
            },
            "confidence": conf,
            "ptsEngine": "season+last10_weighted",
        },
    }
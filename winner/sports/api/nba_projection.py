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


def _weighted_rate_from_games(
    games: list,
    stat_key: str,
    max_games: int = 10,
    half_life_games: float = 5.0,
) -> Optional[float]:
    """
    Minutes-weighted + recency-weighted per-minute rate from a list of game dicts.
    half_life_games=5 means game i=5 has half the weight of the most recent.
    Assumes games are reverse-chron (most recent first).
    """
    if not games:
        return None

    use = games[:max_games]
    num = 0.0
    den = 0.0

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


def _weighted_fg_pct_from_games(
    games: list,
    max_games: int = 10,
    half_life_games: float = 5.0,
) -> Optional[float]:
    """
    Weighted FG% from recent games using made/attempted shot components.
    """
    if not games:
        return None

    made = 0.0
    att = 0.0

    for i, g in enumerate(games[:max_games]):
        fgm = g.get("fgm")
        fga = g.get("fga")
        if not isinstance(fgm, (int, float)) or not isinstance(fga, (int, float)) or fga <= 0:
            continue
        w = 0.5 ** (i / max(0.5, half_life_games))
        made += w * float(fgm)
        att += w * float(fga)

    if att <= 0:
        return None
    return made / att


def _blend_rate(
    r_season: Optional[float],
    r_last: Optional[float],
    *,
    n_last: int,
    min_season: Optional[float],
) -> Optional[float]:
    if r_season is None and r_last is None:
        return None
    if r_season is None:
        return r_last
    if r_last is None:
        return r_season

    w_last = 0.65 if n_last >= 5 else 0.48
    w_season = 1.0 - w_last

    if min_season is None:
        w_last = min(0.80, w_last + 0.10)
        w_season = 1.0 - w_last

    return (w_season * r_season) + (w_last * r_last)


def build_projection(
    season_avg: dict,
    season_minutes: Optional[float],
    last_games: list,
    vs_games: list,
    season_shoot: Optional[dict] = None,
) -> dict:
    """
    A minutes + rate + opponent-adjust model with opportunity-aware points logic.

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
        est_min = 0.82 * last_min + 0.18 * min_season
        mins_stability = "Blend"

    est_min = clamp(est_min, 10.0, 42.0)

    # ---------------------------
    # 2) Base rates (per-minute)
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

    r_last_pts = _weighted_rate_from_games(last_games, "pts", max_games=10, half_life_games=5.0)
    r_last_reb = _weighted_rate_from_games(last_games, "reb", max_games=10, half_life_games=5.0)
    r_last_ast = _weighted_rate_from_games(last_games, "ast", max_games=10, half_life_games=5.0)

    n_last = len(last_games) if isinstance(last_games, list) else 0

    r_pts = _blend_rate(r_season_pts, r_last_pts, n_last=n_last, min_season=min_season)
    r_reb = _blend_rate(r_season_reb, r_last_reb, n_last=n_last, min_season=min_season)
    r_ast = _blend_rate(r_season_ast, r_last_ast, n_last=n_last, min_season=min_season)

    # ---------------------------
    # 2b) Opportunity-aware points adjustment
    # ---------------------------
    # Use recent attempt rates + recent FG% to decide whether recent scoring
    # was supported by good volume or driven by hot/cold efficiency.
    season_fga = safe_float((season_shoot or {}).get("fga"))
    season_tpa = safe_float((season_shoot or {}).get("tpa"))
    season_fta = safe_float((season_shoot or {}).get("fta"))
    season_fg_pct = safe_float((season_shoot or {}).get("fg_pct"))

    r_season_fga = rate_from_avg(season_fga, min_season)
    r_season_tpa = rate_from_avg(season_tpa, min_season)
    r_season_fta = rate_from_avg(season_fta, min_season)

    r_last_fga = _weighted_rate_from_games(last_games, "fga", max_games=10, half_life_games=5.0)
    r_last_tpa = _weighted_rate_from_games(last_games, "tpa", max_games=10, half_life_games=5.0)
    r_last_fta = _weighted_rate_from_games(last_games, "fta", max_games=10, half_life_games=5.0)

    r_fga = _blend_rate(r_season_fga, r_last_fga, n_last=n_last, min_season=min_season)
    r_tpa = _blend_rate(r_season_tpa, r_last_tpa, n_last=n_last, min_season=min_season)
    r_fta = _blend_rate(r_season_fta, r_last_fta, n_last=n_last, min_season=min_season)

    recent_fg_pct = _weighted_fg_pct_from_games(last_games, max_games=10, half_life_games=5.0)

    opportunity_mult_pts = 1.0
    opportunity_dbg = {
        "seasonFGAPerMin": round(r_season_fga, 4) if r_season_fga is not None else None,
        "recentFGAPerMin": round(r_last_fga, 4) if r_last_fga is not None else None,
        "blendedFGAPerMin": round(r_fga, 4) if r_fga is not None else None,
        "seasonTPAPerMin": round(r_season_tpa, 4) if r_season_tpa is not None else None,
        "recentTPAPerMin": round(r_last_tpa, 4) if r_last_tpa is not None else None,
        "blendedTPAPerMin": round(r_tpa, 4) if r_tpa is not None else None,
        "seasonFTAPerMin": round(r_season_fta, 4) if r_season_fta is not None else None,
        "recentFTAPerMin": round(r_last_fta, 4) if r_last_fta is not None else None,
        "blendedFTAPerMin": round(r_fta, 4) if r_fta is not None else None,
        "recentFGPct": round(recent_fg_pct, 4) if recent_fg_pct is not None else None,
        "seasonFGPct": round(season_fg_pct, 4) if season_fg_pct is not None else None,
        "opportunityMultPts": None,
        "notes": [],
    }

    if r_pts is not None:
        vol_signal = 0.0
        eff_signal = 0.0

        # Volume signal
        if r_fga is not None and r_season_fga is not None and r_season_fga > 0:
            fga_ratio = clamp(r_fga / r_season_fga, 0.78, 1.25)
            vol_signal += (fga_ratio - 1.0) * 0.55
            opportunity_dbg["notes"].append(f"fgaRatio={round(fga_ratio, 3)}")

        if r_fta is not None and r_season_fta is not None and r_season_fta > 0:
            fta_ratio = clamp(r_fta / r_season_fta, 0.75, 1.30)
            vol_signal += (fta_ratio - 1.0) * 0.25
            opportunity_dbg["notes"].append(f"ftaRatio={round(fta_ratio, 3)}")

        if r_tpa is not None and r_season_tpa is not None and r_season_tpa > 0:
            tpa_ratio = clamp(r_tpa / r_season_tpa, 0.75, 1.30)
            vol_signal += (tpa_ratio - 1.0) * 0.12
            opportunity_dbg["notes"].append(f"tpaRatio={round(tpa_ratio, 3)}")

        # Efficiency signal
        if recent_fg_pct is not None and season_fg_pct is not None:
            fg_delta = clamp(recent_fg_pct - season_fg_pct, -0.12, 0.12)
            eff_signal = fg_delta * 0.55
            opportunity_dbg["notes"].append(f"fgDelta={round(fg_delta, 4)}")

        # Strong volume + cold shooting => slightly lift projection
        # Weak volume + hot shooting => slightly trim projection
        opportunity_mult_pts = 1.0 + vol_signal - eff_signal
        opportunity_mult_pts = clamp(opportunity_mult_pts, 0.93, 1.08)
        opportunity_dbg["opportunityMultPts"] = round(opportunity_mult_pts, 4)

        r_pts = r_pts * opportunity_mult_pts

    # ---------------------------
    # 3) Opponent adjustment (shrink toward 1.0)
    # ---------------------------
    def opponent_multiplier(vs_games, key, season_val):
        if not vs_games or season_val is None or season_val <= 0:
            return 1.0

        vs_avg = avg([g.get(key) for g in vs_games if isinstance(g.get(key), (int, float))])
        if vs_avg is None:
            return 1.0

        raw = vs_avg / season_val
        raw = clamp(raw, 0.78, 1.24)

        n = len(vs_games)
        shrink = clamp(n / 7.0, 0.0, 0.78)
        mult = (1.0 - shrink) * 1.0 + shrink * raw

        return clamp(mult, 0.88, 1.14)

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
            "ptsEngine": "season+last10_weighted+opportunity",
            "opportunity": opportunity_dbg,
        },
    }
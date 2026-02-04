from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Projection:
    player_name: str
    min: float
    pts: float
    reb: float
    ast: float
    sigma_pts: float
    sigma_reb: float
    sigma_ast: float


def _exp_weights(n: int, half_life: float) -> List[float]:
    weights = []
    for i in range(n):
        age = (n - 1) - i
        weights.append(0.5 ** (age / half_life))
    s = sum(weights)
    return [w / s for w in weights]


def _wmean(xs: List[float], ws: List[float]) -> float:
    return sum(x * w for x, w in zip(xs, ws))


def _wstd(xs: List[float], ws: List[float]) -> float:
    m = _wmean(xs, ws)
    var = sum(w * (x - m) ** 2 for x, w in zip(xs, ws))
    return math.sqrt(max(var, 1e-9))


def _season_rate(season: dict, total_key: str) -> float:
    mins = float(season["min_total"])
    if mins <= 0:
        return 0.0
    return float(season[total_key]) / mins


def _recent_rate(last_n: List[dict], stat: str) -> float:
    mins = [max(1e-6, float(g["min"])) for g in last_n]
    rates = [float(g[stat]) / m for g, m in zip(last_n, mins)]
    ws = _exp_weights(len(rates), half_life=7.0)
    return _wmean(rates, ws)


def _recent_rate_sigma(last_n: List[dict], stat: str) -> float:
    mins = [max(1e-6, float(g["min"])) for g in last_n]
    rates = [float(g[stat]) / m for g, m in zip(last_n, mins)]
    ws = _exp_weights(len(rates), half_life=7.0)
    return _wstd(rates, ws)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _out_boost_by_usage(usage_role: str) -> dict:
    """
    Simple but effective: redistribute production when a key teammate is OUT.
    This is intentionally conservative.
    """
    usage_role = (usage_role or "secondary").lower()

    if usage_role == "primary":
        # main scorer/handler benefits mostly in points + some assists
        return {"min": 1.0, "pts": 3.0, "ast": 0.6, "reb": 0.1}
    if usage_role == "support":
        # role player gets more minutes and a little bump everywhere
        return {"min": 2.5, "pts": 1.5, "ast": 0.3, "reb": 0.6}
    # secondary
    return {"min": 2.0, "pts": 2.2, "ast": 0.4, "reb": 0.3}


def project_next_game(
    player_name: str,
    player_meta: dict,
    season: dict,
    last_10: List[dict],
    is_home: Optional[bool] = None,
    out_mode: bool = False,
    blowout_risk: Optional[float] = None,  # NEW
    opp: Optional[dict] = None,
    league: Optional[dict] = None,
    vs_opp_games: Optional[List[dict]] = None,
) -> Projection:

    role = str(player_meta.get("role", "starter")).lower()
    usage_role = str(player_meta.get("usage_role", "secondary")).lower()
    min_vol = float(player_meta.get("min_volatility", 1.05))  # 1.0..1.25

    home_mult = float(player_meta.get("home_mult", 1.0))
    away_mult = float(player_meta.get("away_mult", 1.0))

    # ---- 1) Minutes projection ----
    min_series = [float(g["min"]) for g in last_10]
    w_min = _exp_weights(len(min_series), half_life=6.0)
    min_recent = _wmean(min_series, w_min)

    mpg_season = float(season["min_total"]) / max(1.0, float(season["games_played"]))
    min_proj = 0.85 * min_recent + 0.15 * mpg_season

    # Role-aware clamp
    if role == "starter":
        min_proj = _clamp(min_proj, 30.0, 42.0)
    else:
        min_proj = _clamp(min_proj, 16.0, 30.0)

    # Blowout risk reduces expected minutes (stars sit late in blowouts)
    if blowout_risk is not None:
        br = float(_clamp(blowout_risk, 0.0, 1.0))
        if role == "starter":
            min_proj -= 2.5 * br
        else:
            min_proj -= 1.0 * br
        min_proj = _clamp(min_proj, 6.0, 42.0)

    # OUT-mode minutes bump (usage-aware)
    if out_mode:
        boost = _out_boost_by_usage(usage_role)
        min_proj = _clamp(min_proj + float(boost["min"]), 6.0, 42.0)

    # ---- 2) Per-minute rates (recent + season shrinkage) ----
    shrink_recent = 0.70

    pts_rate = shrink_recent * _recent_rate(last_10, "pts") + (1 - shrink_recent) * _season_rate(season, "pts_total")
    reb_rate = shrink_recent * _recent_rate(last_10, "reb") + (1 - shrink_recent) * _season_rate(season, "reb_total")
    ast_rate = shrink_recent * _recent_rate(last_10, "ast") + (1 - shrink_recent) * _season_rate(season, "ast_total")

    # ---- 3) Baseline projection ----
    pts = pts_rate * min_proj
    reb = reb_rate * min_proj
    ast = ast_rate * min_proj

    # ---- 4) Home/Away adjustment (small) ----
    if is_home is True:
        pts *= home_mult
        ast *= home_mult
    elif is_home is False:
        pts *= away_mult
        ast *= away_mult

    # ---- 5) Matchup multiplier (pace + defense, modest + capped) ----
    if opp and league:
        pace_factor = float(opp["pace"]) / float(league["pace"])
        def_factor = float(league["def_rating"]) / float(opp["def_rating"])
        mult = (pace_factor ** 0.50) * (def_factor ** 0.35)
        mult = _clamp(float(mult), 0.92, 1.08)
        pts *= mult
        reb *= mult
        ast *= mult

    # ---- 6) Head-to-head vs opponent (shrunk + capped) ----
    if vs_opp_games:
        n = len(vs_opp_games)

        season_ppg = float(season["pts_total"]) / max(1.0, float(season["games_played"]))
        season_rpg = float(season["reb_total"]) / max(1.0, float(season["games_played"]))
        season_apg = float(season["ast_total"]) / max(1.0, float(season["games_played"]))

        vs_ppg = sum(float(g["pts"]) for g in vs_opp_games) / n
        vs_rpg = sum(float(g["reb"]) for g in vs_opp_games) / n
        vs_apg = sum(float(g["ast"]) for g in vs_opp_games) / n

        d_pts = vs_ppg - season_ppg
        d_reb = vs_rpg - season_rpg
        d_ast = vs_apg - season_apg

        k = 8.0
        shrink = n / (n + k)

        pts += _clamp(float(shrink * d_pts), -3.0, 3.0)
        reb += _clamp(float(shrink * d_reb), -1.5, 1.5)
        ast += _clamp(float(shrink * d_ast), -1.5, 1.5)

    # ---- 7) OUT-mode stat redistribution (usage-aware) ----
    if out_mode:
        boost = _out_boost_by_usage(usage_role)
        pts += float(boost["pts"])
        reb += float(boost["reb"])
        ast += float(boost["ast"])

        # small efficiency bump (conservative) for primary/secondary
        if usage_role in ("primary", "secondary"):
            pts *= 1.015

    # ---- 8) Uncertainty (sigma) ----
    sigma_pts = max(2.5, _recent_rate_sigma(last_10, "pts") * min_proj)
    sigma_reb = max(1.5, _recent_rate_sigma(last_10, "reb") * min_proj)
    sigma_ast = max(1.5, _recent_rate_sigma(last_10, "ast") * min_proj)

    # Minutes volatility scales uncertainty (this improves “too close” decisions)
    sigma_pts *= min_vol
    sigma_reb *= (1.0 + (min_vol - 1.0) * 0.7)
    sigma_ast *= (1.0 + (min_vol - 1.0) * 0.7)

    # Bench players are more volatile
    if role != "starter":
        sigma_pts *= 1.08
        sigma_reb *= 1.05
        sigma_ast *= 1.05

    # Blowouts increase uncertainty (late-game bench time)
    if blowout_risk is not None:
        br = float(_clamp(blowout_risk, 0.0, 1.0))
        sigma_pts *= (1.0 + 0.15 * br)
        sigma_reb *= (1.0 + 0.10 * br)
        sigma_ast *= (1.0 + 0.10 * br)

    return Projection(
        player_name=player_name,
        min=float(min_proj),
        pts=float(pts),
        reb=float(reb),
        ast=float(ast),
        sigma_pts=float(sigma_pts),
        sigma_reb=float(sigma_reb),
        sigma_ast=float(sigma_ast),
    )

from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class Projection:
    pts: float
    reb: float
    ast: float
    min: float
    sigma_pts: float
    sigma_reb: float
    sigma_ast: float


def _exp_weights(n: int, half_life: float = 7.0) -> np.ndarray:
    idx = np.arange(n)[::-1]  # newest gets biggest weight
    w = 0.5 ** (idx / half_life)
    w = w / w.sum()
    return w


def _weighted_mean(x: np.ndarray, w: np.ndarray) -> float:
    return float(np.sum(x * w))


def _weighted_std(x: np.ndarray, w: np.ndarray) -> float:
    m = np.sum(x * w)
    v = np.sum(w * (x - m) ** 2)
    return float(np.sqrt(max(v, 1e-9)))


def project_from_gamelog(df: pd.DataFrame, window: int = 15) -> Projection:
    if df.empty:
        raise ValueError("No games found for that player/season.")

    recent = df.tail(window).copy()
    n = len(recent)
    w = _exp_weights(n, half_life=max(5.0, window / 2))

    mins = recent["MIN"].to_numpy(dtype=float)
    min_mu = _weighted_mean(mins, w)

    # mild trend
    if n >= 10:
        last5 = float(recent.tail(5)["MIN"].mean())
        prev5 = float(recent.iloc[-10:-5]["MIN"].mean())
        trend = float(np.clip((last5 - prev5) / 5.0, -1.0, 1.0))
        min_mu = float(np.clip(min_mu + trend, 10.0, 42.0))
    else:
        min_mu = float(np.clip(min_mu, 10.0, 42.0))

    def rate_proj(col: str):
        y = recent[col].to_numpy(dtype=float)
        r = y / np.clip(mins, 1.0, None)
        r_mu = _weighted_mean(r, w)
        r_sd = _weighted_std(r, w)
        mu = r_mu * min_mu
        sd = float(np.sqrt((r_sd * min_mu) ** 2 + 1.0))  # +1 keeps from overconfidence
        return float(mu), sd

    pts_mu, pts_sd = rate_proj("PTS")
    reb_mu, reb_sd = rate_proj("REB")
    ast_mu, ast_sd = rate_proj("AST")

    return Projection(
        pts=pts_mu, reb=reb_mu, ast=ast_mu, min=min_mu,
        sigma_pts=pts_sd, sigma_reb=reb_sd, sigma_ast=ast_sd
    )


def apply_matchup_adjustments(proj: Projection, ctx) -> Projection:
    exp_pace = (ctx.team_pace + ctx.opp_pace) / 2.0
    pace_factor = exp_pace / max(ctx.league_pace, 1e-6)

    def_factor = ctx.opp_def_rating / max(ctx.league_def_rating, 1e-6)
    home_factor = 1.015 if ctx.is_home else 0.985

    pts = proj.pts * pace_factor * def_factor * home_factor
    ast = proj.ast * pace_factor * (0.6 * def_factor + 0.4) * home_factor
    reb = proj.reb * pace_factor * (0.2 * def_factor + 0.8)

    return Projection(
        pts=float(pts), reb=float(reb), ast=float(ast), min=float(proj.min),
        sigma_pts=float(proj.sigma_pts * 1.05),
        sigma_reb=float(proj.sigma_reb * 1.05),
        sigma_ast=float(proj.sigma_ast * 1.05),
    )

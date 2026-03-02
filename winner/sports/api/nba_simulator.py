# winner/sports/api/nba_simulator.py

from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Tuple


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def safe_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def avg(vals: List[float]) -> Optional[float]:
    vals = [v for v in vals if isinstance(v, (int, float))]
    return (sum(vals) / len(vals)) if vals else None


def sample_std(vals: List[float]) -> Optional[float]:
    vals = [v for v in vals if isinstance(v, (int, float))]
    if len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    var = sum((v - m) ** 2 for v in vals) / (len(vals) - 1)
    return math.sqrt(var)


def percentile(sorted_vals: List[float], p: float) -> Optional[float]:
    if not sorted_vals:
        return None
    a = sorted_vals
    k = (len(a) - 1) * (p / 100.0)
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return a[lo]
    frac = k - lo
    return a[lo] * (1 - frac) + a[hi] * frac


def _trunc_normal(mu: float, sigma: float, lo: float, hi: float) -> float:
    sigma = max(1e-6, sigma)
    for _ in range(30):
        x = random.gauss(mu, sigma)
        if lo <= x <= hi:
            return x
    return clamp(mu, lo, hi)


def _poisson_knuth(lam: float) -> int:
    lam = max(0.0, lam)
    L = math.exp(-lam)
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= random.random()
        if k > 10000:
            break
    return max(0, k - 1)


def _negbin_gamma_poisson(mu: float, alpha: float) -> int:
    """
    NegBin via Gamma-Poisson mixture.
    Var = mu + alpha*mu^2
    alpha=0 -> Poisson
    """
    mu = max(0.0, mu)
    alpha = max(0.0, alpha)
    if mu <= 1e-12:
        return 0
    if alpha <= 1e-12:
        return _poisson_knuth(mu)

    k = 1.0 / alpha
    theta = alpha * mu
    lam = random.gammavariate(k, theta)
    return _poisson_knuth(lam)


def _lognormal_sample_from_mean(mean: float, rel_sd: float) -> float:
    mean = max(1e-9, mean)
    rel_sd = clamp(rel_sd, 0.01, 1.50)
    s2 = math.log(1.0 + rel_sd * rel_sd)
    s = math.sqrt(s2)
    m = math.log(mean) - 0.5 * s2
    return random.lognormvariate(m, s)


def _binomial(n: int, p: float) -> int:
    n = int(max(0, n))
    p = clamp(float(p), 0.0, 1.0)
    if n <= 0:
        return 0
    # fast paths
    if p <= 0.0:
        return 0
    if p >= 1.0:
        return n
    # n is small (attempts), simple loop is fine
    c = 0
    r = random.random
    for _ in range(n):
        if r() < p:
            c += 1
    return c


def build_minutes_distribution(last_games: List[dict], est_minutes_point: float) -> Tuple[float, float, str]:
    mins = [safe_float(g.get("min")) for g in last_games]
    mins = [m for m in mins if isinstance(m, (int, float)) and m is not None]

    mu = float(est_minutes_point if est_minutes_point is not None else 32.0)
    mu = clamp(mu, 8.0, 42.0)

    sd = sample_std(mins) if len(mins) >= 2 else None

    if sd is None:
        sd = 3.0 if mu >= 30 else 5.5
    else:
        prior_sd = 3.0 if mu >= 30 else 5.5
        sd = 0.65 * float(sd) + 0.35 * prior_sd

    sd = clamp(sd, 1.5, 9.0)

    if sd <= 3.2:
        tag = "Stable"
    elif sd <= 5.5:
        tag = "Medium"
    else:
        tag = "Volatile"

    return mu, sd, tag


def build_rate_model(season_avg: Dict, season_minutes: Optional[float], last_games: List[dict], stat: str) -> Tuple[float, float, float]:
    min_season = safe_float(season_minutes)
    stat_season = safe_float((season_avg or {}).get(stat))
    r_season = None
    if min_season and min_season > 0 and stat_season is not None:
        r_season = stat_season / min_season

    mins = []
    stats = []
    for g in last_games:
        m = safe_float(g.get("min"))
        v = safe_float(g.get(stat))
        if m is not None and m > 0 and v is not None:
            mins.append(m)
            stats.append(v)

    total_min = sum(mins) if mins else 0.0
    r_recent = (sum(stats) / total_min) if total_min > 0 else None

    if r_season is None and r_recent is None:
        r_mean = 0.0
    elif r_season is None:
        r_mean = float(r_recent)
    elif r_recent is None:
        r_mean = float(r_season)
    else:
        w_recent = clamp(total_min / 300.0, 0.20, 0.55)
        r_mean = (1 - w_recent) * float(r_season) + w_recent * float(r_recent)

    r_mean = max(0.0, r_mean)

    per_min_rates = []
    for m, v in zip(mins, stats):
        if m and m > 0:
            per_min_rates.append(v / m)

    r_sd = sample_std(per_min_rates) if len(per_min_rates) >= 2 else None
    if r_sd is None:
        base_rel = 0.22 if stat == "pts" else (0.28 if stat == "reb" else 0.30)
        rel_sd = base_rel
    else:
        rel = float(r_sd) / max(1e-9, r_mean) if r_mean > 0 else 0.35
        prior = 0.20 if stat == "pts" else (0.25 if stat == "reb" else 0.27)
        rel_sd = 0.60 * rel + 0.40 * prior

    rel_sd = clamp(rel_sd, 0.08, 0.85)
    alpha = clamp((rel_sd ** 2) * 0.8, 0.02, 0.35)

    return float(r_mean), float(rel_sd), float(alpha)


def _build_attempt_rate_model(
    season_shoot: Optional[Dict[str, Optional[float]]],
    season_minutes: Optional[float],
    last_games: List[dict],
    key_att: str,  # "fga" | "tpa" | "fta"
) -> Tuple[float, float, float]:
    """
    Returns (att_per_min_mean, rel_sd, alpha) for attempts.
    """
    min_season = safe_float(season_minutes)
    att_season = safe_float((season_shoot or {}).get(key_att)) if season_shoot else None
    r_season = None
    if min_season and min_season > 0 and att_season is not None:
        r_season = att_season / min_season

    mins = []
    atts = []
    for g in last_games:
        m = safe_float(g.get("min"))
        a = safe_float(g.get(key_att))
        if m is not None and m > 0 and a is not None:
            mins.append(m)
            atts.append(a)

    total_min = sum(mins) if mins else 0.0
    r_recent = (sum(atts) / total_min) if total_min > 0 else None

    if r_season is None and r_recent is None:
        r_mean = 0.0
    elif r_season is None:
        r_mean = float(r_recent)
    elif r_recent is None:
        r_mean = float(r_season)
    else:
        # attempts stabilize quicker than points → allow a little more recent weight
        w_recent = clamp(total_min / 260.0, 0.25, 0.60)
        r_mean = (1 - w_recent) * float(r_season) + w_recent * float(r_recent)

    r_mean = max(0.0, r_mean)

    per_min = []
    for m, a in zip(mins, atts):
        if m and m > 0:
            per_min.append(a / m)

    sd = sample_std(per_min) if len(per_min) >= 2 else None
    if sd is None or r_mean <= 0:
        rel_sd = 0.20 if key_att == "fga" else (0.28 if key_att == "tpa" else 0.30)
    else:
        rel = float(sd) / max(1e-9, r_mean)
        prior = 0.18 if key_att == "fga" else (0.25 if key_att == "tpa" else 0.27)
        rel_sd = 0.60 * rel + 0.40 * prior

    rel_sd = clamp(rel_sd, 0.08, 0.90)
    alpha = clamp((rel_sd ** 2) * 0.9, 0.03, 0.45)
    return float(r_mean), float(rel_sd), float(alpha)


def _blend_pct(season_pct: Optional[float], recent_pct: Optional[float], n_recent_att: float) -> float:
    """
    Conservative blend of shooting % with shrinkage toward season.
    If season pct missing, fallback to recent; if both missing, use generic priors.
    """
    # generic priors
    if season_pct is None and recent_pct is None:
        return 0.47
    if season_pct is None:
        return clamp(float(recent_pct), 0.20, 0.85)
    if recent_pct is None:
        return clamp(float(season_pct), 0.20, 0.85)

    # shrink recent toward season based on volume
    w_recent = clamp(n_recent_att / 120.0, 0.15, 0.45)
    return clamp((1 - w_recent) * float(season_pct) + w_recent * float(recent_pct), 0.20, 0.85)


def _recent_pct_from_games(last_games: List[dict], made_key: str, att_key: str) -> Tuple[Optional[float], float]:
    m = 0.0
    a = 0.0
    for g in last_games:
        mm = safe_float(g.get(made_key))
        aa = safe_float(g.get(att_key))
        if mm is not None and aa is not None and aa > 0:
            m += mm
            a += aa
    if a <= 0:
        return None, 0.0
    return (m / a), a


def _has_component_shooting(last_games: List[dict]) -> bool:
    # require at least 5 games with FGA and FTA available
    ok = 0
    for g in last_games:
        if g.get("fga") is not None and g.get("fta") is not None and g.get("tpa") is not None:
            ok += 1
    return ok >= 5


def simulate_props(
    season_avg: Dict,
    season_minutes: Optional[float],
    last_games_10: List[dict],
    opp_mult: Dict[str, float],
    est_minutes_point: float,
    season_shoot: Optional[Dict[str, Optional[float]]] = None,
    n: int = 10000,
) -> Dict:
    """
    Simulates distributions:
      - PTS: component-based model (FGA/3PA/FTA + binomial makes) when data is sufficient
      - REB/AST: NegBin model on per-minute rates (as before)

    Returns:
      projection (p50), distribution bands, samples, diagnostics
    """
    mu_min, sd_min, stability = build_minutes_distribution(last_games_10, est_minutes_point)

    out_samples = {"pts": [], "reb": [], "ast": []}
    diagnostics = {
        "minutesMu": round(mu_min, 2),
        "minutesSd": round(sd_min, 2),
        "minutesStability": stability,
        "n": int(n),
        "oppMult": {k: float(opp_mult.get(k, 1.0)) for k in ("pts", "reb", "ast")},
        "engine": {"pts": "direct", "reb": "negbin", "ast": "negbin"},
        "rates": {},
        "alpha": {},
        "shooting": {},
    }

    # --- REB/AST rate models (same as before) ---
    for stat in ("reb", "ast"):
        r_mean, r_rel_sd, alpha = build_rate_model(season_avg, season_minutes, last_games_10, stat)
        diagnostics["rates"][stat] = {"perMinMean": round(r_mean, 6), "relSd": round(r_rel_sd, 4)}
        diagnostics["alpha"][stat] = round(alpha, 4)

    # --- PTS: component model if possible ---
    use_components = _has_component_shooting(last_games_10)

    if use_components:
        diagnostics["engine"]["pts"] = "components"

        # attempt rate models
        r_fga, rel_fga, a_fga = _build_attempt_rate_model(season_shoot, season_minutes, last_games_10, "fga")
        r_tpa, rel_tpa, a_tpa = _build_attempt_rate_model(season_shoot, season_minutes, last_games_10, "tpa")
        r_fta, rel_fta, a_fta = _build_attempt_rate_model(season_shoot, season_minutes, last_games_10, "fta")

        diagnostics["rates"]["fga"] = {"perMinMean": round(r_fga, 6), "relSd": round(rel_fga, 4)}
        diagnostics["rates"]["tpa"] = {"perMinMean": round(r_tpa, 6), "relSd": round(rel_tpa, 4)}
        diagnostics["rates"]["fta"] = {"perMinMean": round(r_fta, 6), "relSd": round(rel_fta, 4)}
        diagnostics["alpha"]["fga"] = round(a_fga, 4)
        diagnostics["alpha"]["tpa"] = round(a_tpa, 4)
        diagnostics["alpha"]["fta"] = round(a_fta, 4)

        # shooting % blend (season % + recent %)
        fg_recent, fg_att = _recent_pct_from_games(last_games_10, "fgm", "fga")
        tp_recent, tp_att = _recent_pct_from_games(last_games_10, "tpm", "tpa")
        ft_recent, ft_att = _recent_pct_from_games(last_games_10, "ftm", "fta")

        fg_season = safe_float((season_shoot or {}).get("fg_pct")) if season_shoot else None
        tp_season = safe_float((season_shoot or {}).get("tp_pct")) if season_shoot else None
        ft_season = safe_float((season_shoot or {}).get("ft_pct")) if season_shoot else None

        p_fg = _blend_pct(fg_season, fg_recent, fg_att)
        p_tp = _blend_pct(tp_season, tp_recent, tp_att)
        p_ft = _blend_pct(ft_season, ft_recent, ft_att)

        diagnostics["shooting"] = {
            "fg_pct": round(p_fg, 4),
            "tp_pct": round(p_tp, 4),
            "ft_pct": round(p_ft, 4),
            "season_fg_pct": fg_season,
            "season_tp_pct": tp_season,
            "season_ft_pct": ft_season,
            "recent_fg_pct": (round(fg_recent, 4) if fg_recent is not None else None),
            "recent_tp_pct": (round(tp_recent, 4) if tp_recent is not None else None),
            "recent_ft_pct": (round(ft_recent, 4) if ft_recent is not None else None),
        }

    else:
        # fallback: direct points model
        r_mean, r_rel_sd, alpha = build_rate_model(season_avg, season_minutes, last_games_10, "pts")
        diagnostics["rates"]["pts"] = {"perMinMean": round(r_mean, 6), "relSd": round(r_rel_sd, 4)}
        diagnostics["alpha"]["pts"] = round(alpha, 4)

    # --- Simulation loop ---
    for _ in range(int(n)):
        mins = _trunc_normal(mu_min, sd_min, 5.0, 44.0)

        # PTS
        if use_components:
            # sample attempt rates
            r_fga = diagnostics["rates"]["fga"]["perMinMean"]
            r_tpa = diagnostics["rates"]["tpa"]["perMinMean"]
            r_fta = diagnostics["rates"]["fta"]["perMinMean"]

            rel_fga = diagnostics["rates"]["fga"]["relSd"]
            rel_tpa = diagnostics["rates"]["tpa"]["relSd"]
            rel_fta = diagnostics["rates"]["fta"]["relSd"]

            a_fga = diagnostics["alpha"]["fga"]
            a_tpa = diagnostics["alpha"]["tpa"]
            a_fta = diagnostics["alpha"]["fta"]

            fga_mu = mins * _lognormal_sample_from_mean(r_fga, rel_fga)
            tpa_mu = mins * _lognormal_sample_from_mean(r_tpa, rel_tpa)
            fta_mu = mins * _lognormal_sample_from_mean(r_fta, rel_fta)

            # convert means to attempts with overdispersion
            fga = _negbin_gamma_poisson(fga_mu, a_fga)
            tpa = _negbin_gamma_poisson(tpa_mu, a_tpa)
            fta = _negbin_gamma_poisson(fta_mu, a_fta)

            # ensure 3PA <= FGA
            tpa = min(tpa, fga)
            two_pa = max(0, fga - tpa)

            p_fg = diagnostics["shooting"]["fg_pct"]
            p_tp = diagnostics["shooting"]["tp_pct"]
            p_ft = diagnostics["shooting"]["ft_pct"]

            # make 3s and FTs
            tpm = _binomial(tpa, p_tp)
            ftm = _binomial(fta, p_ft)

            # 2PT% derived from FG% and 3PT% (rough but consistent):
            # FGM = 2PM + 3PM; FG% applies to total FGA.
            # We'll estimate p2 so expected overall FG% matches:
            # p_fg*fga ≈ p2*two_pa + p3*tpa
            denom = max(1, two_pa)
            p2 = (p_fg * fga - p_tp * tpa) / denom
            p2 = clamp(p2, 0.25, 0.75)
            two_pm = _binomial(two_pa, p2)

            pts = 2 * two_pm + 3 * tpm + 1 * ftm
            pts = float(pts) * float(opp_mult.get("pts", 1.0))
            out_samples["pts"].append(max(0.0, pts))
        else:
            # direct points fallback
            r_mean = diagnostics["rates"]["pts"]["perMinMean"]
            rel_sd = diagnostics["rates"]["pts"]["relSd"]
            alpha = diagnostics["alpha"]["pts"]
            r_draw = _lognormal_sample_from_mean(r_mean, rel_sd)
            mu = (mins * r_draw) * float(opp_mult.get("pts", 1.0))
            out_samples["pts"].append(float(_negbin_gamma_poisson(mu, float(alpha))))

        # REB/AST
        for stat in ("reb", "ast"):
            r_mean = diagnostics["rates"][stat]["perMinMean"]
            rel_sd = diagnostics["rates"][stat]["relSd"]
            alpha = diagnostics["alpha"][stat]
            r_draw = _lognormal_sample_from_mean(r_mean, rel_sd)
            mu = (mins * r_draw) * float(opp_mult.get(stat, 1.0))
            x = _negbin_gamma_poisson(mu, float(alpha))
            out_samples[stat].append(float(max(0, x)))

    # percentiles
    dist = {}
    proj = {}
    for stat in ("pts", "reb", "ast"):
        arr = sorted(out_samples[stat])
        d = {
            "p10": round(percentile(arr, 10) or 0.0, 1),
            "p25": round(percentile(arr, 25) or 0.0, 1),
            "p50": round(percentile(arr, 50) or 0.0, 1),
            "p75": round(percentile(arr, 75) or 0.0, 1),
            "p90": round(percentile(arr, 90) or 0.0, 1),
            "mean": round((sum(arr) / len(arr)) if arr else 0.0, 2),
        }
        dist[stat] = d
        proj[stat] = d["p50"]

    return {
        "projection": proj,
        "distribution": dist,
        "samples": out_samples,
        "diagnostics": diagnostics,
    }


def prob_over(samples: List[float], line: float) -> float:
    if not samples:
        return 0.0
    threshold = float(line) + 0.5
    cnt = sum(1 for x in samples if x > threshold)
    return cnt / len(samples)


def fair_line(samples: List[float]) -> float:
    if not samples:
        return 0.0
    arr = sorted(samples)
    p50 = percentile(arr, 50) or 0.0
    return round(float(p50), 1)


def alt_lines_probs(samples: List[float], stat: str, center_line: float) -> List[dict]:
    if not samples:
        return []

    if stat == "pts":
        steps = [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5]
    else:
        steps = [-3, -2, -1, 0, 1, 2, 3]

    alts = []
    for s in steps:
        line = float(center_line) + float(s)
        p = prob_over(samples, line)
        alts.append({"line": round(line, 1), "pOver": round(p, 4), "pUnder": round(1.0 - p, 4)})
    return alts
from __future__ import annotations

from typing import Iterable


LEAGUE_BASELINES = {
    "starter_bf_per_start": 22.0,
    "reliever_bf_per_app": 5.5,
    "k_pct": 0.225,
}


def _to_float(value, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def _to_int(value, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return default


def _safe_div(n: float, d: float, default: float = 0.0) -> float:
    if not d:
        return default
    return n / d


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _sample_weight(n: int, full_weight_at: int) -> float:
    if full_weight_at <= 0:
        return 1.0
    return _clamp(n / float(full_weight_at), 0.0, 1.0)


def _stabilize(metric_value: float, baseline: float, sample_n: int, full_weight_at: int) -> float:
    w = _sample_weight(sample_n, full_weight_at)
    return (w * metric_value) + ((1.0 - w) * baseline)


def _confidence_label(recent_games_n: int, season_starts: int) -> str:
    n = max(recent_games_n, season_starts)
    if n <= 2:
        return "low"
    if n <= 5:
        return "medium"
    return "higher"


def _detect_role(season: dict, recent_games: list[dict]) -> str:
    season_starts = _to_int(season.get("gamesStarted"), 0)

    if season_starts >= 2:
        return "starter"

    if season_starts == 0:
        bfs = [_to_float(g.get("battersFaced"), 0.0) for g in recent_games]
        avg_bf = sum(bfs) / len(bfs) if bfs else 0.0
        if avg_bf <= 8.0:
            return "reliever"
        return "uncertain"

    return "uncertain"


def season_bf_per_start(season: dict) -> float:
    bf = _to_float(season.get("battersFaced"))
    gs = _to_float(season.get("gamesStarted"))
    return _safe_div(bf, gs, 0.0)


def season_k_pct(season: dict) -> float:
    bf = _to_float(season.get("battersFaced"))
    k = _to_float(season.get("strikeOuts"))
    return _safe_div(k, bf, 0.0)


def recent_bf_per_app(games: Iterable[dict]) -> float:
    vals = [_to_float(g.get("battersFaced")) for g in games if g.get("battersFaced") not in (None, "")]
    if not vals:
        return 0.0
    return sum(vals) / len(vals)


def recent_k_pct(games: Iterable[dict]) -> float:
    total_bf = 0.0
    total_k = 0.0
    for g in games:
        bf = _to_float(g.get("battersFaced"))
        k = _to_float(g.get("strikeOuts"))
        total_bf += bf
        total_k += k
    return _safe_div(total_k, total_bf, 0.0)


def build_pitcher_projection(
    season: dict,
    recent_games: list[dict],
    opponent_adjustment: float = 1.0,
) -> dict:
    season_starts = _to_int(season.get("gamesStarted"), 0)
    recent_n = len(recent_games)
    role = _detect_role(season, recent_games)

    raw_s_bf = season_bf_per_start(season)
    raw_s_kpct = season_k_pct(season)

    raw_r_bf = recent_bf_per_app(recent_games)
    raw_r_kpct = recent_k_pct(recent_games)

    if raw_s_kpct <= 0:
        raw_s_kpct = LEAGUE_BASELINES["k_pct"]
    if raw_r_kpct <= 0:
        raw_r_kpct = raw_s_kpct

    if role == "starter":
        if raw_s_bf <= 0:
            raw_s_bf = LEAGUE_BASELINES["starter_bf_per_start"]
        if raw_r_bf <= 0:
            raw_r_bf = raw_s_bf

        s_bf = _stabilize(raw_s_bf, LEAGUE_BASELINES["starter_bf_per_start"], season_starts, full_weight_at=8)
        r_bf = _stabilize(raw_r_bf, LEAGUE_BASELINES["starter_bf_per_start"], recent_n, full_weight_at=5)
        expected_bf = (0.65 * r_bf) + (0.35 * s_bf)

    elif role == "reliever":
        if raw_r_bf <= 0:
            raw_r_bf = LEAGUE_BASELINES["reliever_bf_per_app"]

        s_bf = LEAGUE_BASELINES["reliever_bf_per_app"]
        r_bf = _stabilize(raw_r_bf, LEAGUE_BASELINES["reliever_bf_per_app"], recent_n, full_weight_at=6)
        expected_bf = _clamp(r_bf, 3.0, 9.0)

    else:
        uncertain_base = 13.0
        if raw_s_bf <= 0:
            raw_s_bf = uncertain_base
        if raw_r_bf <= 0:
            raw_r_bf = uncertain_base

        s_bf = _stabilize(raw_s_bf, LEAGUE_BASELINES["starter_bf_per_start"], season_starts, full_weight_at=8)
        r_bf = _stabilize(raw_r_bf, uncertain_base, recent_n, full_weight_at=5)
        expected_bf = _clamp(
            (0.60 * r_bf) + (0.40 * s_bf),
            LEAGUE_BASELINES["reliever_bf_per_app"],
            LEAGUE_BASELINES["starter_bf_per_start"],
        )

    s_kpct = _stabilize(raw_s_kpct, LEAGUE_BASELINES["k_pct"], season_starts, full_weight_at=8)
    r_kpct = _stabilize(raw_r_kpct, LEAGUE_BASELINES["k_pct"], recent_n, full_weight_at=5)

    blended_kpct = (0.60 * r_kpct) + (0.40 * s_kpct)

    opp_adj = _clamp(_to_float(opponent_adjustment, 1.0), 0.90, 1.10)
    adjusted_kpct = blended_kpct * opp_adj

    projected_ks = expected_bf * adjusted_kpct

    return {
        "projection": {
            "expectedBattersFaced": round(expected_bf, 2),
            "kPct": round(blended_kpct, 3),
            "adjustedKPct": round(adjusted_kpct, 3),
            "strikeouts": round(projected_ks, 2),
            "confidence": _confidence_label(recent_n, season_starts),
            "role": role,
            "modelVersion": "phase2_bf_kpct_v2",
        },
        "season": {
            "inningsPitched": season.get("inningsPitched"),
            "strikeOuts": season.get("strikeOuts"),
            "gamesStarted": season.get("gamesStarted"),
            "battersFaced": season.get("battersFaced"),
            "rawBfPerStart": round(raw_s_bf, 2),
            "rawKPct": round(raw_s_kpct, 3),
            "bfPerStart": round(s_bf, 2),
            "kPct": round(s_kpct, 3),
        },
        "recent": {
            "starts": recent_n,
            "rawBfPerStart": round(raw_r_bf, 2),
            "rawKPct": round(raw_r_kpct, 3),
            "bfPerStart": round(r_bf, 2),
            "kPct": round(r_kpct, 3),
        },
        "meta": {
            "weights": {
                "recentBfPerStart": 0.65,
                "seasonBfPerStart": 0.35,
                "recentKPct": 0.60,
                "seasonKPct": 0.40,
            },
            "stabilization": {
                "starterBfPerStart": LEAGUE_BASELINES["starter_bf_per_start"],
                "relieverBfPerApp": LEAGUE_BASELINES["reliever_bf_per_app"],
                "leagueKPct": LEAGUE_BASELINES["k_pct"],
                "seasonFullWeightAtStarts": 8,
                "recentFullWeightAtStarts": 5,
            },
            "opponentAdjustment": round(opp_adj, 3),
        },
    }
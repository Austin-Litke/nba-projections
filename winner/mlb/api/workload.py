from __future__ import annotations

import math


def _to_float(value, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _avg(vals: list[float]) -> float:
    vals = [v for v in vals if v > 0]
    return sum(vals) / len(vals) if vals else 0.0


def _std(vals: list[float]) -> float:
    vals = [v for v in vals if v > 0]
    if len(vals) < 2:
        return 0.0
    mean = _avg(vals)
    return math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))

def build_workload_adjustment(role: str, recent_games: list[dict]) -> dict:
    bf_vals = [_to_float(g.get("battersFaced")) for g in recent_games]
    ip_vals = [_to_float(g.get("inningsPitched")) for g in recent_games]
    er_vals = [_to_float(g.get("earnedRuns")) for g in recent_games]
    bb_vals = [_to_float(g.get("baseOnBalls")) for g in recent_games]

    avg_bf = _avg(bf_vals)
    std_bf = _std(bf_vals)
    avg_ip = _avg(ip_vals)
    avg_er = _avg(er_vals)
    avg_bb = _avg(bb_vals)

    short_start_count = sum(1 for ip in ip_vals if 0 < ip < 5.0)
    deep_start_count = sum(1 for ip in ip_vals if ip >= 6.0)

    adj = 1.0
    reasons = []

    if role == "starter":
        if std_bf >= 5.0:
            adj -= 0.03
            reasons.append("high BF volatility")

        if short_start_count >= 2:
            adj -= 0.04
            reasons.append("multiple recent short starts")

        if avg_er >= 4.0:
            adj -= 0.03
            reasons.append("high recent ER allowed")

        if avg_bb >= 3.0:
            adj -= 0.02
            reasons.append("high recent walk pressure")

        if deep_start_count >= 3 and std_bf < 4.0:
            adj += 0.02
            reasons.append("stable recent deep workload")

        # Trend detection based on recent innings.
        # Assumes games are ordered oldest -> newest.
        recent_ip_vals = [ip for ip in ip_vals if ip > 0]
        if len(recent_ip_vals) >= 3:
            last = recent_ip_vals[-1]
            prev = recent_ip_vals[-2]
            prev2 = recent_ip_vals[-3]

            if last > prev > prev2:
                adj += 0.02
                reasons.append("upward workload trend")

            if last < prev < prev2:
                adj -= 0.03
                reasons.append("downward workload trend")

        adj = _clamp(adj, 0.88, 1.05)

    elif role == "reliever":
        if std_bf >= 3.0:
            adj -= 0.03
            reasons.append("volatile reliever usage")

        recent_ip_vals = [ip for ip in ip_vals if ip > 0]
        if len(recent_ip_vals) >= 3:
            last = recent_ip_vals[-1]
            prev = recent_ip_vals[-2]
            prev2 = recent_ip_vals[-3]

            if last < prev < prev2:
                adj -= 0.02
                reasons.append("downward reliever workload trend")

        adj = _clamp(adj, 0.85, 1.03)

    else:
        if std_bf >= 5.0:
            adj -= 0.03
            reasons.append("uncertain workload volatility")

        recent_ip_vals = [ip for ip in ip_vals if ip > 0]
        if len(recent_ip_vals) >= 3:
            last = recent_ip_vals[-1]
            prev = recent_ip_vals[-2]
            prev2 = recent_ip_vals[-3]

            if last > prev > prev2:
                adj += 0.01
                reasons.append("upward uncertain workload trend")

            if last < prev < prev2:
                adj -= 0.02
                reasons.append("downward uncertain workload trend")

        adj = _clamp(adj, 0.88, 1.03)

    if not reasons:
        reasons.append("neutral workload profile")

    if std_bf >= 5:
        volatility = "high"
    elif std_bf >= 3:
        volatility = "medium"
    else:
        volatility = "low"

    if adj <= 0.94:
        risk = "elevated"
    elif adj >= 1.02:
        risk = "favorable"
    else:
        risk = "normal"

    return {
        "adjustment": round(adj, 3),
        "risk": risk,
        "volatility": volatility,
        "avgBF": round(avg_bf, 2),
        "stdBF": round(std_bf, 2),
        "avgIP": round(avg_ip, 2),
        "avgER": round(avg_er, 2),
        "avgBB": round(avg_bb, 2),
        "shortStartCount": short_start_count,
        "deepStartCount": deep_start_count,
        "reasons": reasons,
    }  
    
    
    
    
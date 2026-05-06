from __future__ import annotations

import random


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _percentile(vals: list[int], p: float) -> int:
    if not vals:
        return 0
    vals = sorted(vals)
    idx = int(round((len(vals) - 1) * p))
    return vals[idx]


def _binomial(n: int, p: float) -> int:
    return sum(1 for _ in range(n) if random.random() < p)


def american_to_implied_prob(odds) -> float | None:
    if odds is None:
        return None

    try:
        odds = int(odds)
    except Exception:
        return None

    if odds > 0:
        return 100.0 / (odds + 100.0)

    return -odds / (-odds + 100.0)


def american_payout_per_unit(odds) -> float | None:
    if odds is None:
        return None

    try:
        odds = int(odds)
    except Exception:
        return None

    if odds > 0:
        return odds / 100.0

    return 100.0 / abs(odds)


def compute_ev(prob: float | None, odds) -> float | None:
    if prob is None or odds is None:
        return None

    payout = american_payout_per_unit(odds)
    if payout is None:
        return None

    loss_prob = 1.0 - prob
    return (prob * payout) - loss_prob


def simulate_strikeouts(
    expected_bf: float,
    adjusted_k_pct: float,
    line: float | None = None,
    over_odds=None,
    under_odds=None,
    workload_volatility: str = "medium",
    n_sims: int = 10000,
) -> dict:
    expected_bf = max(1.0, float(expected_bf or 1.0))
    adjusted_k_pct = _clamp(float(adjusted_k_pct or 0.0), 0.02, 0.55)

    if workload_volatility == "high":
        bf_sd = 4.5
    elif workload_volatility == "low":
        bf_sd = 2.5
    else:
        bf_sd = 3.5

    samples = []

    for _ in range(n_sims):
        bf = int(round(random.gauss(expected_bf, bf_sd)))
        bf = max(1, min(35, bf))
        ks = _binomial(bf, adjusted_k_pct)
        samples.append(ks)

    mean = sum(samples) / len(samples)
    median = _percentile(samples, 0.50)

    out = {
        "samples": len(samples),
        "mean": round(mean, 2),
        "median": median,
        "p10": _percentile(samples, 0.10),
        "p25": _percentile(samples, 0.25),
        "p50": median,
        "p75": _percentile(samples, 0.75),
        "p90": _percentile(samples, 0.90),
    }

    if line is not None:
        line = float(line)

        over_count = sum(1 for x in samples if x > line)
        under_count = sum(1 for x in samples if x < line)
        push_count = len(samples) - over_count - under_count

        prob_over = over_count / len(samples)
        prob_under = under_count / len(samples)
        prob_push = push_count / len(samples)

        prob_lean = "No edge"
        if prob_over >= 0.60:
            prob_lean = "Strong Over"
        elif prob_over >= 0.54:
            prob_lean = "Lean Over"
        elif prob_under >= 0.60:
            prob_lean = "Strong Under"
        elif prob_under >= 0.54:
            prob_lean = "Lean Under"

        over_implied = american_to_implied_prob(over_odds)
        under_implied = american_to_implied_prob(under_odds)

        over_ev = compute_ev(prob_over, over_odds)
        under_ev = compute_ev(prob_under, under_odds)

        ev_lean = "No +EV"
        best_side = None
        best_ev = None

        if over_ev is not None or under_ev is not None:
            candidates = []
            if over_ev is not None:
                candidates.append(("Over", over_ev))
            if under_ev is not None:
                candidates.append(("Under", under_ev))

            best_side, best_ev = max(candidates, key=lambda x: x[1])

            if best_ev >= 0.15:
                ev_lean = f"Strong +EV {best_side}"
            elif best_ev >= 0.05:
                ev_lean = f"Lean +EV {best_side}"
            else:
                ev_lean = "No +EV"

        out.update({
            "line": line,
            "probOver": round(prob_over, 3),
            "probUnder": round(prob_under, 3),
            "probPush": round(prob_push, 3),
            "lean": prob_lean,

            "overOdds": over_odds,
            "underOdds": under_odds,
            "overImplied": round(over_implied, 3) if over_implied is not None else None,
            "underImplied": round(under_implied, 3) if under_implied is not None else None,
            "overEV": round(over_ev, 3) if over_ev is not None else None,
            "underEV": round(under_ev, 3) if under_ev is not None else None,
            "bestEVSide": best_side,
            "bestEV": round(best_ev, 3) if best_ev is not None else None,
            "evLean": ev_lean,
        })

    return out
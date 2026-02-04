from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class OUResult:
    pick: str                 # "OVER" | "UNDER" | "TOO CLOSE"
    prob_over: float
    prob_under: float


def _normal_cdf(z: float) -> float:
    # standard normal CDF via erf
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def over_under(mean: float, sigma: float, line: float, threshold: float = 0.60) -> OUResult:
    sigma = max(1e-6, float(sigma))
    z = (line - mean) / sigma
    p_under = _normal_cdf(z)
    p_over = 1.0 - p_under

    if p_over >= threshold:
        pick = "OVER"
    elif p_under >= threshold:
        pick = "UNDER"
    else:
        pick = "TOO CLOSE"

    return OUResult(pick=pick, prob_over=float(p_over), prob_under=float(p_under))

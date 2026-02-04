from __future__ import annotations
from dataclasses import dataclass
from math import erf, sqrt


@dataclass
class OUResult:
    pick: str
    p_over: float
    p_under: float
    note: str


def _norm_cdf(x: float, mu: float, sigma: float) -> float:
    z = (x - mu) / max(sigma, 1e-9)
    return 0.5 * (1.0 + erf(z / sqrt(2.0)))


def over_under(mu: float, sigma: float, line: float, dead_zone: float = 0.07) -> OUResult:
    p_under = _norm_cdf(line, mu, sigma)
    p_over = 1.0 - p_under

    if p_over >= 0.5 + dead_zone:
        return OUResult("OVER", p_over, p_under, "Edge above threshold.")
    if p_over <= 0.5 - dead_zone:
        return OUResult("UNDER", p_over, p_under, "Edge below threshold.")
    return OUResult("TOO CLOSE", p_over, p_under, "Within no-bet zone.")

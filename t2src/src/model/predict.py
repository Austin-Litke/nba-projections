from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import nbinom

from src.config import Config

EPS = 1e-6

def predict_from_last_row(cfg: Config, last_row: pd.Series, min_model, rate_model, X_min_cols, X_rate_cols):
    x_min = last_row[X_min_cols].values.reshape(1, -1)
    x_rate = last_row[X_rate_cols].values.reshape(1, -1)

    m_hat = float(min_model.predict(x_min)[0])
    r_hat = float(rate_model.predict(x_rate)[0])

    # Clamp minutes
    m_hat = max(0.0, min(48.0, m_hat))
    mu = m_hat * r_hat

    # Negative Binomial for probability outputs (global k in v1)
    k = float(cfg.negbin_k)
    n = k
    p = n / (n + mu + EPS)

    def p_ge(T: int) -> float:
        return float(1.0 - nbinom.cdf(T - 1, n, p))

    # Quantiles (rough interval)
    q10 = float(nbinom.ppf(0.10, n, p))
    q50 = float(nbinom.ppf(0.50, n, p))
    q90 = float(nbinom.ppf(0.90, n, p))

    return {
        "m_hat": m_hat,
        "r_hat": r_hat,
        "pts_mu": mu,
        "pts_q10": q10,
        "pts_q50": q50,
        "pts_q90": q90,
        "p_10plus": p_ge(10),
        "p_20plus": p_ge(20),
        "p_30plus": p_ge(30),
    }

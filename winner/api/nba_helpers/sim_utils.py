# api/nba_helpers/sim_utils.py
from __future__ import annotations

from sports.api.nba_simulator import simulate_props


def call_simulate_props(
    *,
    season_avg,
    season_minutes,
    last_games_10,
    opp_mult,
    est_minutes_point,
    season_shoot,
    pace_mult,
    minutes_mult,
    n,
):
    """
    Backward-safe: if your simulate_props doesn't accept pace_mult/minutes_mult yet,
    we fall back to calling without them.
    """
    try:
        return simulate_props(
            season_avg=season_avg,
            season_minutes=season_minutes,
            last_games_10=last_games_10,
            opp_mult=opp_mult,
            est_minutes_point=est_minutes_point,
            season_shoot=season_shoot,
            pace_mult=pace_mult,
            minutes_mult=minutes_mult,
            n=n,
        )
    except TypeError:
        return simulate_props(
            season_avg=season_avg,
            season_minutes=season_minutes,
            last_games_10=last_games_10,
            opp_mult=opp_mult,
            est_minutes_point=est_minutes_point,
            season_shoot=season_shoot,
            n=n,
        )


def histogram(samples: list[float], n_bins: int = 30):
    if not samples:
        return None
    try:
        mn = float(min(samples))
        mx = float(max(samples))
        if mx - mn < 6:
            pad = 6.0
            mn = max(0.0, mn - pad / 2.0)
            mx = mx + pad / 2.0

        n_bins = max(5, min(80, int(n_bins)))
        width = (mx - mn) / n_bins if n_bins > 0 else 1.0

        bins = [round(mn + i * width, 3) for i in range(n_bins + 1)]
        counts = [0] * n_bins

        for v in samples:
            try:
                if v <= mn:
                    idx = 0
                elif v >= mx:
                    idx = n_bins - 1
                else:
                    idx = int((v - mn) / width)
                    if idx < 0:
                        idx = 0
                    if idx >= n_bins:
                        idx = n_bins - 1
                counts[idx] += 1
            except Exception:
                continue

        total = sum(counts) or 1
        freqs = [c / total for c in counts]

        return {"bins": bins, "counts": counts, "freqs": freqs, "min": mn, "max": mx}
    except Exception:
        return None
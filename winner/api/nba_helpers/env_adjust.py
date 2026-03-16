# api/nba_helpers/env_adjust.py
from __future__ import annotations


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def game_total_points(g: dict):
    # common enriched keys
    for a, b in [
        ("teamScore", "oppScore"),
        ("scoreFor", "scoreAgainst"),
        ("homeScore", "awayScore"),
    ]:
        sa = g.get(a)
        sb = g.get(b)
        if isinstance(sa, (int, float)) and isinstance(sb, (int, float)):
            return float(sa) + float(sb)

    # string fallback: "110-104"
    s = g.get("score")
    if isinstance(s, str) and "-" in s:
        try:
            x, y = s.split("-", 1)
            return float(x.strip()) + float(y.strip())
        except Exception:
            pass

    return None


def game_margin_abs(g: dict):
    for a, b in [
        ("teamScore", "oppScore"),
        ("scoreFor", "scoreAgainst"),
        ("homeScore", "awayScore"),
    ]:
        sa = g.get(a)
        sb = g.get(b)
        if isinstance(sa, (int, float)) and isinstance(sb, (int, float)):
            return abs(float(sa) - float(sb))

    s = g.get("score")
    if isinstance(s, str) and "-" in s:
        try:
            x, y = s.split("-", 1)
            return abs(float(x.strip()) - float(y.strip()))
        except Exception:
            pass

    return None


def pace_and_blowout_from_games(vs_games: list, last_games_10: list) -> tuple[float, float, dict]:
    BASELINE_TOTAL = 228.0  # proxy NBA baseline

    def collect(games: list):
        totals = []
        margins = []
        for g in (games or []):
            t = game_total_points(g)
            if t is not None:
                totals.append(float(t))
            m = game_margin_abs(g)
            if m is not None:
                margins.append(float(m))
        return totals, margins

    vs_totals, vs_margins = collect(vs_games)
    lg_totals, lg_margins = collect(last_games_10)

    # ✅ use vs_games ONLY if we have enough actual parsed samples
    use_vs = (len(vs_totals) >= 2 and len(vs_margins) >= 2)
    totals = vs_totals if use_vs else lg_totals
    margins = vs_margins if use_vs else lg_margins
    source = "vs_games" if use_vs else "last_games_10"

    avg_total = (sum(totals) / len(totals)) if totals else BASELINE_TOTAL
    avg_margin = (sum(margins) / len(margins)) if margins else 8.0

    raw_pace = avg_total / BASELINE_TOTAL
    pace_mult = clamp(0.45 * 1.0 + 0.55 * raw_pace, 0.94, 1.08)

    if avg_margin > 8.0:
        minutes_mult = 1.0 - (avg_margin - 8.0) * 0.004
    else:
        minutes_mult = 1.0 + (8.0 - avg_margin) * 0.0025

    minutes_mult = clamp(minutes_mult, 0.96, 1.04)

    dbg = {
        "avgTotalPts": round(avg_total, 2),
        "avgMarginAbs": round(avg_margin, 2),
        "paceMult": round(pace_mult, 4),
        "minutesMult": round(minutes_mult, 4),
        "source": source,
        "nTotals": len(totals),
        "nMargins": len(margins),
        "vsParsed": {"totals": len(vs_totals), "margins": len(vs_margins)},
        "last10Parsed": {"totals": len(lg_totals), "margins": len(lg_margins)},
    }
    return pace_mult, minutes_mult, dbg
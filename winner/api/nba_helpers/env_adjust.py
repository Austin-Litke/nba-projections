# api/nba_helpers/env_adjust.py
from __future__ import annotations


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def game_total_points(g: dict):
    for a, b in [
        ("teamScore", "oppScore"),
        ("scoreFor", "scoreAgainst"),
        ("homeScore", "awayScore"),
    ]:
        sa = g.get(a)
        sb = g.get(b)
        if isinstance(sa, (int, float)) and isinstance(sb, (int, float)):
            return float(sa) + float(sb)

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


def _tier_from_pct(pct: float) -> str:
    p = float(pct or 0.0)
    if p >= 55:
        return "very_high"
    if p >= 38:
        return "high"
    if p >= 22:
        return "moderate"
    return "low"


def _role_from_minutes(est_minutes: float) -> tuple[str, float]:
    """
    Returns:
      role_bucket, role_sensitivity

    role_sensitivity controls how strongly blowout risk affects minutes.
    """
    est = float(est_minutes or 32.0)

    if est >= 35.5:
        return "star", 1.22
    if est >= 30.0:
        return "starter", 1.00
    if est >= 22.0:
        return "rotation", 0.82
    return "bench", 0.58


def pace_and_blowout_from_games(
    vs_games: list,
    last_games_10: list,
    injury_ctx: dict | None = None,
    est_minutes: float | None = None,
) -> tuple[float, float, dict]:
    """
    Returns:
      pace_mult, minutes_mult, debug

    injury_ctx example:
      {
        "ownTeamImpact": 2.3,
        "oppTeamImpact": 7.4
      }

    Interpretation:
      - higher ownTeamImpact => player's team is more depleted
      - higher oppTeamImpact => opponent is more depleted

    Key idea:
      - blowoutRiskPct is a shared game-level value
      - minutesMult is player-specific based on role + team side
    """

    BASELINE_TOTAL = 228.0
    BASELINE_MARGIN = 8.0

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

    use_vs = (len(vs_totals) >= 2 and len(vs_margins) >= 2)
    totals = vs_totals if use_vs else lg_totals
    margins = vs_margins if use_vs else lg_margins
    source = "vs_games" if use_vs else "last_games_10"

    avg_total = (sum(totals) / len(totals)) if totals else BASELINE_TOTAL
    avg_margin = (sum(margins) / len(margins)) if margins else BASELINE_MARGIN

    # ---------------------------
    # Pace multiplier
    # ---------------------------
    raw_pace = avg_total / BASELINE_TOTAL
    pace_mult = clamp(0.45 * 1.0 + 0.55 * raw_pace, 0.94, 1.08)

    # ---------------------------
    # Shared game-level blowout risk
    # ---------------------------
    injury_ctx = injury_ctx or {}
    own_team_impact = float(injury_ctx.get("ownTeamImpact") or 0.0)
    opp_team_impact = float(injury_ctx.get("oppTeamImpact") or 0.0)

    # positive => opponent more depleted => player's team more likely to control game
    team_strength_delta = opp_team_impact - own_team_impact

    # historical signal from prior game environments
    hist_margin_component = clamp((avg_margin - BASELINE_MARGIN) * 2.1, -7.0, 16.0)

    # matchup mismatch from injury imbalance
    mismatch_abs = abs(team_strength_delta)
    injury_component = clamp(mismatch_abs * 5.9, 0.0, 24.0)

    # shared risk for the game, regardless of which player is being evaluated
    blowout_risk_pct = 14.0 + hist_margin_component + injury_component
    blowout_risk_pct = clamp(blowout_risk_pct, 4.0, 76.0)
    blowout_tier = _tier_from_pct(blowout_risk_pct)

    # ---------------------------
    # Player-specific minutes effect
    # ---------------------------
    est = float(est_minutes or 32.0)
    role_bucket, role_sensitivity = _role_from_minutes(est)

    # side interpretation:
    #  > 0 means player's team is stronger side
    #  < 0 means player's team is weaker side
    if team_strength_delta >= 1.0:
        side = "stronger_team"
    elif team_strength_delta <= -1.0:
        side = "weaker_team"
    else:
        side = "balanced"

    risk = blowout_risk_pct / 100.0

    # Stronger team stars lose the most in likely blowouts
    if side == "stronger_team":
        base_penalty = risk * 0.19 * role_sensitivity

        # high-minute stars get extra downside
        if est >= 36:
            base_penalty += 0.018
        elif est >= 33:
            base_penalty += 0.010

        # bench guys are much less harmed; could even get garbage time
        if role_bucket == "bench":
            base_penalty *= 0.45
        elif role_bucket == "rotation":
            base_penalty *= 0.78

    # Weaker team players also get hurt by blowouts, but usually less than
    # stars on the stronger team because they may play until the game gets away.
    elif side == "weaker_team":
        base_penalty = risk * 0.11 * role_sensitivity

        if est >= 36:
            base_penalty += 0.008

        if role_bucket == "bench":
            base_penalty *= 0.72
        elif role_bucket == "rotation":
            base_penalty *= 0.88

    else:
        # balanced game: only small environment effect
        base_penalty = risk * 0.06 * role_sensitivity
        if role_bucket == "bench":
            base_penalty *= 0.65

    # Small bonus in very competitive projected spots
    close_game_bonus = 0.0
    if blowout_risk_pct < 16:
        close_game_bonus = ((16.0 - blowout_risk_pct) / 100.0) * (0.030 + 0.008 * role_sensitivity)

    # In extreme blowout spots, bench/low-minute players should not be penalized much
    # and may even get a tiny neutralizer.
    bench_garbage_time_relief = 0.0
    if blowout_risk_pct >= 46 and role_bucket == "bench":
        bench_garbage_time_relief = 0.012
    elif blowout_risk_pct >= 52 and role_bucket == "rotation" and est < 25:
        bench_garbage_time_relief = 0.006

    minutes_mult = 1.0 - base_penalty + close_game_bonus + bench_garbage_time_relief
    minutes_mult = clamp(minutes_mult, 0.84, 1.05)

    dbg = {
        "avgTotalPts": round(avg_total, 2),
        "avgMarginAbs": round(avg_margin, 2),
        "paceMult": round(pace_mult, 4),
        "minutesMult": round(minutes_mult, 4),

        # shared game-level blowout info
        "blowoutRiskPct": round(blowout_risk_pct, 1),
        "blowoutTier": blowout_tier,
        "sharedGameBlowoutRisk": True,

        # mismatch / side context
        "teamStrengthDelta": round(team_strength_delta, 3),
        "ownTeamImpact": round(own_team_impact, 3),
        "oppTeamImpact": round(opp_team_impact, 3),
        "histMarginComponent": round(hist_margin_component, 3),
        "injuryComponent": round(injury_component, 3),
        "side": side,

        # player-level minutes effect
        "roleBucket": role_bucket,
        "roleSensitivity": round(role_sensitivity, 3),
        "estMinutesInput": round(est, 2),
        "basePenalty": round(base_penalty, 4),
        "closeGameBonus": round(close_game_bonus, 4),
        "benchGarbageTimeRelief": round(bench_garbage_time_relief, 4),

        # source info
        "source": source,
        "nTotals": len(totals),
        "nMargins": len(margins),
        "vsParsed": {"totals": len(vs_totals), "margins": len(vs_margins)},
        "last10Parsed": {"totals": len(lg_totals), "margins": len(lg_margins)},
    }
    return pace_mult, minutes_mult, dbg
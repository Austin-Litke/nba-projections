# api/nba_helpers/injury_adjust.py
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from sports.api.nba_gamelog import build_last_games


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def _avg(nums: List[float]) -> Optional[float]:
    xs = [float(n) for n in nums if isinstance(n, (int, float))]
    return (sum(xs) / len(xs)) if xs else None


def _status_weight(status: str) -> float:
    s = (status or "").strip().lower()
    if s in ("out", "suspension"):
        return 1.0
    if s == "doubtful":
        return 0.75
    if s == "questionable":
        return 0.40
    if s in ("day-to-day", "dtd"):
        return 0.20
    return 0.0


def _creation_proxy(g: dict) -> Optional[float]:
    pts = g.get("pts")
    ast = g.get("ast")
    if not isinstance(pts, (int, float)) and not isinstance(ast, (int, float)):
        return None
    return float(pts or 0) + 1.6 * float(ast or 0)


def _attempt_proxy(g: dict) -> Optional[float]:
    """
    Light offensive opportunity proxy.
    FGA matters most, FTA adds some signal.
    """
    fga = g.get("fga")
    fta = g.get("fta")
    if not isinstance(fga, (int, float)) and not isinstance(fta, (int, float)):
        return None
    return float(fga or 0) + 0.45 * float(fta or 0)


def _player_profile(last_games_10: List[dict], est_minutes: float) -> dict:
    mins = []
    cre_vals = []
    opp_vals = []

    for g in (last_games_10 or []):
        m = g.get("min")
        c = _creation_proxy(g)
        o = _attempt_proxy(g)
        if isinstance(m, (int, float)) and m > 0:
            mins.append(float(m))
            if c is not None:
                cre_vals.append((float(c), float(m)))
            if o is not None:
                opp_vals.append((float(o), float(m)))

    recent_min = _avg(mins) or float(est_minutes or 0.0)

    cre_per_min = None
    if cre_vals:
        c_num = sum(v for v, _m in cre_vals)
        c_den = sum(m for _v, m in cre_vals)
        if c_den > 0:
            cre_per_min = c_num / c_den

    opp_per_min = None
    if opp_vals:
        o_num = sum(v for v, _m in opp_vals)
        o_den = sum(m for _v, m in opp_vals)
        if o_den > 0:
            opp_per_min = o_num / o_den

    est = float(est_minutes or recent_min or 0.0)

    if est >= 34:
        role = "star"
        minute_ceiling = 38.5
    elif est >= 28:
        role = "starter"
        minute_ceiling = 36.0
    elif est >= 20:
        role = "rotation"
        minute_ceiling = 31.0
    else:
        role = "bench"
        minute_ceiling = 25.0

    headroom = clamp(minute_ceiling - est, 0.0, 10.0)

    # How likely this player is to absorb minutes
    minute_share_score = clamp((est / 36.0) * 0.75 + (headroom / 10.0) * 0.55, 0.08, 1.15)

    # How likely this player is to absorb offense
    creation_component = 0.0 if cre_per_min is None else cre_per_min
    opp_component = 0.0 if opp_per_min is None else opp_per_min

    usage_absorb_score = (
        0.55 * clamp(creation_component / 1.05, 0.20, 1.45)
        + 0.30 * clamp(opp_component / 0.58, 0.20, 1.45)
        + 0.15 * clamp(est / 34.0, 0.20, 1.25)
    )
    usage_absorb_score = clamp(usage_absorb_score, 0.15, 1.35)

    return {
        "recentMin": round(recent_min, 3),
        "crePerMin": round(cre_per_min, 4) if cre_per_min is not None else None,
        "oppPerMin": round(opp_per_min, 4) if opp_per_min is not None else None,
        "role": role,
        "minuteCeiling": round(minute_ceiling, 2),
        "headroom": round(headroom, 3),
        "minuteShareScore": round(minute_share_score, 4),
        "usageAbsorbScore": round(usage_absorb_score, 4),
    }


def injury_adjust_for_event(
    *,
    athlete_id: int,
    athlete_team_id: Optional[int],
    event_injuries_rows: List[dict],
    est_minutes: float,
    last_games_10: List[dict],
    max_teammates: int = 9,
) -> Tuple[float, Dict[str, float], Dict]:
    """
    Returns:
      minutes_delta, usage_mult (pts/reb/ast), debug

    Philosophy:
      - separate minute redistribution from usage redistribution
      - use player-specific minute headroom instead of hard role cap
      - do NOT hand broad scoring boosts to everyone
      - star/creator outs should concentrate points/assist gains more
      - low-usage outs should mostly create smaller minute effects
    """

    dbg = {
        "used": False,
        "summary": None,
        "athleteTeamId": athlete_team_id,
        "inactiveTeammates": [],
        "missing": {
            "minutes": 0.0,
            "creationPerMin": 0.0,
            "opportunityPerMin": 0.0,
            "starWeightedMinutes": 0.0,
        },
        "player": {},
        "result": {
            "minutesDelta": 0.0,
            "usageMult": {"pts": 1.0, "reb": 1.0, "ast": 1.0},
            "teamImpactScore": 0.0,
            "role": None,
            "minuteGainComponent": 0.0,
            "minuteLossComponent": 0.0,
            "usageAbsorbScore": 0.0,
        },
        "notes": [],
    }

    if not athlete_team_id or not event_injuries_rows:
        dbg["notes"].append("No teamId or no injuries rows - skipping injury adjust.")
        return 0.0, {"pts": 1.0, "reb": 1.0, "ast": 1.0}, dbg

    athlete_team_id_str = str(athlete_team_id)
    athlete_id_str = str(athlete_id)

    inactive = []
    for r in event_injuries_rows:
        row_team_id = str(r.get("teamId"))
        if row_team_id != athlete_team_id_str:
            continue

        aid = r.get("athleteId")
        if aid is None:
            continue
        if str(aid) == athlete_id_str:
            continue

        w = _status_weight(r.get("status") or "")
        if w <= 0:
            continue

        inactive.append({**r, "weight": w})

    if not inactive:
        dbg["notes"].append("No inactive teammates detected for this event/team.")
        dbg["summary"] = None
        return 0.0, {"pts": 1.0, "reb": 1.0, "ast": 1.0}, dbg

    names = []
    for r in inactive:
        nm = str(r.get("name") or "Unknown")
        st = str(r.get("status") or "")
        names.append(f"{nm} ({st})")
    dbg["summary"] = ", ".join(names[:6]) if names else None

    inactive = inactive[:max_teammates]

    player_prof = _player_profile(last_games_10, est_minutes)
    dbg["player"] = player_prof
    dbg["result"]["role"] = player_prof.get("role")
    dbg["result"]["usageAbsorbScore"] = player_prof.get("usageAbsorbScore")

    missing_minutes = 0.0
    miss_cre_weighted_sum = 0.0
    miss_opp_weighted_sum = 0.0
    miss_min_weighted_sum = 0.0
    star_weighted_minutes = 0.0

    for r in inactive:
        try:
            tid = int(r["athleteId"])
        except Exception:
            continue

        w = float(r.get("weight") or 1.0)

        games, _dbg = build_last_games(tid, limit=10)
        mins = _avg([g.get("min") for g in games]) or 0.0

        t_mins = []
        t_cre = []
        t_opp = []
        for g in games:
            m = g.get("min")
            c = _creation_proxy(g)
            o = _attempt_proxy(g)
            if isinstance(m, (int, float)) and m > 0:
                t_mins.append(float(m))
                if c is not None:
                    t_cre.append((float(c), float(m)))
                if o is not None:
                    t_opp.append((float(o), float(m)))

        cre_per_min = None
        if t_cre:
            t_cre_num = sum(v for v, _m in t_cre)
            t_cre_den = sum(m for _v, m in t_cre)
            if t_cre_den > 0:
                cre_per_min = t_cre_num / t_cre_den

        opp_per_min = None
        if t_opp:
            t_opp_num = sum(v for v, _m in t_opp)
            t_opp_den = sum(m for _v, m in t_opp)
            if t_opp_den > 0:
                opp_per_min = t_opp_num / t_opp_den

        missing_minutes += w * mins

        if cre_per_min is not None:
            miss_cre_weighted_sum += (w * mins) * float(cre_per_min)
        if opp_per_min is not None:
            miss_opp_weighted_sum += (w * mins) * float(opp_per_min)
        miss_min_weighted_sum += (w * mins)

        # star/creator absence signal
        star_like = 0.0
        if mins >= 32:
            star_like += 0.45
        if cre_per_min is not None:
            star_like += clamp((cre_per_min - 0.90) / 0.60, 0.0, 0.85)
        if opp_per_min is not None:
            star_like += clamp((opp_per_min - 0.55) / 0.30, 0.0, 0.55)
        star_like = clamp(star_like, 0.0, 1.5)

        star_weighted_minutes += w * mins * star_like

        dbg["inactiveTeammates"].append({
            "athleteId": tid,
            "name": r.get("name"),
            "status": r.get("status"),
            "w": round(w, 2),
            "avgMin10": round(mins, 2),
            "creationPerMin": (round(cre_per_min, 4) if cre_per_min is not None else None),
            "opportunityPerMin": (round(opp_per_min, 4) if opp_per_min is not None else None),
            "starLikeScore": round(star_like, 3),
        })

    missing_cre_per_min = 0.0
    missing_opp_per_min = 0.0
    if miss_min_weighted_sum > 0:
        missing_cre_per_min = miss_cre_weighted_sum / miss_min_weighted_sum
        missing_opp_per_min = miss_opp_weighted_sum / miss_min_weighted_sum

    dbg["missing"]["minutes"] = round(missing_minutes, 2)
    dbg["missing"]["creationPerMin"] = round(missing_cre_per_min, 4)
    dbg["missing"]["opportunityPerMin"] = round(missing_opp_per_min, 4)
    dbg["missing"]["starWeightedMinutes"] = round(star_weighted_minutes, 2)

    # team impact score used elsewhere for blowout / context
    team_impact_score = clamp(
        (missing_minutes / 15.0)
        + (missing_cre_per_min * 1.55)
        + (star_weighted_minutes / 85.0),
        0.0,
        12.0,
    )
    dbg["result"]["teamImpactScore"] = round(team_impact_score, 3)

    if missing_minutes < 4.0:
        dbg["notes"].append("Missing minutes < 4 - skipping injury adjust.")
        return 0.0, {"pts": 1.0, "reb": 1.0, "ast": 1.0}, dbg

    dbg["used"] = True

    est = float(est_minutes or 32.0)
    role = str(player_prof.get("role") or "rotation")
    headroom = float(player_prof.get("headroom") or 0.0)
    minute_share_score = float(player_prof.get("minuteShareScore") or 0.0)
    usage_absorb_score = float(player_prof.get("usageAbsorbScore") or 0.0)

    dbg["notes"].append(f"Role={role}")
    dbg["notes"].append(f"Headroom={round(headroom, 3)}")
    dbg["notes"].append(f"MinuteShareScore={round(minute_share_score, 3)}")
    dbg["notes"].append(f"UsageAbsorbScore={round(usage_absorb_score, 3)}")

    # -------------------------
    # Minutes redistribution
    # -------------------------
    # More missing minutes -> more room to gain, but constrained by headroom.
    # High-minute players can gain only if they still have real headroom.
    minute_pool_intensity = clamp(missing_minutes / 70.0, 0.06, 1.00)

    base_gain = missing_minutes * 0.16 * minute_share_score * minute_pool_intensity

    # Star absences create more concentrated replacement minutes for real rotation guys,
    # but should not blindly hand huge gains to everyone.
    star_absence_bonus = clamp(star_weighted_minutes / 120.0, 0.0, 0.85)
    if role == "star":
        star_gain_mult = 0.95
    elif role == "starter":
        star_gain_mult = 1.05
    elif role == "rotation":
        star_gain_mult = 1.12
    else:
        star_gain_mult = 0.92

    minutes_gain = base_gain * (1.0 + star_absence_bonus * star_gain_mult)

    # Cap by realistic headroom, not blunt fixed role cap
    dynamic_cap = clamp(headroom + 1.2, 0.5, 7.0)
    minutes_gain = clamp(minutes_gain, 0.0, dynamic_cap)

    # -------------------------
    # Minutes downside / crowding penalty
    # -------------------------
    # If the player is already low-absorption and the missing players were mostly
    # low-creation role guys, this player may not really benefit much.
    low_creation_missing = clamp(1.0 - (missing_cre_per_min / 0.95), 0.0, 1.0)
    low_absorb_player = clamp(1.0 - (usage_absorb_score / 0.85), 0.0, 1.0)

    # Negative adjustment is intentionally mild; true blowout downside is handled elsewhere.
    minutes_loss = 0.0
    if role in ("bench", "rotation"):
        minutes_loss = 0.85 * low_creation_missing * low_absorb_player * clamp(est / 26.0, 0.35, 1.0)

    minutes_loss = clamp(minutes_loss, 0.0, 1.6)

    minutes_delta = minutes_gain - minutes_loss

    dbg["result"]["minuteGainComponent"] = round(minutes_gain, 3)
    dbg["result"]["minuteLossComponent"] = round(minutes_loss, 3)
    dbg["result"]["minutesDelta"] = round(minutes_delta, 3)

    # -------------------------
    # Usage redistribution
    # -------------------------
    # Concentrate boosts mainly when missing players were actual creators.
    creation_intensity = clamp(missing_cre_per_min / 1.15, 0.0, 1.0)
    opportunity_intensity = clamp(missing_opp_per_min / 0.72, 0.0, 1.0)

    # Stronger when a star/high-creation teammate is out
    star_creation_bonus = clamp(star_weighted_minutes / 110.0, 0.0, 1.0)

    # Player-specific absorption
    absorb = clamp(
        0.35 * usage_absorb_score
        + 0.35 * clamp((est / 32.0), 0.35, 1.20)
        + 0.30 * clamp((player_prof.get("crePerMin") or 0.55) / 0.95, 0.25, 1.35),
        0.18,
        1.30,
    )

    # Key idea:
    # - if missing player(s) were low-creation, pts/ast boosts should be modest
    # - if missing star creator(s), pts/ast boosts can be meaningful for real absorbers
    pts_boost = (
        0.14 * creation_intensity * absorb
        + 0.08 * opportunity_intensity * absorb
        + 0.08 * star_creation_bonus * absorb
    )
    ast_boost = (
        0.16 * creation_intensity * absorb
        + 0.10 * star_creation_bonus * absorb
    )
    reb_boost = (
        0.05 * opportunity_intensity
        + 0.03 * clamp(missing_minutes / 55.0, 0.0, 1.0)
    )

    # Reduce broad boosts for low-usage role players
    if role == "bench":
        pts_boost *= 0.62
        ast_boost *= 0.58
    elif role == "rotation":
        pts_boost *= 0.78
        ast_boost *= 0.74

    # If missing players were mostly low-creation, don't inflate everyone
    pts_boost *= (0.55 + 0.45 * creation_intensity)
    ast_boost *= (0.45 + 0.55 * creation_intensity)

    # Bounded, conservative
    pts_mult = 1.0 + clamp(pts_boost, 0.0, 0.18)
    ast_mult = 1.0 + clamp(ast_boost, 0.0, 0.20)
    reb_mult = 1.0 + clamp(reb_boost, 0.0, 0.10)

    usage_mult = {
        "pts": round(pts_mult, 4),
        "reb": round(reb_mult, 4),
        "ast": round(ast_mult, 4),
    }

    dbg["result"]["usageMult"] = usage_mult
    dbg["notes"].append(f"CreationIntensity={round(creation_intensity, 3)}")
    dbg["notes"].append(f"OpportunityIntensity={round(opportunity_intensity, 3)}")
    dbg["notes"].append(f"StarCreationBonus={round(star_creation_bonus, 3)}")
    dbg["notes"].append(f"Absorb={round(absorb, 3)}")

    return float(minutes_delta), {
        "pts": float(pts_mult),
        "reb": float(reb_mult),
        "ast": float(ast_mult),
    }, dbg
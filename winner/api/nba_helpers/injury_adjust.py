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
    # hard out
    if s in ("out", "suspension"):
        return 1.0
    # optional: treat doubtful as mostly-out
    if s == "doubtful":
        return 0.75
    if s == "questionable":
        return 0.40
    if s in ("day-to-day", "dtd"):
        return 0.20
    return 0.0

def _creation_proxy(g: dict) -> Optional[float]:
    # simple, works well:
    # creation ≈ PTS + 1.6*AST
    pts = g.get("pts")
    ast = g.get("ast")
    if not isinstance(pts, (int, float)) and not isinstance(ast, (int, float)):
        return None
    return float(pts or 0) + 1.6 * float(ast or 0)

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
      minutes_add, usage_mult (pts/reb/ast), debug
    """

    dbg = {
        "used": False,
        "summary": None,
        "athleteTeamId": athlete_team_id,
        "inactiveTeammates": [],
        "missing": {"minutes": 0.0, "creationPerMin": 0.0},
        "player": {"estMinutes": est_minutes, "recentCreationPerMin": None},
        "result": {"minutesAdd": 0.0, "usageMult": {"pts": 1.0, "reb": 1.0, "ast": 1.0}},
        "notes": [],
    }

    if not athlete_team_id or not event_injuries_rows:
        dbg["notes"].append("No teamId or no injuries rows — skipping injury adjust.")
        return 0.0, {"pts": 1.0, "reb": 1.0, "ast": 1.0}, dbg

    # Identify inactive teammates (same team, not the player)
    inactive = []
    for r in event_injuries_rows:
        if r.get("teamId") != athlete_team_id:
            continue
        aid = r.get("athleteId")
        if aid is None or int(aid) == int(athlete_id):
            continue

        w = _status_weight(r.get("status") or "")
        if w <= 0:
            continue

        inactive.append({**r, "weight": w})

    if not inactive:
        dbg["notes"].append("No inactive teammates detected for this event/team.")
        return 0.0, {"pts": 1.0, "reb": 1.0, "ast": 1.0}, dbg
    # Human-readable summary for UI/debug
        names = []
        for r in inactive:
            nm = str(r.get("name") or "Unknown")
            st = str(r.get("status") or "")
            names.append(f"{nm} ({st})")
        dbg["summary"] = ", ".join(names[:6]) if names else None

    # Cap for speed
    inactive = inactive[:max_teammates]

    # Player recent creation/min
    player_cre = []
    player_mins = []
    for g in last_games_10:
        m = g.get("min")
        c = _creation_proxy(g)
        if isinstance(m, (int, float)) and m > 0 and c is not None:
            player_mins.append(float(m))
            player_cre.append(float(c))
    player_cre_per_min = (sum(player_cre) / sum(player_mins)) if sum(player_mins) > 0 else None
    dbg["player"]["recentCreationPerMin"] = round(player_cre_per_min, 4) if player_cre_per_min is not None else None

    # Estimate missing minutes + missing creation/minute pool
    missing_minutes = 0.0
    missing_cre_per_min = 0.0  # weighted average of missing creation per min (not total)
    miss_cre_weighted_sum = 0.0
    miss_min_weighted_sum = 0.0

    for r in inactive:
        tid = int(r["athleteId"])
        w = float(r.get("weight") or 1.0)

        games, _dbg = build_last_games(tid, limit=10)
        mins = _avg([g.get("min") for g in games]) or 0.0

        # teammate creation per minute
        t_mins = []
        t_cre = []
        for g in games:
            m = g.get("min")
            c = _creation_proxy(g)
            if isinstance(m, (int, float)) and m > 0 and c is not None:
                t_mins.append(float(m))
                t_cre.append(float(c))
        cre_per_min = (sum(t_cre) / sum(t_mins)) if sum(t_mins) > 0 else None

        # apply status weight (questionable contributes partially)
        missing_minutes += w * mins
        if cre_per_min is not None:
            miss_cre_weighted_sum += (w * mins) * float(cre_per_min)
            miss_min_weighted_sum += (w * mins)

        dbg["inactiveTeammates"].append({
            "athleteId": tid,
            "name": r.get("name"),
            "status": r.get("status"),
            "w": round(w, 2),
            "avgMin10": round(mins, 2),
            "creationPerMin": (round(cre_per_min, 4) if cre_per_min is not None else None),
        })

    if miss_min_weighted_sum > 0:
        missing_cre_per_min = miss_cre_weighted_sum / miss_min_weighted_sum

    dbg["missing"]["minutes"] = round(missing_minutes, 2)
    dbg["missing"]["creationPerMin"] = round(missing_cre_per_min, 4)

    # If missing minutes small, don’t overreact
    if missing_minutes < 6.0:
        dbg["notes"].append("Missing minutes < 6 — skipping injury adjust.")
        return 0.0, {"pts": 1.0, "reb": 1.0, "ast": 1.0}, dbg

    dbg["used"] = True

    # -------------------------
    # Allocate minutes bump
    # -------------------------
    # Baseline: starters gain more; bench capped
    est = float(est_minutes or 32.0)
    role = "starter" if est >= 28 else ("rotation" if est >= 18 else "bench")
    dbg["notes"].append(f"Role bucket: {role}")

    # share based on role and minutes
    # (works surprisingly well without full roster minutes)
    base_share = clamp(est / 220.0, 0.05, 0.24)
    role_boost = 1.30 if role == "starter" else (1.05 if role == "rotation" else 0.75)

    minutes_add = missing_minutes * base_share * role_boost

    # cap minutes add (realistic)
    minutes_cap = 6.5 if role == "starter" else (4.0 if role == "rotation" else 2.5)
    minutes_add = clamp(minutes_add, 0.0, minutes_cap)

    # -------------------------
    # Allocate usage bump
    # -------------------------
    # Bigger effect when high-creation guys are missing
    # Use player creation/min vs missing creation/min as a “can absorb usage” gate
    if player_cre_per_min is None or missing_cre_per_min <= 1e-9:
        absorb = 0.55
    else:
        ratio = player_cre_per_min / missing_cre_per_min
        absorb = clamp(0.35 + 0.35 * ratio, 0.35, 0.95)

    # Scale with missing minutes (more missing = more usage opportunity)
    intensity = clamp(missing_minutes / 60.0, 0.10, 1.00)

    # Stat-specific multipliers
    pts_mult = 1.0 + clamp(0.22 * intensity * absorb, 0.0, 0.28)
    ast_mult = 1.0 + clamp(0.30 * intensity * absorb, 0.0, 0.35)
    reb_mult = 1.0 + clamp(0.10 * intensity, 0.0, 0.14)

    usage_mult = {"pts": round(pts_mult, 4), "reb": round(reb_mult, 4), "ast": round(ast_mult, 4)}

    dbg["result"]["minutesAdd"] = round(minutes_add, 2)
    dbg["result"]["usageMult"] = usage_mult
    dbg["notes"].append(f"Absorb={round(absorb, 3)} intensity={round(intensity, 3)}")

    return float(minutes_add), {"pts": float(pts_mult), "reb": float(reb_mult), "ast": float(ast_mult)}, dbg
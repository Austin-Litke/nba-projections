from __future__ import annotations

from mlb.api.client import get_hitter_stats


LEAGUE_K_RATE = 0.225

# Approx plate appearance exposure by lineup spot.
# Top of order matters more because they are more likely to face the starter again.
LINEUP_SPOT_WEIGHTS = {
    1: 1.12,
    2: 1.10,
    3: 1.08,
    4: 1.06,
    5: 1.03,
    6: 1.00,
    7: 0.96,
    8: 0.94,
    9: 0.91,
}

# PA threshold where we mostly trust hitter K%.
HITTER_FULL_WEIGHT_PA = 120


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return default


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _sample_weight(pa: float) -> float:
    return _clamp(pa / HITTER_FULL_WEIGHT_PA, 0.0, 1.0)


def _stabilize_k_rate(raw_k_rate: float | None, pa: float) -> float:
    if raw_k_rate is None:
        return LEAGUE_K_RATE

    w = _sample_weight(pa)
    return (w * raw_k_rate) + ((1.0 - w) * LEAGUE_K_RATE)


def _lineup_spot_from_batting_order(value) -> int | None:
    try:
        # MLB battingOrder is often "100", "200", ... "900"
        n = int(value)
        if n >= 100:
            spot = n // 100
        else:
            spot = n

        if 1 <= spot <= 9:
            return spot
    except Exception:
        return None

    return None


def _extract_hitter_k_profile(player_id: int | str, season: str) -> dict:
    payload = get_hitter_stats(str(player_id), season)
    people = payload.get("people") or []
    person = people[0] if people else {}

    stats = person.get("stats") or []
    stat = {}

    for block in stats:
        splits = block.get("splits") or []
        if splits:
            stat = (splits[0] or {}).get("stat") or {}
            break

    strikeouts = _safe_float(stat.get("strikeOuts"), 0.0)

    pa = _safe_float(stat.get("plateAppearances"), 0.0)
    if pa <= 0:
        ab = _safe_float(stat.get("atBats"), 0.0)
        bb = _safe_float(stat.get("baseOnBalls"), 0.0)
        hbp = _safe_float(stat.get("hitByPitch"), 0.0)
        sf = _safe_float(stat.get("sacFlies"), 0.0)
        pa = ab + bb + hbp + sf

    raw_k_rate = strikeouts / pa if pa > 0 else None
    stabilized_k_rate = _stabilize_k_rate(raw_k_rate, pa)

    return {
        "id": person.get("id") or player_id,
        "name": person.get("fullName"),
        "strikeOuts": int(strikeouts) if strikeouts else 0,
        "plateAppearances": round(pa, 1) if pa else 0,
        "rawKRate": round(raw_k_rate, 4) if raw_k_rate is not None else None,
        "kRate": round(stabilized_k_rate, 4),
        "sampleWeight": round(_sample_weight(pa), 3),
    }


def build_lineup_k_environment(lineup_batters: list[dict], season: str) -> dict:
    hitters = []

    for idx, batter in enumerate(lineup_batters or []):
        player_id = batter.get("id")
        if not player_id:
            continue

        spot = _lineup_spot_from_batting_order(batter.get("battingOrder")) or (idx + 1)
        spot_weight = LINEUP_SPOT_WEIGHTS.get(spot, 1.0)

        try:
            profile = _extract_hitter_k_profile(player_id, season)
        except Exception:
            profile = {
                "id": player_id,
                "name": batter.get("name"),
                "strikeOuts": 0,
                "plateAppearances": 0,
                "rawKRate": None,
                "kRate": LEAGUE_K_RATE,
                "sampleWeight": 0.0,
            }

        hitters.append({
            **batter,
            "lineupSpot": spot,
            "spotWeight": round(spot_weight, 3),
            "rawKRate": profile.get("rawKRate"),
            "kRate": profile.get("kRate"),
            "sampleWeight": profile.get("sampleWeight"),
            "plateAppearances": profile.get("plateAppearances"),
            "seasonStrikeOuts": profile.get("strikeOuts"),
        })

    valid = [h for h in hitters if h.get("kRate") is not None]

    if not valid:
        return {
            "source": "lineup_k_env_empty",
            "lineupKRate": None,
            "leagueKRate": LEAGUE_K_RATE,
            "adjustment": 1.0,
            "hittersUsed": 0,
            "hitters": hitters,
        }

    weighted_sum = 0.0
    weight_total = 0.0

    for h in valid:
        k_rate = _safe_float(h.get("kRate"), LEAGUE_K_RATE)
        weight = _safe_float(h.get("spotWeight"), 1.0)
        weighted_sum += k_rate * weight
        weight_total += weight

    lineup_k = weighted_sum / weight_total if weight_total > 0 else LEAGUE_K_RATE
    adj = lineup_k / LEAGUE_K_RATE if LEAGUE_K_RATE > 0 else 1.0
    adj = max(0.90, min(1.10, adj))

    raw_valid = [h for h in hitters if h.get("rawKRate") is not None]
    raw_lineup_k = None
    if raw_valid:
        raw_sum = 0.0
        raw_weight_total = 0.0
        for h in raw_valid:
            raw_sum += _safe_float(h.get("rawKRate"), LEAGUE_K_RATE) * _safe_float(h.get("spotWeight"), 1.0)
            raw_weight_total += _safe_float(h.get("spotWeight"), 1.0)
        raw_lineup_k = raw_sum / raw_weight_total if raw_weight_total > 0 else None

    return {
        "source": "lineup_k_env_weighted_stabilized",
        "lineupKRate": round(lineup_k, 4),
        "rawLineupKRate": round(raw_lineup_k, 4) if raw_lineup_k is not None else None,
        "leagueKRate": LEAGUE_K_RATE,
        "adjustment": round(adj, 3),
        "hittersUsed": len(valid),
        "weighting": "lineup_spot_weighted",
        "stabilization": {
            "leagueKRate": LEAGUE_K_RATE,
            "fullWeightPA": HITTER_FULL_WEIGHT_PA,
        },
        "hitters": hitters,
    }
from __future__ import annotations

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo


DB_PATH = os.path.join(os.path.dirname(__file__), "tracker_db.json")


def _now_iso() -> str:
    return datetime.now(ZoneInfo("America/Chicago")).isoformat()


def _read_db() -> dict:
    if not os.path.exists(DB_PATH):
        return {"predictions": []}

    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return {"predictions": []}

        data.setdefault("predictions", [])
        return data

    except Exception:
        return {"predictions": []}


def _write_db(data: dict):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def add_prediction(payload: dict) -> dict:
    db = _read_db()
    preds = db.setdefault("predictions", [])

    next_id = 1

    if preds:
        next_id = max(int(p.get("id", 0)) for p in preds) + 1

    row = {
        "id": next_id,
        "createdAt": _now_iso(),
        "settled": False,
        "actual": None,
        "result": None,
        **payload,
    }

    preds.append(row)

    _write_db(db)

    return row


def list_predictions() -> list[dict]:
    db = _read_db()
    preds = db.get("predictions") or []

    return sorted(
        preds,
        key=lambda p: p.get("createdAt") or "",
        reverse=True,
    )


def settle_prediction(pred_id: int, actual_value: float) -> dict | None:
    db = _read_db()
    preds = db.get("predictions") or []

    for p in preds:
        if int(p.get("id")) == int(pred_id):
            p["actual"] = actual_value
            p["settled"] = True

            line = p.get("line")
            side = (p.get("side") or "").lower()

            result = "unknown"

            if line is not None:
                if actual_value > line:
                    result = "over"
                elif actual_value < line:
                    result = "under"
                else:
                    result = "push"

            if result == side:
                p["result"] = "win"
            elif result == "push":
                p["result"] = "push"
            else:
                p["result"] = "loss"

            p["settledAt"] = _now_iso()

            _write_db(db)
            return p

    return None


def metrics() -> dict:
    preds = list_predictions()
    settled = [p for p in preds if p.get("settled") or p.get("result")]

    wins = 0
    losses = 0
    pushes = 0

    over_wins = 0
    over_losses = 0

    under_wins = 0
    under_losses = 0

    plus_ev_wins = 0
    plus_ev_losses = 0

    total_ev = 0.0
    ev_count = 0

    total_prob = 0.0
    prob_count = 0

    units = 0.0

    calibration = {
        "50-55": {"wins": 0, "losses": 0, "pushes": 0},
        "55-60": {"wins": 0, "losses": 0, "pushes": 0},
        "60-70": {"wins": 0, "losses": 0, "pushes": 0},
        "70+": {"wins": 0, "losses": 0, "pushes": 0},
    }

    for p in settled:
        result = (p.get("result") or "").lower()
        side = (p.get("side") or "").lower()

        sim = p.get("simulation") or {}

        over_ev = sim.get("overEV")
        under_ev = sim.get("underEV")

        over_prob = sim.get("probOver")
        under_prob = sim.get("probUnder")

        if result == "win":
            wins += 1
        elif result == "loss":
            losses += 1
        elif result == "push":
            pushes += 1

        if side == "over":
            if result == "win":
                over_wins += 1
            elif result == "loss":
                over_losses += 1

        if side == "under":
            if result == "win":
                under_wins += 1
            elif result == "loss":
                under_losses += 1

        chosen_ev = None
        chosen_prob = None
        odds = None

        if side == "over":
            chosen_ev = over_ev
            chosen_prob = over_prob
            odds = sim.get("overOdds")

        elif side == "under":
            chosen_ev = under_ev
            chosen_prob = under_prob
            odds = sim.get("underOdds")

        if chosen_ev is not None:
            total_ev += chosen_ev
            ev_count += 1

        if chosen_prob is not None:
            total_prob += chosen_prob
            prob_count += 1

        if chosen_ev is not None and chosen_ev > 0:
            if result == "win":
                plus_ev_wins += 1
            elif result == "loss":
                plus_ev_losses += 1

        if chosen_prob is not None:
            bucket = None

            if 0.50 <= chosen_prob < 0.55:
                bucket = "50-55"
            elif 0.55 <= chosen_prob < 0.60:
                bucket = "55-60"
            elif 0.60 <= chosen_prob < 0.70:
                bucket = "60-70"
            elif chosen_prob >= 0.70:
                bucket = "70+"

            if bucket:
                if result == "win":
                    calibration[bucket]["wins"] += 1
                elif result == "loss":
                    calibration[bucket]["losses"] += 1
                elif result == "push":
                    calibration[bucket]["pushes"] += 1

        if result == "win":
            try:
                odds = int(odds)

                if odds > 0:
                    units += odds / 100.0
                else:
                    units += 100.0 / abs(odds)

            except Exception:
                units += 1.0

        elif result == "loss":
            units -= 1.0

    graded = wins + losses
    total = wins + losses + pushes

    win_rate = (wins / graded) if graded > 0 else None
    roi = (units / graded) if graded > 0 else None

    avg_ev = (total_ev / ev_count) if ev_count > 0 else None
    avg_prob = (total_prob / prob_count) if prob_count > 0 else None

    calibration_out = {}

    for bucket, row in calibration.items():
        w = row["wins"]
        l = row["losses"]
        psh = row["pushes"]

        graded_bucket = w + l
        win_rate_bucket = (w / graded_bucket) if graded_bucket > 0 else None

        calibration_out[bucket] = {
            "record": f"{w}-{l}-{psh}",
            "winRate": round(win_rate_bucket, 3) if win_rate_bucket is not None else None,
            "count": w + l + psh,
        }

    return {
        "settled": total,
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "record": f"{wins}-{losses}-{pushes}",
        "winRate": round(win_rate, 3) if win_rate is not None else None,
        "units": round(units, 2),
        "roi": round(roi, 3) if roi is not None else None,
        "averageEV": round(avg_ev, 3) if avg_ev is not None else None,
        "averageProbability": round(avg_prob, 3) if avg_prob is not None else None,
        "overRecord": f"{over_wins}-{over_losses}",
        "underRecord": f"{under_wins}-{under_losses}",
        "plusEVRecord": f"{plus_ev_wins}-{plus_ev_losses}",
        "calibration": calibration_out,
    }


def counts() -> dict:
    preds = list_predictions()

    total = len(preds)

    settled = [
        p for p in preds
        if p.get("settled") or p.get("result")
    ]

    pending = [
        p for p in preds
        if not (p.get("settled") or p.get("result"))
    ]

    plus_ev = []

    for p in preds:
        side = (p.get("side") or "").lower()
        sim = p.get("simulation") or {}

        ev = None

        if side == "over":
            ev = sim.get("overEV")
        elif side == "under":
            ev = sim.get("underEV")

        if ev is not None and ev > 0:
            plus_ev.append(p)

    plus_ev_settled = [
        p for p in plus_ev
        if p.get("settled") or p.get("result")
    ]

    plus_ev_pending = [
        p for p in plus_ev
        if not (p.get("settled") or p.get("result"))
    ]

    return {
        "total": total,
        "pending": len(pending),
        "settled": len(settled),
        "plusEV": len(plus_ev),
        "plusEVSettled": len(plus_ev_settled),
        "plusEVPending": len(plus_ev_pending),
    }
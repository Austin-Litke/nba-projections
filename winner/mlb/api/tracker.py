from __future__ import annotations

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo


DB_PATH = os.path.join(os.path.dirname(__file__), "tracker_db.json")


def _now_iso() -> str:
    return datetime.now(ZoneInfo("America/Chicago")).isoformat()


def _ev_bucket(ev):
    try:
        ev = float(ev)
    except Exception:
        return None

    if ev < 0:
        return "negative"
    if ev < 0.05:
        return "0.00-0.05"
    if ev < 0.10:
        return "0.05-0.10"
    if ev < 0.20:
        return "0.10-0.20"
    if ev < 0.40:
        return "0.20-0.40"
    return "0.40+"



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

    ev_buckets = {
        "0-5": {"wins": 0, "losses": 0, "pushes": 0, "units": 0.0, "evTotal": 0.0, "count": 0},
        "5-10": {"wins": 0, "losses": 0, "pushes": 0, "units": 0.0, "evTotal": 0.0, "count": 0},
        "10-20": {"wins": 0, "losses": 0, "pushes": 0, "units": 0.0, "evTotal": 0.0, "count": 0},
        "20-40": {"wins": 0, "losses": 0, "pushes": 0, "units": 0.0, "evTotal": 0.0, "count": 0},
        "40+": {"wins": 0, "losses": 0, "pushes": 0, "units": 0.0, "evTotal": 0.0, "count": 0},
    }
    
    ev_buckets_by_side = {
        "over": {
            "0-5": {"wins": 0, "losses": 0, "pushes": 0, "units": 0.0, "evTotal": 0.0, "count": 0},
            "5-10": {"wins": 0, "losses": 0, "pushes": 0, "units": 0.0, "evTotal": 0.0, "count": 0},
            "10-20": {"wins": 0, "losses": 0, "pushes": 0, "units": 0.0, "evTotal": 0.0, "count": 0},
            "20-40": {"wins": 0, "losses": 0, "pushes": 0, "units": 0.0, "evTotal": 0.0, "count": 0},
            "40+": {"wins": 0, "losses": 0, "pushes": 0, "units": 0.0, "evTotal": 0.0, "count": 0},
        },
        "under": {
            "0-5": {"wins": 0, "losses": 0, "pushes": 0, "units": 0.0, "evTotal": 0.0, "count": 0},
            "5-10": {"wins": 0, "losses": 0, "pushes": 0, "units": 0.0, "evTotal": 0.0, "count": 0},
            "10-20": {"wins": 0, "losses": 0, "pushes": 0, "units": 0.0, "evTotal": 0.0, "count": 0},
            "20-40": {"wins": 0, "losses": 0, "pushes": 0, "units": 0.0, "evTotal": 0.0, "count": 0},
            "40+": {"wins": 0, "losses": 0, "pushes": 0, "units": 0.0, "evTotal": 0.0, "count": 0},
        },
    }
    
    
    line_buckets = {
        "3.5": {"wins": 0, "losses": 0, "pushes": 0, "units": 0.0, "evTotal": 0.0, "count": 0},
        "4.5": {"wins": 0, "losses": 0, "pushes": 0, "units": 0.0, "evTotal": 0.0, "count": 0},
        "5.5": {"wins": 0, "losses": 0, "pushes": 0, "units": 0.0, "evTotal": 0.0, "count": 0},
        "6.5+": {"wins": 0, "losses": 0, "pushes": 0, "units": 0.0, "evTotal": 0.0, "count": 0},
    }

    def ev_bucket_for(ev):
        if ev is None:
            return None

        try:
            ev = float(ev)
        except Exception:
            return None

        if ev < 0:
            return None
        if ev < 0.05:
            return "0-5"
        if ev < 0.10:
            return "5-10"
        if ev < 0.20:
            return "10-20"
        if ev < 0.40:
            return "20-40"
        return "40+"
    
    
    def line_bucket_for(line):
        try:
            line = float(line)
        except Exception:
            return None

        if line <= 3.5:
            return "3.5"
        if line <= 4.5:
            return "4.5"
        if line <= 5.5:
            return "5.5"

        return "6.5+"

    def profit_for_result(result, odds):
        if result == "win":
            try:
                odds = int(odds)

                if odds > 0:
                    return odds / 100.0

                return 100.0 / abs(odds)

            except Exception:
                return 1.0

        if result == "loss":
            return -1.0

        return 0.0



        line_bucket = line_bucket_for(p.get("line"))

        if line_bucket:
            line_row = line_buckets[line_bucket]

            line_row["count"] += 1
            line_row["evTotal"] += float(chosen_ev or 0)
            line_row["units"] += pick_units

            if result == "win":
                line_row["wins"] += 1
            elif result == "loss":
                line_row["losses"] += 1
            elif result == "push":
                line_row["pushes"] += 1


    for p in settled:
        result = (p.get("result") or "").lower()
        side = (p.get("side") or "").lower()

        sim = p.get("simulation") or {}

        over_ev = sim.get("overEV")
        under_ev = sim.get("underEV")

        over_prob = sim.get("probOver")
        under_prob = sim.get("probUnder")

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

        pick_units = profit_for_result(result, odds)

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

        ev_bucket = ev_bucket_for(chosen_ev)

        if ev_bucket:
            row = ev_buckets[ev_bucket]

            row["count"] += 1
            row["evTotal"] += float(chosen_ev or 0)
            row["units"] += pick_units

            if result == "win":
                row["wins"] += 1
            elif result == "loss":
                row["losses"] += 1
            elif result == "push":
                row["pushes"] += 1

            if side in ev_buckets_by_side:
                side_row = ev_buckets_by_side[side][ev_bucket]

                side_row["count"] += 1
                side_row["evTotal"] += float(chosen_ev or 0)
                side_row["units"] += pick_units

                if result == "win":
                    side_row["wins"] += 1
                elif result == "loss":
                    side_row["losses"] += 1
                elif result == "push":
                    side_row["pushes"] += 1

        units += pick_units

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

    ev_buckets_out = {}

    for bucket, row in ev_buckets.items():
        w = row["wins"]
        l = row["losses"]
        psh = row["pushes"]
        count = row["count"]
        graded_bucket = w + l

        win_rate_bucket = (w / graded_bucket) if graded_bucket > 0 else None
        roi_bucket = (row["units"] / graded_bucket) if graded_bucket > 0 else None
        avg_ev_bucket = (row["evTotal"] / count) if count > 0 else None

        ev_buckets_out[bucket] = {
            "record": f"{w}-{l}-{psh}",
            "wins": w,
            "losses": l,
            "pushes": psh,
            "count": count,
            "units": round(row["units"], 2),
            "roi": round(roi_bucket, 3) if roi_bucket is not None else None,
            "winRate": round(win_rate_bucket, 3) if win_rate_bucket is not None else None,
            "averageEV": round(avg_ev_bucket, 3) if avg_ev_bucket is not None else None,
        }



    ev_buckets_by_side_out = {}

    for side_key, buckets in ev_buckets_by_side.items():
        ev_buckets_by_side_out[side_key] = {}

        for bucket, row in buckets.items():
            w = row["wins"]
            l = row["losses"]
            psh = row["pushes"]
            count = row["count"]
            graded_bucket = w + l

            win_rate_bucket = (w / graded_bucket) if graded_bucket > 0 else None
            roi_bucket = (row["units"] / graded_bucket) if graded_bucket > 0 else None
            avg_ev_bucket = (row["evTotal"] / count) if count > 0 else None

            ev_buckets_by_side_out[side_key][bucket] = {
                "record": f"{w}-{l}-{psh}",
                "wins": w,
                "losses": l,
                "pushes": psh,
                "count": count,
                "units": round(row["units"], 2),
                "roi": round(roi_bucket, 3) if roi_bucket is not None else None,
                "winRate": round(win_rate_bucket, 3) if win_rate_bucket is not None else None,
                "averageEV": round(avg_ev_bucket, 3) if avg_ev_bucket is not None else None,
            }
            
            
    line_buckets_out = {}

    for bucket, row in line_buckets.items():
        w = row["wins"]
        l = row["losses"]
        psh = row["pushes"]
        count = row["count"]
        graded_bucket = w + l

        win_rate_bucket = (w / graded_bucket) if graded_bucket > 0 else None
        roi_bucket = (row["units"] / graded_bucket) if graded_bucket > 0 else None
        avg_ev_bucket = (row["evTotal"] / count) if count > 0 else None

        line_buckets_out[bucket] = {
            "record": f"{w}-{l}-{psh}",
            "wins": w,
            "losses": l,
            "pushes": psh,
            "count": count,
            "units": round(row["units"], 2),
            "roi": round(roi_bucket, 3) if roi_bucket is not None else None,
            "winRate": round(win_rate_bucket, 3) if win_rate_bucket is not None else None,
            "averageEV": round(avg_ev_bucket, 3) if avg_ev_bucket is not None else None,
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
        "evBuckets": ev_buckets_out,
        "evBucketsBySide": ev_buckets_by_side_out,
        "lineBuckets": line_buckets_out,
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
    
def update_clv(pred_id: int, clv_payload: dict) -> dict | None:
    db = _read_db()
    preds = db.get("predictions") or []

    for p in preds:
        if int(p.get("id")) == int(pred_id):
            p["clv"] = {
                "updatedAt": _now_iso(),
                **clv_payload,
            }

            _write_db(db)
            return p

    return None
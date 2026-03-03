# winner/sports/api/nba_tracker.py

from __future__ import annotations
import os
import json
import math
from typing import Any, Dict, List, Optional

from .nba_client import http_get, safe_json_load, ESPN_SUMMARY

DB_PATH = os.path.join(os.path.dirname(__file__), "tracker_db.json")


def _now_iso() -> str:
    import datetime
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _read_db() -> Dict[str, Any]:
    if not os.path.exists(DB_PATH):
        return {"version": 1, "predictions": []}
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"version": 1, "predictions": []}


def _write_db(db: Dict[str, Any]) -> None:
    tmp = DB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DB_PATH)


def add_prediction(rec: Dict[str, Any]) -> Dict[str, Any]:
    db = _read_db()
    preds = db.get("predictions", [])
    if not isinstance(preds, list):
        preds = []

    next_id = 1
    if preds:
        try:
            next_id = max(int(p.get("id", 0)) for p in preds) + 1
        except Exception:
            next_id = len(preds) + 1

    out = {
        "id": next_id,
        "createdAt": _now_iso(),
        "settledAt": None,
        "athleteId": int(rec.get("athleteId")),
        "stat": str(rec.get("stat")),
        "line": float(rec.get("line")),
        "probOver": float(rec.get("probOver")),
        "fairLine": float(rec.get("fairLine")),
        "projectionP50": float(rec.get("projectionP50")),
        "opponentTeamId": rec.get("opponentTeamId"),
        "gameId": rec.get("gameId"),       # optional but required to auto-settle
        "gameDate": rec.get("gameDate"),   # optional
        "actual": None,
        "result": None,                    # "over"|"under"|None
        "meta": rec.get("meta") or {},
    }

    preds.append(out)
    db["predictions"] = preds
    _write_db(db)
    return out


def list_predictions(athlete_id: Optional[int] = None) -> List[Dict[str, Any]]:
    db = _read_db()
    preds = db.get("predictions", [])
    if not isinstance(preds, list):
        return []
    if athlete_id is None:
        return preds
    return [p for p in preds if str(p.get("athleteId")) == str(athlete_id)]


def _extract_actual_from_summary(summary_data: dict, athlete_id: int) -> Optional[Dict[str, float]]:
    box = summary_data.get("boxscore") or {}
    players = box.get("players") or []
    if not isinstance(players, list):
        return None

    target = str(athlete_id)

    for team_block in players:
        stat_tables = team_block.get("statistics") or []
        if not isinstance(stat_tables, list):
            continue

        for table in stat_tables:
            labels = table.get("labels") or table.get("keys") or []
            athletes = table.get("athletes") or []
            if not isinstance(labels, list) or not isinstance(athletes, list):
                continue

            idx = {lab: i for i, lab in enumerate(labels) if isinstance(lab, str)}

            for a in athletes:
                ainfo = a.get("athlete") or {}
                aid = ainfo.get("id")
                if str(aid) != target:
                    continue

                stats = a.get("stats") or []
                if not isinstance(stats, list) or not stats:
                    continue

                def get(lab):
                    i = idx.get(lab)
                    if i is None or i >= len(stats):
                        return None
                    return stats[i]

                def to_int(x):
                    try:
                        return int(float(x))
                    except Exception:
                        return None

                pts = to_int(get("PTS"))
                reb = to_int(get("REB"))
                ast = to_int(get("AST"))
                if pts is None and reb is None and ast is None:
                    return None
                return {"pts": float(pts or 0), "reb": float(reb or 0), "ast": float(ast or 0)}
    return None


def settle_prediction(pred_id: int) -> Dict[str, Any]:
    db = _read_db()
    preds = db.get("predictions", [])
    if not isinstance(preds, list):
        raise ValueError("DB is corrupted")

    p = next((x for x in preds if int(x.get("id", -1)) == int(pred_id)), None)
    if not p:
        raise ValueError("Prediction not found")

    if p.get("settledAt"):
        return p

    game_id = p.get("gameId")
    athlete_id = int(p.get("athleteId"))
    stat = p.get("stat")
    line = float(p.get("line"))

    if not game_id:
        raise ValueError("Missing gameId on prediction; cannot settle automatically")

    url = ESPN_SUMMARY.format(gameId=str(game_id))
    data = safe_json_load(http_get(url))
    actuals = _extract_actual_from_summary(data, athlete_id)
    if not actuals:
        raise ValueError("Could not find player in boxscore (maybe DNP)")

    actual = float(actuals.get(stat, 0.0))
    p["actual"] = actual
    p["settledAt"] = _now_iso()
    p["result"] = "over" if actual > (line + 0.5) else "under"

    _write_db(db)
    return p


def _brier(prob: float, y: int) -> float:
    return (prob - y) ** 2


def _logloss(prob: float, y: int) -> float:
    p = min(1 - 1e-9, max(1e-9, prob))
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def metrics(preds: List[Dict[str, Any]]) -> Dict[str, Any]:
    settled = [p for p in preds if p.get("settledAt") and p.get("actual") is not None]
    if not settled:
        return {"count": 0, "brier": None, "logloss": None, "calibration": []}

    bs = []
    ll = []
    bins = [{"lo": i / 10, "hi": (i + 1) / 10, "n": 0, "avgP": None, "hitRate": None} for i in range(10)]
    sum_p = [0.0] * 10
    sum_y = [0.0] * 10

    for p in settled:
        prob = float(p.get("probOver"))
        y = 1 if p.get("result") == "over" else 0
        bs.append(_brier(prob, y))
        ll.append(_logloss(prob, y))

        idx = min(9, max(0, int(prob * 10)))
        bins[idx]["n"] += 1
        sum_p[idx] += prob
        sum_y[idx] += y

    for i in range(10):
        n = bins[i]["n"]
        if n > 0:
            bins[i]["avgP"] = round(sum_p[i] / n, 4)
            bins[i]["hitRate"] = round(sum_y[i] / n, 4)

    return {
        "count": len(settled),
        "brier": round(sum(bs) / len(bs), 6),
        "logloss": round(sum(ll) / len(ll), 6),
        "calibration": bins,
    }
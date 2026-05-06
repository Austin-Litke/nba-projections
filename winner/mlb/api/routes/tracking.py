from __future__ import annotations

from mlb.api.tracker import (
    add_prediction,
    list_predictions,
    settle_prediction,
    metrics,
    counts,
)
from mlb.api.client import get_game_boxscore
from mlb.api.utils import read_json_body


def get_tracked(qs):
    return 200, {
        "ok": True,
        "counts": counts(),
        "metrics": metrics(),
        "predictions": list_predictions(),
    }


def post_track(handler):
    body = read_json_body(handler)

    if not isinstance(body, dict):
        return 400, {"error": "Invalid JSON body"}

    pitcher = body.get("pitcher") or {}
    line = body.get("line")

    if not pitcher.get("id"):
        return 400, {"error": "pitcher.id is required"}

    if line is None:
        return 400, {"error": "line is required"}

    saved = add_prediction(body)

    return 200, {
        "ok": True,
        "prediction": saved,
    }


def post_settle(handler):
    body = read_json_body(handler)

    pred_id = body.get("id")
    game_id = body.get("gameId")
    pitcher_id = body.get("pitcherId")

    if not pred_id or not game_id or not pitcher_id:
        return 400, {"error": "id, gameId, pitcherId required"}

    payload = get_game_boxscore(str(game_id))
    teams = payload.get("teams") or {}

    all_players = []

    for side in ("away", "home"):
        team = teams.get(side) or {}
        players = team.get("players") or {}
        all_players.extend(players.values())

    actual_ks = None

    for p in all_players:
        person = p.get("person") or {}

        if str(person.get("id")) == str(pitcher_id):
            stats = (p.get("stats") or {}).get("pitching") or {}
            actual_ks = stats.get("strikeOuts")
            break

    if actual_ks is None:
        return 404, {"error": "Pitcher stats not found"}

    updated = settle_prediction(pred_id, float(actual_ks))

    if not updated:
        return 404, {"error": "Prediction not found"}

    return 200, {
        "ok": True,
        "prediction": updated,
    }


def post_settle_all(handler):
    preds = list_predictions()

    pending = [
        p for p in preds
        if not (p.get("settled") or p.get("result"))
    ]

    settled = []
    errors = []

    for p in pending:
        pred_id = p.get("id")
        game_id = (p.get("matchup") or {}).get("gameId")
        pitcher_id = (p.get("pitcher") or {}).get("id")

        if not pred_id or not game_id or not pitcher_id:
            errors.append({
                "id": pred_id,
                "error": "Missing id, gameId, or pitcherId",
            })
            continue

        try:
            payload = get_game_boxscore(str(game_id))
            teams = payload.get("teams") or {}

            all_players = []

            for side in ("away", "home"):
                team = teams.get(side) or {}
                players = team.get("players") or {}
                all_players.extend(players.values())

            actual_ks = None

            for player in all_players:
                person = player.get("person") or {}

                if str(person.get("id")) == str(pitcher_id):
                    stats = (player.get("stats") or {}).get("pitching") or {}
                    actual_ks = stats.get("strikeOuts")
                    break

            if actual_ks is None:
                errors.append({
                    "id": pred_id,
                    "error": "Pitcher stats not found",
                })
                continue

            updated = settle_prediction(pred_id, float(actual_ks))

            if updated:
                settled.append(updated)
            else:
                errors.append({
                    "id": pred_id,
                    "error": "Prediction not found",
                })

        except Exception as e:
            errors.append({
                "id": pred_id,
                "error": str(e),
            })

    return 200, {
        "ok": True,
        "settledCount": len(settled),
        "errorCount": len(errors),
        "settled": settled,
        "errors": errors,
    }
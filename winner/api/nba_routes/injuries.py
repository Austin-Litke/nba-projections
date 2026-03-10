# api/nba_routes/injuries.py
from __future__ import annotations

from sports.api.nba_client import http_get, safe_json_load, ESPN_CORE_ATHLETE


def extract_event_injuries(event_id: str):
    # returns flat list with team mapping
    url = (
        "https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
        f"?region=us&lang=en&contentorigin=espn&event={event_id}"
    )
    data = safe_json_load(http_get(url))

    # walk JSON and pull injury objects
    injuries = []
    stack = [data]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            inj = node.get("injuries")
            if isinstance(inj, list):
                for it in inj:
                    if isinstance(it, dict) and isinstance(it.get("athlete"), dict) and isinstance(it.get("status"), str):
                        injuries.append(it)
            for v in node.values():
                stack.append(v)
        elif isinstance(node, list):
            for v in node:
                stack.append(v)

    out = []
    for it in injuries:
        ath = it.get("athlete") or {}
        athlete_id = str(ath.get("id") or "").strip()
        if not athlete_id.isdigit():
            continue

        # map athlete -> team using core endpoint
        ath_url = ESPN_CORE_ATHLETE.format(athleteId=int(athlete_id))
        ath_json = safe_json_load(http_get(ath_url))

        # try common team shapes
        team = ath_json.get("team") or {}
        team_id = team.get("id")
        team_name = team.get("displayName") or team.get("name")

        out.append({
            "athleteId": int(athlete_id),
            "name": ath.get("displayName") or ath.get("fullName") or "—",
            "status": it.get("status"),
            "injType": (it.get("details") or {}).get("type"),
            "detail": (it.get("details") or {}).get("detail"),
            "returnDate": (it.get("details") or {}).get("returnDate"),
            "teamId": int(team_id) if str(team_id).isdigit() else None,
            "teamName": team_name,
        })

    return out


def get_event_injuries(qs: dict):
    event_id = (qs.get("eventId", [""])[0] or "").strip()
    if not event_id.isdigit():
        return 400, {"error": "eventId required"}

    rows = extract_event_injuries(event_id)

    # group by team
    by_team = {}
    for r in rows:
        key = str(r.get("teamId") or "unknown")
        by_team.setdefault(key, {"teamId": r.get("teamId"), "teamName": r.get("teamName"), "players": []})
        by_team[key]["players"].append(r)

    # sort players: Out/Suspension/Doubtful first
    order = {"Out": 0, "Suspension": 0, "Doubtful": 1, "Questionable": 2, "Day-To-Day": 3}
    for k in by_team:
        by_team[k]["players"].sort(key=lambda x: order.get(x.get("status") or "", 9))

    return 200, {
        "eventId": int(event_id),
        "teams": list(by_team.values()),
        "count": len(rows),
    }
# api/nba_routes/injuries.py
from __future__ import annotations

from sports.api.nba_client import http_get, safe_json_load, ESPN_CORE_ATHLETE


def _load_event_summary(event_id: str | int):
    url = (
        "https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
        f"?region=us&lang=en&contentorigin=espn&event={event_id}"
    )
    return safe_json_load(http_get(url))


def extract_event_teams(event_id: str | int):
    data = _load_event_summary(event_id)

    teams = []
    seen = set()

    for comp in (((data or {}).get("header") or {}).get("competitions") or []):
        for c in (comp.get("competitors") or []):
            team = c.get("team") or {}
            tid = team.get("id")
            if not str(tid).isdigit():
                continue

            tid_int = int(tid)
            if tid_int in seen:
                continue
            seen.add(tid_int)

            teams.append({
                "teamId": tid_int,
                "teamName": team.get("displayName") or team.get("name") or "—",
                "abbrev": team.get("abbreviation") or "",
                "homeAway": c.get("homeAway"),
                "winner": c.get("winner"),
            })

    return teams


def _team_ctx_from_node(node: dict):
    """
    Try to identify a team context from the current dict node.
    ESPN summary payloads can embed team info in a few different shapes.
    """
    candidates = []

    if isinstance(node.get("team"), dict):
        candidates.append(node.get("team"))

    if isinstance(node.get("competitor"), dict):
        comp = node.get("competitor") or {}
        if isinstance(comp.get("team"), dict):
            candidates.append(comp.get("team"))

    # Sometimes competitor objects themselves contain team-like fields
    candidates.append(node)

    for team in candidates:
        tid = team.get("id")
        if str(tid).isdigit():
            return {
                "teamId": int(tid),
                "teamName": team.get("displayName") or team.get("name") or "—",
                "abbrev": team.get("abbreviation") or "",
            }

    return None


def extract_event_injuries(event_id: str | int):
    """
    Returns flat list of injury rows.

    Main strategy:
    - recursively walk the event summary
    - carry forward the current team context whenever we enter a team/competitor node
    - when an injuries list is found, attach that current team context to each injury row

    Fallback:
    - if no team context is available for an injury, try ESPN_CORE_ATHLETE
    """
    data = _load_event_summary(event_id)

    out = []
    seen = set()

    def walk(node, team_ctx=None):
        if isinstance(node, dict):
            local_team_ctx = _team_ctx_from_node(node) or team_ctx

            inj = node.get("injuries")
            if isinstance(inj, list):
                for it in inj:
                    if not isinstance(it, dict):
                        continue
                    ath = it.get("athlete") or {}
                    athlete_id = str(ath.get("id") or "").strip()
                    status = it.get("status")

                    if not athlete_id.isdigit() or not isinstance(status, str):
                        continue

                    team_id = None
                    team_name = None

                    if local_team_ctx:
                        team_id = local_team_ctx.get("teamId")
                        team_name = local_team_ctx.get("teamName")

                    # fallback only if summary context did not provide team
                    if team_id is None:
                        try:
                            ath_url = ESPN_CORE_ATHLETE.format(athleteId=int(athlete_id))
                            ath_json = safe_json_load(http_get(ath_url))
                            team = ath_json.get("team") or {}
                            tid = team.get("id")
                            if str(tid).isdigit():
                                team_id = int(tid)
                            team_name = team_name or team.get("displayName") or team.get("name")
                        except Exception:
                            pass

                    key = (athlete_id, str(status), str(team_id))
                    if key in seen:
                        continue
                    seen.add(key)

                    out.append({
                        "athleteId": int(athlete_id),
                        "name": ath.get("displayName") or ath.get("fullName") or "—",
                        "status": status,
                        "injType": (it.get("details") or {}).get("type"),
                        "detail": (it.get("details") or {}).get("detail"),
                        "returnDate": (it.get("details") or {}).get("returnDate"),
                        "teamId": team_id,
                        "teamName": team_name,
                    })

            for v in node.values():
                walk(v, local_team_ctx)

        elif isinstance(node, list):
            for v in node:
                walk(v, team_ctx)

    walk(data, None)
    return out


def get_event_injuries(qs: dict):
    event_id = (qs.get("eventId", [""])[0] or "").strip()
    if not event_id.isdigit():
        return 400, {"error": "eventId required"}

    rows = extract_event_injuries(event_id)
    event_teams = extract_event_teams(event_id)

    by_team = {}
    for r in rows:
        key = str(r.get("teamId") or "unknown")
        by_team.setdefault(
            key,
            {
                "teamId": r.get("teamId"),
                "teamName": r.get("teamName"),
                "players": [],
            },
        )
        by_team[key]["players"].append(r)

    order = {"Out": 0, "Suspension": 0, "Doubtful": 1, "Questionable": 2, "Day-To-Day": 3}
    for k in by_team:
        by_team[k]["players"].sort(key=lambda x: order.get(x.get("status") or "", 9))

    return 200, {
        "eventId": int(event_id),
        "teams": list(by_team.values()),
        "count": len(rows),
        "eventTeams": event_teams,
    }
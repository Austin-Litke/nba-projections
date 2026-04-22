from __future__ import annotations

from mlb.api.client import get_person
from mlb.api.lines import lines_for_pitcher_strikeouts


def _first(qs, key: str, default: str = "") -> str:
    return (qs.get(key) or [default])[0]


def get_underdog_lines(qs):
    pitcher_id = _first(qs, "pitcherId").strip()
    if not pitcher_id:
        return 400, {"error": "pitcherId is required"}

    payload = get_person(pitcher_id)
    people = payload.get("people") or []
    person = people[0] if people else {}

    name = person.get("fullName") or ""
    if not name:
        return 404, {"error": "Pitcher not found"}

    lines = lines_for_pitcher_strikeouts(name)

    return 200, {
        "ok": True,
        "pitcherId": pitcher_id,
        "name": name,
        "lines": lines,
    }
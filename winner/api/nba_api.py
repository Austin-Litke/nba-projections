# api/nba_api.py
from __future__ import annotations

from urllib.parse import urlparse, parse_qs

import sports.api.nba_simulator as nba_simulator_mod

from api.nba_helpers.errors import err_with_trace

from api.nba_routes.core import get_scoreboard, get_teams, get_roster
from api.nba_routes.injuries import get_event_injuries
from api.nba_routes.lines import get_underdog_debug, get_underdog_lines
from api.nba_routes.player import (
    get_player,
    get_player_gamelog,
    get_player_gamelog_raw,
    get_player_webstats_raw,
    get_player_vs_opponent,
    get_player_projection,
)
from api.nba_routes.tracking import (
    get_tracked,
    get_tracked_metrics,
    post_track,
    post_settle,
    post_assess_line,
)

GET_ROUTES = {
    "/api/nba/scoreboard": get_scoreboard,
    "/api/nba/teams": get_teams,
    "/api/nba/roster": get_roster,
    "/api/nba/event_injuries": get_event_injuries,

    "/api/nba/player_webstats_raw": get_player_webstats_raw,
    "/api/nba/player_gamelog_raw": get_player_gamelog_raw,

    "/api/nba/player": get_player,
    "/api/nba/player_gamelog": get_player_gamelog,
    "/api/nba/player_vs_opponent": get_player_vs_opponent,

    # Pass simulator module for debug stamping
    "/api/nba/player_projection": lambda qs: get_player_projection(qs, nba_simulator_mod_passed=nba_simulator_mod),

    "/api/nba/underdog_debug": get_underdog_debug,
    "/api/nba/underdog_lines": get_underdog_lines,
    "/api/nba/over_under_lines": get_underdog_lines,

    "/api/nba/tracked": get_tracked,
    "/api/nba/tracked_metrics": get_tracked_metrics,
}

POST_ROUTES = {
    "/api/nba/track": post_track,
    "/api/nba/settle": post_settle,

    # Pass simulator module for debug stamping
    "/api/nba/assess_line": lambda handler: post_assess_line(handler, nba_simulator_mod=nba_simulator_mod),
}


def handle_get(path: str, query: str):
    parsed = urlparse(path + (("?" + query) if query else ""))
    qs = parse_qs(parsed.query)

    try:
        fn = GET_ROUTES.get(parsed.path)
        if not fn:
            return None
        return fn(qs)
    except Exception as e:
        return 500, err_with_trace(e)


def handle_post(handler, path: str):
    parsed = urlparse(path)

    try:
        fn = POST_ROUTES.get(parsed.path)
        if not fn:
            return None
        return fn(handler)
    except Exception as e:
        return 500, err_with_trace(e)
from __future__ import annotations

from urllib.parse import urlparse, parse_qs

from mlb.api.helpers.errors import err_with_trace
from mlb.api.routes.core import get_health, get_scoreboard
from mlb.api.routes.pitcher import get_pitcher, get_pitcher_gamelog


GET_ROUTES = {
    "/api/mlb/health": get_health,
    "/api/mlb/scoreboard": get_scoreboard,
    "/api/mlb/pitcher": get_pitcher,
    "/api/mlb/pitcher_gamelog": get_pitcher_gamelog,
}

POST_ROUTES = {
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
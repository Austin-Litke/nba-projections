# winner/sports/api/nba_client.py

import json
import urllib.request
from urllib.parse import urlparse
import time

_CACHE = {}  # url -> (expires_at, bytes)
_DEFAULT_TTL = 60  # seconds

# ESPN endpoints (these are the ones we’ve been using successfully)
ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date}"
ESPN_TEAMS = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"
ESPN_ROSTER = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{teamId}/roster"

# Athlete “core” (sometimes used for name/team)
ESPN_CORE_ATHLETE = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/athletes/{athleteId}?lang=en&region=us"

# Web JSON athlete stats (where we extracted season averages)
ESPN_WEB_STATS = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{athleteId}/stats?region=us&lang=en&contentorigin=espn"

# Web JSON gamelog
ESPN_WEB_GAMELOG = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{athleteId}/gamelog?region=us&lang=en"

# Box score / game summary (works for extracting a player's line)
ESPN_SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={gameId}"

ESPN_SEARCH = "https://site.web.api.espn.com/apis/common/v3/search?query={q}&limit=10"

_ALLOWED_HOST_SUFFIXES = (
    "espn.com",
)

_ALLOWED_HOSTS = (
    "site.api.espn.com",
    "sports.core.api.espn.com",
    "site.web.api.espn.com",
    "www.espn.com",
    "m.espn.com",

    # ✅ ADD: Underdog Fantasy
    "api.underdogfantasy.com",
)

_DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Winner Arcade; +local dev)",
    "Accept": "application/json",
}


def _is_allowed_url(url: str) -> (bool, str):
    p = urlparse(url)
    if p.scheme.lower() != "https":
        return False, "Blocked URL (only https allowed)"
    host = (p.hostname or "").lower()
    if host in _ALLOWED_HOSTS:
        return True, ""
    if any(host.endswith(suf) for suf in _ALLOWED_HOST_SUFFIXES):
        return True, ""
    return False, "Blocked URL (only ESPN domains allowed)"


def http_get(url: str, timeout: int = 20, ttl: int = _DEFAULT_TTL) -> bytes:
    ok, reason = _is_allowed_url(url)
    if not ok:
        raise ValueError(f"{reason}: {url}")

    now = time.time()
    hit = _CACHE.get(url)
    if hit:
        exp, data = hit
        if now < exp:
            return data
        else:
            _CACHE.pop(url, None)

    req = urllib.request.Request(url, headers=_DEFAULT_HEADERS, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()

    _CACHE[url] = (now + ttl, data)
    return data


def safe_json_load(raw: bytes | str):
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    return json.loads(raw)
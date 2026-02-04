from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import (
    playergamelog,
    teamgamelog,
    leaguedashteamstats,
)

# -----------------------------
# Cache setup
# -----------------------------
BASE_CACHE = Path(__file__).parent / "cache"
PLAYER_CACHE_DIR = BASE_CACHE / "players"
TEAM_CACHE_DIR = BASE_CACHE / "teams"
PLAYER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
TEAM_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# -----------------------------
# Helpers
# -----------------------------
def _find_player(name: str) -> dict:
    all_players = players.get_players()
    name = name.lower().strip()

    matches = [p for p in all_players if p["full_name"].lower() == name]
    if not matches:
        raise ValueError(f"Player '{name}' not found (try exact full name).")
    return matches[0]


def _player_cache_path(player_id: int, season: str) -> Path:
    # season-specific cache so you don't mix seasons
    safe = season.replace("/", "-")
    return PLAYER_CACHE_DIR / f"{player_id}_{safe}.json"


def _load_player_cache(player_id: int, season: str) -> dict | None:
    path = _player_cache_path(player_id, season)
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return None


def _save_player_cache(player_id: int, season: str, data: dict):
    with open(_player_cache_path(player_id, season), "w") as f:
        json.dump(data, f, indent=2)


def _team_ratings_cache_path(season: str) -> Path:
    safe = season.replace("/", "-")
    return TEAM_CACHE_DIR / f"team_ratings_{safe}.json"


def _load_team_ratings(season: str) -> dict | None:
    path = _team_ratings_cache_path(season)
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return None


def _save_team_ratings(season: str, data: dict):
    with open(_team_ratings_cache_path(season), "w") as f:
        json.dump(data, f, indent=2)


def _infer_usage_role(ppg: float, apg: float) -> str:
    """
    Simple, effective heuristic:
      - primary: high scorer or high assist
      - secondary: decent scorer
      - support: everyone else
    """
    if ppg >= 22.0 or apg >= 7.0:
        return "primary"
    if ppg >= 14.0:
        return "secondary"
    return "support"


def _compute_min_volatility(last_10_min: list[float]) -> float:
    """
    Returns a multiplier ~ [1.0 .. 1.25]
    Higher = minutes are more volatile (riskier for props, especially unders/overs).
    """
    if not last_10_min:
        return 1.10
    s = pd.Series(last_10_min)
    mean = float(s.mean())
    std = float(s.std(ddof=0))  # population std
    if mean <= 1e-6:
        return 1.15
    cv = std / mean  # coefficient of variation
    # Map CV to a reasonable band
    # typical starters: 0.03-0.08; bench: 0.10-0.25
    vol = 1.0 + (cv * 1.2)  # scale
    return float(max(1.0, min(1.25, vol)))


# -----------------------------
# Public API: Player data
# -----------------------------
def load_player_data(name: str, season: str) -> dict:
    """
    Loads REAL NBA data and returns the SAME STRUCTURE your model expects.
    Adds:
      - usage_role
      - min_volatility
    """
    player = _find_player(name)
    player_id = player["id"]

    cached = _load_player_cache(player_id, season)
    if cached:
        return cached

    gl = playergamelog.PlayerGameLog(
        player_id=player_id,
        season=season,
        season_type_all_star="Regular Season",
    )
    df = gl.get_data_frames()[0]
    if df.empty:
        raise RuntimeError("No games returned for player.")

    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
    df = df.sort_values("GAME_DATE")

    games_played = int(len(df))
    min_total = float(df["MIN"].sum())
    pts_total = float(df["PTS"].sum())
    reb_total = float(df["REB"].sum())
    ast_total = float(df["AST"].sum())

    # ---- season totals ----
    season_data = {
        "games_played": games_played,
        "min_total": min_total,
        "pts_total": pts_total,
        "reb_total": reb_total,
        "ast_total": ast_total,
    }

    # ---- last 10 ----
    tail = df.tail(10)
    last_10 = [
        {"min": float(r["MIN"]), "pts": float(r["PTS"]), "reb": float(r["REB"]), "ast": float(r["AST"])}
        for _, r in tail.iterrows()
    ]
    last_10_min = [g["min"] for g in last_10]

    # ---- starter vs bench ----
    starts = int((tail["START_POSITION"].notna()).sum())
    role = "starter" if starts >= 6 else "bench"

    # ---- usage_role + minutes volatility ----
    ppg = pts_total / max(1, games_played)
    apg = ast_total / max(1, games_played)
    usage_role = _infer_usage_role(ppg, apg)
    min_volatility = _compute_min_volatility(last_10_min)

    data = {
        "role": role,                     # starter/bench
        "usage_role": usage_role,         # primary/secondary/support
        "min_volatility": min_volatility, # 1.0..1.25

        # small, stable home/away multipliers (you can tune later)
        "home_mult": 1.04,
        "away_mult": 0.97,

        # OUT boost dict is kept, but model now uses usage_role for smarter redistribution
        "out_boost": {"min": 1.0, "pts": 2.0, "ast": 0.5, "reb": 0.0},

        "season": season_data,
        "last_10": last_10,
        "vs_opp": {},  # (optional later: fill with H2H)
    }

    _save_player_cache(player_id, season, data)
    return data


# -----------------------------
# Public API: Next game info
# -----------------------------
def get_player_team_abbr(name: str, season: str) -> str:
    """
    Uses the player's most recent game to determine their team.
    """
    player = _find_player(name)
    player_id = player["id"]

    gl = playergamelog.PlayerGameLog(
        player_id=player_id,
        season=season,
        season_type_all_star="Regular Season",
    )
    df = gl.get_data_frames()[0]
    if df.empty:
        raise RuntimeError("Could not determine player's team.")
    return str(df.iloc[-1]["TEAM_ABBREVIATION"])


def get_next_game(team_abbr: str, season: str) -> dict:
    """
    Determines the next scheduled game for a team.
    Returns:
      { "opp_abbr": "DEN", "is_home": True }
    """
    team = next(t for t in teams.get_teams() if t["abbreviation"] == team_abbr)
    team_id = team["id"]

    tg = teamgamelog.TeamGameLog(
        team_id=team_id,
        season=season,
        season_type_all_star="Regular Season",
    )
    df = tg.get_data_frames()[0]
    if df.empty:
        raise RuntimeError("No games found for team.")

    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
    today = pd.Timestamp.utcnow().normalize()

    future = df[df["GAME_DATE"] > today]
    if future.empty:
        raise RuntimeError("No upcoming games found (teamgamelog may not include future games).")

    next_game = future.sort_values("GAME_DATE").iloc[0]
    matchup = str(next_game["MATCHUP"])

    is_home = "vs" in matchup
    opp_abbr = matchup.split()[-1]
    return {"opp_abbr": opp_abbr, "is_home": bool(is_home)}


# -----------------------------
# Public API: Blowout risk (NEW)
# -----------------------------
def get_team_net_ratings(season: str) -> dict:
    """
    Returns dict: { "MIN": net_rating, "DEN": net_rating, ... }
    Cached to disk.
    """
    cached = _load_team_ratings(season)
    if cached:
        return cached

    # Team advanced stats table contains NET_RATING
    endpoint = leaguedashteamstats.LeagueDashTeamStats(
        season=season,
        season_type_all_star="Regular Season",
        measure_type_detailed_defense="Advanced",
    )
    df = endpoint.get_data_frames()[0]
    if df.empty:
        raise RuntimeError("Could not load team ratings.")

    out = {}
    for _, r in df.iterrows():
        abbr = str(r.get("TEAM_ABBREVIATION"))
        net = float(r.get("NET_RATING"))
        out[abbr] = net

    _save_team_ratings(season, out)
    return out


def estimate_blowout_risk(team_abbr: str, opp_abbr: str, season: str) -> float | None:
    """
    Approximate blowout risk using NET_RATING gap.
    Returns 0..1, where higher = more blowout risk.
    If ratings can't be loaded, returns None.
    """
    try:
        nets = get_team_net_ratings(season)
        a = float(nets[team_abbr])
        b = float(nets[opp_abbr])
    except Exception:
        return None

    gap = abs(a - b)

    # Map rating gap to risk:
    # <4  → ~0.0
    # 8   → ~0.4
    # 12  → ~0.8
    # 15+ → 1.0
    risk = (gap - 4.0) / 11.0
    return float(max(0.0, min(1.0, risk)))

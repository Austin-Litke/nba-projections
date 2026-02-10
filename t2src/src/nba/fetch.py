from __future__ import annotations

import time
from datetime import date
from typing import Iterable

import pandas as pd
from nba_api.stats.endpoints import scoreboardv2, commonteamroster, playergamelogs

from src.config import Config
from src.utils.cache import cache_path, load_parquet_if_exists, save_parquet, ensure_dir
from src.utils.logging import get_logger

log = get_logger("nba.fetch")

def fetch_todays_games(cfg: Config, game_date: date) -> pd.DataFrame:
    """
    Returns games scheduled for the given date (local date).
    """
    ensure_dir(cfg.cache_dir)
    cache = cache_path(cfg.cache_dir, f"scoreboard_{game_date.isoformat()}")
    cached = load_parquet_if_exists(cache)
    if cached is not None and len(cached) > 0:
        return cached

    log.info(f"Fetching scoreboard for {game_date.isoformat()}...")
    resp = scoreboardv2.ScoreboardV2(game_date=game_date.strftime("%m/%d/%Y"))
    # GameHeader has one row per game
    game_header = resp.get_data_frames()[0].copy()
    save_parquet(game_header, cache)
    time.sleep(cfg.api_sleep_seconds)
    return game_header

def fetch_team_roster(cfg: Config, team_id: int, season: str) -> pd.DataFrame:
    ensure_dir(cfg.cache_dir)
    cache = cache_path(cfg.cache_dir, f"roster_{season}_{team_id}")
    cached = load_parquet_if_exists(cache)
    if cached is not None and len(cached) > 0:
        return cached

    log.info(f"Fetching roster for team_id={team_id}, season={season}...")
    resp = commonteamroster.CommonTeamRoster(team_id=team_id, season=season)
    roster = resp.get_data_frames()[0].copy()
    # roster contains PLAYER_ID, PLAYER, etc.
    save_parquet(roster, cache)
    time.sleep(cfg.api_sleep_seconds)
    return roster

def fetch_player_game_logs_season(cfg: Config, season: str, season_type: str) -> pd.DataFrame:
    """
    Pulls a full player-game table for the season. Cache it because it’s large.
    """
    ensure_dir(cfg.cache_dir)
    cache = cache_path(cfg.cache_dir, f"playergamelogs_{season}_{season_type.replace(' ', '_')}")
    cached = load_parquet_if_exists(cache)
    if cached is not None and len(cached) > 0:
        return cached

    log.info(f"Fetching PlayerGameLogs for season={season}, type={season_type}...")
    resp = playergamelogs.PlayerGameLogs(
        season_nullable=season,
        season_type_nullable=season_type
    )
    df = resp.get_data_frames()[0].copy()
    save_parquet(df, cache)
    time.sleep(cfg.api_sleep_seconds)
    return df

def teams_playing_today(games_df: pd.DataFrame) -> list[int]:
    """
    From GameHeader, extract HOME_TEAM_ID and VISITOR_TEAM_ID.
    """
    cols = set(games_df.columns)
    needed = {"HOME_TEAM_ID", "VISITOR_TEAM_ID"}
    if not needed.issubset(cols):
        raise ValueError(f"Scoreboard missing expected columns: {needed - cols}")

    team_ids = pd.concat([
        games_df["HOME_TEAM_ID"],
        games_df["VISITOR_TEAM_ID"],
    ]).dropna().astype(int).unique().tolist()

    return sorted(team_ids)

def players_on_teams(cfg: Config, team_ids: Iterable[int]) -> pd.DataFrame:
    """
    Returns combined roster players for all team_ids.
    """
    frames = []
    for tid in team_ids:
        frames.append(fetch_team_roster(cfg, tid, cfg.season))
    out = pd.concat(frames, ignore_index=True)
    # Keep key columns; roster schema can change slightly, so be defensive:
    keep = [c for c in ["TEAM_ID", "PLAYER", "PLAYER_ID", "POSITION", "NUM"] if c in out.columns]
    return out[keep].drop_duplicates(subset=["PLAYER_ID"])

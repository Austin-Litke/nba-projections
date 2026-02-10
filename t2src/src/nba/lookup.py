from __future__ import annotations

import time
import pandas as pd
from nba_api.stats.endpoints import commonallplayers

from src.config import Config
from src.utils.cache import cache_path, load_parquet_if_exists, save_parquet, ensure_dir
from src.utils.logging import get_logger

log = get_logger("nba.lookup")

def fetch_all_players(cfg: Config) -> pd.DataFrame:
    """
    Pull a master player list and cache it.
    """
    ensure_dir(cfg.cache_dir / "lookups")
    cache = cache_path(cfg.cache_dir / "lookups", "commonallplayers")
    cached = load_parquet_if_exists(cache)
    if cached is not None and len(cached) > 0:
        return cached

    log.info("Fetching CommonAllPlayers list...")
    resp = commonallplayers.CommonAllPlayers(is_only_current_season=1)
    df = resp.get_data_frames()[0].copy()
    save_parquet(df, cache)
    time.sleep(cfg.api_sleep_seconds)
    return df

def find_player_id(cfg: Config, query: str) -> pd.DataFrame:
    """
    Returns matching players (so you can choose if multiple matches).
    """
    df = fetch_all_players(cfg)
    # CommonAllPlayers usually has DISPLAY_FIRST_LAST and PERSON_ID
    name_col = "DISPLAY_FIRST_LAST" if "DISPLAY_FIRST_LAST" in df.columns else None
    id_col = "PERSON_ID" if "PERSON_ID" in df.columns else None
    if not name_col or not id_col:
        raise ValueError("Unexpected CommonAllPlayers schema (missing DISPLAY_FIRST_LAST or PERSON_ID).")

    q = query.strip().lower()
    hits = df[df[name_col].str.lower().str.contains(q, na=False)].copy()
    hits = hits[[name_col, id_col]]
    hits = hits.rename(columns={name_col: "player_name", id_col: "player_id"})
    hits["player_id"] = hits["player_id"].astype(int)
    return hits.sort_values("player_name").reset_index(drop=True)

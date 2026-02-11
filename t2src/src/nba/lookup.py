from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from nba_api.stats.endpoints import commonallplayers

from src.config import Config
from src.utils.cache import (
    ensure_dir,
    cache_path,
    load_parquet_if_exists,
    save_parquet,
)
from src.utils.logging import get_logger

log = get_logger("nba.lookup")


# -----------------------------
# Manual fallback (offline)
# -----------------------------
def _manual_lookup_path(cfg: Config) -> Path:
    return cfg.cache_dir / "lookups" / "player_manual.csv"


def fallback_manual_lookup(cfg: Config, query: str) -> pd.DataFrame:
    """
    Offline fallback: looks in data/cache/lookups/player_manual.csv
    Expected columns: player_name, player_id
    """
    path = _manual_lookup_path(cfg)
    if not path.exists():
        return pd.DataFrame(columns=["player_name", "player_id"])

    df = pd.read_csv(path)
    if "player_name" not in df.columns or "player_id" not in df.columns:
        raise ValueError(f"Manual lookup file must have columns: player_name, player_id. Found: {list(df.columns)}")

    q = query.strip().lower()
    hits = df[df["player_name"].astype(str).str.lower().str.contains(q, na=False)].copy()
    if hits.empty:
        return pd.DataFrame(columns=["player_name", "player_id"])

    hits["player_id"] = pd.to_numeric(hits["player_id"], errors="coerce")
    hits = hits.dropna(subset=["player_id"]).copy()
    hits["player_id"] = hits["player_id"].astype(int)

    return hits[["player_name", "player_id"]].sort_values("player_name").reset_index(drop=True)


# -----------------------------
# Online lookup (nba_api)
# -----------------------------
def fetch_all_players(cfg: Config) -> pd.DataFrame:
    """
    Fetches CommonAllPlayers (current season) and caches it.
    Adds: retries + larger timeout so it works at home even if stats.nba.com is flaky.
    """
    ensure_dir(cfg.cache_dir / "lookups")
    cache = cache_path(cfg.cache_dir / "lookups", "commonallplayers")
    cached = load_parquet_if_exists(cache)
    if cached is not None and len(cached) > 0:
        return cached

    log.info("Fetching CommonAllPlayers list...")

    last_err: Optional[Exception] = None
    for attempt in range(1, 6):
        try:
            # nba_api supports timeout kwarg on endpoint constructors in recent versions
            resp = commonallplayers.CommonAllPlayers(
                is_only_current_season=1,
                timeout=120
            )
            df = resp.get_data_frames()[0].copy()

            # Cache it
            save_parquet(df, cache)
            time.sleep(cfg.api_sleep_seconds)
            return df

        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
            last_err = e
            backoff = 2 ** (attempt - 1)
            log.warning(
                f"CommonAllPlayers attempt {attempt}/5 failed: {e}. "
                f"Retrying in {backoff}s..."
            )
            time.sleep(backoff)

        except Exception as e:
            # Catch-all: schema changes, blocked network, etc.
            last_err = e
            log.warning(f"CommonAllPlayers attempt {attempt}/5 failed: {e}")
            time.sleep(2 ** (attempt - 1))

    raise RuntimeError(f"Failed to fetch CommonAllPlayers after retries. Last error: {last_err}")


def find_player_id(cfg: Config, query: str) -> pd.DataFrame:
    """
    Returns matching players with columns:
      - player_name
      - player_id

    Strategy:
      1) Try cached/API CommonAllPlayers
      2) If blocked/unavailable, use manual fallback CSV
    """
    query = (query or "").strip()
    if not query:
        return pd.DataFrame(columns=["player_name", "player_id"])

    # 1) Try online/cached lookup
    try:
        df = fetch_all_players(cfg)

        name_col = "DISPLAY_FIRST_LAST"
        id_col = "PERSON_ID"

        if name_col not in df.columns or id_col not in df.columns:
            raise ValueError(
                f"Unexpected CommonAllPlayers schema. "
                f"Missing {name_col} or {id_col}. Columns: {list(df.columns)}"
            )

        q = query.lower()
        hits = df[df[name_col].astype(str).str.lower().str.contains(q, na=False)].copy()

        if hits.empty:
            return pd.DataFrame(columns=["player_name", "player_id"])

        hits = hits[[name_col, id_col]].rename(columns={name_col: "player_name", id_col: "player_id"})
        hits["player_id"] = pd.to_numeric(hits["player_id"], errors="coerce")
        hits = hits.dropna(subset=["player_id"]).copy()
        hits["player_id"] = hits["player_id"].astype(int)

        return hits.sort_values("player_name").reset_index(drop=True)

    except Exception as e:
        log.warning(f"CommonAllPlayers unavailable ({e}). Trying manual lookup fallback...")
        return fallback_manual_lookup(cfg, query)

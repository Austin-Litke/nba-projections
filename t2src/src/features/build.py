from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import Config

EPS = 1e-6

def build_player_game_features(cfg: Config, df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Input: PlayerGameLogs dataframe (one row per player-game).
    Output: Adds leakage-safe rolling features + targets for training.
    """
    df = df_raw.copy()

    # Required columns (defensive)
    required = {"PLAYER_ID", "GAME_DATE", "MIN", "PTS"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in logs: {missing}")

    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"], errors="coerce")
    df["PLAYER_ID"] = pd.to_numeric(df["PLAYER_ID"], errors="coerce").astype("Int64")
    df["MIN"] = pd.to_numeric(df["MIN"], errors="coerce")
    df["PTS"] = pd.to_numeric(df["PTS"], errors="coerce")

    df = df.dropna(subset=["PLAYER_ID", "GAME_DATE", "MIN", "PTS"]).copy()
    df = df.sort_values(["PLAYER_ID", "GAME_DATE"]).reset_index(drop=True)

    g = df.groupby("PLAYER_ID", group_keys=False)

    # Rolling means (shifted to avoid leakage)
    for w in cfg.roll_windows:
        df[f"MIN_roll{w}"] = g["MIN"].apply(lambda s: s.shift(1).rolling(w).mean())
        df[f"PTS_roll{w}"] = g["PTS"].apply(lambda s: s.shift(1).rolling(w).mean())

    # EWMA points (shifted)
    alpha = cfg.ewma_alpha
    df["PTS_ewma"] = g["PTS"].apply(lambda s: s.shift(1).ewm(alpha=1 - alpha, adjust=False).mean())

    # Training target for rate model
    df["PTS_per_min"] = df["PTS"] / (df["MIN"] + EPS)

    # Drop rows without enough history (at least roll5 and ewma)
    needed = [f"MIN_roll5", f"PTS_roll5", "PTS_ewma"]
    df = df.dropna(subset=needed).reset_index(drop=True)

    return df

def feature_columns_minutes(cfg: Config) -> list[str]:
    # Starter set (expand later)
    cols = ["MIN_roll5", "MIN_roll10", "PTS_roll5", "PTS_ewma"]
    return cols

def feature_columns_rate(cfg: Config) -> list[str]:
    cols = ["PTS_roll5", "PTS_roll10", "PTS_ewma", "MIN_roll5"]
    return cols

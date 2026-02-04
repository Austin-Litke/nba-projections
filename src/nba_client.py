from __future__ import annotations

import pandas as pd
from dataclasses import dataclass
from rapidfuzz import process, fuzz

from nba_api.stats.static import players
from nba_api.stats.endpoints import playergamelog


@dataclass(frozen=True)
class PlayerMatch:
    player_id: int
    full_name: str


def find_player(name: str) -> PlayerMatch:
    all_players = players.get_players()
    names = [p["full_name"] for p in all_players]

    best = process.extractOne(name, names, scorer=fuzz.WRatio)
    if not best or best[1] < 70:
        raise ValueError(f"Couldn't confidently match '{name}'. Try full name.")

    full_name = best[0]
    rec = next(p for p in all_players if p["full_name"] == full_name)
    return PlayerMatch(player_id=int(rec["id"]), full_name=rec["full_name"])


def get_player_gamelog_df(player_id: int, season: str, season_type: str = "Regular Season") -> pd.DataFrame:
    gl = playergamelog.PlayerGameLog(
        player_id=player_id,
        season=season,
        season_type_all_star=season_type,
    )
    df = gl.get_data_frames()[0]
    if df.empty:
        return df

    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"], errors="coerce")

    numeric_cols = ["MIN", "PTS", "REB", "AST", "TOV", "STL", "BLK", "PLUS_MINUS"]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.sort_values("GAME_DATE").reset_index(drop=True)

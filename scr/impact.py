from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Iterable, Set
import numpy as np
import pandas as pd

from nba_client import get_player_gamelog_df


@dataclass(frozen=True)
class TeammateDelta:
    d_min: float
    d_pts: float
    d_reb: float
    d_ast: float
    n_out: int
    n_in: int


def _safe_mean(s: pd.Series) -> float:
    if s is None or len(s) == 0:
        return 0.0
    return float(np.nanmean(s.to_numpy(dtype=float)))


def _delta_for_teammate(
    teammate_df: pd.DataFrame,
    out_game_ids: Set[str],
    in_game_ids: Set[str],
    min_out_games: int = 2,
    min_in_games: int = 5,
) -> TeammateDelta:
    out_rows = teammate_df[teammate_df["GAME_ID"].isin(out_game_ids)]
    in_rows = teammate_df[teammate_df["GAME_ID"].isin(in_game_ids)]

    n_out = int(len(out_rows))
    n_in = int(len(in_rows))

    if n_out < min_out_games or n_in < min_in_games:
        return TeammateDelta(0.0, 0.0, 0.0, 0.0, n_out=n_out, n_in=n_in)

    return TeammateDelta(
        d_min=_safe_mean(out_rows["MIN"]) - _safe_mean(in_rows["MIN"]),
        d_pts=_safe_mean(out_rows["PTS"]) - _safe_mean(in_rows["PTS"]),
        d_reb=_safe_mean(out_rows["REB"]) - _safe_mean(in_rows["REB"]),
        d_ast=_safe_mean(out_rows["AST"]) - _safe_mean(in_rows["AST"]),
        n_out=n_out,
        n_in=n_in,
    )


def build_out_impact_map(
    team_game_ids: Set[str],
    out_player_id: int,
    teammate_ids: Iterable[int],
    season: str,
) -> Dict[int, TeammateDelta]:
    out_df = get_player_gamelog_df(out_player_id, season=season)
    played_ids = set(out_df["GAME_ID"].astype(str).tolist())

    out_game_ids = set(str(g) for g in team_game_ids if str(g) not in played_ids)
    in_game_ids = set(str(g) for g in team_game_ids if str(g) in played_ids)

    impacts: Dict[int, TeammateDelta] = {}
    for tid in teammate_ids:
        if tid == out_player_id:
            continue
        tdf = get_player_gamelog_df(tid, season=season)
        impacts[int(tid)] = _delta_for_teammate(tdf, out_game_ids, in_game_ids)

    return impacts

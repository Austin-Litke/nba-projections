from __future__ import annotations
from dataclasses import dataclass
import pandas as pd

from nba_api.stats.endpoints import commonplayerinfo, leaguedashteamstats


@dataclass(frozen=True)
class TeamContext:
    team_id: int
    opp_team_id: int
    is_home: bool
    matchup_text: str
    team_pace: float
    opp_pace: float
    opp_def_rating: float
    league_pace: float
    league_def_rating: float


def get_player_team_id(player_id: int) -> int:
    info = commonplayerinfo.CommonPlayerInfo(player_id=player_id).get_data_frames()[0]
    return int(info.loc[0, "TEAM_ID"])


def get_team_advanced_df(season: str, season_type: str = "Regular Season") -> pd.DataFrame:
    df = leaguedashteamstats.LeagueDashTeamStats(
        season=season,
        season_type_all_star=season_type,
        per_mode_detailed="PerGame",
        measure_type_detailed_defense="Advanced",
    ).get_data_frames()[0]
    return df


def build_team_context(season: str, player_team_id: int, next_game: dict) -> TeamContext:
    home_id = int(next_game["homeTeam"]["teamId"])
    away_id = int(next_game["awayTeam"]["teamId"])
    is_home = (home_id == player_team_id)
    opp_id = away_id if is_home else home_id

    matchup = f'{next_game["awayTeam"]["teamTricode"]} @ {next_game["homeTeam"]["teamTricode"]}'

    df = get_team_advanced_df(season=season)

    def _get(team_id: int, col: str) -> float:
        row = df[df["TEAM_ID"] == team_id]
        if row.empty:
            raise ValueError(f"Team {team_id} not found in team stats.")
        if col not in row.columns:
            raise ValueError(f"Column '{col}' missing in team stats.")
        return float(row.iloc[0][col])

    def _league_avg(col: str) -> float:
        if col not in df.columns:
            raise ValueError(f"Column '{col}' missing in team stats.")
        return float(df[col].mean())

    return TeamContext(
        team_id=player_team_id,
        opp_team_id=opp_id,
        is_home=is_home,
        matchup_text=matchup,
        team_pace=_get(player_team_id, "PACE"),
        opp_pace=_get(opp_id, "PACE"),
        opp_def_rating=_get(opp_id, "DEF_RATING"),
        league_pace=_league_avg("PACE"),
        league_def_rating=_league_avg("DEF_RATING"),
    )

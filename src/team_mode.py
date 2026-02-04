from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
import pandas as pd
from rapidfuzz import process, fuzz

from nba_api.stats.static import teams
from nba_api.stats.endpoints import leaguegamefinder, boxscoretraditionalv2

from schedule import get_next_game_for_team
from team_context import build_team_context
from projections import project_from_gamelog, apply_matchup_adjustments, Projection
from nba_client import get_player_gamelog_df


@dataclass(frozen=True)
class TeamPlayerProjection:
    player_id: int
    name: str
    min: float
    pts: float
    reb: float
    ast: float
    sigma_pts: float
    sigma_reb: float
    sigma_ast: float


def _guess_current_season_year() -> str:
    now = dt.datetime.now()
    y = now.year
    return f"{y}-{str(y+1)[-2:]}" if now.month >= 10 else f"{y-1}-{str(y)[-2:]}"


def resolve_team(team_query: str) -> dict:
    all_teams = teams.get_teams()
    tq = team_query.strip().upper()

    for t in all_teams:
        if t.get("abbreviation", "").upper() == tq:
            return t

    candidates = []
    for t in all_teams:
        candidates.extend([t["full_name"], t["nickname"], t["city"], t["abbreviation"]])

    best = process.extractOne(team_query, candidates, scorer=fuzz.WRatio)
    if not best or best[1] < 70:
        raise ValueError(f"Couldn't match team '{team_query}'. Try MIN, LAL, BOS, etc.")

    s = best[0]
    for t in all_teams:
        if s in (t["full_name"], t["nickname"], t["city"], t["abbreviation"]):
            return t

    best2 = process.extractOne(team_query, [t["full_name"] for t in all_teams], scorer=fuzz.WRatio)
    if not best2:
        raise ValueError(f"Couldn't match team '{team_query}'.")
    return next(t for t in all_teams if t["full_name"] == best2[0])


def get_recent_team_game_ids(team_id: int, n_games: int = 8) -> List[str]:
    gf = leaguegamefinder.LeagueGameFinder(team_id_nullable=team_id)
    df = gf.get_data_frames()[0]
    if df.empty:
        return []
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
    df = df.sort_values("GAME_DATE").tail(n_games)
    return [str(x) for x in df["GAME_ID"].tolist()]


def get_team_game_ids(team_id: int, season: str, season_type: str = "Regular Season") -> List[str]:
    gf = leaguegamefinder.LeagueGameFinder(
        team_id_nullable=team_id,
        season_nullable=season,
        season_type_nullable=season_type,
    )
    df = gf.get_data_frames()[0]
    if df.empty:
        return []
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
    df = df.sort_values("GAME_DATE")
    return [str(x) for x in df["GAME_ID"].tolist()]


def get_active_players_from_boxscores(game_ids: List[str], min_games_played: int = 2) -> pd.DataFrame:
    rows = []
    for gid in game_ids:
        bs = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=gid)
        pdf = bs.get_data_frames()[0]
        if pdf.empty:
            continue

        pdf = pdf.copy()
        pdf["MIN_STR"] = pdf["MIN"].astype(str)

        def min_to_float(x: str) -> float:
            if ":" in x:
                m, s = x.split(":")
                try:
                    return float(m) + float(s) / 60.0
                except Exception:
                    return 0.0
            try:
                return float(x)
            except Exception:
                return 0.0

        pdf["MIN_F"] = pdf["MIN_STR"].map(min_to_float)
        pdf = pdf[pdf["MIN_F"] > 0.0]
        rows.append(pdf[["PLAYER_ID", "PLAYER_NAME", "MIN_F"]])

    if not rows:
        return pd.DataFrame(columns=["PLAYER_ID", "PLAYER_NAME", "games_played_recent", "avg_min_recent"])

    allp = pd.concat(rows, ignore_index=True)
    agg = (
        allp.groupby(["PLAYER_ID", "PLAYER_NAME"])
        .agg(games_played_recent=("MIN_F", "count"), avg_min_recent=("MIN_F", "mean"))
        .reset_index()
    )
    agg = agg[agg["games_played_recent"] >= min_games_played]
    agg = agg.sort_values("avg_min_recent", ascending=False).reset_index(drop=True)
    return agg


def minutes_model_from_gamelog(df: pd.DataFrame, window: int = 12) -> Tuple[float, float]:
    if df.empty:
        return 0.0, 0.0

    recent = df.sort_values("GAME_DATE").tail(window).copy()
    mins = recent["MIN"].to_numpy(dtype=float)
    n = len(mins)

    half_life = max(4.0, window / 2)
    idx = np.arange(n)[::-1]
    w = 0.5 ** (idx / half_life)
    w = w / w.sum()

    mu = float(np.sum(mins * w))

    if n >= 8:
        last4 = float(np.mean(mins[-4:]))
        prev4 = float(np.mean(mins[-8:-4]))
        trend = float(np.clip((last4 - prev4) / 4.0, -1.5, 1.5))
        mu = float(np.clip(mu + trend, 6.0, 42.0))
    else:
        mu = float(np.clip(mu, 6.0, 42.0))

    m = float(np.sum(mins * w))
    var = float(np.sum(w * (mins - m) ** 2))
    sigma = float(np.sqrt(max(var, 4.0)))  # floor

    return mu, sigma


def project_player_for_next_game(player_id: int, season: str, ctx) -> Projection:
    df = get_player_gamelog_df(player_id, season=season)
    base = project_from_gamelog(df, window=15)

    min_mu, _ = minutes_model_from_gamelog(df, window=12)
    base.min = float(min_mu)

    recent = df.sort_values("GAME_DATE").tail(15).copy()
    mins = np.clip(recent["MIN"].to_numpy(dtype=float), 1.0, None)

    def rate(col: str) -> float:
        y = recent[col].to_numpy(dtype=float)
        r = y / mins
        n = len(r)
        idx = np.arange(n)[::-1]
        w = 0.5 ** (idx / 7.0)
        w = w / w.sum()
        return float(np.sum(r * w))

    base.pts = float(rate("PTS") * base.min)
    base.reb = float(rate("REB") * base.min)
    base.ast = float(rate("AST") * base.min)

    return apply_matchup_adjustments(base, ctx)


def build_team_projection_table(team_query: str, n_recent_games_scan: int = 8, top_n: int = 12):
    season = _guess_current_season_year()
    team = resolve_team(team_query)
    team_id = int(team["id"])

    next_game = get_next_game_for_team(team_id, now_utc=dt.datetime.now(dt.timezone.utc))
    ctx = build_team_context(season=season, player_team_id=team_id, next_game=next_game)

    recent_game_ids = get_recent_team_game_ids(team_id, n_games=n_recent_games_scan)
    active_df = get_active_players_from_boxscores(recent_game_ids, min_games_played=2)
    if active_df.empty:
        raise ValueError("Couldn't find active players from recent boxscores. Try increasing scan games.")

    projections = []
    for _, r in active_df.head(max(top_n * 2, top_n)).iterrows():
        pid = int(r["PLAYER_ID"])
        name = str(r["PLAYER_NAME"])
        try:
            proj = project_player_for_next_game(pid, season=season, ctx=ctx)
        except Exception:
            continue

        projections.append(
            TeamPlayerProjection(
                player_id=pid,
                name=name,
                min=proj.min,
                pts=proj.pts,
                reb=proj.reb,
                ast=proj.ast,
                sigma_pts=proj.sigma_pts,
                sigma_reb=proj.sigma_reb,
                sigma_ast=proj.sigma_ast,
            )
        )

    if not projections:
        raise ValueError("No projections generated (API may be blocked/rate-limited). Try again.")

    pdf = pd.DataFrame([p.__dict__ for p in projections])
    pdf = pdf.sort_values("min", ascending=False).head(top_n).reset_index(drop=True)

    team_game_ids = set(get_team_game_ids(team_id, season=season))

    meta = {
        "season": season,
        "team_id": team_id,
        "team_name": team["full_name"],
        "team_abbr": team["abbreviation"],
        "matchup": ctx.matchup_text,
        "is_home": ctx.is_home,
        "pace_team": ctx.team_pace,
        "pace_opp": ctx.opp_pace,
        "pace_league": ctx.league_pace,
        "opp_def": ctx.opp_def_rating,
        "def_league": ctx.league_def_rating,
        "active_players_df": active_df,
        "team_game_ids": team_game_ids,
    }
    return pdf, meta


def match_player_in_table(name: str, proj_df: pd.DataFrame) -> Tuple[int, str]:
    candidates = proj_df["name"].tolist()
    best = process.extractOne(name, candidates, scorer=fuzz.WRatio)
    if not best or best[1] < 70:
        raise ValueError(f"Couldn't match '{name}' to a player in this team table.")
    canonical = best[0]
    row = proj_df[proj_df["name"] == canonical].iloc[0]
    return int(row["player_id"]), canonical

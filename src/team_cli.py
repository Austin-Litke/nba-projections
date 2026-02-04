from __future__ import annotations

import re
from typing import Dict, Set, Tuple

import pandas as pd
from rich.console import Console
from rich.table import Table

from team_mode import build_team_projection_table, match_player_in_table
from ou import over_under
from impact import build_out_impact_map, TeammateDelta

console = Console()


def render_table(df: pd.DataFrame, title: str, out_ids: Set[int]):
    t = Table(title=title)
    t.add_column("Status", justify="left")
    t.add_column("Player")
    t.add_column("MIN", justify="right")
    t.add_column("PTS", justify="right")
    t.add_column("REB", justify="right")
    t.add_column("AST", justify="right")

    for _, r in df.iterrows():
        pid = int(r["player_id"])
        status = "OUT" if pid in out_ids else ""
        t.add_row(
            status,
            str(r["name"]),
            f'{float(r["min"]):.1f}',
            f'{float(r["pts"]):.1f}',
            f'{float(r["reb"]):.1f}',
            f'{float(r["ast"]):.1f}',
        )
    console.print(t)


def show_impact_report(
    base_df: pd.DataFrame,
    meta: dict,
    out_player_id: int,
    out_player_name: str,
    impact_cache,
    top_n: int = 10,
):
    season = meta["season"]
    team_id = meta["team_id"]
    team_game_ids = meta["team_game_ids"]
    teammate_ids = [int(x) for x in base_df["player_id"].tolist()]

    key = (team_id, out_player_id)
    if key not in impact_cache:
        impact_cache[key] = build_out_impact_map(
            team_game_ids=team_game_ids,
            out_player_id=out_player_id,
            teammate_ids=teammate_ids,
            season=season,
        )

    impacts = impact_cache[key]

    rows = []
    for _, r in base_df.iterrows():
        pid = int(r["player_id"])
        if pid == out_player_id:
            continue
        d = impacts.get(pid)
        if not d:
            continue
        rows.append({
            "Player": r["name"],
            "dMIN": d.d_min,
            "dPTS": d.d_pts,
            "dREB": d.d_reb,
            "dAST": d.d_ast,
            "n_OUT": d.n_out,
            "n_IN": d.n_in,
        })

    if not rows:
        console.print("[yellow]No impact data available.[/yellow]")
        return

    rdf = pd.DataFrame(rows)

    def conf(n_out: int) -> str:
        if n_out >= 10:
            return "High"
        if n_out >= 5:
            return "Medium"
        if n_out >= 2:
            return "Low"
        return "None"

    rdf["Conf"] = rdf["n_OUT"].map(lambda x: conf(int(x)))
    rdf = rdf.sort_values(["dPTS", "dMIN"], ascending=False).head(top_n).reset_index(drop=True)

    t = Table(title=f"Impact when OUT: {out_player_name}  (season {season})")
    t.add_column("Teammate")
    t.add_column("dMIN", justify="right")
    t.add_column("dPTS", justify="right")
    t.add_column("dREB", justify="right")
    t.add_column("dAST", justify="right")
    t.add_column("OUT", justify="right")
    t.add_column("IN", justify="right")
    t.add_column("Conf", justify="left")

    for _, r in rdf.iterrows():
        t.add_row(
            str(r["Player"]),
            f'{float(r["dMIN"]):+.2f}',
            f'{float(r["dPTS"]):+.2f}',
            f'{float(r["dREB"]):+.2f}',
            f'{float(r["dAST"]):+.2f}',
            str(int(r["n_OUT"])),
            str(int(r["n_IN"])),
            str(r["Conf"]),
        )

    console.print(t)
    console.print("[dim]Deltas = teammate averages in games player was OUT minus games they played.[/dim]\n")


def apply_out_adjustments(
    base_df: pd.DataFrame,
    out_ids: Set[int],
    meta: dict,
    impact_cache: Dict[Tuple[int, int], Dict[int, TeammateDelta]],
) -> pd.DataFrame:
    df = base_df.copy()

    season = meta["season"]
    team_id = meta["team_id"]
    team_game_ids = meta["team_game_ids"]

    df["min_adj"] = 0.0
    df["pts_adj"] = 0.0
    df["reb_adj"] = 0.0
    df["ast_adj"] = 0.0

    teammate_ids = [int(x) for x in df["player_id"].tolist()]

    # Multi-OUT dampener
    k = max(1, len(out_ids))
    damp = 1.0 / (1.0 + 0.33 * (k - 1))

    for out_pid in out_ids:
        key = (team_id, out_pid)
        if key not in impact_cache:
            impact_cache[key] = build_out_impact_map(
                team_game_ids=team_game_ids,
                out_player_id=out_pid,
                teammate_ids=teammate_ids,
                season=season,
            )

        impacts = impact_cache[key]
        for i, row in df.iterrows():
            pid = int(row["player_id"])
            if pid == out_pid:
                continue
            d = impacts.get(pid)
            if not d:
                continue
            df.at[i, "min_adj"] += damp * d.d_min
            df.at[i, "pts_adj"] += damp * d.d_pts
            df.at[i, "reb_adj"] += damp * d.d_reb
            df.at[i, "ast_adj"] += damp * d.d_ast

    df["min"] = df["min"] + df["min_adj"]
    df["pts"] = df["pts"] + df["pts_adj"]
    df["reb"] = df["reb"] + df["reb_adj"]
    df["ast"] = df["ast"] + df["ast_adj"]

    # Prevent "creating minutes": total minutes gained shouldn't exceed minutes removed
    removed = float(base_df[base_df["player_id"].isin(list(out_ids))]["min"].sum())
    gained = float(df[~df["player_id"].isin(list(out_ids))]["min_adj"].clip(lower=0.0).sum())
    if gained > removed and gained > 0:
        scale = removed / gained
        mask = ~df["player_id"].isin(list(out_ids))
        df.loc[mask, "min"] = (
            base_df.loc[mask, "min"].values + df.loc[mask, "min_adj"].values * scale
        )

    # clamp
    df["min"] = df["min"].clip(lower=0.0, upper=48.0)
    df["pts"] = df["pts"].clip(lower=0.0)
    df["reb"] = df["reb"].clip(lower=0.0)
    df["ast"] = df["ast"].clip(lower=0.0)

    # OUT players set to 0
    for i, row in df.iterrows():
        pid = int(row["player_id"])
        if pid in out_ids:
            df.at[i, "min"] = 0.0
            df.at[i, "pts"] = 0.0
            df.at[i, "reb"] = 0.0
            df.at[i, "ast"] = 0.0

    # widen uncertainty with lineup changes
    widen = 1.0 + 0.06 * len(out_ids)
    df["sigma_pts"] = df["sigma_pts"] * widen
    df["sigma_reb"] = df["sigma_reb"] * widen
    df["sigma_ast"] = df["sigma_ast"] * widen

    df = df.sort_values("min", ascending=False).reset_index(drop=True)
    return df


def main():
    console.print("\n[bold]NBA Team Projection CLI (OUT/IN/IMPACT)[/bold]\n")
    team_q = console.input("Team (e.g., MIN or Timberwolves): ").strip()

    base_df, meta = build_team_projection_table(team_q, n_recent_games_scan=8, top_n=12)

    console.print(
        f'\n[bold]{meta["team_name"]}[/bold] next game: [bold]{meta["matchup"]}[/bold]  '
        f'|  {"HOME" if meta["is_home"] else "AWAY"}'
    )
    console.print(
        f'Pace team/opp/league: {meta["pace_team"]:.1f} / {meta["pace_opp"]:.1f} / {meta["pace_league"]:.1f}'
    )
    console.print(
        f'Opp DEF_RATING (opp/league): {meta["opp_def"]:.1f} / {meta["def_league"]:.1f}\n'
    )

    out_ids: Set[int] = set()
    impact_cache: Dict[Tuple[int, int], Dict[int, TeammateDelta]] = {}
    proj_df = base_df.copy()

    render_table(proj_df, title="Projected Leaders", out_ids=out_ids)

    console.print("\nCommands:")
    console.print("- [bold]OUT <player>[/bold]    (e.g., OUT Anthony Edwards)")
    console.print("- [bold]IN <player>[/bold]     (remove from OUT list)")
    console.print("- [bold]IMPACT <player>[/bold] (who benefits historically)")
    console.print("- [bold]RESET[/bold]           (clear all OUT)")
    console.print("- [bold]SHOW[/bold]            (reprint table)")
    console.print("- Or: [bold]<player> (pts|reb|ast) <line>[/bold]  e.g., Jaden McDaniels pts 11.5")
    console.print("Type [bold]q[/bold] to quit.\n")

    while True:
        s = console.input(">> ").strip()
        if not s:
            continue
        if s.lower() in {"q", "quit", "exit"}:
            break

        if s.lower() == "show":
            render_table(proj_df, title="Projected Leaders", out_ids=out_ids)
            continue
        if s.lower() == "reset":
            out_ids.clear()
            proj_df = base_df.copy()
            render_table(proj_df, title="Projected Leaders", out_ids=out_ids)
            continue

        m_imp = re.match(r"^impact\s+(.+)$", s, flags=re.IGNORECASE)
        if m_imp:
            name = m_imp.group(1).strip()
            try:
                pid, canonical = match_player_in_table(name, base_df)
            except Exception as e:
                console.print(f"[red]{e}[/red]")
                continue
            show_impact_report(
                base_df=base_df,
                meta=meta,
                out_player_id=pid,
                out_player_name=canonical,
                impact_cache=impact_cache,
                top_n=10,
            )
            continue

        m_outin = re.match(r"^(out|in)\s+(.+)$", s, flags=re.IGNORECASE)
        if m_outin:
            cmd = m_outin.group(1).lower()
            name = m_outin.group(2).strip()

            try:
                pid, canonical = match_player_in_table(name, base_df)
            except Exception as e:
                console.print(f"[red]{e}[/red]")
                continue

            if cmd == "out":
                out_ids.add(pid)
                proj_df = apply_out_adjustments(base_df, out_ids, meta, impact_cache)
                console.print(f"\nMarked OUT: [bold]{canonical}[/bold]\n")
                render_table(proj_df, title="Projected Leaders (Adjusted)", out_ids=out_ids)
            else:
                out_ids.discard(pid)
                proj_df = apply_out_adjustments(base_df, out_ids, meta, impact_cache) if out_ids else base_df.copy()
                console.print(f"\nMarked IN: [bold]{canonical}[/bold]\n")
                render_table(proj_df, title="Projected Leaders (Adjusted)", out_ids=out_ids)
            continue

        m_line = re.match(r"^(.+?)\s+(pts|reb|ast)\s+([0-9]+(\.[0-9]+)?)$", s.strip(), flags=re.IGNORECASE)
        if not m_line:
            console.print("[red]Format not recognized.[/red] Example: OUT Anthony Edwards | IMPACT Edwards | McDaniels pts 11.5")
            continue

        name = m_line.group(1).strip()
        stat = m_line.group(2).lower()
        line = float(m_line.group(3))

        try:
            pid, canonical = match_player_in_table(name, proj_df)
        except Exception as e:
            console.print(f"[red]{e}[/red]")
            continue

        row = proj_df[proj_df["player_id"] == pid].iloc[0]
        if int(row["player_id"]) in out_ids:
            console.print(f"\n[bold]{canonical}[/bold] is marked OUT → projection set to 0.\n")
            continue

        if stat == "pts":
            mu, sig = float(row["pts"]), float(row["sigma_pts"])
        elif stat == "reb":
            mu, sig = float(row["reb"]), float(row["sigma_reb"])
        else:
            mu, sig = float(row["ast"]), float(row["sigma_ast"])

        res = over_under(mu, sig, line, dead_zone=0.07)
        console.print(
            f"\nPlayer: [bold]{canonical}[/bold]  |  Pick: [bold]{res.pick}[/bold]\n"
            f"Projection: {mu:.2f} (σ={sig:.2f}) vs Line {line:.2f}\n"
            f"P(Over)={res.p_over:.3f}  P(Under)={res.p_under:.3f}\n"
        )


if __name__ == "__main__":
    main()

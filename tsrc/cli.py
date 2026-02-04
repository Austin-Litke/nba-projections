from __future__ import annotations

from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, FloatPrompt, Confirm

from nba_data import (
    load_player_data,
    get_player_team_abbr,
    get_next_game,
    estimate_blowout_risk,
)
from model import project_next_game
from ou import over_under

SEASON = "2024-25"

STAT_MAP = {
    "pts": ("PTS", "pts", "sigma_pts"),
    "reb": ("REB", "reb", "sigma_reb"),
    "ast": ("AST", "ast", "sigma_ast"),
}

console = Console()


def _pick_color(pick: str) -> str:
    pick = pick.upper()
    if pick == "OVER":
        return "green"
    if pick == "UNDER":
        return "red"
    return "yellow"


def _render_last_games_table(player_name: str, last_10: list[dict], n: int = 5) -> Table:
    t = Table(title=f"Last {n} Games (most recent last)", show_lines=False)
    t.add_column("#", justify="right", width=3)
    t.add_column("MIN", justify="right")
    t.add_column("PTS", justify="right")
    t.add_column("REB", justify="right")
    t.add_column("AST", justify="right")

    tail = last_10[-n:] if len(last_10) >= n else last_10
    for i, g in enumerate(tail, start=1):
        t.add_row(
            str(i),
            f"{g['min']:.0f}",
            f"{g['pts']:.0f}",
            f"{g['reb']:.0f}",
            f"{g['ast']:.0f}",
        )
    return t


def _render_projection_table(proj) -> Table:
    t = Table(title="Upcoming Game Projection", show_lines=False)
    t.add_column("Stat", style="bold")
    t.add_column("Projection", justify="right")
    t.add_column("σ (uncertainty)", justify="right")

    t.add_row("MIN", f"{proj.min:.1f}", "—")
    t.add_row("PTS", f"{proj.pts:.1f}", f"{proj.sigma_pts:.1f}")
    t.add_row("REB", f"{proj.reb:.1f}", f"{proj.sigma_reb:.1f}")
    t.add_row("AST", f"{proj.ast:.1f}", f"{proj.sigma_ast:.1f}")
    return t


def _render_line_table(stat_label: str, line: float, mean: float, sigma: float, threshold: float) -> Table:
    res = over_under(mean=mean, sigma=sigma, line=line, threshold=threshold)
    color = _pick_color(res.pick)

    t = Table(title="Line Evaluation", show_lines=False)
    t.add_column("Stat", style="bold")
    t.add_column("Line", justify="right")
    t.add_column("Model Mean", justify="right")
    t.add_column("σ", justify="right")
    t.add_column("P(Over)", justify="right")
    t.add_column("P(Under)", justify="right")
    t.add_column("Pick", justify="center")

    t.add_row(
        stat_label,
        f"{line:.1f}",
        f"{mean:.1f}",
        f"{sigma:.1f}",
        f"{res.prob_over*100:.1f}%",
        f"{res.prob_under*100:.1f}%",
        Text(res.pick, style=f"bold {color}"),
    )
    return t


def main():
    console.print(Panel.fit("NBA Projection Tool", style="bold cyan"))
    console.print("Type [bold]q[/bold] to quit.\n")

    threshold = 0.62  # disciplined default

    while True:
        name = Prompt.ask("Player name").strip()
        if name.lower() in ("q", "quit", "exit"):
            break

        try:
            pdata = load_player_data(name, SEASON)
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            continue

        # Auto next game context
        team_abbr = None
        opp_abbr = None
        is_home = None
        blowout_risk = None

        try:
            team_abbr = get_player_team_abbr(name, SEASON)
            nxt = get_next_game(team_abbr, SEASON)
            opp_abbr = nxt["opp_abbr"]
            is_home = nxt["is_home"]
            blowout_risk = estimate_blowout_risk(team_abbr, opp_abbr, SEASON)
        except Exception as e:
            console.print(f"[yellow]Next game context unavailable:[/yellow] {e}")

        # Header panel
        header_lines = []
        header_lines.append(f"[bold]{name}[/bold]")
        if team_abbr and opp_abbr and is_home is not None:
            header_lines.append(f"Next game: [bold]{team_abbr} {'vs' if is_home else '@'} {opp_abbr}[/bold]")
        else:
            header_lines.append("Next game: (unknown)")

        role = pdata.get("role", "unknown")
        usage_role = pdata.get("usage_role", "unknown")
        min_vol = float(pdata.get("min_volatility", 1.0))
        header_lines.append(f"Role: [bold]{role}[/bold] | Usage: [bold]{usage_role}[/bold] | Min volatility: [bold]{min_vol:.2f}[/bold]")

        if blowout_risk is not None:
            header_lines.append(f"Blowout risk (0–1): [bold]{blowout_risk:.2f}[/bold]")

        console.print(Panel("\n".join(header_lines), style="blue"))

        # OUT toggle
        out_mode = Confirm.ask("Key teammate OUT?", default=False)

        # Projection
        proj = project_next_game(
            player_name=name,
            player_meta=pdata,
            season=pdata["season"],
            last_10=pdata["last_10"],
            is_home=is_home,
            out_mode=out_mode,
            blowout_risk=blowout_risk,
        )

        # Render last 5 + projection
        console.print(_render_last_games_table(name, pdata["last_10"], n=5))
        console.print(_render_projection_table(proj))

        if out_mode:
            console.print("[magenta]OUT boost applied.[/magenta]")

        # Lines loop
        while True:
            raw = Prompt.ask("\nEnter a prop (pts/reb/ast) or press Enter for new player", default="").strip().lower()
            if not raw:
                console.print()
                break
            if raw not in STAT_MAP:
                console.print("[yellow]Stat must be one of: pts, reb, ast[/yellow]")
                continue

            line = FloatPrompt.ask(f"Enter the line for {raw.upper()} (e.g. 29.5)")

            stat_label, mean_attr, sigma_attr = STAT_MAP[raw]
            mean = getattr(proj, mean_attr)
            sigma = getattr(proj, sigma_attr)

            console.print(_render_line_table(stat_label, line, mean, sigma, threshold))

    console.print(Panel.fit("Done.", style="bold green"))


if __name__ == "__main__":
    main()

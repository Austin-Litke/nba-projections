from __future__ import annotations

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
    "pts": ("pts", "sigma_pts"),
    "reb": ("reb", "sigma_reb"),
    "ast": ("ast", "sigma_ast"),
}


def _yesno(prompt: str) -> bool:
    return input(prompt).strip().lower() in ("y", "yes")


def main():
    print("\nNBA Projection Tool (REAL DATA)")
    print("Type 'q' to quit.\n")

    while True:
        name = input("Player name: ").strip()
        if name.lower() in ("q", "quit", "exit"):
            break

        try:
            pdata = load_player_data(name, SEASON)
        except Exception as e:
            print(e)
            continue

        opp_abbr = None
        is_home = None
        blowout_risk = None

        try:
            team_abbr = get_player_team_abbr(name, SEASON)
            nxt = get_next_game(team_abbr, SEASON)
            opp_abbr = nxt["opp_abbr"]
            is_home = nxt["is_home"]

            blowout_risk = estimate_blowout_risk(team_abbr, opp_abbr, SEASON)

            print(f"\nNext game: {team_abbr} {'vs' if is_home else '@'} {opp_abbr}")
            if blowout_risk is not None:
                print(f"Blowout risk (0-1): {blowout_risk:.2f}")
            else:
                print("Blowout risk: unavailable (team ratings not loaded).")

        except Exception as e:
            print("Could not determine next game:", e)

        print(f"Role: {pdata.get('role')} | Usage role: {pdata.get('usage_role')} | Min volatility: {pdata.get('min_volatility'):.2f}")

        out_mode = _yesno("Key teammate OUT? (y/n): ")

        proj = project_next_game(
            player_name=name,
            player_meta=pdata,
            season=pdata["season"],
            last_10=pdata["last_10"],
            is_home=is_home,
            out_mode=out_mode,
            blowout_risk=blowout_risk,
        )

        print("\nProjection")
        print(f"  MIN: {proj.min:.1f}")
        print(f"  PTS: {proj.pts:.1f} (σ≈{proj.sigma_pts:.1f})")
        print(f"  REB: {proj.reb:.1f} (σ≈{proj.sigma_reb:.1f})")
        print(f"  AST: {proj.ast:.1f} (σ≈{proj.sigma_ast:.1f})")

        while True:
            raw = input("\nEnter line (e.g. 'pts 29.5') or Enter for new player: ").strip().lower()
            if not raw:
                break

            parts = raw.split()
            if len(parts) != 2:
                print("Format should be: pts 29.5")
                continue

            stat, line_str = parts
            if stat not in STAT_MAP:
                print("Stat must be one of: pts, reb, ast")
                continue

            try:
                line = float(line_str)
            except ValueError:
                print("Line must be a number like 29.5")
                continue

            mean = getattr(proj, STAT_MAP[stat][0])
            sigma = getattr(proj, STAT_MAP[stat][1])

            res = over_under(mean, sigma, float(line), threshold=0.62)

            print(
                f"{stat.upper()} {line:.1f} → "
                f"P(over)={res.prob_over*100:.1f}% | "
                f"P(under)={res.prob_under*100:.1f}% | "
                f"Pick={res.pick}"
            )

    print("\nDone.")


if __name__ == "__main__":
    main()

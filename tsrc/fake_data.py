from __future__ import annotations

# Fake (made-up) test data to validate pipeline end-to-end.
# Replace with NBA API later.

FAKE_TEAMS = {
    "DEN": {"pace": 97.0, "def_rating": 111.0, "name": "Nuggets"},
    "LAL": {"pace": 101.0, "def_rating": 114.0, "name": "Lakers"},
    "MIN": {"pace": 98.5, "def_rating": 109.0, "name": "Timberwolves"},
}

LEAGUE_BASELINE = {"pace": 99.5, "def_rating": 113.0}

FAKE_PLAYERS = {
    "anthony edwards": {
        # NEW: role awareness for minutes
        "role": "starter",  # "starter" | "bench"

        # NEW: home/away multipliers (small!)
        "home_mult": 1.04,  # +4% pts/ast at home
        "away_mult": 0.97,  # -3% pts/ast away

        # NEW: OUT boost (simple + effective)
        # You’ll toggle this in the CLI by answering "y" when asked.
        "out_boost": {"min": 1.0, "pts": 2.5, "ast": 0.5, "reb": 0.0},

        "season": {
            "games_played": 50,
            "min_total": 1750,
            "pts_total": 1350,
            "reb_total": 275,
            "ast_total": 240,
        },
        "last_10": [
            {"min": 36, "pts": 34, "reb": 6, "ast": 5},
            {"min": 35, "pts": 28, "reb": 7, "ast": 4},
            {"min": 37, "pts": 31, "reb": 5, "ast": 6},
            {"min": 33, "pts": 22, "reb": 4, "ast": 3},
            {"min": 34, "pts": 27, "reb": 8, "ast": 5},
            {"min": 38, "pts": 39, "reb": 6, "ast": 7},
            {"min": 32, "pts": 19, "reb": 3, "ast": 4},
            {"min": 36, "pts": 30, "reb": 5, "ast": 5},
            {"min": 34, "pts": 26, "reb": 7, "ast": 3},
            {"min": 35, "pts": 29, "reb": 4, "ast": 6},
        ],
        # Head-to-head samples (made up)
        "vs_opp": {
            "DEN": [
                {"min": 35, "pts": 24, "reb": 5, "ast": 4},
                {"min": 36, "pts": 26, "reb": 4, "ast": 3},
                {"min": 37, "pts": 25, "reb": 6, "ast": 4},
                {"min": 34, "pts": 27, "reb": 5, "ast": 5},
                {"min": 36, "pts": 23, "reb": 4, "ast": 4},
                {"min": 35, "pts": 26, "reb": 5, "ast": 3},
            ]
        },
    },

    # Optional second player so you can test the "pick another player" flow
    "jaden mcdaniels": {
        "role": "starter",
        "home_mult": 1.02,
        "away_mult": 0.99,
        "out_boost": {"min": 2.0, "pts": 3.0, "ast": 0.3, "reb": 0.5},
        "season": {
            "games_played": 50,
            "min_total": 1500,
            "pts_total": 550,
            "reb_total": 220,
            "ast_total": 90,
        },
        "last_10": [
            {"min": 32, "pts": 14, "reb": 4, "ast": 2},
            {"min": 31, "pts": 10, "reb": 5, "ast": 2},
            {"min": 34, "pts": 16, "reb": 3, "ast": 1},
            {"min": 30, "pts": 9,  "reb": 4, "ast": 1},
            {"min": 33, "pts": 13, "reb": 6, "ast": 2},
            {"min": 35, "pts": 18, "reb": 5, "ast": 2},
            {"min": 28, "pts": 7,  "reb": 3, "ast": 1},
            {"min": 34, "pts": 15, "reb": 4, "ast": 2},
            {"min": 32, "pts": 11, "reb": 6, "ast": 1},
            {"min": 33, "pts": 12, "reb": 4, "ast": 2},
        ],
        "vs_opp": {},
    },
}


def get_fake_player(name: str) -> dict:
    key = name.strip().lower()
    if key not in FAKE_PLAYERS:
        raise KeyError(
            f"Unknown player '{name}'. Add them to src/fake_data.py (FAKE_PLAYERS)."
        )
    return FAKE_PLAYERS[key]


def get_fake_team(team_abbr: str) -> dict:
    key = team_abbr.strip().upper()
    if key not in FAKE_TEAMS:
        raise KeyError(
            f"Unknown team '{team_abbr}'. Add it to src/fake_data.py (FAKE_TEAMS)."
        )
    return FAKE_TEAMS[key]

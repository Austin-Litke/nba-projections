from __future__ import annotations


# Phase 1 simple opponent K environment table.
# 1.00 = league average
# >1.00 = strikeout-friendly opponent
# <1.00 = lower-strikeout opponent
#
# Keep values conservative for now.
TEAM_K_ADJ = {
    "Arizona Diamondbacks": 0.98,
    "Athletics": 1.03,
    "Atlanta Braves": 0.97,
    "Baltimore Orioles": 0.99,
    "Boston Red Sox": 0.99,
    "Chicago Cubs": 0.98,
    "Chicago White Sox": 1.04,
    "Cincinnati Reds": 1.02,
    "Cleveland Guardians": 0.95,
    "Colorado Rockies": 1.01,
    "Detroit Tigers": 1.00,
    "Houston Astros": 0.94,
    "Kansas City Royals": 0.97,
    "Los Angeles Angels": 1.03,
    "Los Angeles Dodgers": 0.93,
    "Miami Marlins": 1.02,
    "Milwaukee Brewers": 1.01,
    "Minnesota Twins": 1.00,
    "New York Mets": 0.98,
    "New York Yankees": 1.00,
    "Philadelphia Phillies": 0.96,
    "Pittsburgh Pirates": 1.03,
    "San Diego Padres": 0.95,
    "San Francisco Giants": 0.99,
    "Seattle Mariners": 1.05,
    "St. Louis Cardinals": 0.97,
    "Tampa Bay Rays": 1.01,
    "Texas Rangers": 0.98,
    "Toronto Blue Jays": 0.99,
    "Washington Nationals": 1.02,
}


def clamp_adj(value: float) -> float:
    return max(0.90, min(1.10, float(value)))


def get_team_k_adjustment(team_name: str | None) -> float:
    if not team_name:
        return 1.0
    return clamp_adj(TEAM_K_ADJ.get(team_name, 1.0))
from __future__ import annotations

import pandas as pd

from src.config import Config
from src.utils.time import today_local_date
from src.utils.cache import ensure_dir
from src.utils.logging import get_logger

from src.nba.fetch import (
    fetch_todays_games,
    teams_playing_today,
    players_on_teams,
    fetch_player_game_logs_season,
)
from src.features.build import build_player_game_features
from src.model.train import train_models
from src.model.predict import predict_from_last_row

log = get_logger("predict_today")

def main():
    cfg = Config()
    ensure_dir(cfg.output_dir)

    today = today_local_date()
    log.info(f"Running TODAY predictions for {today.isoformat()} (season={cfg.season})")

    games = fetch_todays_games(cfg, today)
    if games.empty:
        log.info("No games found for today. Exiting.")
        return

    team_ids = teams_playing_today(games)
    roster = players_on_teams(cfg, team_ids)

    # Fetch season logs (cached)
    logs = fetch_player_game_logs_season(cfg, cfg.season, cfg.season_type)

    # Build features
    feat = build_player_game_features(cfg, logs)

    # Cut training to strictly before today (avoid leakage)
    feat = feat[feat["GAME_DATE"].dt.date < today].copy()
    if feat.empty:
        log.info("No training rows before today (early season?) — consider adding previous season.")
        return

    # Train models
    min_model, rate_model, X_min_cols, X_rate_cols = train_models(cfg, feat)

    # Build per-player predictions using each player's most recent pre-today game row
    preds = []
    feat_by_player = feat.sort_values("GAME_DATE").groupby("PLAYER_ID")

    for _, r in roster.iterrows():
        pid = int(r["PLAYER_ID"])
        pname = r.get("PLAYER", "")
        pos = r.get("POSITION", "")

        if pid not in feat_by_player.groups:
            continue

        player_hist = feat_by_player.get_group(pid)
        last_row = player_hist.iloc[-1]

        out = predict_from_last_row(cfg, last_row, min_model, rate_model, X_min_cols, X_rate_cols)
        preds.append({
            "player_id": pid,
            "player": pname,
            "position": pos,
            "last_game_date": str(last_row["GAME_DATE"].date()),
            **out
        })

    out_df = pd.DataFrame(preds).sort_values("pts_mu", ascending=False).reset_index(drop=True)

    # Save
    output_path = cfg.output_dir / f"predictions_{today.isoformat()}.csv"
    out_df.to_csv(output_path, index=False)

    log.info(f"Saved {len(out_df)} predictions to {output_path}")

    # Print top 25 for convenience
    print(out_df.head(25).to_string(index=False))

if __name__ == "__main__":
    main()

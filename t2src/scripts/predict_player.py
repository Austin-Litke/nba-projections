from __future__ import annotations

import argparse
import pandas as pd

from src.config import Config
from src.utils.logging import get_logger
from src.utils.time import today_local_date
from src.utils.cache import ensure_dir

from src.nba.lookup import find_player_id
from src.nba.fetch import fetch_player_game_logs_season
from src.features.build import build_player_game_features
from src.model.train import train_models
from src.model.predict import predict_from_last_row
from src.model.io import load_models, save_models

log = get_logger("predict_player")

def get_or_train_models(cfg: Config, feat_train: pd.DataFrame):
    ensure_dir(cfg.cache_dir / "models")
    model_path = (cfg.cache_dir / "models" / f"models_{cfg.season}_{cfg.season_type.replace(' ', '_')}.joblib")

    cached = load_models(model_path)
    if cached is not None:
        return cached["min_model"], cached["rate_model"], cached["X_min_cols"], cached["X_rate_cols"]

    log.info("No cached models found. Training once and saving...")
    min_model, rate_model, X_min_cols, X_rate_cols = train_models(cfg, feat_train)
    save_models(model_path, {
        "min_model": min_model,
        "rate_model": rate_model,
        "X_min_cols": X_min_cols,
        "X_rate_cols": X_rate_cols,
    })
    return min_model, rate_model, X_min_cols, X_rate_cols

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--player", required=True, help='Player name search, e.g. "LeBron James"')
    parser.add_argument("--pick", type=int, default=0, help="If multiple matches, choose index (default 0)")
    args = parser.parse_args()

    cfg = Config()
    ensure_dir(cfg.output_dir)

    today = today_local_date()
    log.info(f"Player prediction for {today.isoformat()} (season={cfg.season})")

    # 1) search player
    matches = find_player_id(cfg, args.player)
    if matches.empty:
        print("No players matched your search.")
        return

    if len(matches) > 1:
        print("Multiple matches found:")
        print(matches.head(20).to_string(index=True))
        if args.pick < 0 or args.pick >= len(matches):
            print(f"--pick must be between 0 and {len(matches)-1}")
            return

    pick_row = matches.iloc[args.pick]
    player_id = int(pick_row["player_id"])
    player_name = str(pick_row["player_name"])
    log.info(f"Selected: {player_name} (player_id={player_id})")

    # 2) get season logs (cached)
    logs = fetch_player_game_logs_season(cfg, cfg.season, cfg.season_type)
    feat = build_player_game_features(cfg, logs)

    # 3) train cutoff: strictly before today
    feat_train = feat[feat["GAME_DATE"].dt.date < today].copy()
    if feat_train.empty:
        print("No training rows before today (early season). Add previous season support next.")
        return

    # 4) load cached models or train once
    min_model, rate_model, X_min_cols, X_rate_cols = get_or_train_models(cfg, feat_train)

    # 5) player history rows before today
    ph = feat_train[feat_train["PLAYER_ID"].astype(int) == player_id].sort_values("GAME_DATE")
    if ph.empty:
        print(f"No history for {player_name} in {cfg.season} before today.")
        return

    last_row = ph.iloc[-1]
    pred = predict_from_last_row(cfg, last_row, min_model, rate_model, X_min_cols, X_rate_cols)

    # 6) print + save
    out = {
        "player": player_name,
        "player_id": player_id,
        "as_of_last_game": str(last_row["GAME_DATE"].date()),
        **pred
    }
    out_df = pd.DataFrame([out])
    output_path = cfg.output_dir / f"prediction_{player_id}_{today.isoformat()}.csv"
    out_df.to_csv(output_path, index=False)

    print(out_df.to_string(index=False))
    log.info(f"Saved to {output_path}")

if __name__ == "__main__":
    main()

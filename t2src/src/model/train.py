from __future__ import annotations

import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from src.config import Config
from src.features.build import feature_columns_minutes, feature_columns_rate

def train_models(cfg: Config, df_feat: pd.DataFrame):
    """
    Train:
      - minutes model: predicts MIN
      - rate model: predicts PTS_per_min
    """
    X_min_cols = feature_columns_minutes(cfg)
    X_rate_cols = feature_columns_rate(cfg)

    X_min = df_feat[X_min_cols].values
    y_min = df_feat["MIN"].values

    X_rate = df_feat[X_rate_cols].values
    y_rate = df_feat["PTS_per_min"].values

    min_model = HistGradientBoostingRegressor(
        max_depth=cfg.gbdt_max_depth,
        learning_rate=cfg.gbdt_learning_rate
    )
    rate_model = HistGradientBoostingRegressor(
        max_depth=cfg.gbdt_max_depth,
        learning_rate=cfg.gbdt_learning_rate
    )

    min_model.fit(X_min, y_min)
    rate_model.fit(X_rate, y_rate)

    return min_model, rate_model, X_min_cols, X_rate_cols

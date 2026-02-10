from __future__ import annotations
from pathlib import Path
import pandas as pd

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def cache_path(cache_dir: Path, name: str) -> Path:
    return cache_dir / f"{name}.parquet"

def load_parquet_if_exists(path: Path) -> pd.DataFrame | None:
    if path.exists():
        return pd.read_parquet(path)
    return None

def save_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)

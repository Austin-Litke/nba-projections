from __future__ import annotations
from pathlib import Path
import joblib

def save_models(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(obj, path)

def load_models(path: Path) -> dict | None:
    if path.exists():
        return joblib.load(path)
    return None

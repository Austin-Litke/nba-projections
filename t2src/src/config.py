from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Config:
    # Update season as needed, format used by stats.nba.com endpoints
    season: str = "2025-26"
    season_type: str = "Regular Season"

    cache_dir: Path = Path("data/cache")
    output_dir: Path = Path("data/outputs")

    # Feature windows
    roll_windows: tuple[int, ...] = (3, 5, 10)
    ewma_alpha: float = 0.80  # recent games weighted more

    # Simple API politeness
    api_sleep_seconds: float = 0.7

    # Model params (simple, strong baseline)
    gbdt_max_depth: int = 4
    gbdt_learning_rate: float = 0.05

    # NegBin dispersion (global for v1)
    negbin_k: float = 8.0

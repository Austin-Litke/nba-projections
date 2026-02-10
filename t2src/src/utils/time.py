from __future__ import annotations
from datetime import date, datetime
import pandas as pd

def today_local_date() -> date:
    # Running machine local date; user timezone is America/Chicago,
    # but for v1, local machine date is usually fine if you run it in that timezone.
    return date.today()

def to_datetime_series(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce")

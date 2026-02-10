from __future__ import annotations

import random
import time
from typing import Any, Dict, Optional

import requests

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.nba.com",
    "Referer": "https://www.nba.com/",
    "Connection": "keep-alive",
}


class NBARetrySession:
    """
    Browser-like headers + retries + longer timeout.
    """
    def __init__(self, timeout: int = 120, max_retries: int = 4):
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def get(self, url: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                resp.raise_for_status()
                return resp
            except Exception as e:
                last_err = e
                time.sleep((2 ** attempt) + random.random())
        raise last_err  # type: ignore

from __future__ import annotations

import traceback


def err_with_trace(e: Exception) -> dict:
    return {
        "error": str(e),
        "traceTail": traceback.format_exc().splitlines()[-18:],
    }
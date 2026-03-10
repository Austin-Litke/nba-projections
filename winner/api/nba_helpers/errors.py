# api/nba_helpers/errors.py
import traceback


def err_with_trace(e: Exception):
    tb = traceback.format_exc().splitlines()
    return {
        "error": str(e),
        "traceTail": tb[-18:],
    }
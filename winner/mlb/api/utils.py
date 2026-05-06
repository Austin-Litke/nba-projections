from __future__ import annotations

import json


def json_bytes(obj):
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


def read_json_body(handler):
    try:
        length = int(handler.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = handler.rfile.read(length)
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}
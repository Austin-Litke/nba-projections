# winner/web/app_handler.py
from __future__ import annotations

from http.server import SimpleHTTPRequestHandler
from urllib.parse import urlparse

from api.utils import json_bytes
from api import nba_api


class AppHandler(SimpleHTTPRequestHandler):
    """
    - Serves static files from winner/ (same as before)
    - Dispatches /api/nba/... to nba_api
    """

    def log_message(self, fmt, *args):
        print(fmt % args)

    def send_json(self, code: int, obj: dict):
        body = json_bytes(obj)
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)

        # Route NBA API
        if parsed.path.startswith("/api/nba/"):
            res = nba_api.handle_get(parsed.path, parsed.query)
            if res is None:
                self.send_json(404, {"error": "Not found"})
                return
            code, payload = res
            self.send_json(code, payload)
            return

        # Otherwise static files
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path.startswith("/api/nba/"):
            res = nba_api.handle_post(self, parsed.path)
            if res is None:
                self.send_json(404, {"error": "Not found"})
                return
            code, payload = res
            self.send_json(code, payload)
            return

        self.send_json(404, {"error": "Not found"})
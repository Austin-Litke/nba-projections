# winner/server.py

from __future__ import annotations

import os
from http.server import HTTPServer

# This is your split handler that dispatches:
#   - static files
#   - /api/nba/... routes (via api/nba_api.py)
from web.app_handler import AppHandler

PORT = 8000


def run():
    # Make sure static files are served from the winner/ root
    root = os.path.dirname(__file__)
    os.chdir(root)

    print(f"Serving Winner Arcade at http://localhost:{PORT}")
    print("")
    print("NBA API routes:")
    print("  /api/nba/scoreboard?date=YYYYMMDD")
    print("  /api/nba/teams")
    print("  /api/nba/roster?teamId=25")
    print("  /api/nba/player?athleteId=1966")
    print("  /api/nba/player_gamelog?athleteId=1966&limit=5")
    print("  /api/nba/player_projection?athleteId=1966&opponentTeamId=6")
    print("  /api/nba/underdog_lines?athleteId=1966")  # ✅ new endpoint
    print("")
    print("POST routes:")
    print('  /api/nba/assess_line')
    print('  /api/nba/track')
    print('  /api/nba/settle')
    print("")

    httpd = HTTPServer(("0.0.0.0", PORT), AppHandler)
    httpd.serve_forever()


if __name__ == "__main__":
    run()
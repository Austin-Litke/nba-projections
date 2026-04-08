# winner/server.py
from __future__ import annotations

import os
from http.server import ThreadingHTTPServer

from web.app_handler import AppHandler


def run():
    # ensure we serve from winner/ root
    root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root)

    server = ThreadingHTTPServer(("0.0.0.0", 8000), AppHandler)

    print("Serving Winner Arcade at http://localhost:8000\n")

    print("NBA API routes:")
    print("  /api/nba/scoreboard?date=YYYYMMDD")
    print("  /api/nba/teams")
    print("  /api/nba/roster?teamId=25")
    print("  /api/nba/player?athleteId=1966")
    print("  /api/nba/player_gamelog?athleteId=1966&limit=5")
    print("  /api/nba/player_projection?athleteId=1966&opponentTeamId=6")
    print("  /api/nba/underdog_lines?athleteId=1966")

    print("\nPOST routes:")
    print("  /api/nba/assess_line")
    print("  /api/nba/track")
    print("  /api/nba/settle\n")

    print("Using ThreadingHTTPServer (concurrent requests enabled)\n")

    server.serve_forever()


if __name__ == "__main__":
    run()
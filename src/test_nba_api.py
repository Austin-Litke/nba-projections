import time
from nba_api.stats.endpoints import leaguedashplayerstats

print("Testing leaguedashplayerstats...")

start = time.time()
try:
    stats = leaguedashplayerstats.LeagueDashPlayerStats(
        season="2024-25",
        season_type_all_star="Regular Season",
        per_mode_detailed="PerGame",
        timeout=60,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://stats.nba.com/",
            "Origin": "https://stats.nba.com",
        },
    )
    df = stats.get_data_frames()[0]
    elapsed = time.time() - start

    print(f"SUCCESS in {elapsed:.2f}s")
    print("Rows:", len(df))
    print(df.head(3))

except Exception as e:
    elapsed = time.time() - start
    print(f"FAILED in {elapsed:.2f}s")
    print(type(e).__name__, e)

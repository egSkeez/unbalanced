from match_stats_db import get_player_weapon_stats
import json

# Try to find a player who has matches
import sqlite3
conn = sqlite3.connect('cs2_history.db')
c = conn.cursor()
c.execute("SELECT player_name FROM player_match_stats WHERE rating IS NOT NULL LIMIT 1")
row = c.fetchone()
if row:
    name = row[0]
    print(f"Testing for player: {name}")
    stats = get_player_weapon_stats(name)
    print(f"Stats: {stats}")
else:
    print("No players found with ratings.")
conn.close()

import sqlite3
import json

conn = sqlite3.connect('cs2_history.db')
c = conn.cursor()
c.execute('SELECT player_name, weapon_kills, rating FROM player_match_stats WHERE player_name = "Skeez" AND rating IS NOT NULL')
rows = c.fetchall()
print(f"Total Skeez demo matches: {len(rows)}")
with_kills = [r for r in rows if r[1] and r[1] != "{}" and r[1] != "0"]
print(f"Matches with weapon JSON: {len(with_kills)}")
if with_kills:
    print(f"Sample: {with_kills[0][1]}")
conn.close()

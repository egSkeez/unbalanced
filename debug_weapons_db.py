import sqlite3
import json

conn = sqlite3.connect('cs2_history.db')
c = conn.cursor()
c.execute('SELECT player_name, weapon_kills FROM player_match_stats WHERE weapon_kills IS NOT NULL AND weapon_kills != "0" LIMIT 5')
rows = c.fetchall()
for r in rows:
    print(f"Player: {r[0]}")
    print(f"Weapons: {r[1]}")
conn.close()

import sqlite3
from datetime import date

conn = sqlite3.connect('cs2_history.db')
c = conn.cursor()
c.execute('''
    SELECT md.date_analyzed 
    FROM player_match_stats pms 
    JOIN match_details md ON pms.match_id = md.match_id 
    WHERE pms.player_name = "Skeez" AND pms.rating IS NOT NULL
''')
rows = c.fetchall()
print(f"Total Skeez demo matches: {len(rows)}")
for r in rows[:1]:
    print(f"Sample date: {r[0]}")
conn.close()

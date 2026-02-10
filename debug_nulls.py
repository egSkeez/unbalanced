
import sqlite3

def check_nulls():
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM player_match_stats WHERE rating IS NULL")
    print(f"NULL Ratings: {c.fetchone()[0]}")
    
    c.execute("SELECT COUNT(*) FROM player_match_stats WHERE rating IS NOT NULL")
    print(f"Valid Ratings: {c.fetchone()[0]}")
    
    print("\n--- Rows with Rating NULL but MultiKills present? ---")
    c.execute("SELECT multi_kills FROM player_match_stats WHERE rating IS NULL LIMIT 5")
    print(c.fetchall())

    conn.close()

if __name__ == "__main__":
    check_nulls()

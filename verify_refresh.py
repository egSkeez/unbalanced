
import sqlite3

def verify_stats_refresh():
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    
    print("--- Verify Match Stats ---")
    c.execute("SELECT COUNT(*) FROM match_details")
    matches = c.fetchone()[0]
    print(f"Total Matches: {matches}")
    
    print("\n--- Verify Player Stats & Ratings ---")
    c.execute("SELECT COUNT(*), COUNT(rating), AVG(rating) FROM player_match_stats")
    row = c.fetchone()
    print(f"Total Player Entries: {row[0]}")
    print(f"Entries with Rating: {row[1]}")
    print(f"Average Rating: {row[2]:.2f}")
    
    print("\n--- Sample Ratings ---")
    c.execute("SELECT player_name, rating FROM player_match_stats WHERE rating IS NOT NULL LIMIT 5")
    for r in c.fetchall():
        print(r)

    conn.close()

if __name__ == "__main__":
    verify_stats_refresh()

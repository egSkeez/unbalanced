
import sqlite3

def check_ratings():
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    
    print("--- Distribution of Ratings ---")
    c.execute("SELECT COUNT(*), typeof(rating) FROM player_match_stats GROUP BY typeof(rating)")
    print(c.fetchall())
    
    print("\n--- Any Valid Ratings? ---")
    c.execute("SELECT rating FROM player_match_stats WHERE rating IS NOT NULL LIMIT 10")
    print(c.fetchall())

    conn.close()

if __name__ == "__main__":
    check_ratings()

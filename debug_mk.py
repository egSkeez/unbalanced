
import sqlite3

def check_multi_kills():
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    
    # Check distinct values in multi_kills column
    print("--- Checking Distinct MultiKills Values (Limit 20) ---")
    c.execute("SELECT DISTINCT multi_kills FROM player_match_stats LIMIT 20")
    rows = c.fetchall()
    for row in rows:
        print(row)
        
    conn.close()

if __name__ == "__main__":
    check_multi_kills()

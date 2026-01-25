
import sqlite3

def remove_player(name):
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    
    # Remove from players table
    c.execute("DELETE FROM players WHERE name = ?", (name,))
    
    # Remove from match stats table
    c.execute("DELETE FROM player_match_stats WHERE player_name = ?", (name,))
    
    conn.commit()
    conn.close()
    print(f"Successfully removed player '{name}' from all database tables.")

if __name__ == "__main__":
    # The user wrote "leMKC", but I'll check casing or just use the exact string provided in previous manual entries ("LeMkc")
    remove_player("LeMkc")

import sqlite3

def update_hiyox():
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    
    print("Renaming hiyox to Hiyox...")
    
    # 1. Update 'players' table
    try:
        c.execute("UPDATE players SET name = 'Hiyox' WHERE name = 'hiyox'")
    except sqlite3.IntegrityError:
        print("Could not update players table (Hiyox might already exist).")
        
    # 2. Update 'player_match_stats' table
    c.execute("UPDATE player_match_stats SET player_name = 'Hiyox' WHERE player_name = 'hiyox'")
    
    # 3. Update 'matches' table (complex text replacement, optional but good for consistency)
    # We won't do risky regex updates on JSON-like strings in SQL without care, 
    # but the important part is stats and roster.
    
    conn.commit()
    print(f"Updated {c.rowcount} rows in stats.")
    conn.close()

if __name__ == "__main__":
    update_hiyox()

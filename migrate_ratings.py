import sqlite3
import pandas as pd
import json

def calculate_hltv_rating_migration(kills, deaths, multi_kills_val, total_rounds):
    """
    Calculates HLTV Rating 1.0
    Formula: (KillRating + 0.7 * SurvivalRating + MultiKillRating) / 2.7
    """
    if total_rounds == 0:
        return 0.0
        
    # 1. Kill Rating
    kpr = kills / total_rounds
    kill_rating = kpr / 0.679
    
    # 2. Survival Rating
    survival_rate = (total_rounds - deaths) / total_rounds
    survival_rating = survival_rate / 0.317
    
    # 3. MultiKill Rating
    # We need counts of 1k, 2k, 3k, 4k, 5k
    mk = {}
    if isinstance(multi_kills_val, str):
        try:
            loaded = json.loads(multi_kills_val)
            if isinstance(loaded, dict):
                mk = loaded
            else:
                mk = {}
        except:
            mk = {}
    elif isinstance(multi_kills_val, dict):
        mk = multi_kills_val
            
    # Counts
    # Convert keys to int if possible
    k1 = int(mk.get('1', 0)) + int(mk.get(1, 0))
    k2 = int(mk.get('2', 0)) + int(mk.get(2, 0))
    k3 = int(mk.get('3', 0)) + int(mk.get(3, 0))
    k4 = int(mk.get('4', 0)) + int(mk.get(4, 0))
    k5 = int(mk.get('5', 0)) + int(mk.get(5, 0))
    
    # Value = (1K + 4*2K + 9*3K + 16*4K + 25*5K) / Rounds
    mk_val = (k1 + 4*k2 + 9*k3 + 16*k4 + 25*k5) / total_rounds
    mk_rating = mk_val / 1.277
    
    rating = (kill_rating + 0.7 * survival_rating + mk_rating) / 2.7
    return round(rating, 2)

def has_valid_multi_kills(mk_val):
    """Check if multi_kills data is present and non-empty."""
    if mk_val is None or mk_val == '0' or mk_val == 0:
        return False
    if isinstance(mk_val, str):
        try:
            loaded = json.loads(mk_val)
            return isinstance(loaded, dict) and len(loaded) > 0
        except:
            return False
    if isinstance(mk_val, dict):
        return len(mk_val) > 0
    return False

def migrate():
    print("Starting Rating Migration...")
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    
    # 1. Ensure column exists
    try:
        c.execute("ALTER TABLE player_match_stats ADD COLUMN rating REAL DEFAULT 0")
        print("Added 'rating' column.")
    except Exception as e:
        print(f"Column check: {e}")
        
    # 2. Get Match Rounds
    print("Fetching match details...")
    c.execute("SELECT match_id, total_rounds FROM match_details")
    matches = {row[0]: row[1] for row in c.fetchall()}
    
    # 3. Get Player Stats
    print("Fetching player stats...")
    c.execute("SELECT id, match_id, kills, deaths, multi_kills FROM player_match_stats")
    rows = c.fetchall()
    
    print(f"Processing {len(rows)} stats entries...")
    updates = []
    null_count = 0
    
    for row in rows:
        pid, mid, k, d, mk = row
        rounds = matches.get(mid, 0)
        
        if rounds > 0 and has_valid_multi_kills(mk):
            rating = calculate_hltv_rating_migration(k, d, mk, rounds)
            updates.append((rating, pid))
        else:
            # Set rating to NULL for matches without complete stats
            updates.append((None, pid))
            null_count += 1
            
    # 4. Batch Update
    print(f"Updating {len(updates)} rows ({null_count} set to NULL due to missing data)...")
    c.executemany("UPDATE player_match_stats SET rating = ? WHERE id = ?", updates)
    
    conn.commit()
    conn.close()
    print("Migration Complete!")

if __name__ == "__main__":
    migrate()

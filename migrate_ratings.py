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
    from database import sync_engine
    from sqlalchemy import text as sa_text

    print("Starting Rating Migration...")
    
    with sync_engine.begin() as conn:
        # 1. Ensure column exists
        try:
            conn.execute(sa_text("ALTER TABLE player_match_stats ADD COLUMN rating REAL DEFAULT 0"))
            print("Added 'rating' column.")
        except Exception as e:
            print(f"Column check: {e}")
        
    with sync_engine.connect() as conn:
        # 2. Get Match Rounds
        print("Fetching match details...")
        rows_md = conn.execute(sa_text("SELECT match_id, total_rounds FROM match_details")).fetchall()
        matches = {row[0]: row[1] for row in rows_md}
        
        # 3. Get Player Stats
        print("Fetching player stats...")
        rows = conn.execute(sa_text("SELECT id, match_id, kills, deaths, multi_kills FROM player_match_stats")).fetchall()
    
    print(f"Processing {len(rows)} stats entries...")
    updates = []
    null_count = 0
    
    for row in rows:
        pid, mid, k, d, mk = row
        rounds = matches.get(mid, 0)
        
        if rounds > 0 and has_valid_multi_kills(mk):
            rating = calculate_hltv_rating_migration(k, d, mk, rounds)
            updates.append({"rating": rating, "pid": pid})
        else:
            updates.append({"rating": None, "pid": pid})
            null_count += 1
            
    # 4. Batch Update
    print(f"Updating {len(updates)} rows ({null_count} set to NULL due to missing data)...")
    with sync_engine.begin() as conn:
        for u in updates:
            conn.execute(sa_text("UPDATE player_match_stats SET rating = :rating WHERE id = :pid"), u)
    
    print("Migration Complete!")

def check_and_migrate():
    """
    Checks if ratings are uninitialized (all 0 or NULL) despite having matches.
    If so, runs migration automatically.
    """
    from database import sync_engine
    from sqlalchemy import text as sa_text

    try:
        with sync_engine.connect() as conn:
            # Check if we have matches
            total_rows = conn.execute(sa_text("SELECT COUNT(*) FROM player_match_stats")).scalar()
            
            if total_rows == 0:
                return
                
            # Check if we have ANY valid ratings
            valid_ratings = conn.execute(sa_text("SELECT COUNT(*) FROM player_match_stats WHERE rating IS NOT NULL AND rating > 0")).scalar()
        
        if valid_ratings == 0:
            print("⚠️ Detected uninitialized ratings. Running auto-migration...")
            migrate()
            
    except Exception as e:
        print(f"Auto-migration check failed: {e}")

if __name__ == "__main__":
    migrate()



import os
import shutil
import sqlite3
import json
import pandas as pd
from match_stats_db import save_match_stats
from datetime import datetime

MATCH_DB = 'cs2_history.db'
PROCESSED_DIR = 'processed_matches'

def backup_database():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{MATCH_DB}.backup_{timestamp}"
    
    if os.path.exists(MATCH_DB):
        shutil.copy2(MATCH_DB, backup_file)
        print(f"✅ Created database backup: {backup_file}")
        return True
    else:
        print(f"❌ Database not found: {MATCH_DB}")
        return False

def clear_match_data():
    conn = sqlite3.connect(MATCH_DB)
    c = conn.cursor()
    
    try:
        # Delete only match-related data, preserving players/configs
        c.execute("DELETE FROM player_match_stats")
        c.execute("DELETE FROM match_details")
        # c.execute("DELETE FROM cybershoke_lobbies") # Keep lobby tracking history
        
        conn.commit()
        print("✅ Cleared existing match statistics and details.")
    except Exception as e:
        print(f"❌ Error clearing data: {e}")
    finally:
        conn.close()

def import_json_stats():
    if not os.path.exists(PROCESSED_DIR):
        print(f"❌ Directory not found: {PROCESSED_DIR}")
        return
        
    files = [f for f in os.listdir(PROCESSED_DIR) if f.endswith('.json')]
    print(f"Found {len(files)} JSON files to import.")
    
    success_count = 0
    fail_count = 0
    
    for filename in files:
        file_path = os.path.join(PROCESSED_DIR, filename)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            match_id = data.get('match_id')
            score_str = data.get('score_str')
            score_t = data.get('score_t', 0)
            score_ct = data.get('score_ct', 0)
            map_name = data.get('map_name', 'Unknown')
            lobby_url = data.get('lobby_url', None)
            player_stats = data.get('player_stats', [])
            
            if not player_stats:
                print(f"⚠️ No player stats in {filename}, skipping.")
                continue
                
            # Convert to DataFrame
            df = pd.DataFrame(player_stats)
            
            # Save using our DB function
            save_match_stats(
                match_id=f"match_{match_id}",
                cybershoke_id=str(match_id),
                score_str=score_str,
                stats_df=df,
                map_name=map_name,
                score_t=int(score_t),
                score_ct=int(score_ct),
                force_overwrite=True,
                lobby_url=lobby_url
            )
            success_count += 1
            print(f"✅ Imported {match_id}")
            
        except Exception as e:
            print(f"❌ Failed to import {filename}: {e}")
            fail_count += 1
            
    print("\n--- Import Complete ---")
    print(f"Success: {success_count}")
    print(f"Failed: {fail_count}")

if __name__ == "__main__":
    if backup_database():
        clear_match_data()
        import_json_stats()

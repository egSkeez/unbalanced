"""
Bulk Import Cybershoke Match IDs
================================
Reads match IDs from cybershoke_match_ids.txt, processes each one:
1. Checks if already in database (skip duplicates)
2. Fetches lobby info to detect 1v1 matches (skip those)
3. Downloads demo, analyzes, reconciles with web stats
4. Saves to database with lobby URL and HLTV rating
5. Updates player aggregate stats when done
"""

import os
import sys
import json
import time
import sqlite3
import pandas as pd
from datetime import datetime

# Local imports
from cybershoke import get_lobby_player_stats
from demo_download import download_demo
from demo_analysis import analyze_demo_file
from match_stats_db import (
    init_match_stats_tables,
    is_lobby_already_analyzed,
    save_match_stats,
)

# ── Configuration ──────────────────────────────────────────────────────
MATCH_IDS_FILE = r"C:\Users\Skeez\Downloads\cybershoke_match_ids.txt"
OUTPUT_DIR = "processed_matches"
ADMIN_NAME = "Skeez"
DELAY_BETWEEN_MATCHES = 2  # seconds between API calls to avoid rate limiting
LOG_FILE = "bulk_import_log.txt"

# ── Helpers ────────────────────────────────────────────────────────────

def read_match_ids(filepath):
    """Parse match IDs from the text file, ignoring headers and empty lines."""
    ids = []
    with open(filepath, 'r') as f:
        for line in f:
            stripped = line.strip()
            # Only keep lines that are purely numeric (match IDs)
            if stripped.isdigit():
                ids.append(stripped)
    return ids


# Maps that indicate 1v1 lobbies
_1V1_MAP_PREFIXES = ['aim_', 'awp_', '1v1_', 'fy_']

def is_1v1_map(map_name):
    """Returns True if the map name suggests a 1v1 lobby."""
    if not map_name or map_name == 'Unknown':
        return False
    lower = map_name.lower()
    return any(lower.startswith(prefix) for prefix in _1V1_MAP_PREFIXES)


def check_lobby_player_count(match_id):
    """
    Queries Cybershoke API to get lobby info.
    Returns (player_count, web_stats, web_score, web_map) or (0, None, None, None) on failure.
    Used to detect 1v1 lobbies.
    """
    try:
        web_stats, web_score, web_map = get_lobby_player_stats(match_id)
        if web_stats:
            return len(web_stats), web_stats, web_score, web_map
        else:
            # API returned but no player data — might be expired/unavailable
            return -1, None, web_score, web_map
    except Exception as e:
        print(f"    ⚠️ Error checking lobby info: {e}")
        return -1, None, None, None


def log_result(msg):
    """Append a line to the log file."""
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")


def process_single_match(match_id, web_stats=None, web_score=None, web_map=None):
    """
    Process a single match: download demo, analyse, reconcile with web, save JSON.
    Returns True on success, False on failure.
    """
    lobby_url = f"https://cybershoke.net/match/{match_id}"
    
    # ─ Step 1: Download demo ─────────────────────────────────────────
    print(f"    📥 Downloading demo...")
    success, msg = download_demo(match_id, admin_name=ADMIN_NAME)
    
    if not success:
        print(f"    ❌ Download failed: {msg}")
        # Even if demo fails, we can try web-only stats
        if web_stats and web_score and web_score != "Unknown":
            print(f"    🔄 Attempting web-only import (no demo)...")
            return save_web_only_match(match_id, web_stats, web_score, web_map, lobby_url)
        return False
    print(f"    ✅ {msg}")
    
    # ─ Step 2: Analyze demo ──────────────────────────────────────────
    demo_file = f"demos/match_{match_id}.dem"
    if not os.path.exists(demo_file):
        print(f"    ❌ Demo file not found: {demo_file}")
        if web_stats and web_score and web_score != "Unknown":
            return save_web_only_match(match_id, web_stats, web_score, web_map, lobby_url)
        return False
    
    print(f"    🔬 Analyzing demo...")
    try:
        score_res, stats_df, map_name, score_t, score_ct = analyze_demo_file(demo_file)
        
        # Cleanup demo file
        if os.path.exists(demo_file):
            os.remove(demo_file)
            
        if stats_df is None:
            print(f"    ❌ Analysis failed: {score_res}")
            if web_stats and web_score and web_score != "Unknown":
                return save_web_only_match(match_id, web_stats, web_score, web_map, lobby_url)
            return False
    except Exception as e:
        print(f"    ❌ Error during analysis: {e}")
        # Cleanup on error
        if os.path.exists(demo_file):
            os.remove(demo_file)
        if web_stats and web_score and web_score != "Unknown":
            return save_web_only_match(match_id, web_stats, web_score, web_map, lobby_url)
        return False

    print(f"    ✅ Analysis complete! Score: {score_res}, Map: {map_name}")
    
    # Post-analysis 1v1 check: skip if less than 6 players (need at least 3v3)
    # or if the map is an aim/1v1 map
    if len(stats_df) < 6 or is_1v1_map(map_name):
        print(f"    ⏭️ Post-demo 1v1/small match detected ({len(stats_df)} players, map={map_name}). Skipping.")
        return 'SKIP_1V1'

    # ─ Step 3: Reconcile with web stats ──────────────────────────────
    if web_stats:
        print(f"    🔗 Reconciling with web stats...")
        
        # Prioritize Web Metadata
        if web_score and web_score != "Unknown":
            score_res = web_score
            try:
                parts = web_score.split("-")
                score_t = int(parts[0].strip())
                score_ct = int(parts[1].strip())
            except:
                pass
        if web_map and web_map != "Unknown":
            map_name = web_map

        # Correct Player Stats
        changes = 0
        for index, row in stats_df.iterrows():
            p_name = row['Player']
            if p_name in web_stats:
                w = web_stats[p_name]
                stats_df.at[index, 'Kills'] = w['kills']
                stats_df.at[index, 'Deaths'] = w['deaths']
                stats_df.at[index, 'Assists'] = w['assists']
                stats_df.at[index, 'Headshots'] = w['headshots']
                
                k, d, hs = w['kills'], w['deaths'], w['headshots']
                stats_df.at[index, 'K/D'] = round(k / d, 2) if d > 0 else k
                stats_df.at[index, 'HS%'] = round((hs / k * 100), 1) if k > 0 else 0
                changes += 1
        print(f"    ✅ Reconciled {changes} players")
    
    # ─ Step 4: Save JSON ─────────────────────────────────────────────
    players_data = []
    for _, row in stats_df.iterrows():
        players_data.append(row.to_dict())

    output_data = {
        "match_id": str(match_id),
        "map_name": map_name,
        "score_str": score_res,
        "score_t": score_t,
        "score_ct": score_ct,
        "lobby_url": lobby_url,
        "player_stats": players_data
    }
    
    json_path = os.path.join(OUTPUT_DIR, f"match_{match_id}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=4)
    
    # ─ Step 5: Save to database ──────────────────────────────────────
    db_match_id = f"match_{match_id}"
    result = save_match_stats(
        match_id=db_match_id,
        cybershoke_id=str(match_id),
        score_str=score_res,
        stats_df=stats_df,
        map_name=map_name,
        score_t=int(score_t),
        score_ct=int(score_ct),
        force_overwrite=False,
        lobby_url=lobby_url
    )
    
    if result:
        print(f"    💾 Saved to database")
    else:
        print(f"    ⚠️ Database save returned False (might be duplicate)")
    
    return True


def save_web_only_match(match_id, web_stats, web_score, web_map, lobby_url):
    """
    Fallback: save a match using only web stats (no demo data).
    This won't have detailed stats like multi-kills/weapon kills, but will
    have core KDA/HS data.
    """
    print(f"    📊 Saving web-only stats...")
    
    try:
        parts = web_score.split("-")
        score_t = int(parts[0].strip())
        score_ct = int(parts[1].strip())
    except:
        score_t = 0
        score_ct = 0
    
    map_name = web_map if web_map and web_map != "Unknown" else "Unknown"
    
    # Build a DataFrame from web stats
    rows = []
    for name, s in web_stats.items():
        k = s.get('kills', 0)
        d = s.get('deaths', 0)
        a = s.get('assists', 0)
        hs = s.get('headshots', 0)
        
        rows.append({
            'Player': name,
            'SteamID': '',
            'TeamNum': 0,
            'Kills': k,
            'Deaths': d,
            'Assists': a,
            'K/D': round(k / d, 2) if d > 0 else k,
            'ADR': 0,
            'HS%': round((hs / k * 100), 1) if k > 0 else 0,
            'Score': 0,
            'Damage': 0,
            'UtilityDamage': 0,
            'Flashed': 0,
            'TeamFlashed': 0,
            'FlashAssists': 0,
            'TotalSpent': 0,
            'EntryKills': 0,
            'EntryDeaths': 0,
            'ClutchWins': 0,
            'BaiterRating': 0,
            'BombPlants': 0,
            'BombDefuses': 0,
            'Headshots': hs,
            'MultiKills': {},
            'WeaponKills': {},
        })
    
    stats_df = pd.DataFrame(rows)
    
    # Save JSON
    output_data = {
        "match_id": str(match_id),
        "map_name": map_name,
        "score_str": web_score,
        "score_t": score_t,
        "score_ct": score_ct,
        "lobby_url": lobby_url,
        "player_stats": rows
    }
    
    json_path = os.path.join(OUTPUT_DIR, f"match_{match_id}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=4)
    
    # Save to DB
    db_match_id = f"match_{match_id}"
    result = save_match_stats(
        match_id=db_match_id,
        cybershoke_id=str(match_id),
        score_str=web_score,
        stats_df=stats_df,
        map_name=map_name,
        score_t=score_t,
        score_ct=score_ct,
        force_overwrite=False,
        lobby_url=lobby_url
    )
    
    if result:
        print(f"    💾 Web-only stats saved to database")
        return True
    return False


def update_player_stats_cache():
    """
    After all matches are imported, update the aggregate stats
    by calling the player stats refresh logic.
    """
    print("\n🔄 Refreshing player aggregate statistics...")
    try:
        from database import get_player_stats
        df = get_player_stats()
        print(f"✅ Refreshed stats for {len(df)} players")
        print(df[['name', 'avg_kd', 'avg_rating']].to_string(index=False))
    except Exception as e:
        print(f"⚠️ Error refreshing player stats: {e}")


# ── Main ───────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  CYBERSHOKE BULK MATCH IMPORTER")
    print("=" * 60)
    
    # Ensure tables exist (runs migration for lobby_url column)
    init_match_stats_tables()
    
    # Ensure output directory exists
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    # Read match IDs
    if not os.path.exists(MATCH_IDS_FILE):
        print(f"❌ Match IDs file not found: {MATCH_IDS_FILE}")
        return
    
    all_ids = read_match_ids(MATCH_IDS_FILE)
    print(f"\n📋 Found {len(all_ids)} match IDs in file")
    
    # Initialize log
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write(f"Bulk Import Started: {datetime.now()}\n")
        f.write(f"Total IDs: {len(all_ids)}\n\n")
    
    # Counters
    processed = 0
    skipped_duplicate = 0
    skipped_1v1 = 0
    skipped_api_fail = 0
    success = 0
    failed = 0
    
    for i, match_id in enumerate(all_ids, 1):
        print(f"\n{'─' * 50}")
        print(f"[{i}/{len(all_ids)}] Match ID: {match_id}")
        
        # ─ Duplicate check ───────────────────────────────────────────
        if is_lobby_already_analyzed(match_id):
            print(f"    ⏭️ Already in database. Skipping.")
            skipped_duplicate += 1
            log_result(f"SKIP_DUPLICATE {match_id}")
            continue
        
        # ─ Check lobby player count (detect 1v1) ────────────────────
        print(f"    🔍 Checking lobby info...")
        player_count, web_stats, web_score, web_map = check_lobby_player_count(match_id)
        
        # Pre-filter: obvious 1v1s by player count or map name
        if player_count == 0 or (0 < player_count <= 4):
            print(f"    ⏭️ 1v1/small lobby detected ({player_count} players). Skipping.")
            skipped_1v1 += 1
            log_result(f"SKIP_1V1 {match_id} (players={player_count})")
            time.sleep(0.5)
            continue
        
        if web_map and is_1v1_map(web_map):
            print(f"    ⏭️ 1v1 map detected ({web_map}). Skipping.")
            skipped_1v1 += 1
            log_result(f"SKIP_1V1_MAP {match_id} (map={web_map})")
            time.sleep(0.5)
            continue
        
        if player_count == -1:
            # API failed — could be expired lobby. Try processing anyway via demo.
            print(f"    ⚠️ Could not fetch lobby info. Attempting demo-only processing...")
            skipped_api_fail += 1  # Count but still try
        else:
            print(f"    ✅ {player_count} players found in lobby")
        
        # ─ Process the match ─────────────────────────────────────────
        try:
            result = process_single_match(match_id, web_stats, web_score, web_map)
            if result == 'SKIP_1V1':
                skipped_1v1 += 1
                log_result(f"SKIP_1V1_POSTDEMO {match_id}")
            elif result:
                success += 1
                log_result(f"SUCCESS {match_id}")
            else:
                failed += 1
                log_result(f"FAILED {match_id}")
        except Exception as e:
            failed += 1
            print(f"    ❌ Unhandled error: {e}")
            log_result(f"ERROR {match_id}: {e}")
        
        processed += 1
        
        # Rate limiting delay
        time.sleep(DELAY_BETWEEN_MATCHES)
    
    # ── Summary ──────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  BULK IMPORT COMPLETE")
    print("=" * 60)
    print(f"  Total IDs:          {len(all_ids)}")
    print(f"  Already in DB:      {skipped_duplicate}")
    print(f"  Skipped (1v1):      {skipped_1v1}")
    print(f"  API Info Failed:    {skipped_api_fail}")
    print(f"  Processed:          {processed}")
    print(f"  ✅ Succeeded:       {success}")
    print(f"  ❌ Failed:          {failed}")
    print("=" * 60)
    
    log_result(f"\nSUMMARY: Total={len(all_ids)}, DB_Skip={skipped_duplicate}, 1v1_Skip={skipped_1v1}, Success={success}, Failed={failed}")
    
    # ── Refresh player stats ─────────────────────────────────────────
    if success > 0:
        update_player_stats_cache()
    
    print(f"\n📄 Full log saved to: {LOG_FILE}")


if __name__ == "__main__":
    main()

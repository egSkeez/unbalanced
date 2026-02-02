import os
import streamlit as st
from match_registry import get_pending_matches, update_match_status
from demo_download import download_demo
from demo_analysis import analyze_demo_file
from match_stats_db import save_match_stats
from cybershoke import get_lobby_player_stats

def process_match_queue(admin_name="Skeez"):
    """
    Processes all pending matches in the registry.
    Returns a summary string.
    """
    pending_ids = get_pending_matches()
    
    if not pending_ids:
        return "No pending matches in queue."
    
    success_count = 0
    fail_count = 0
    total = len(pending_ids)
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    results_log = []

    for i, match_id in enumerate(pending_ids):
        status_text.text(f"Processing match {match_id} ({i+1}/{total})...")
        progress_bar.progress((i) / total)
        
        # 1. Update Status to Processing
        update_match_status(match_id, 'processing')
        
        try:
            # 2. Download Demo
            # We don't have a direct URL stored, so we rely on auto-detection in download_demo
            dl_success, dl_msg = download_demo(match_id, admin_name=admin_name)
            
            if not dl_success:
                raise Exception(f"Download failed: {dl_msg}")
            
            # 3. Analyze Demo
            expected_filename = f"demos/match_{match_id}.dem"
            if not os.path.exists(expected_filename):
                raise Exception(f"File not found after download: {expected_filename}")
                
            score_res, stats_res, map_name, score_t, score_ct = analyze_demo_file(expected_filename)
            
            # Cleanup demo file immediately after analysis
            if os.path.exists(expected_filename):
                os.remove(expected_filename)
            
            if stats_res is None:
                raise Exception(f"Analysis failed: {score_res}")

            # --- DOUBLE CHECK WITH WEB STATS (SOURCE OF TRUTH) ---
            try:
                print(f"Verifying stats for match {match_id} against web...")
                web_stats = get_lobby_player_stats(match_id)
                if web_stats:
                    mismatches = []
                    # We will loop through the DataFrame and CORRECT the stats if they differ
                    # The Web API is the Source of Truth for Kills, Deaths, Assists, Headshots
                    
                    # Create a map for quick lookups
                    # We handle potential name differences by matching names exactly for now
                    # (The demo parser might clean names differently, but usually they match)
                    
                    for index, row in stats_res.iterrows():
                        p_name = row['Player']
                        
                        if p_name in web_stats:
                            web_data = web_stats[p_name] # Expecting dict or int depending on what we return
                            
                            # Our get_lobby_player_stats currently returns just Kills (int)
                            # We should probably update it to return more if we want to correct more.
                            # For now, let's correct Kills.
                            
                            # Update: We need to enhance get_lobby_player_stats to returns dict of {kills, deaths, assists, hs}
                            # Assuming get_lobby_player_stats returns just kills for now based on previous step. 
                            # I will update cybershoke.py first to return full object.
                            
                            web_kills = web_stats[p_name]
                            demo_kills = row['Kills']
                            
                            if demo_kills != web_kills:
                                mismatches.append(f"{p_name}: Demo={demo_kills} -> Web={web_kills} (Fixed)")
                                stats_res.at[index, 'Kills'] = web_kills
                                # We might need to reject other derived stats or leave them inconsistent?
                                # Ideally we leave ADR/Utility as is, but Kills are fixed.
                                
                    if mismatches:
                        warn_msg = f"⚠️ Corrected Stats for {match_id}: " + ", ".join(mismatches)
                        print(warn_msg)
                        results_log.append(warn_msg)
                    else:
                        print("✅ Web stats verification passed (No changes needed).")
                else:
                    print("⚠️ Could not fetch web stats for verification.")
            except Exception as e:
                print(f"Stats verification/correction failed: {e}")
            # -----------------------------------
            
            # 4. Save to Database
            # We construct a unique match_id for the stats table, usually 'match_ID'
            db_match_id = f"match_{match_id}"
            save_match_stats(db_match_id, match_id, score_res, stats_res, map_name, score_t, score_ct)
            
            # 5. Mark Completed
            update_match_status(match_id, 'completed', set_processed_time=True)
            success_count += 1
            results_log.append(f"✅ {match_id}: Success ({map_name})")
            
        except Exception as e:
            # Mark Failed
            print(f"Failed to process {match_id}: {e}")
            update_match_status(match_id, 'failed')
            fail_count += 1
            results_log.append(f"❌ {match_id}: {str(e)}")
            
        # Update progress after step
        progress_bar.progress((i + 1) / total)

    status_text.text("Processing complete.")
    progress_bar.empty()
    
    summary = f"Processed {total} matches: {success_count} success, {fail_count} failed."
    return summary, results_log

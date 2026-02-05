import os
import sys
import json
import argparse
import pandas as pd
from demo_download import download_demo
from demo_analysis import analyze_demo_file
from cybershoke import get_lobby_player_stats

# Ensure output directory exists
OUTPUT_DIR = "processed_matches"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def process_match_local(match_id, admin_name="Skeez"):
    print(f"--- Starting Local Processing for Match {match_id} ---")
    
    # 1. Download Demo
    print(f"Step 1: Downloading demo for {match_id}...")
    success, msg = download_demo(match_id, admin_name=admin_name)
    
    if not success:
        print(f"❌ Download failed: {msg}")
        return False
    print(f"✅ {msg}")
    
    # 2. Analyze Demo
    expected_filename = f"demos/match_{match_id}.dem"
    if not os.path.exists(expected_filename):
        print(f"❌ File not found after download: {expected_filename}")
        return False
        
    print(f"Step 2: Analyzing demo file {expected_filename}...")
    try:
        score_res, stats_res, map_name, score_t, score_ct = analyze_demo_file(expected_filename)
        
        # Cleanup
        if os.path.exists(expected_filename):
            os.remove(expected_filename)
            print("Deleted demo file to save space.")
            
        if stats_res is None:
            print(f"❌ Analysis failed: {score_res}")
            return False
            
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        return False

    print(f"✅ Analysis complete! Raw Score: {score_res}, Map: {map_name}")

    # 3. Verify & Correct with Web Stats
    print("Step 3: Verifying against Cybershoke Web Stats...")
    try:
        web_stats, web_score, web_map = get_lobby_player_stats(match_id)
        
        if web_stats:
            print("✅ Fetched web stats. reconciling...")
            
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
            changes_count = 0
            for index, row in stats_res.iterrows():
                p_name = row['Player']
                if p_name in web_stats:
                    w_det = web_stats[p_name]
                    
                    # Update Key Metrics
                    stats_res.at[index, 'Kills'] = w_det['kills']
                    stats_res.at[index, 'Deaths'] = w_det['deaths']
                    stats_res.at[index, 'Assists'] = w_det['assists']
                    stats_res.at[index, 'Headshots'] = w_det['headshots']
                    
                    # Recalculate Derived
                    k, d, hs = w_det['kills'], w_det['deaths'], w_det['headshots']
                    stats_res.at[index, 'K/D'] = round(k / d, 2) if d > 0 else k
                    stats_res.at[index, 'HS%'] = round((hs / k * 100), 1) if k > 0 else 0
                    
                    changes_count += 1
            print(f"✅ Reconciled {changes_count} players with web data.")
        else:
            print("⚠️ Could not fetch web stats. Proceeding with demo data only.")
            
    except Exception as e:
        print(f"⚠️ Warning during verification: {e}")

    # 4. Export to JSON
    print("Step 4: Exporting to JSON...")
    
    # Convert Dataframe to list of dicts for JSON serialization
    players_data = []
    for _, row in stats_res.iterrows():
        p_data = row.to_dict()
        players_data.append(p_data)

    output_data = {
        "match_id": str(match_id),
        "map_name": map_name,
        "score_str": score_res,
        "score_t": score_t,
        "score_ct": score_ct,
        "player_stats": players_data
    }
    
    file_path = os.path.join(OUTPUT_DIR, f"match_{match_id}.json")
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=4)
        print(f"✅ SUCCESSFULLY SAVED: {file_path}")
        
        # 5. Upload to API if URL provided
        if upload_url:
            print(f"Step 5: Uploading to API ({upload_url})...")
            try:
                headers = {'Content-Type': 'application/json'}
                resp = requests.post(upload_url, json=output_data, headers=headers)
                if resp.status_code == 200:
                    print("🚀 MATCH UPLOADED SUCCESSFULLY TO WEB APP!")
                else:
                    print(f"❌ Upload Failed: {resp.status_code} - {resp.text}")
            except Exception as ul_e:
                print(f"❌ Connection Error during upload: {ul_e}")
                
        return True
    except Exception as e:
        print(f"❌ Failed to handle/save JSON: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Local CS2 Match Processor")
    parser.add_argument("match_id", help="Cybershoke Match ID (e.g. 5394408)")
    parser.add_argument("--admin", default="Skeez", help="Admin name for cookies (default: Skeez)")
    parser.add_argument("--upload-url", help="API URL to auto-upload results (e.g. http://localhost:8000/upload_match)")
    
    args = parser.parse_args()
    
    process_match_local(args.match_id, args.admin, upload_url=args.upload_url)

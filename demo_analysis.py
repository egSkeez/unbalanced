
import pandas as pd
import json
import subprocess
import os
import sys

def analyze_demo_file(demo_path):
    """
    Analyzes a .dem file using the external Go parser.
    Returns:
    - score_str: String describing match result
    - stats_df: DataFrame with player stats
    - map_name: Map name
    - score_t: T side score
    - score_ct: CT side score
    """
    # Path to the Go binary
    # Assumes the binary is located at go_parser/parser.exe relative to this script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    go_binary = os.path.join(current_dir, "go_parser", "parser.exe")
    
    # Check if binary exists, if not, try to build it or warn
    if not os.path.exists(go_binary):
        print(f"Error: Go binary not found at {go_binary}")
        return "Parser not found", None, "Unknown", 0, 0

    try:
        # Run Go parser
        print(f"Running Go parser on: {demo_path}")
        result = subprocess.run([go_binary, demo_path], capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode != 0:
            print(f"Go parser error: {result.stderr}")
            return f"Parser Error: {result.stderr}", None, "Unknown", 0, 0
            
        # Parse JSON output
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            print(f"Failed to decode JSON: {result.stdout}")
            return "JSON Error", None, "Unknown", 0, 0
            
        if data.get("error"):
            print(f"Parser reported error: {data['error']}")
            return f"Error: {data['error']}", None, "Unknown", 0, 0

        # Extract basic info
        score_str = data.get("score_str", "Unknown")
        map_name = data.get("map_name", "Unknown")
        score_t = data.get("score_t", 0)
        score_ct = data.get("score_ct", 0)
        
        stats_list = data.get("stats", [])
        
        if not stats_list:
            print("No stats found in parser output")
            return score_str, None, map_name, score_t, score_ct
            
        # Convert to DataFrame
        stats_df = pd.DataFrame(stats_list)
        
        # Ensure columns exist and order them
        expected_cols = ['Player', 'SteamID', 'TeamNum', 'Kills', 'Deaths', 'Assists', 'K/D', 'ADR', 'HS%', 'Score', 
                         'Damage', 'UtilityDamage', 'Flashed', 'TeamFlashed', 'FlashAssists', 
                         'TotalSpent', 'EntryKills', 'EntryDeaths', 'ClutchWins', 
                         'BombPlants', 'BombDefuses', 'Headshots', 'MultiKills', 'WeaponKills']
        
        for col in expected_cols:
            if col not in stats_df.columns:
                # specific handling for object/map columns
                if col in ['MultiKills', 'WeaponKills']:
                     stats_df[col] = [{} for _ in range(len(stats_df))]
                else:
                     stats_df[col] = 0
                
        # Sort by Score or Kills
        stats_df = stats_df.sort_values("Score", ascending=False)
        
        print(f"Successfully parsed stats for {len(stats_df)} players")
        return score_str, stats_df, map_name, score_t, score_ct

    except Exception as e:
        print(f"Error executing Go parser: {e}")
        return f"Execution Error: {str(e)}", None, "Unknown", 0, 0

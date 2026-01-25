
import os
import pandas as pd
from demo_download import download_demo
from demo_analysis import analyze_demo_file

MATCH_ID = "5394408"
DEMO_PATH = f"demos/match_{MATCH_ID}.dem"

# Ensure demo exists (download if needed)
if not os.path.exists(DEMO_PATH):
    print(f"Downloading {MATCH_ID}...")
    success, msg = download_demo(MATCH_ID, "debug_user")
    if not success:
        print(f"Download failed: {msg}")
        exit()

print(f"Running Full Analysis on {DEMO_PATH}...")
score, df, map_name, t, ct = analyze_demo_file(DEMO_PATH)

print("\n--- ANALYSIS RESULTS ---")
print(f"Score: {score}")
print(f"Map: {map_name}")

if df is not None and not df.empty:
    print("\nColumns:", df.columns.tolist())
    
    # Check Extended Stats
    print("\nSample Rows:")
    print(df[['Player', 'Kills', 'EntryKills', 'EntryDeaths', 'BaiterRating', 'ClutchWins', 'TotalSpent']].head(10))
    
    # Assertions
    total_entries = df['EntryKills'].sum()
    total_spent = df['TotalSpent'].sum()
    total_bait = df['BaiterRating'].sum()
    total_clutches = df['ClutchWins'].sum()
    
    print(f"\nTotal Entry Kills: {total_entries}")
    print(f"Total Spent: {total_spent}")
    print(f"Total Baiter Points: {total_bait}")
    print(f"Total Clutches: {total_clutches}")
    
    if total_entries > 0 and total_bait > 0:
        if total_spent > 0:
             print("\n✅ SUCCESS: ALL stats (Entries, Bait, Spend) working.")
        else:
             print("\n⚠️ PARTIAL SUCCESS: Entries & Bait working. Spend is 0 (Property missing in demo).")
else:
    print("❌ FAILURE: No stats dataframe returned.")

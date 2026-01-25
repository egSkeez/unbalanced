
import os
from demoparser2 import DemoParser
import pandas as pd
from demo_download import download_demo

MATCH_ID = "5394408"
DEMO_PATH = f"demos/match_{MATCH_ID}.dem"

# Ensure demo exists
if not os.path.exists(DEMO_PATH):
    print(f"Downloading {MATCH_ID}...")
    success, msg = download_demo(MATCH_ID, "debug_user")
    if not success:
        print(f"Download failed: {msg}")
        exit()

print(f"Analyzing {DEMO_PATH}...")
parser = DemoParser(DEMO_PATH)

# 1. CHECK CASH SPENT PROPERTY
print("\n--- CHECKING CASH SPENT ---")
props = [
    "CCSPlayerController.m_iszPlayerName",
    "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iTotalCashSpent",
    "CCSPlayerController.m_iTotalCashSpent" # Alternative?
]
try:
    df = parser.parse_ticks(props)
    if not df.empty:
        max_tick = df['tick'].max()
        final = df[df['tick'] == max_tick]
        print(final.head())
        print("Columns found:", final.columns.tolist())
        # Check if any non-zero
        col_name = "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iTotalCashSpent"
        if col_name in final.columns:
            print(f"Non-zero cash entries: {len(final[final[col_name] > 0])}")
    else:
        print("No tick data returned.")
except Exception as e:
    print(f"Tick parsing error: {e}")

# 2. CHECK EVENTS FOR NAMES
print("\n--- CHECKING EVENTS ---")
events = parser.parse_events(["player_death", "round_end"])
deaths = pd.DataFrame(events[0][1])
if not deaths.empty:
    print("Death Event Columns:", deaths.columns.tolist())
    print("Sample Death Rows:")
    print(deaths[['attacker_name', 'user_name']].head())
    
    # Check if names match what we expect
    sample_name = deaths.iloc[0]['user_name']
    print(f"Sample User Name from Event: '{sample_name}'")

# 3. COMPARE WITH TICK NAMES
if not df.empty:
    tick_names = df['CCSPlayerController.m_iszPlayerName'].unique()
    print(f"Sample User Name from Ticks: '{tick_names[0] if len(tick_names)>0 else 'None'}'")
    
    if sample_name in tick_names:
        print("✅ Names MATCH between Events and Ticks")
    else:
        print("❌ Names DO NOT MATCH (Encoding issue?)")

# 4. ENTRY LOGIC TEST
print("\n--- TEST ENTRY LOGIC ---")
# ... (simplified check)

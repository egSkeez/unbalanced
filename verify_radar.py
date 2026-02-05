import requests
import json
import time
from cybershoke import create_cybershoke_lobby_api, get_headers

def check_radar_capability():
    print("Creating a test lobby to check API capabilities...")
    # Attempt to create a lobby
    link, lobby_id = create_cybershoke_lobby_api(admin_name="Skeez")
    
    if not lobby_id:
        print("Failed to create lobby. Cannot inspect API structure.")
        return

    print(f"Lobby created! ID: {lobby_id}")
    print(f"Link: {link}")
    
    # Wait a moment for propagation if needed
    time.sleep(2)
    
    url = "https://api.cybershoke.net/api/v1/custom-matches/lobbys/info"
    payload = {"id_lobby": lobby_id}
    
    try:
        print("Fetching lobby info...")
        resp = requests.post(url, headers=get_headers("Skeez"), json=payload, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            
            # Save full response for detailed inspection
            with open("cybershoke_lobby_dump.json", "w") as f:
                json.dump(data, f, indent=4)
            print("Full API response saved to 'cybershoke_lobby_dump.json'")
            
            # Inspect for position data
            lobby_data = data.get("data", {})
            players = lobby_data.get("players", {})
            
            print(f"Lobby status: {lobby_data.get('status')}")
            print(f"Players found: {len(players)}")
            
            # Even if empty, we might see the structure or we might be able to add a dummy bot/wait
            # Usually in an empty lobby 'players' might be empty or contain the creator.
            
            if players:
                first_player_key = next(iter(players))
                p_data = players[first_player_key]
                print(f"Sample Player Data Keys: {list(p_data.keys())}")
                
                if "match_stats" in p_data:
                    print(f"Match Stats Keys: {list(p_data['match_stats'].keys())}")
                    if "live" in p_data['match_stats']:
                         print(f"Live Stats Keys: {list(p_data['match_stats']['live'].keys())}")
                         
                # Check explicitly for common coordinate names
                found_coords = False
                for k in ["x", "y", "z", "pos", "position", "coordinates", "location"]:
                    if k in p_data or k in p_data.get("match_stats", {}).get("live", {}):
                        print(f"FOUND POSSIBLE COORDINATE FIELD: {k}")
                        found_coords = True
                
                if not found_coords:
                    print("No obvious coordinate fields found in player data.")
            else:
                print("No players in lobby to inspect structure.")
                
        else:
            print(f"Failed to fetch info: {resp.status_code}")
            
    except Exception as e:
        print(f"Error checking API: {e}")

if __name__ == "__main__":
    check_radar_capability()

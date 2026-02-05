import requests
import sqlite3
import json
from cybershoke import get_headers, get_lobby_link

def inspect_lobby():
    link, cs_id = get_lobby_link()
    print(f"Link: {link}, CS ID: {cs_id}")
    
    if not cs_id:
        # If no CS ID, try to extract from link if present
        if link and "cybershoke.net/match/" in link:
            cs_id = link.split("/")[-1]
            print(f"Extracted CS ID from link: {cs_id}")
    
    if not cs_id:
        print("No active lobby found in DB.")
        return

    print(f"Inspecting Lobby ID: {cs_id}")
    
    url = "https://api.cybershoke.net/api/v1/custom-matches/lobbys/info"
    payload = {"id_lobby": int(cs_id)}
    
    try:
        resp = requests.post(url, headers=get_headers("Skeez"), json=payload, timeout=10)
        print(f"Status Code: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            # Save to a file for inspection
            with open("cybershoke_api_response.json", "w") as f:
                json.dump(data, f, indent=4)
            print("Saved response to cybershoke_api_response.json")
            
            # Print keys in data
            print("Top level keys:", data.keys())
            if "data" in data:
                print("Data keys:", data["data"].keys())
                if "players" in data["data"]:
                   first_player = next(iter(data["data"]["players"].values()))
                   print("Player keys:", first_player.keys())
                   if "match_stats" in first_player:
                       print("Match stats keys:", first_player["match_stats"].keys())
                       if "live" in first_player["match_stats"]:
                           print("Live stats keys:", first_player["match_stats"]["live"].keys())
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_lobby()

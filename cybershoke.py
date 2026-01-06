# cybershoke.py
import requests
import sqlite3
import random
import time

# --- CONFIGURATION ---
# The new cookie you provided
NEW_COOKIE = '_ym_uid=1767725166389867440; _ym_d=1767725166; categories={}; showFull=false; hideFullAmong=false; sCategories={}; competitionsLeague=high; gMapFilerv=[]; gCategoryFiler=[]; glocationFilerNewv=[]; gSortFiler=online; gPrimeFiler=both; gSortShopFiler2=down; gCompetitionsDataStats=month; gCompetitionsDataId=12; gCompetitionsDataClass=low; gCompetitionsDataHalfmonth=0; gProfileSkinchangerFilterQ=%E2%98%85%20Karambit; gProfileSkinchangerFilterCollection=1; hideFullServers=true; gSkipPremiumModal=0; gServersPrimeMode=all; gHideFilledServers=1; _gid=GA1.2.405774975.1767725166; _gat_gtag_UA_132864474_3=1; _gat_UA-151937518-1=1; _gat_gtag_UA_151937518_1=1; lang_g=en; translation_unix=1767623559; _ym_isad=2; changer_update=1762379362; multitoken=t9HMMczcbjXbYVbPl7uBafZg2O1767725193343l1yXzqZULVne8FrN1mXDlE39EtzDoUiRL1VJj3qY1G8F0pkA53K13; multitoken_created=1; _ga_5676S8YGZK=GS2.1.s1767725165$o1$g1$t1767725193$j32$l0$h0; _ga=GA1.1.1937088403.1767725166; last_page=/matches; _ga_VLRBXFQ6V5=GS2.1.s1767725165$o1$g1$t1767725197$j28$l0$h0'

def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Cookie": NEW_COOKIE,
        "Referer": "https://cybershoke.net/",
        "Origin": "https://cybershoke.net"
    }

def create_cybershoke_lobby_api():
    """
    Creates a lobby using the real Cybershoke API.
    If it fails, returns None (instead of a fake link) so you can create it manually.
    """
    url = "https://cybershoke.net/api/lobby/create"
    
    payload = {
        "server": "eu",     
        "mode": "cs2_5x5",  
        "map": "de_mirage", 
        "private": 1,
        "password": "kimkim"
    }

    try:
        response = requests.post(url, headers=get_headers(), data=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'url' in data:
                return data['url']
            elif 'id' in data:
                return f"https://cybershoke.net/lobby/{data['id']}"
            else:
                print("API Success but no URL found in response:", data)
                return None
        else:
            print(f"Cybershoke API Failed: {response.status_code}")
            # print(response.text) # Uncomment to debug exact error
            return None

    except Exception as e:
        print(f"Request failed: {e}")
        return None

def init_cybershoke_db():
    pass

# --- DB PERSISTENCE FUNCTIONS ---
def set_lobby_link(link):
    """Saves the lobby link to the database."""
    conn = sqlite3.connect('cs2_history.db')
    try:
        conn.execute("UPDATE active_draft_state SET current_lobby=? WHERE id=1", (link,))
        conn.commit()
    except Exception as e:
        print(f"Error saving lobby link: {e}")
    finally:
        conn.close()

def get_lobby_link():
    """Retrieves the active lobby link from the database."""
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    link = None
    try:
        c.execute("SELECT current_lobby FROM active_draft_state WHERE id=1")
        row = c.fetchone()
        if row and row[0]:
            link = row[0]
    except Exception as e:
        print(f"Error reading lobby link: {e}")
    finally:
        conn.close()
    return link

def clear_lobby_link():
    """Removes the lobby link from the database."""
    conn = sqlite3.connect('cs2_history.db')
    try:
        conn.execute("UPDATE active_draft_state SET current_lobby=NULL WHERE id=1")
        conn.commit()
    except:
        pass
    finally:
        conn.close()

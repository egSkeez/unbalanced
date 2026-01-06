# cybershoke.py
import requests
import sqlite3
import json

# --- CONFIGURATION ---
# The working cookie provided
AUTH_COOKIE = "ategories={}; showFull=false; hideFullAmong=false; sCategories={}; competitionsLeague=high; gMapFilerv=[]; gCategoryFiler=[]; glocationFilerNewv=[]; gSortFiler=online; gPrimeFiler=both; gSortShopFiler2=down; gCompetitionsDataStats=month; gCompetitionsDataId=12; gCompetitionsDataClass=low; gCompetitionsDataHalfmonth=0; gProfileSkinchangerFilterQ=%E2%98%85%20Karambit; gProfileSkinchangerFilterCollection=1; hideFullServers=true; gSkipPremiumModal=0; gServersPrimeMode=all; gHideFilledServers=1; lang_g=en; cookie_read=1; multitoken=7YV8DwPzGAGXlNBFM5ZIQGng991762105429993ouD8eCPqmRlZZ4WWXoCtz2vPmbLLw4kkBdGMaxach87Olkwr0Tx5W; multitoken_created=1; changer_update=1762379362; pinsFeatured=[]; ph_phc_PUoVkcukLD6bmHE3VxpSErcJlifbGlWTWgtiWllB7NA_posthog=%7B%22distinct_id%22%3A%2276561198294799864%22%2C%22%24sesid%22%3A%5Bnull%2Cnull%2Cnull%5D%2C%22%24epp%22%3Atrue%2C%22%24initial_person_info%22%3A%7B%22r%22%3A%22%24direct%22%2C%22u%22%3A%22https%3A%2F%2Fcybershoke.net%2Fmatch%2F3387473%22%7D%7D; ph_phc_rrPtSJqWrZYBNTKe0xXhqX06PeeesY7hSuVvVtrshEk_posthog=%7B%22distinct_id%22%3A%2276561198294799864%22%2C%22%24sesid%22%3A%5B1764023851069%2C%22019ab800-b1f9-7247-8b54-6c4dadca6f78%22%2C1764023644665%5D%2C%22%24epp%22%3Atrue%2C%22%24initial_person_info%22%3A%7B%22r%22%3A%22%24direct%22%2C%22u%22%3A%22https%3A%2F%2Fcybershoke.net%2Fmatch%2F3601759%22%7D%7D; view=grid; ph_phc_axKew8iO1uHqh7VyQ70xd8gwbda3IhtRbV5TG7xDu0I_posthog=%7B%22distinct_id%22%3A%2276561198294799864%22%2C%22%24sesid%22%3A%5B1765230599167%2C%22019affeb-902a-7488-b7a3-928c5b8c3923%22%2C1765230219300%5D%2C%22%24epp%22%3Atrue%2C%22%24initial_person_info%22%3A%7B%22r%22%3A%22%24direct%22%2C%22u%22%3A%22https%3A%2F%2Fcybershoke.net%2Fmatch%2F3742184%22%7D%7D; translation_unix=1767362692; pings_list={%22pings%22:{%22germany%22:17%2C%22warsaw%22:32%2C%22finland%22:39%2C%22sweden%22:41%2C%22lithuania%22:36%2C%22gb%22:23%2C%22france%22:7%2C%22kazakhstan%22:0%2C%22astana%22:0%2C%22turkey%22:46%2C%22new-york%22:0%2C%22chicago%22:98%2C%22dallas%22:0%2C%22los-angeles%22:0%2C%22moscow%22:0%2C%22yakutsk%22:0%2C%22kiev%22:40%2C%22georgia%22:0%2C%22singapore%22:0%2C%22mumbai%22:0%2C%22sydney%22:0%2C%22sao-paulo%22:0}%2C%22ip%22:%2291.166.107.158%22}; last_page=/matches"

def get_headers():
    return {
        "authority": "api.cybershoke.net",
        "accept": "application/json, text/plain, */*",
        "accept-language": "fr,fr-FR;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "content-type": "application/json",
        "origin": "https://cybershoke.net",
        "referer": "https://cybershoke.net/",
        "sec-ch-ua": '"Microsoft Edge";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
        "cookie": AUTH_COOKIE
    }

def create_cybershoke_lobby_api():
    """
    Creates a lobby using the working Custom Match API endpoint.
    Returns the lobby URL on success, or None on failure.
    """
    url = "https://api.cybershoke.net/api/v1/custom-matches/lobbys/create"
    
    payload = {
        "type_lobby": 2, 
        "lobby_password": "kimkim"
    }

    try:
        response = requests.post(url, headers=get_headers(), json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("result") == "success":
                lobby_id = data["data"]["id_lobby"]
                return f"https://cybershoke.net/match/{lobby_id}"
            else:
                print("API returned error:", data.get("message"))
                return None
        else:
            print(f"API Failed with status {response.status_code}: {response.text}")
            return None

    except Exception as e:
        print(f"Request failed: {e}")
        return None

def init_cybershoke_db():
    pass

# --- DB PERSISTENCE FUNCTIONS (Unchanged) ---
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

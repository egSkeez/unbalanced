# cybershoke.py
import requests
import sqlite3
import json

# --- COOKIE REPOSITORY ---
COOKIES = {
    "Skeez": "ategories={}; showFull=false; hideFullAmong=false; sCategories={}; competitionsLeague=high; gMapFilerv=[]; gCategoryFiler=[]; glocationFilerNewv=[]; gSortFiler=online; gPrimeFiler=both; gSortShopFiler2=down; gCompetitionsDataStats=month; gCompetitionsDataId=12; gCompetitionsDataClass=low; gCompetitionsDataHalfmonth=0; gProfileSkinchangerFilterQ=%E2%98%85%20Karambit; gProfileSkinchangerFilterCollection=1; hideFullServers=true; gSkipPremiumModal=0; gServersPrimeMode=all; gHideFilledServers=1; lang_g=en; cookie_read=1; multitoken=7YV8DwPzGAGXlNBFM5ZIQGng991762105429993ouD8eCPqmRlZZ4WWXoCtz2vPmbLLw4kkBdGMaxach87Olkwr0Tx5W; multitoken_created=1; changer_update=1762379362; pinsFeatured=[]; ph_phc_PUoVkcukLD6bmHE3VxpSErcJlifbGlWTWgtiWllB7NA_posthog=%7B%22distinct_id%22%3A%2276561198294799864%22%2C%22%24sesid%22%3A%5Bnull%2Cnull%2Cnull%5D%2C%22%24epp%22%3Atrue%2C%22%24initial_person_info%22%3A%7B%22r%22%3A%22%24direct%22%2C%22u%22%3A%22https%3A%2F%2Fcybershoke.net%2Fmatch%2F3387473%22%7D%7D; ph_phc_rrPtSJqWrZYBNTKe0xXhqX06PeeesY7hSuVvVtrshEk_posthog=%7B%22distinct_id%22%3A%2276561198294799864%22%2C%22%24sesid%22%3A%5B1764023851069%2C%22019ab800-b1f9-7247-8b54-6c4dadca6f78%22%2C1764023644665%5D%2C%22%24epp%22%3Atrue%2C%22%24initial_person_info%22%3A%7B%22r%22%3A%22%24direct%22%2C%22u%22%3A%22https%3A%2F%2Fcybershoke.net%2Fmatch%2F3601759%22%7D%7D; view=grid; ph_phc_axKew8iO1uHqh7VyQ70xd8gwbda3IhtRbV5TG7xDu0I_posthog=%7B%22distinct_id%22%3A%2276561198294799864%22%2C%22%24sesid%22%3A%5B1765230599167%2C%22019affeb-902a-7488-b7a3-928c5b8c3923%22%2C1765230219300%5D%2C%22%24epp%22%3Atrue%2C%22%24initial_person_info%22%3A%7B%22r%22%3A%22%24direct%22%2C%22u%22%3A%22https%3A%2F%2Fcybershoke.net%2Fmatch%2F3742184%22%7D%7D; translation_unix=1767362692; pings_list={%22pings%22:{%22germany%22:17%2C%22warsaw%22:32%2C%22finland%22:39%2C%22sweden%22:41%2C%22lithuania%22:36%2C%22gb%22:23%2C%22france%22:7%2C%22kazakhstan%22:0%2C%22astana%22:0%2C%22turkey%22:46%2C%22new-york%22:0%2C%22chicago%22:98%2C%22dallas%22:0%2C%22los-angeles%22:0%2C%22moscow%22:0%2C%22yakutsk%22:0%2C%22kiev%22:40%2C%22georgia%22:0%2C%22singapore%22:0%2C%22mumbai%22:0%2C%22sydney%22:0%2C%22sao-paulo%22:0}%2C%22ip%22:%2291.166.107.158%22}; last_page=/matches",
    
    "Kim": "_ym_uid=1767725166389867440; _ym_d=1767725166; categories={}; showFull=false; hideFullAmong=false; sCategories={}; competitionsLeague=high; gMapFilerv=[]; gCategoryFiler=[]; glocationFilerNewv=[]; gSortFiler=online; gPrimeFiler=both; gSortShopFiler2=down; gCompetitionsDataStats=month; gCompetitionsDataId=12; gCompetitionsDataClass=low; gCompetitionsDataHalfmonth=0; gProfileSkinchangerFilterQ=%E2%98%85%20Karambit; gProfileSkinchangerFilterCollection=1; hideFullServers=true; gSkipPremiumModal=0; gServersPrimeMode=all; gHideFilledServers=1; _gid=GA1.2.405774975.1767725166; _gat_gtag_UA_132864474_3=1; _gat_UA-151937518-1=1; _gat_gtag_UA_151937518_1=1; lang_g=en; translation_unix=1767623559; _ym_isad=2; changer_update=1762379362; multitoken=t9HMMczcbjXbYVbPl7uBafZg2O1767725193343l1yXzqZULVne8FrN1mXDlE39EtzDoUiRL1VJj3qY1G8F0pkA53K13; multitoken_created=1; _ga_5676S8YGZK=GS2.1.s1767725165$o1$g1$t1767725193$j32$l0$h0; _ga=GA1.1.1937088403.1767725166; last_page=/matches; _ga_VLRBXFQ6V5=GS2.1.s1767725165$o1$g1$t1767725197$j28$l0$h0",
    
    "Ghoufa": "_ym_uid=1767714178395001989; _ym_d=1767714178; categories={}; showFull=false; hideFullAmong=false; sCategories={}; competitionsLeague=high; gMapFilerv=[]; gCategoryFiler=[]; glocationFilerNewv=[]; gSortFiler=online; gPrimeFiler=both; gSortShopFiler2=down; gCompetitionsDataStats=month; gCompetitionsDataId=12; gCompetitionsDataClass=low; gCompetitionsDataHalfmonth=0; gProfileSkinchangerFilterQ=%E2%98%85%20Karambit; gProfileSkinchangerFilterCollection=1; hideFullServers=true; gSkipPremiumModal=0; gServersPrimeMode=all; gHideFilledServers=1; lang_g=en; translation_unix=1767623559; changer_update=1762379362; _gid=GA1.2.689440989.1767714179; multitoken=QuhNXivQITPL4kGFOpAF6jBDKs1767728352453lZX5YWWITp0XRsvUpraIRGKMGHDQHdDu3BCZuyN05GgCWBf6WhpJz; multitoken_created=1; cookie_read=1; _ym_isad=1; _gat_gtag_UA_132864474_3=1; _gat_UA-151937518-1=1; _gat_gtag_UA_151937518_1=1; _ga_5676S8YGZK=GS2.1.s1767817922$o5$g0$t1767817922$j60$l0$h0; _ga=GA1.1.2065653719.1767714178; last_page=/matches; _ga_VLRBXFQ6V5=GS2.1.s1767817921$o6$g1$t1767817926$j55$l0$h0; pings_list={%22pings%22:{%22germany%22:833%2C%22warsaw%22:1193%2C%22finland%22:0%2C%22sweden%22:0%2C%22lithuania%22:1192%2C%22gb%22:1209%2C%22france%22:0%2C%22kazakhstan%22:0%2C%22astana%22:0%2C%22turkey%22:1192%2C%22new-york%22:0%2C%22chicago%22:0%2C%22dallas%22:0%2C%22los-angeles%22:0%2C%22moscow%22:0%2C%22yakutsk%22:0%2C%22kiev%22:0%2C%22georgia%22:0%2C%22singapore%22:0%2C%22mumbai%22:0%2C%22sydney%22:0%2C%22sao-paulo%22:0}%2C%22ip%22:%22196.239.143.39%22}"
}

def get_headers(admin_name):
    # Fallback to Skeez if name not in dict or not logged in
    cookie = COOKIES.get(admin_name, COOKIES["Skeez"])
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
        "cookie": cookie
    }

def create_cybershoke_lobby_api(admin_name="Skeez"):
    """
    Creates a lobby using the working Custom Match API endpoint.
    Uses specific cookie based on who is logged in as Admin.
    """
    url = "https://api.cybershoke.net/api/v1/custom-matches/lobbys/create"
    
    payload = {
        "type_lobby": 2, 
        "lobby_password": "kimkim"
    }

    try:
        response = requests.post(url, headers=get_headers(admin_name), json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("result") == "success":
                lobby_id = data["data"]["id_lobby"]
                
                # Persist to lobby history
                try:
                   from match_stats_db import add_lobby
                   add_lobby(lobby_id)
                except Exception as e:
                   print(f"Failed to track lobby history: {e}")
                
                return f"https://cybershoke.net/match/{lobby_id}", lobby_id
            else:
                print(f"API returned error for {admin_name}:", data.get("message"))
                return None, None
        else:
            print(f"API Failed with status {response.status_code}")
            return None, None
    except Exception as e:
        print(f"Request failed: {e}")
        return None, None

def init_cybershoke_db():
    """Placeholder function to satisfy app.py imports."""
    pass

# --- DB PERSISTENCE FUNCTIONS ---
def set_lobby_link(link, match_id=None):
    """Saves the lobby link and optional match ID to the database."""
    conn = sqlite3.connect('cs2_history.db')
    try:
        if match_id:
            conn.execute("UPDATE active_draft_state SET current_lobby=?, cybershoke_match_id=? WHERE id=1", (link, str(match_id)))
        else:
            conn.execute("UPDATE active_draft_state SET current_lobby=? WHERE id=1", (link,))
        conn.commit()
    except Exception as e:
        print(f"Error saving lobby link: {e}")
    finally:
        conn.close()

def get_lobby_link():
    """Retrieves the active lobby link and match ID from the database."""
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    link = None
    cs_id = None
    try:
        c.execute("SELECT current_lobby, cybershoke_match_id FROM active_draft_state WHERE id=1")
        row = c.fetchone()
        if row:
            link = row[0]
            cs_id = row[1]
    except:
        pass
    finally:
        conn.close()
    return link, cs_id

def clear_lobby_link():
    """Removes the lobby link and match ID from the database."""
    conn = sqlite3.connect('cs2_history.db')
    try:
        conn.execute("UPDATE active_draft_state SET current_lobby=NULL, cybershoke_match_id=NULL WHERE id=1")
        conn.commit()
    except:
        pass
    finally:
        conn.close()

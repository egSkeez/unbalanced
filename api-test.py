import requests
import json

def test_api():
    url = "https://api.cybershoke.net/api/v1/custom-matches/lobbys/create"
    
    # ⚠️ PASTE YOUR FULL COOKIE HERE
    auth_cookie = "ategories={}; showFull=false; hideFullAmong=false; sCategories={}; competitionsLeague=high; gMapFilerv=[]; gCategoryFiler=[]; glocationFilerNewv=[]; gSortFiler=online; gPrimeFiler=both; gSortShopFiler2=down; gCompetitionsDataStats=month; gCompetitionsDataId=12; gCompetitionsDataClass=low; gCompetitionsDataHalfmonth=0; gProfileSkinchangerFilterQ=%E2%98%85%20Karambit; gProfileSkinchangerFilterCollection=1; hideFullServers=true; gSkipPremiumModal=0; gServersPrimeMode=all; gHideFilledServers=1; lang_g=en; cookie_read=1; multitoken=7YV8DwPzGAGXlNBFM5ZIQGng991762105429993ouD8eCPqmRlZZ4WWXoCtz2vPmbLLw4kkBdGMaxach87Olkwr0Tx5W; multitoken_created=1; changer_update=1762379362; pinsFeatured=[]; ph_phc_PUoVkcukLD6bmHE3VxpSErcJlifbGlWTWgtiWllB7NA_posthog=%7B%22distinct_id%22%3A%2276561198294799864%22%2C%22%24sesid%22%3A%5Bnull%2Cnull%2Cnull%5D%2C%22%24epp%22%3Atrue%2C%22%24initial_person_info%22%3A%7B%22r%22%3A%22%24direct%22%2C%22u%22%3A%22https%3A%2F%2Fcybershoke.net%2Fmatch%2F3387473%22%7D%7D; ph_phc_rrPtSJqWrZYBNTKe0xXhqX06PeeesY7hSuVvVtrshEk_posthog=%7B%22distinct_id%22%3A%2276561198294799864%22%2C%22%24sesid%22%3A%5B1764023851069%2C%22019ab800-b1f9-7247-8b54-6c4dadca6f78%22%2C1764023644665%5D%2C%22%24epp%22%3Atrue%2C%22%24initial_person_info%22%3A%7B%22r%22%3A%22%24direct%22%2C%22u%22%3A%22https%3A%2F%2Fcybershoke.net%2Fmatch%2F3601759%22%7D%7D; view=grid; ph_phc_axKew8iO1uHqh7VyQ70xd8gwbda3IhtRbV5TG7xDu0I_posthog=%7B%22distinct_id%22%3A%2276561198294799864%22%2C%22%24sesid%22%3A%5B1765230599167%2C%22019affeb-902a-7488-b7a3-928c5b8c3923%22%2C1765230219300%5D%2C%22%24epp%22%3Atrue%2C%22%24initial_person_info%22%3A%7B%22r%22%3A%22%24direct%22%2C%22u%22%3A%22https%3A%2F%2Fcybershoke.net%2Fmatch%2F3742184%22%7D%7D; translation_unix=1767362692; pings_list={%22pings%22:{%22germany%22:17%2C%22warsaw%22:32%2C%22finland%22:39%2C%22sweden%22:41%2C%22lithuania%22:36%2C%22gb%22:23%2C%22france%22:7%2C%22kazakhstan%22:0%2C%22astana%22:0%2C%22turkey%22:46%2C%22new-york%22:0%2C%22chicago%22:98%2C%22dallas%22:0%2C%22los-angeles%22:0%2C%22moscow%22:0%2C%22yakutsk%22:0%2C%22kiev%22:40%2C%22georgia%22:0%2C%22singapore%22:0%2C%22mumbai%22:0%2C%22sydney%22:0%2C%22sao-paulo%22:0}%2C%22ip%22:%2291.166.107.158%22}; last_page=/matches"
    # These values come directly from your screenshot image_01392b.png
    headers = {
        "authority": "api.cybershoke.net",
        "accept": "application/json, text/plain, */*",
        "accept-language": "fr,fr-FR;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "content-type": "application/json",
        "origin": "https://cybershoke.net",
        "referer": "https://cybershoke.net/",
        # Critical Security Headers to bypass Cloudflare
        "sec-ch-ua": '"Microsoft Edge";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
        "cookie": auth_cookie
    }

    # Payload EXACTLY as seen in image_013a23.png
    payload = {
        "type_lobby": 2, 
        "lobby_password": "kimkim"
    }

    print("--- Sending Request to Cybershoke ---")
    try:
        response = requests.post(url, json=payload, headers=headers)
        print(f"Status Code: {response.status_code}")

        # Check raw text if it fails
        if not response.text:
            print("❌ FAILED: Empty response.")
            return

        # Attempt to decode JSON
        try:
            data = response.json()
            print("Response JSON:")
            print(json.dumps(data, indent=4))
            
            if data.get("result") == "success":
                lobby_id = data["data"]["id_lobby"]
                print(f"\n✅ SUCCESS! Lobby Created: https://cybershoke.net/match/{lobby_id}")
            else:
                msg = data.get("message") or data.get("error_message") or "Unknown"
                print(f"\n❌ API REJECTED: {msg}")

        except json.JSONDecodeError:
            print("\n❌ JSON DECODE ERROR (Server sent HTML/Text instead of JSON)")
            print("This usually means Cloudflare blocked the bot or the cookie is invalid.")
            print("-" * 20)
            print(response.text[:500]) # Print first 500 chars to debug
            print("-" * 20)

    except Exception as e:
        print(f"❌ CONNECTION ERROR: {e}")

if __name__ == "__main__":
    test_api()

import requests
import json

def test_api():
    url = "https://api.cybershoke.net/api/v1/custom-matches/lobbys/create"
    
    # ⚠️ PASTE YOUR FULL COOKIE HERE
    auth_cookie = "_ym_uid=1767725166389867440; _ym_d=1767725166; categories={}; showFull=false; hideFullAmong=false; sCategories={}; competitionsLeague=high; gMapFilerv=[]; gCategoryFiler=[]; glocationFilerNewv=[]; gSortFiler=online; gPrimeFiler=both; gSortShopFiler2=down; gCompetitionsDataStats=month; gCompetitionsDataId=12; gCompetitionsDataClass=low; gCompetitionsDataHalfmonth=0; gProfileSkinchangerFilterQ=%E2%98%85%20Karambit; gProfileSkinchangerFilterCollection=1; hideFullServers=true; gSkipPremiumModal=0; gServersPrimeMode=all; gHideFilledServers=1; _gid=GA1.2.405774975.1767725166; _gat_gtag_UA_132864474_3=1; _gat_UA-151937518-1=1; _gat_gtag_UA_151937518_1=1; lang_g=en; translation_unix=1767623559; _ym_isad=2; changer_update=1762379362; multitoken=t9HMMczcbjXbYVbPl7uBafZg2O1767725193343l1yXzqZULVne8FrN1mXDlE39EtzDoUiRL1VJj3qY1G8F0pkA53K13; multitoken_created=1; _ga_5676S8YGZK=GS2.1.s1767725165$o1$g1$t1767725193$j32$l0$h0; _ga=GA1.1.1937088403.1767725166; last_page=/matches; _ga_VLRBXFQ6V5=GS2.1.s1767725165$o1$g1$t1767725197$j28$l0$h0"
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

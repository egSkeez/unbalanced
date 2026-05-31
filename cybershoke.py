# cybershoke.py
import requests
import json
import re
import time as _time
from database import sync_engine
from sqlalchemy import text as sa_text

# ── Cookie storage ────────────────────────────────────────────────────

# Hardcoded fallback (used only if nothing in DB yet)
_FALLBACK_COOKIES = {
    "Skeez": "lang_g=en; cookie_read=1; multitoken=7YV8DwPzGAGXlNBFM5ZIQGng991762105429993ouD8eCPqmRlZZ4WWXoCtz2vPmbLLw4kkBdGMaxach87Olkwr0Tx5W; multitoken_created=1",
    "Kim": "lang_g=en; multitoken=t9HMMczcbjXbYVbPl7uBafZg2O1767725193343l1yXzqZULVne8FrN1mXDlE39EtzDoUiRL1VJj3qY1G8F0pkA53K13; multitoken_created=1",
    "Magon": "lang_g=en; multitoken=QuhNXivQITPL4kGFOpAF6jBDKs1767728352453lZX5YWWITp0XRsvUpraIRGKMGHDQHdDu3BCZuyN05GgCWBf6WhpJz; multitoken_created=1",
}

_cookie_cache: dict = {"data": None, "ts": 0.0}
_COOKIE_CACHE_TTL = 120

def init_cybershoke_cookies_table():
    """Create DB table and seed with hardcoded fallbacks if empty."""
    with sync_engine.begin() as conn:
        conn.execute(sa_text("""
            CREATE TABLE IF NOT EXISTS cybershoke_cookies (
                admin_name TEXT PRIMARY KEY,
                cookie_string TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """))
        count = conn.execute(sa_text("SELECT COUNT(*) FROM cybershoke_cookies")).scalar()
        if count == 0:
            for name, cookie in _FALLBACK_COOKIES.items():
                conn.execute(sa_text(
                    "INSERT INTO cybershoke_cookies (admin_name, cookie_string) VALUES (:name, :cookie)"
                ), {"name": name, "cookie": cookie})

def get_all_cookies_db() -> dict[str, dict]:
    """Return {name: {cookie_string, updated_at}} from DB, cached."""
    now = _time.time()
    if _cookie_cache["data"] is not None and now - _cookie_cache["ts"] < _COOKIE_CACHE_TTL:
        return _cookie_cache["data"]
    try:
        with sync_engine.connect() as conn:
            rows = conn.execute(sa_text("SELECT admin_name, cookie_string, updated_at FROM cybershoke_cookies")).fetchall()
        result = {r[0]: {"cookie_string": r[1], "updated_at": r[2]} for r in rows}
    except Exception:
        result = {name: {"cookie_string": c, "updated_at": ""} for name, c in _FALLBACK_COOKIES.items()}
    _cookie_cache["data"] = result
    _cookie_cache["ts"] = now
    return result

def set_cookie_db(admin_name: str, cookie_string: str):
    """Upsert a cookie and invalidate cache."""
    cookie_string = _normalize_cookie(cookie_string)
    with sync_engine.begin() as conn:
        existing = conn.execute(sa_text("SELECT admin_name FROM cybershoke_cookies WHERE admin_name = :name"), {"name": admin_name}).fetchone()
        if existing:
            conn.execute(sa_text(
                "UPDATE cybershoke_cookies SET cookie_string = :cookie, updated_at = CURRENT_TIMESTAMP WHERE admin_name = :name"
            ), {"name": admin_name, "cookie": cookie_string})
        else:
            conn.execute(sa_text(
                "INSERT INTO cybershoke_cookies (admin_name, cookie_string) VALUES (:name, :cookie)"
            ), {"name": admin_name, "cookie": cookie_string})
    _cookie_cache["data"] = None
    _cookie_cache["ts"] = 0.0

def delete_cookie_db(admin_name: str):
    with sync_engine.begin() as conn:
        conn.execute(sa_text("DELETE FROM cybershoke_cookies WHERE admin_name = :name"), {"name": admin_name})
    _cookie_cache["data"] = None
    _cookie_cache["ts"] = 0.0

def _normalize_cookie(raw: str) -> str:
    """Accept a bare multitoken value or a full cookie string and return a proper cookie string."""
    raw = raw.strip()
    if "multitoken=" in raw:
        return raw
    # Bare token value — wrap it
    return f"lang_g=en; cookie_read=1; multitoken={raw}; multitoken_created=1"

def _get_cookie_for(admin_name: str) -> str:
    """Get cookie string for an admin, falling back through DB → hardcoded."""
    db = get_all_cookies_db()
    entry = db.get(admin_name) or db.get("Skeez")
    if entry:
        return _normalize_cookie(entry["cookie_string"])
    return _FALLBACK_COOKIES.get(admin_name, _FALLBACK_COOKIES["Skeez"])

def test_cookie(admin_name: str) -> dict:
    """Test if a cookie is valid by hitting a lightweight Cybershoke endpoint."""
    try:
        resp = requests.post(
            "https://api.cybershoke.net/api/v1/custom-matches/lobbys/info",
            headers=get_headers(admin_name),
            json={"id_lobby": 1},
            timeout=8,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("result") == "error" and "auth" in str(data.get("message", "")).lower():
                return {"valid": False, "reason": "Auth rejected — cookie expired"}
            return {"valid": True, "reason": f"OK (HTTP {resp.status_code})"}
        if resp.status_code in (401, 403):
            return {"valid": False, "reason": f"HTTP {resp.status_code} — cookie expired or invalid"}
        return {"valid": True, "reason": f"HTTP {resp.status_code} (may still work)"}
    except Exception as e:
        return {"valid": False, "reason": f"Connection error: {e}"}

def get_headers(admin_name):
    cookie = _get_cookie_for(admin_name)
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
        
        # Log response for debugging
        print(f"Cybershoke create response: {response.status_code} - {response.text}")

        if response.status_code == 200:
            data = response.json()
            if data.get("result") == "success":
                lobby_id = data.get("data", {}).get("id_lobby")
                
                if not lobby_id:
                    print(f"API returned success but no lobby_id for {admin_name}: {data}")
                    return None, None

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
    try:
        with sync_engine.begin() as conn:
            if match_id:
                conn.execute(sa_text("UPDATE active_draft_state SET current_lobby=:link, cybershoke_match_id=:mid WHERE id=1"),
                             {"link": link, "mid": str(match_id)})
            else:
                conn.execute(sa_text("UPDATE active_draft_state SET current_lobby=:link WHERE id=1"),
                             {"link": link})
    except Exception as e:
        print(f"Error saving lobby link: {e}")

def get_lobby_link():
    """Retrieves the active lobby link and match ID from the database."""
    link = None
    cs_id = None
    try:
        with sync_engine.connect() as conn:
            row = conn.execute(sa_text("SELECT current_lobby, cybershoke_match_id FROM active_draft_state WHERE id=1")).fetchone()
            if row:
                link = row[0]
                cs_id = row[1]
    except:
        pass
    return link, cs_id

def clear_lobby_link():
    """Removes the lobby link and match ID from the database."""
    try:
        with sync_engine.begin() as conn:
            conn.execute(sa_text("UPDATE active_draft_state SET current_lobby=NULL, cybershoke_match_id=NULL WHERE id=1"))
    except:
        pass

def get_lobby_match_result(lobby_id):
    """
    Fetches lobby info and determines the match result for tournament use.
    Returns a dict with:
        - score: "X - Y" string
        - map_name: str
        - winning_team: 2 or 3 (the team number with the higher score)
        - players: list of {name, team, kills, deaths, assists, headshots}
        - finished: bool (whether the match has concluded)
    Returns None on failure.
    """
    url = "https://api.cybershoke.net/api/v1/custom-matches/lobbys/info"
    try:
        payload = {"id_lobby": lobby_id}
        resp = requests.post(url, headers=get_headers("Skeez"), json=payload, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("result") != "success":
            return None

        lobby_data = data.get("data", {})

        # Score
        match_stats_base = lobby_data.get("match_stats", {}).get("base", {})
        score_t2 = int(match_stats_base.get("team_2", {}).get("score", 0))
        score_t3 = int(match_stats_base.get("team_3", {}).get("score", 0))

        # Lobby status
        status = lobby_data.get("status", "")
        finished = status in ("ended", "finished", "completed") or (score_t2 + score_t3) > 0

        # Determine winning team
        if score_t2 > score_t3:
            winning_team = 2
        elif score_t3 > score_t2:
            winning_team = 3
        else:
            winning_team = None  # draw or not finished

        # Map
        match_settings = lobby_data.get("match_settings", {})
        map_name = match_settings.get("map_name", "Unknown")

        # Players with team info
        players_dict = lobby_data.get("players", {})
        players = []
        for pid, p_data in players_dict.items():
            nick = p_data.get("name")
            # Team is stored in the slot or team field
            # Cybershoke uses "slot" where slots 0-4 = team_2, slots 5-9 = team_3
            slot = p_data.get("slot", -1)
            if isinstance(slot, str):
                slot = int(slot) if slot.isdigit() else -1
            team = 2 if slot < 5 else 3

            p_stats = p_data.get("match_stats", {}).get("live", {})
            if nick:
                players.append({
                    "name": nick,
                    "team": team,
                    "kills": int(p_stats.get("kills", 0)),
                    "deaths": int(p_stats.get("deaths", 0)),
                    "assists": int(p_stats.get("assists", 0)),
                    "headshots": int(p_stats.get("headshots", 0)),
                })

        return {
            "score": f"{score_t2} - {score_t3}",
            "score_t2": score_t2,
            "score_t3": score_t3,
            "map_name": map_name,
            "winning_team": winning_team,
            "players": players,
            "finished": finished,
        }
    except Exception as e:
        print(f"Lobby match result error: {e}")
        return None


def get_lobby_player_stats(lobby_id):
    """
    Fetches the Cybershoke lobby info and returns detailed stats.
    Returns:
       - stats_dict: {player_name: {kills, deaths, assists, headshots}}
       - score_str: "T X - Y CT" (estimated)
       - map_name: "de_mapname"
    """
    # Use the internal API that returns the lobby data including stats
    url = "https://api.cybershoke.net/api/v1/custom-matches/lobbys/info"
    
    try:
        payload = {"id_lobby": lobby_id}
        # Use Skeez headers (cookie required)
        resp = requests.post(url, headers=get_headers("Skeez"), json=payload, timeout=10)
        
        if resp.status_code != 200:
            print(f"Web stats API failed: {resp.status_code}")
            return None, "Unknown", "Unknown"
        
        data = resp.json()
        if data.get("result") != "success":
            print(f"Web stats API returned error: {data.get('code')}")
            return None, "Unknown", "Unknown"
            
        lobby_data = data.get("data", {})
        
        # Extract Match Info
        match_settings = lobby_data.get("match_settings", {})
        map_name = match_settings.get("map_name", "Unknown")
        
        # Extract Score if available
        # Structure seems to be match_stats -> base -> team_2/3 -> score
        # Note: Team numbering might vary. Usually team_2 and team_3 in the dump.
        match_stats_base = lobby_data.get("match_stats", {}).get("base", {})
        score_t = match_stats_base.get("team_2", {}).get("score", 0)
        score_ct = match_stats_base.get("team_3", {}).get("score", 0)
        score_str = f"{score_t} - {score_ct}" # We don't know who is T/CT easily without more info, just returning raw
        
        players_dict = lobby_data.get("players", {})
        
        stats = {}
        # print(f"DEBUG: Found {len(players_dict)} players")
        for pid, p_data in players_dict.items():
            nick = p_data.get("name")
            # Stats are nested in match_stats -> live -> kills
            try:
                p_stats = p_data.get("match_stats", {}).get("live", {})
                kills = p_stats.get("kills", 0)
                deaths = p_stats.get("deaths", 0)
                assists = p_stats.get("assists", 0)
                headshots = p_stats.get("headshots", 0)
                
                if nick:
                    stats[nick] = {
                        "kills": int(kills),
                        "deaths": int(deaths),
                        "assists": int(assists),
                        "headshots": int(headshots)
                    }
            except Exception as e:
                # print(f"DEBUG Error for {nick}: {e}")
                continue
                
        return stats, score_str, map_name
        
    except Exception as e:
        print(f"Web stats extraction error: {e}")
        return None, "Unknown", "Unknown"

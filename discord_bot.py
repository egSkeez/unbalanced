# discord_bot.py
import requests
import json

# REPLACE WITH YOUR WEBHOOK
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1458395495511883939/3Tbp0qzRn71lerSbXDwOWSaSbzd9UCqGLzcToqitlHkVRRkVCSJloD7uDdiBLDIelI_9"

MAP_IMAGE_URLS = {
    "de_mirage": "https://liquipedia.net/commons/images/f/f3/Csgo_mirage.jpg",
    "de_inferno": "https://liquipedia.net/commons/images/2/2b/De_inferno_cs2.jpg",
    "de_nuke": "https://liquipedia.net/commons/images/5/5e/Nuke_cs2.jpg",
    "de_overpass": "https://liquipedia.net/commons/images/0/0f/Csgo_overpass.jpg",
    "de_vertigo": "https://liquipedia.net/commons/images/5/59/De_vertigo_cs2.jpg",
    "de_ancient": "https://liquipedia.net/commons/images/d/d9/Ancient_cs2.jpg",
    "de_anubis": "https://liquipedia.net/commons/images/1/11/Anubis_cs2.jpg",
    "de_dust2": "https://liquipedia.net/commons/images/1/12/Dust2_cs2.jpg"
}

def send_full_match_info(name_a, t1_players, name_b, t2_players, maps, lobby_link):
    """
    Sends a highly visible, organized match summary to Discord.
    """
    if not DISCORD_WEBHOOK_URL: return
    
    # --- 1. THE MAIN HEADER EMBED ---
    header_embed = {
        "title": "⚔️ MATCH READY: PRO BALANCER DRAFT",
        "description": "The teams have been drafted and the veto is complete. Good luck!",
        "color": 15158332, # Red/Orange
        "fields": [
            {
                "name": f"🟦 {name_a}",
                "value": "```" + "\n".join([f"• {p}" for p in t1_players]) + "```",
                "inline": True
            },
            {
                "name": f"🟧 {name_b}",
                "value": "```" + "\n".join([f"• {p}" for p in t2_players]) + "```",
                "inline": True
            }
        ]
    }

    # --- 2. THE MAPS SECTION ---
    # We send map names as a list, and then individual images
    map_list = maps if isinstance(maps, list) else maps.split(",")
    map_text = " • ".join([f"**{m.strip()}**" for m in map_list])
    
    header_embed["fields"].append({
        "name": "🗺️ MAP POOL",
        "value": map_text,
        "inline": False
    })

    # --- 3. THE SERVER LINK (The Finale) ---
    server_text = "⚠️ Server link not generated yet."
    if lobby_link:
        server_text = f"🔑 Password: `kimkim`"

    header_embed["fields"].append({
        "name": "🚀 JOIN THE SERVER",
        "value": server_text,
        "inline": False
    })

    # Put the raw URL in message content so Discord auto-links it (embed fields don't auto-link)
    content = f"🔗 **SERVER LINK:** {lobby_link}\n🔑 Password: `kimkim`" if lobby_link else ""

    payload = {"content": content, "embeds": [header_embed]}
    
    # --- 4. MAP IMAGES (Appended as small thumbnails) ---
    for m_name in map_list:
        clean_name = m_name.strip()
        img_url = MAP_IMAGE_URLS.get(clean_name)
        if img_url:
            payload["embeds"].append({
                "title": f"📍 {clean_name}",
                "url": "https://cybershoke.net", # Makes the title a link
                "image": {"url": img_url},
                "color": 3447003
            })

    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload)
    except Exception as e:
        print(f"Discord Error: {e}")

# Keep legacy stubs to prevent crashes
# Keep legacy stubs to prevent crashes
def send_teams_to_discord(na, t1, nb, t2): pass

def send_lobby_to_discord(link, map_name=None):
    if not DISCORD_WEBHOOK_URL: return
    
    server_text = (
        f"🔗 **[3me fi 3inik]({link})**\n"
        f"⌨️ `connect {link.split('/')[-1]}`\n"
        f"🔑 Password: `kimkim`"
    )

    embed = {
        "title": "🚀 SERVER RE-BROADCAST",
        "description": f"The lobby link has been updated/resent.",
        "color": 3066993, # Green
        "fields": [
            {
                "name": "Server Info",
                "value": server_text,
                "inline": False
            }
        ]
    }

    if map_name:
         embed["fields"].append({
             "name": "Current Map",
             "value": f"**{map_name}**",
             "inline": True
         })

    payload = {"embeds": [embed]}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload)
    except Exception as e:
        print(f"Discord Error: {e}")

def send_maps_to_discord(maps): pass

# discord_bot.py
import requests

# ⚠️ PASTE YOUR DISCORD WEBHOOK URL HERE
WEBHOOK_URL = "https://discord.com/api/webhooks/1457771719795409099/xFgRiQifX2JAi245C7-GeJJlv9l9rJ6Tb18FAgWMkioTZWbosmtxWv0FP-YgUZGuB-HX"

def send_discord_message(content):
    if "YOUR_WEBHOOK_URL" in WEBHOOK_URL or not WEBHOOK_URL:
        return
    try:
        data = {"content": content}
        requests.post(WEBHOOK_URL, json=data)
    except Exception as e:
        print(f"Discord Error: {e}")

def send_teams_to_discord(t1_name, t1_list, t2_name, t2_list):
    t1_block = "\n".join([f"> 🔹 {p}" for p in t1_list])
    t2_block = "\n".join([f"> 🔸 {p}" for p in t2_list])
    
    msg = (
        f"**⚔️ MATCH READY: {t1_name} vs {t2_name}**\n\n"
        f"**🟦 {t1_name}**\n{t1_block}\n\n"
        f"**🟧 {t2_name}**\n{t2_block}\n\n"
        f"*GLHF! Waiting for Map Veto...*"
    )
    send_discord_message(msg)

def send_maps_to_discord(map_list):
    # Formats the map list
    map_block = "\n".join([f"{i+1}. {m}" for i, m in enumerate(map_list)])
    msg = (
        f"**🗺️ MAPS PICKED**\n"
        f"{map_block}\n\n"
        f"*Lobby creation starting...*"
    )
    send_discord_message(msg)

def send_lobby_to_discord(lobby_link, map_name, password="kimkim"):
    msg = (
        f"**🚀 LOBBY CREATED**\n"
        f"**Map:** `{map_name}`\n"
        f"**Password:** `{password}`\n"
        f"**Link:** {lobby_link}\n"
        f"---------------------------------"
    )
    send_discord_message(msg)

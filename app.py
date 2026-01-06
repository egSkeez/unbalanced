# app.py
import streamlit as st
import random
import time
import sqlite3
import pandas as pd
import uuid
import socket
import qrcode
import io
import json
from constants import SKEEZ_TITLES, TEAM_NAMES, MAP_POOL, MAP_LOGOS
from database import (init_db, get_player_stats, update_elo, set_draft_pins, submit_vote, 
                      get_vote_status, save_draft_state, load_draft_state, clear_draft_state, 
                      update_draft_map, init_veto_state, get_veto_state, update_veto_turn)
from logic import get_best_combinations, pick_captains, cycle_new_captain
from wheel import render_bench_wheel  # Ensure this is imported
from cybershoke import init_cybershoke_db, set_lobby_link, get_lobby_link, clear_lobby_link, create_cybershoke_lobby_api
from discord_bot import send_teams_to_discord, send_lobby_to_discord, send_maps_to_discord

# --- CONFIGURATION ---
QR_BASE_URL = "https://unbalanced-wac3gydqklzbeeuomp6adp.streamlit.app"
ROOMMATES = ["Chajra", "Ghoufa"]

# --- HELPER: GET LOCAL IP ---
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"

def generate_qr(url):
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue()

# ==========================================
# PAGE: MOBILE VOTING & VETO
# ==========================================
def render_mobile_vote_page(token):
    st.set_page_config(page_title="Captain Portal", layout="centered")
    
    st.markdown("""
    <style>
        .stButton button { width: 100%; font-weight: bold; border-radius: 8px; min-height: 50px; }
    </style>
    """, unsafe_allow_html=True)

    # 1. AUTH CHECK
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("SELECT captain_name, vote FROM current_draft_votes WHERE pin=?", (token,))
    row = c.fetchone()
    conn.close()

    if not row:
        st.error("❌ Invalid Token.")
        return

    cap_name, current_vote = row

    st.markdown(f"<h3 style='text-align:center;'>👑 {cap_name}</h3>", unsafe_allow_html=True)

    # 2. VOTE PHASE
    if current_vote == "Waiting":
        st.info("Draft Pending Approval")
        col1, col2 = st.columns(2)
        if col1.button("✅ APPROVE", use_container_width=True):
            submit_vote(token, "Approve")
            st.rerun()
        if col2.button("❌ REROLL", use_container_width=True):
            submit_vote(token, "Reroll")
            st.rerun()
        return

    # 3. CHECK VETO STATE
    rem, prot, turn_team = get_veto_state()
    
    if not rem: 
        st.success("✅ Veto Complete! Check Host Screen.")
        time.sleep(5)
        st.rerun()

    # Determine My Team
    saved = load_draft_state()
    if not saved: return
    t1_json, t2_json, n_a, n_b, _, _, _ = saved
    
    my_team_name = n_a if cap_name in t1_json else n_b
    opp_team_name = n_b if my_team_name == n_a else n_a

    # 4. VETO PHASE INTERFACE
    st.divider()
    if turn_team == my_team_name:
        st.markdown(f"<h4 style='color:#4da6ff; text-align:center;'>👉 YOUR TURN</h4>", unsafe_allow_html=True)
        
        is_protection_phase = (len(prot) < 2)
        action_text = "PICK" if is_protection_phase else "BAN"
        btn_color = "primary" if is_protection_phase else "secondary"
        
        st.write(f"**Action: {action_text}**")
        
        cols = st.columns(2)
        for i, m in enumerate(rem):
            with cols[i % 2]:
                st.image(MAP_LOGOS.get(m, ""), width=100) 
                if st.button(f"{action_text} {m}", key=f"mob_{m}", type=btn_color, use_container_width=True):
                    # EXECUTE ACTION
                    if is_protection_phase:
                        prot.append(m)
                    
                    rem.remove(m)
                    
                    if len(rem) == 1 and not is_protection_phase:
                        final_map = rem[0]
                        final_three = prot + [final_map]
                        update_draft_map(final_three)
                        init_veto_state([], "") 
                    else:
                        update_veto_turn(rem, prot, opp_team_name)
                    
                    st.rerun()
    else:
        st.warning(f"⏳ Opponent is thinking...")
        st.caption("Waiting for their move...")
        time.sleep(2)
        st.rerun()

# ==========================================
# FRAGMENT: HOST VETO DISPLAY
# ==========================================
@st.fragment(run_every=2)
def render_veto_fragment(name_a, name_b, cap1_name, cap2_name):
    rem, prot, turn_team = get_veto_state()
    
    if rem is None:
        st.info("Waiting for coin flip to start Veto...")
        if st.button("🪙 Flip Coin to Start Veto", use_container_width=True):
            winner = random.choice([name_a, name_b])
            init_veto_state(MAP_POOL.copy(), winner)
            disp = cap1_name if winner == name_a else cap2_name
            st.toast(f"Winner: {disp}")
            st.rerun()
        return

    if not rem:
        st.session_state.veto_complete_trigger = True
        st.rerun()
        return

    turn_captain = cap1_name if turn_team == name_a else cap2_name
    
    phase = "PICKING (PROTECT)" if len(prot) < 2 else "BANNING"
    st.markdown(f"""
        <div class="turn-indicator">
            {phase} <br>
            Current Turn: <span style="color: #4da6ff;">{turn_captain}</span>
        </div>
    """, unsafe_allow_html=True)
    
    if prot:
        st.write(f"**Protected:** {', '.join(prot)}")

    cols = st.columns(7)
    for i, m in enumerate(MAP_POOL):
        with cols[i]:
            is_avail = m in rem
            is_prot = m in prot
            opacity = "1.0" if is_avail or is_prot else "0.2"
            border = "2px solid #00E500" if is_prot else "1px solid #333"
            
            st.markdown(f"""
            <div style="opacity: {opacity}; border: {border}; padding: 5px; border-radius: 5px; text-align: center;">
                <img src="{MAP_LOGOS.get(m, '')}" style="width: 100%; border-radius: 5px;">
                <div style="font-size: 0.8em; font-weight: bold; margin-top: 5px; color: white;">{m}</div>
            </div>
            """, unsafe_allow_html=True)

# ==========================================
# FRAGMENT: VOTING & QR
# ==========================================
@st.fragment(run_every=2)
def render_voting_fragment(t1, t2, name_a, name_b):
    st.subheader("📲 Captains: Scan to Vote")
    v_df = get_vote_status()
    
    if not v_df.empty:
        qr_c1, qr_c2 = st.columns(2)
        row_t1 = v_df[v_df['captain_name'].isin(t1)]
        row_t2 = v_df[v_df['captain_name'].isin(t2)]
        
        with qr_c1:
            if not row_t1.empty:
                r = row_t1.iloc[0]
                c_name, c_token, c_vote = r['captain_name'], r['pin'], r['vote']
                st.markdown(f"**{c_name}**")
                if c_vote == "Waiting":
                    img = generate_qr(f"{QR_BASE_URL}/?vote_token={c_token}")
                    st.image(img, width=200, caption="Scan to Vote")
                else:
                    st.success("🗳️ VOTE RECEIVED")

        with qr_c2:
            if not row_t2.empty:
                r = row_t2.iloc[0]
                c_name, c_token, c_vote = r['captain_name'], r['pin'], r['vote']
                st.markdown(f"**{c_name}**")
                if c_vote == "Waiting":
                    img = generate_qr(f"{QR_BASE_URL}/?vote_token={c_token}")
                    st.image(img, width=200, caption="Scan to Vote")
                else:
                    st.success("🗳️ VOTE RECEIVED")

        votes = v_df['vote'].tolist()
        if "Reroll" in votes:
            st.warning("🔄 Reroll requested...")
            conn = sqlite3.connect('cs2_history.db'); conn.execute("DELETE FROM current_draft_votes"); conn.commit(); conn.close()
            if 'draft_pins' in st.session_state: del st.session_state.draft_pins
            st.session_state.revealed = False
            st.session_state.trigger_reroll = True
            st.rerun()

        if "Waiting" not in votes and len(votes) == 2 and all(v == "Approve" for v in votes):
             st.success("🎉 Teams Approved!")
             send_teams_to_discord(name_a, t1, name_b, t2)
             st.session_state.vote_completed = True
             st.rerun()

# ==========================================
# MAIN APP LOGIC
# ==========================================

if "vote_token" in st.query_params:
    render_mobile_vote_page(st.query_params["vote_token"])
    st.stop() 

init_db()
init_cybershoke_db()

st.set_page_config(page_title="CS2 Pro Balancer", layout="centered")
player_df = get_player_stats()

if "admin_user" in st.query_params:
    st.session_state.admin_authenticated = True
    st.session_state.admin_user = st.query_params["admin_user"]
if 'admin_authenticated' not in st.session_state: st.session_state.admin_authenticated = False
if 'admin_user' not in st.session_state: st.session_state.admin_user = None

if 'teams_locked' not in st.session_state: st.session_state.teams_locked = False
if 'revealed' not in st.session_state: st.session_state.revealed = False
if 'global_map_pick' not in st.session_state: st.session_state.global_map_pick = None
if 'maps_sent_to_discord' not in st.session_state: st.session_state.maps_sent_to_discord = False

if st.session_state.get("trigger_reroll", False):
    st.session_state.trigger_reroll = False
    current_players = [p for p in player_df['name'] if p in st.session_state.get("current_selection", [])]
    if not current_players:
         t1, t2, _, _, _ = st.session_state.final_teams
         current_players = t1 + t2
    
    score_map = dict(zip(player_df['name'], player_df['overall']))
    sorted_p = sorted(current_players, key=lambda x: score_map.get(x, 0), reverse=True)
    top_2 = [sorted_p[0], sorted_p[1]]
    
    all_combos = get_best_combinations(current_players, force_split=top_2, force_together=ROOMMATES)
    ridx = random.randint(1, min(50, len(all_combos) - 1))
    nt1, nt2, na1, na2, ngap = all_combos[ridx]
    
    save_draft_state(nt1, nt2, st.session_state.assigned_names[0], st.session_state.assigned_names[1], na1, na2)
    st.session_state.final_teams = all_combos[ridx]
    st.session_state.revealed = False
    st.session_state.maps_sent_to_discord = False
    st.rerun()

if st.session_state.get("veto_complete_trigger", False):
    st.session_state.veto_complete_trigger = False
    saved = load_draft_state()
    if saved:
         if saved[6]: 
             st.session_state.global_map_pick = saved[6]
    st.rerun()

st.markdown("""
<style>
    [data-testid="stVerticalBlock"] h3 { min-height: 110px; display: flex; align-items: center; text-align: center; justify-content: center; font-size: 1.5rem !important; }
    [data-testid="stImage"] img { max-height: 120px; width: auto; margin: 0 auto; }
    .team-header-blue { color: #4da6ff; border-bottom: 2px solid #4da6ff; padding-bottom: 5px; text-align: center; }
    .team-header-orange { color: #ff9f43; border-bottom: 2px solid #ff9f43; padding-bottom: 5px; text-align: center; }
    .cs-box { border: 2px solid #00E500; background-color: #0e1117; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px; }
    .cs-title { color: #00E500; font-weight: bold; font-size: 1.2em; margin-bottom: 10px; }
    .map-box-container { text-align: center; border: 1px solid #333; padding: 10px; border-radius: 8px; background-color: #1E1E1E; }
    .map-order { color: #FFD700; font-weight: bold; font-size: 0.9em; margin-bottom: 5px; }
    .map-name { color: white; font-weight: bold; font-size: 1.1em; }
    .turn-indicator {
        background-color: #262730; border: 1px solid #444; color: #FFD700;
        padding: 10px; border-radius: 8px; text-align: center; font-size: 1.2em; font-weight: bold; margin-bottom: 15px;
    }
    .admin-badge { color: #00E500; font-size: 0.8em; font-weight: bold; margin-left: 10px; }
</style>
""", unsafe_allow_html=True)

if 'teams_locked' not in st.session_state or not st.session_state.teams_locked:
    saved_draft = load_draft_state()
    if saved_draft:
        t1, t2, n_a, n_b, a1, a2, db_map = saved_draft
        st.session_state.final_teams = (t1, t2, a1, a2, 0)
        st.session_state.assigned_names = (n_a, n_b)
        st.session_state.teams_locked = True
        st.session_state.revealed = True
        if db_map:
            st.session_state.global_map_pick = db_map

def render_comparision_row(label, val1, val2):
    row_c1, row_c2, row_c3 = st.columns([1, 4, 1])
    with row_c1: st.markdown(f"<h3 style='text-align: right; color: #4da6ff; margin:0;'>{int(val1)}</h3>", unsafe_allow_html=True)
    with row_c2:
        st.markdown(f"<div style='text-align: center; font-weight: bold; margin-bottom: 5px;'>{label}</div>", unsafe_allow_html=True)
        total = val1 + val2
        p1_pct = (val1 / total) * 100 if total > 0 else 50
        p2_pct = (val2 / total) * 100 if total > 0 else 50
        st.markdown(f"""
            <div style="display: flex; width: 100%; height: 12px; border-radius: 6px; overflow: hidden;">
                <div style="width: {p1_pct}%; background-color: #4da6ff;"></div>
                <div style="width: {p2_pct}%; background-color: #ff9f43;"></div>
            </div>""", unsafe_allow_html=True)
    with row_c3: st.markdown(f"<h3 style='text-align: left; color: #ff9f43; margin:0;'>{int(val2)}</h3>", unsafe_allow_html=True)

tabs = st.tabs(["🎮 Mixer & Veto", "🎡 Bench Wheel", "📜 History", "⚙️ Admin"])

with tabs[0]:
    title_text = "🎮 CS2 Draft & Veto"
    if st.session_state.admin_authenticated:
        title_text += f" <span class='admin-badge'>HOST: {st.session_state.admin_user}</span>"
    st.markdown(f"## {title_text}", unsafe_allow_html=True)
    
    if not st.session_state.teams_locked:
        if st.session_state.admin_authenticated:
            current_sel = st.session_state.get("current_selection", [])
            st.write(f"**Players Selected:** `{len(current_sel)}/10`")
            selected = st.multiselect("Select 10 Players:", options=player_df['name'].tolist(), key="current_selection", label_visibility="collapsed")
            if len(selected) == 10:
                score_map = dict(zip(player_df['name'], player_df['overall']))
                sorted_sel = sorted(selected, key=lambda x: score_map.get(x, 0), reverse=True)
                top_2 = [sorted_sel[0], sorted_sel[1]]
                col1, col2 = st.columns(2)
                if col1.button("⚖️ Perfect Balance", use_container_width=True):
                    all_combos = get_best_combinations(selected, force_split=top_2, force_together=ROOMMATES)
                    t1, t2, a1, a2, gap = all_combos[0]
                    n_a, n_b = random.sample(TEAM_NAMES, 2)
                    save_draft_state(t1, t2, n_a, n_b, a1, a2)
                    st.session_state.final_teams = all_combos[0]
                    st.session_state.assigned_names = (n_a, n_b)
                    st.session_state.teams_locked = True
                    st.session_state.revealed = False
                    st.session_state.global_map_pick = None
                    if 'draft_pins' in st.session_state: del st.session_state.draft_pins
                    st.rerun()
                if col2.button("🎲 Chaos Mode", use_container_width=True):
                    all_combos = get_best_combinations(selected, force_split=top_2, force_together=ROOMMATES)
                    ridx = random.randint(1, min(50, len(all_combos) - 1))
                    t1, t2, a1, a2, gap = all_combos[ridx]
                    n_a, n_b = random.sample(TEAM_NAMES, 2)
                    save_draft_state(t1, t2, n_a, n_b, a1, a2)
                    st.session_state.final_teams = all_combos[ridx]
                    st.session_state.assigned_names = (n_a, n_b)
                    st.session_state.teams_locked = True
                    st.session_state.revealed = False
                    st.session_state.global_map_pick = None
                    if 'draft_pins' in st.session_state: del st.session_state.draft_pins
                    st.rerun()
        else:
            st.info("👋 Waiting for an Admin (Skeez, Ghoufa, or Kim) to start the session...")
            time.sleep(2); st.rerun()

    else:
        t1_unsorted, t2_unsorted, avg1, avg2, _ = st.session_state.final_teams 
        name_a, name_b = st.session_state.assigned_names
        
        score_map = dict(zip(player_df['name'], player_df['overall']))
        t1 = sorted(t1_unsorted, key=lambda x: score_map.get(x, 0), reverse=True)
        t2 = sorted(t2_unsorted, key=lambda x: score_map.get(x, 0), reverse=True)
        
        if st.session_state.admin_authenticated:
            with st.expander("🛠️ Draft Options (Reroll / Reset)"):
                rc1, rc2, rc3 = st.columns(3)
                if rc1.button("⚖️ Reroll (Balanced)", use_container_width=True): st.session_state.trigger_reroll = True; st.rerun()
                if rc2.button("🎲 Reroll (Chaos)", use_container_width=True): st.session_state.trigger_reroll = True; st.rerun()
                if rc3.button("🔄 Full Reset", type="primary", use_container_width=True):
                    clear_draft_state(); clear_lobby_link(); st.session_state.clear(); st.session_state.maps_sent_to_discord = False; st.rerun()

        active_lobby = get_lobby_link()
        if st.session_state.global_map_pick and not active_lobby:
             with st.spinner("🤖 Automatically creating Cybershoke lobby..."):
                 auto_link = create_cybershoke_lobby_api()
                 if auto_link:
                     set_lobby_link(auto_link)
                     map_name = st.session_state.global_map_pick.split(",")[0]
                     send_lobby_to_discord(auto_link, map_name)
                     st.rerun()
                 else:
                     st.error("Auto-creation failed. Use Admin tab to create manually.")

        if active_lobby and st.session_state.global_map_pick:
            st.markdown(f"""<div class="cs-box"><div class="cs-title">🚀 CYBERSHOKE LOBBY READY</div><p style="color:white; font-family: monospace; font-size: 1.1em;">{active_lobby} <br> <span style="color: #FFD700; font-weight: bold;">Password: kimkim</span></p><a href="{active_lobby}" target="_blank"><button style="background-color: #00E500; color: black; border: none; padding: 10px 20px; font-weight: bold; border-radius: 5px; cursor: pointer; width: 100%;">▶️ JOIN SERVER</button></a></div>""", unsafe_allow_html=True)
            if st.session_state.admin_authenticated and st.button("🗑️ Clear Link (Admin)"): clear_lobby_link(); st.rerun()

        sum1, sum2 = round(avg1 * 5, 2), round(avg2 * 5, 2)
        gap = round(abs(sum1 - sum2), 2)
        
        st.divider()
        c1, c2 = st.columns(2)
        with c1: 
            st.markdown(f"<h3 class='team-header-blue'>🟦 {name_a}</h3>", unsafe_allow_html=True)
            st.markdown(f"<div style='text-align: center; font-weight: bold;'>Total Power: {sum1}</div>", unsafe_allow_html=True)
            p1_holders = [st.empty() for _ in range(5)]
            if st.session_state.admin_authenticated and st.session_state.revealed and st.session_state.teams_locked:
                if st.button("♻️ Cycle Captain", key="cycle_a"):
                     v_df = get_vote_status()
                     if not v_df.empty:
                         caps = v_df['captain_name'].tolist()
                         old_cap = next((c for c in caps if c in t1), None)
                         if old_cap:
                             new_cap = cycle_new_captain(t1, old_cap)
                             new_token = str(uuid.uuid4())
                             other_cap = next((c for c in caps if c not in t1), None)
                             other_row = v_df[v_df['captain_name'] == other_cap].iloc[0]
                             set_draft_pins(new_cap, new_token, other_cap, other_row['pin'])
                             st.toast(f"Captain changed to {new_cap}"); st.rerun()
        with c2: 
            st.markdown(f"<h3 class='team-header-orange'>🟧 {name_b}</h3>", unsafe_allow_html=True)
            st.markdown(f"<div style='text-align: center; font-weight: bold;'>Total Power: {sum2}</div>", unsafe_allow_html=True)
            p2_holders = [st.empty() for _ in range(5)]
            if st.session_state.admin_authenticated and st.session_state.revealed and st.session_state.teams_locked:
                if st.button("♻️ Cycle Captain", key="cycle_b"):
                     v_df = get_vote_status()
                     if not v_df.empty:
                         caps = v_df['captain_name'].tolist()
                         old_cap = next((c for c in caps if c in t2), None)
                         if old_cap:
                             new_cap = cycle_new_captain(t2, old_cap)
                             new_token = str(uuid.uuid4())
                             other_cap = next((c for c in caps if c not in t2), None)
                             other_row = v_df[v_df['captain_name'] == other_cap].iloc[0]
                             set_draft_pins(other_cap, other_row['pin'], new_cap, new_token)
                             st.toast(f"Captain changed to {new_cap}"); st.rerun()
        
        if st.session_state.global_map_pick:
             st.divider()
             st.markdown("<h4 style='text-align: center; color: #FFD700;'>🗺️ MAP QUEUE</h4>", unsafe_allow_html=True)
             picked_maps = st.session_state.global_map_pick.split(",")
             if picked_maps and picked_maps[0] != '':
                 if not st.session_state.maps_sent_to_discord:
                     send_maps_to_discord(picked_maps); st.session_state.maps_sent_to_discord = True
                 m_cols = st.columns(len(picked_maps))
                 for i, m_name in enumerate(picked_maps):
                     with m_cols[i]:
                         st.markdown(f"""<div class="map-box-container"><div class="map-order">MATCH #{i+1}</div><div class="map-name">{m_name}</div></div>""", unsafe_allow_html=True)
                         st.image(MAP_LOGOS[m_name], use_container_width=True)

        current_votes = get_vote_status()
        cap1_name, cap2_name = None, None
        if not current_votes.empty:
            cap1_name = current_votes.iloc[0]['captain_name']
            cap2_name = current_votes.iloc[1]['captain_name']

        def format_player(name, idx, is_skeez_team):
            if name == cap1_name or name == cap2_name: return f"👑 {name}"
            return name

        if not st.session_state.revealed:
            if 'draft_pins' not in st.session_state:
                c1_pick, c2_pick = pick_captains(t1, t2)
                t1_token, t2_token = str(uuid.uuid4()), str(uuid.uuid4())
                st.session_state.draft_pins = {c1_pick: t1_token, c2_pick: t2_token}
                set_draft_pins(c1_pick, t1_token, c2_pick, t2_token)
                cap1_name, cap2_name = c1_pick, c2_pick

            for i in range(5):
                time.sleep(0.4); p1_holders[i].info(format_player(t1[i], i, 1))
                time.sleep(0.4); p2_holders[i].warning(format_player(t2[i], i, 2))
            st.session_state.revealed = True; st.rerun()
        else:
            for i in range(5):
                p1_holders[i].info(format_player(t1[i], i, 1))
                p2_holders[i].warning(format_player(t2[i], i, 2))

        st.divider()
        t1_stats = player_df[player_df['name'].isin(t1)][['aim', 'util', 'team_play']].sum()
        t2_stats = player_df[player_df['name'].isin(t2)][['aim', 'util', 'team_play']].sum()
        render_comparision_row("🎯 AIM", t1_stats['aim'], t2_stats['aim']); st.write("") 
        render_comparision_row("🧠 UTILITY", t1_stats['util'], t2_stats['util']); st.write("") 
        render_comparision_row("🤝 TEAM PLAY", t1_stats['team_play'], t2_stats['team_play'])
        st.markdown(f"<br><div style='text-align: center; color: #77dd77; font-size: 0.9em;'>Total Metric Gap: {gap}</div>", unsafe_allow_html=True)
        st.divider()

        if st.session_state.revealed and not st.session_state.get("vote_completed", False):
            render_voting_fragment(t1, t2, name_a, name_b)

        if st.session_state.get("vote_completed", False) and not st.session_state.global_map_pick:
            render_veto_fragment(name_a, name_b, cap1_name, cap2_name)

        if st.session_state.global_map_pick and st.session_state.admin_authenticated:
             st.divider()
             rc1, rc2 = st.columns(2)
             if rc1.button(f"🏆 {name_a} Won Match", use_container_width=True):
                 maps = st.session_state.global_map_pick.split(",")
                 update_elo(t1, t2, name_a, name_b, 1, maps[0])
                 rem = maps[1:]
                 if rem: update_draft_map(rem); st.session_state.global_map_pick = ",".join(rem); clear_lobby_link()
                 else: update_draft_map(""); st.session_state.global_map_pick = ""; clear_lobby_link()
                 st.rerun()
             if rc2.button(f"🏆 {name_b} Won Match", use_container_width=True):
                 maps = st.session_state.global_map_pick.split(",")
                 update_elo(t1, t2, name_a, name_b, 2, maps[0])
                 rem = maps[1:]
                 if rem: update_draft_map(rem); st.session_state.global_map_pick = ",".join(rem); clear_lobby_link()
                 else: update_draft_map(""); st.session_state.global_map_pick = ""; clear_lobby_link()
                 st.rerun()

with tabs[1]:
    # Determine the pool of players for the wheel
    if st.session_state.teams_locked and st.session_state.final_teams:
        # If draft is locked, use the 10 players from the draft
        t1, t2, _, _, _ = st.session_state.final_teams
        wheel_pool = t1 + t2
    elif "current_selection" in st.session_state and st.session_state.current_selection:
        # If selecting players, use the currently selected ones
        wheel_pool = st.session_state.current_selection
    else:
        # Fallback to everyone
        wheel_pool = player_df['name'].tolist()

    render_bench_wheel(wheel_pool)

with tabs[2]:
    st.title("📜 History")
    conn = sqlite3.connect('cs2_history.db')
    hist_df = pd.read_sql_query("SELECT * FROM matches ORDER BY date DESC", conn); conn.close()
    if hist_df.empty: st.info("No matches played yet.")
    else:
        for _, row in hist_df.iterrows():
            winner = row['team1_name'] if row['winner_idx'] == 1 else row['team2_name']
            with st.expander(f"🎮 {row['date'].split()[0]} | {winner} on {row['map']}"):
                c_a, c_b = st.columns(2)
                with c_a: st.write(f"**🟦 {row['team1_name']}**"); st.write(row['team1_players'])
                with c_b: st.write(f"**🟧 {row['team2_name']}**"); st.write(row['team2_players'])

with tabs[3]:
    if not st.session_state.admin_authenticated:
        st.title("🔐 Admin Login")
        with st.form("admin_login_form"):
            admin_user = st.selectbox("Who are you?", ["Skeez", "Ghoufa", "Kim"])
            pwd_input = st.text_input("Enter Admin Password", type="password")
            if st.form_submit_button("Login"):
                if (admin_user=="Skeez" and pwd_input=="2567") or (admin_user=="Ghoufa" and pwd_input=="ghoufa123") or (admin_user=="Kim" and pwd_input=="kim123"):
                    st.session_state.admin_authenticated = True; st.session_state.admin_user = admin_user; st.query_params["admin_user"] = admin_user; st.rerun()
                else: st.error("Incorrect Password")
    else:
        st.title(f"⚙️ Management ({st.session_state.admin_user})")
        if st.button("Logout"): st.session_state.admin_authenticated = False; st.query_params.clear(); st.rerun()

        st.subheader("📊 Player Roster")
        st.dataframe(get_player_stats()[['name', 'elo', 'aim', 'util', 'team_play', 'W', 'D', 'overall']], use_container_width=True, hide_index=True)
        
        st.subheader("🚀 Session & Lobby")
        curr_link = get_lobby_link()
        admin_link_in = st.text_input("Set Server Link", value=curr_link if curr_link else "")
        if st.button("✅ Broadcast Link"): set_lobby_link(admin_link_in); st.success("Done!")
        
        st.divider(); st.subheader("⚠️ Danger Zone")
        if st.button("🛑 RESET WHOLE SESSION", type="primary"): clear_draft_state(); clear_lobby_link(); st.session_state.clear(); st.session_state.maps_sent_to_discord = False; st.rerun()

        st.divider(); st.subheader("📝 Player Editor")
        all_p = get_player_stats()
        target_name = st.selectbox("Select Player", [""] + all_p['name'].tolist())
        if target_name:
            p_row = all_p[all_p['name'] == target_name].iloc[0]
            with st.form("edit_form"):
                new_aim = st.slider("Aim", 1.0, 10.0, float(p_row['aim']))
                new_util = st.slider("Util", 1.0, 10.0, float(p_row['util']))
                new_team = st.slider("Team Play", 1.0, 10.0, float(p_row['team_play']))
                if st.form_submit_button("💾 Save"):
                    conn = sqlite3.connect('cs2_history.db'); conn.execute("UPDATE players SET aim=?, util=?, team_play=? WHERE name=?", (new_aim, new_util, new_team, target_name)); conn.commit(); conn.close(); st.success("Saved!"); time.sleep(1); st.rerun()
            if st.button("🗑️ Delete Player"): conn = sqlite3.connect('cs2_history.db'); conn.execute("DELETE FROM players WHERE name=?", (target_name,)); conn.commit(); conn.close(); st.rerun()
        
        with st.form("add_form"):
            st.write("Add New Player"); n_name = st.text_input("Name"); n_a = st.slider("Aim",1.0,10.0,5.0); n_u = st.slider("Util",1.0,10.0,5.0); n_t = st.slider("Team",1.0,10.0,5.0)
            if st.form_submit_button("➕ Add"): conn = sqlite3.connect('cs2_history.db'); conn.execute("INSERT OR IGNORE INTO players (name, elo, aim, util, team_play, secret_word) VALUES (?, 1200, ?, ?, ?, ?)", (n_name, n_a, n_u, n_t, "cs2pro")); conn.commit(); conn.close(); st.rerun()

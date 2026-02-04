# views/mixer.py
import streamlit as st
import random
import time
import uuid
import sqlite3
import os
import base64
from constants import TEAM_NAMES, MAP_POOL, MAP_LOGOS, SKEEZ_TITLES
from database import (save_draft_state, load_draft_state, clear_draft_state, 
                      update_draft_map, update_elo, get_vote_status, set_draft_pins,
                      init_veto_state, get_veto_state, get_roommates)
from logic import get_best_combinations, pick_captains, cycle_new_captain
from cybershoke import create_cybershoke_lobby_api, set_lobby_link, get_lobby_link, clear_lobby_link
from discord_bot import send_full_match_info # <--- Manual Broadcast Function
from utils import generate_qr, get_local_ip

# ROOMMATES config is now dynamic via get_roommates()
QR_BASE_URL = "https://unbalanced-wac3gydqklzbeeuomp6adp.streamlit.app/"
SOUNDS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "sounds")

def play_sound(sound_name):
    """Play a sound from the assets/sounds directory."""
    sound_file = os.path.join(SOUNDS_DIR, f"{sound_name}.mp3")
    if os.path.exists(sound_file):
        try:
            # Using data URI to force reload/play can be more reliable for quick cues
            with open(sound_file, "rb") as f:
                data = f.read()
                b64 = base64.b64encode(data).decode()
                md = f"""
                    <audio autoplay class="stAudio">
                    <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
                    </audio>
                    """
                st.markdown(md, unsafe_allow_html=True)
        except Exception as e:
            st.warning(f"Audio error: {e}")
    else:
        # st.warning(f"Sound file not found: {sound_file}") # Suppress for now
        pass

        # st.warning(f"Sound file not found: {sound_file}") # Suppress for now
        pass

def render_coin_flip(cap1, cap2, winner_idx):
    # winner_idx: 0 for cap1, 1 for cap2
    # If winner is cap1 (Heads), end rotation is 0 (or multiple of 360)
    # If winner is cap2 (Tails), end rotation is 180 (or 180 + 360)
    
    rotations = 5 # 5 full spins
    base_deg = rotations * 360
    end_deg = base_deg if winner_idx == 0 else base_deg + 180
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ background: transparent; display: flex; justify-content: center; align-items: center; height: 300px; margin: 0; overflow: hidden; }}
        .coin-container {{ perspective: 1000px; }}
        .coin {{
            width: 200px; height: 200px; position: relative; transform-style: preserve-3d;
            animation: flip 3s cubic-bezier(0.5, 0, 0.5, 1) forwards;
        }}
        .side {{
            position: absolute; width: 100%; height: 100%; border-radius: 50%;
            display: flex; justify-content: center; align-items: center;
            font-family: 'Arial', sans-serif; font-weight: bold; font-size: 24px; color: white;
            text-align: center; border: 4px solid #FFD700;
            backface-visibility: hidden; box-shadow: 0 0 20px rgba(0,0,0,0.5);
        }}
        .heads {{ background: linear-gradient(135deg, #4da6ff, #0056b3); transform: rotateX(0deg); }}
        .tails {{ background: linear-gradient(135deg, #ff9f43, #d35400); transform: rotateX(180deg); }}
        
        @keyframes flip {{
            from {{ transform: rotateX(0); }}
            to {{ transform: rotateX({end_deg}deg); }}
        }}
    </style>
    </head>
    <body>
        <div class="coin-container">
            <div class="coin">
                <div class="side heads">{cap1}</div>
                <div class="side tails">{cap2}</div>
            </div>
        </div>
    </body>
    </html>
    """
    import streamlit.components.v1 as components
    components.html(html, height=320)

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

@st.fragment(run_every=2)
def render_veto_fragment(name_a, name_b, cap1_name, cap2_name):
    rem, prot, turn_team = get_veto_state()
    if rem is None:
        # Automate Coin Flip
        winner = random.choice([name_a, name_b])
        winner_idx = 0 if winner == name_a else 1
        
        render_coin_flip(cap1_name, cap2_name, winner_idx)
        
        with st.spinner("🪙 Flipping coin..."):
            time.sleep(3.5) # Wait for animation
            print(f"DEBUG: Initializing veto state. Winner: {winner}")
            init_veto_state(MAP_POOL.copy(), winner)
            disp = cap1_name if winner == name_a else cap2_name
            st.toast(f"🪙 Coin Flip Winner: {disp}")
            st.rerun()
        return

    if not rem:
        st.session_state.veto_complete_trigger = True
        st.rerun()
        return

    turn_captain = cap1_name if turn_team == name_a else cap2_name
    phase = "PICKING (PROTECT)" if len(prot) < 2 else "BANNING"
    st.markdown(f"""<div class="turn-indicator">{phase} <br>Current Turn: <span style="color: #4da6ff;">{turn_captain}</span></div>""", unsafe_allow_html=True)
    if prot: st.write(f"**Protected:** {', '.join(prot)}")

    # --- AUDIO LOGIC ---
    if 'last_rem_len' not in st.session_state:
        st.session_state.last_rem_len = len(rem)
    
    # Detect Ban
    if len(rem) < st.session_state.last_rem_len:
        if len(rem) == 1:
            play_sound("fanfare")
        else:
            play_sound("ban")
        st.session_state.last_rem_len = len(rem)

    cols = st.columns(7)
    for i, m in enumerate(MAP_POOL):
        with cols[i]:
            is_avail = m in rem
            is_prot = m in prot
            
            if is_avail or is_prot:
                opacity = "1.0"
                border = "2px solid #00E500" if is_prot else "1px solid #333"
                st.markdown(f"""<div style="opacity: {opacity}; border: {border}; padding: 5px; border-radius: 5px; text-align: center;"><img src="{MAP_LOGOS.get(m, '')}" style="width: 100%; border-radius: 5px;"><div style="font-size: 0.8em; font-weight: bold; margin-top: 5px; color: white;">{m}</div></div>""", unsafe_allow_html=True)
            else:
                # BANNED VISUAL
                st.markdown(f"""
                <div style="position: relative; opacity: 0.4; border: 1px solid #555; padding: 5px; border-radius: 5px; text-align: center; filter: grayscale(100%);">
                    <img src="{MAP_LOGOS.get(m, '')}" style="width: 100%; border-radius: 5px;">
                    <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%) rotate(-20deg); 
                                color: #ff4444; font-size: 1.5em; font-weight: 900; 
                                border: 3px solid #ff4444; padding: 5px 10px; border-radius: 8px;
                                text-shadow: 2px 2px 0px #000;">
                        BANNED
                    </div>
                    <div style="font-size: 0.8em; font-weight: bold; margin-top: 5px; color: #aaa;">{m}</div>
                </div>""", unsafe_allow_html=True)

@st.fragment(run_every=1)
def render_voting_fragment(t1, t2, name_a, name_b):
    st.subheader("📲 Captains: Scan to Vote")
    
    if "show_qr_codes" not in st.session_state: 
        st.session_state.show_qr_codes = False

    if st.session_state.get("admin_authenticated"):
        if st.checkbox("Show QR Codes for Captains", value=st.session_state.show_qr_codes, key="chk_show_qr"):
            st.session_state.show_qr_codes = True
        else:
            st.session_state.show_qr_codes = False
    v_df = get_vote_status()
    if not v_df.empty:
        # Spaced QR Codes
        qr_c1, _, qr_c2 = st.columns([1, 0.2, 1])
        row_t1 = v_df[v_df['captain_name'].isin(t1)]
        row_t2 = v_df[v_df['captain_name'].isin(t2)]
        
        with qr_c1:
            if not row_t1.empty:
                r = row_t1.iloc[0]
                c_name, c_token, c_vote = r['captain_name'], r['pin'], r['vote']
                st.markdown(f"**{c_name}**")
                if c_vote == "Waiting":
                    if st.session_state.get("show_qr_codes", False):
                        img = generate_qr(f"{QR_BASE_URL}/?vote_token={c_token}")
                        st.image(img, width=400, caption="Scan to Vote")
                    else:
                        st.info("👀 QR Code Hidden")
                else: st.success("🗳️ VOTE RECEIVED")
        with qr_c2:
            if not row_t2.empty:
                r = row_t2.iloc[0]
                c_name, c_token, c_vote = r['captain_name'], r['pin'], r['vote']
                st.markdown(f"**{c_name}**")
                if c_vote == "Waiting":
                    if st.session_state.get("show_qr_codes", False):
                        img = generate_qr(f"{QR_BASE_URL}/?vote_token={c_token}")
                        st.image(img, width=400, caption="Scan to Vote")
                    else:
                        st.info("👀 QR Code Hidden")
                else: st.success("🗳️ VOTE RECEIVED")

        votes = v_df['vote'].tolist()
        if "Reroll" in votes:
            st.warning("🔄 Reroll requested...")
            conn = sqlite3.connect('cs2_history.db'); conn.execute("DELETE FROM current_draft_votes"); conn.commit(); conn.close()
            if 'draft_pins' in st.session_state: del st.session_state.draft_pins
            st.session_state.revealed = False
            st.session_state.trigger_reroll = True
            st.rerun()

        if "Waiting" not in votes and len(votes) == 2 and all(v == "Approve" for v in votes):
             if not st.session_state.get("vote_completed", False):
                 st.success("🎉 Teams Approved!")
                 # REMOVED AUTO SEND TO DISCORD
                 st.session_state.vote_completed = True
                 st.rerun()

@st.fragment(run_every=3)
def render_waiting_screen():
    saved = load_draft_state()
    if saved:
        st.session_state.teams_locked = True
        st.rerun()
    st.info("👋 Waiting for an Admin to start the session...")

def render_mixer_tab(player_df):
    # Check for queued audio from previous interactions (before rerun)
    if st.session_state.get("audio_cue"):
        play_sound(st.session_state.audio_cue)
        del st.session_state.audio_cue

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
                col1, col2, col3 = st.columns(3)
                
                def run_draft(mode="balanced"):
                    metric = "avg_kd" if mode == "kd_balanced" else "overall"
                    
                    # Dynamically determine Top 2 based on the chosen metric to force split them
                    current_score_map = dict(zip(player_df['name'], player_df[metric]))
                    sorted_by_metric = sorted(selected, key=lambda x: current_score_map.get(x, 0), reverse=True)
                    dynamic_top_2 = [sorted_by_metric[0], sorted_by_metric[1]]

                    roommates = get_roommates()
                    all_combos = get_best_combinations(selected, force_split=dynamic_top_2, force_together=roommates, metric=metric)
                    ridx = 0 if mode in ["balanced", "kd_balanced"] else random.randint(1, min(50, len(all_combos) - 1))
                    t1, t2, a1, a2, gap = all_combos[ridx]
                    n_a, n_b = random.sample(TEAM_NAMES, 2)
                    save_draft_state(t1, t2, n_a, n_b, a1, a2, mode=mode)
                    
                    # Update session state with mode
                    st.session_state.draft_mode = mode
                    
                    # RESTORE MAP IF PRESERVED
                    if st.session_state.get("preserved_map_pick"):
                        update_draft_map(st.session_state.preserved_map_pick)
                        st.session_state.global_map_pick = st.session_state.preserved_map_pick
                        del st.session_state.preserved_map_pick
                    else:
                        st.session_state.global_map_pick = None

                    st.session_state.final_teams = all_combos[ridx]
                    st.session_state.assigned_names = (n_a, n_b)
                    st.session_state.teams_locked = True
                    st.session_state.revealed = False
                    if 'draft_pins' in st.session_state: del st.session_state.draft_pins
                    st.rerun()

                if col1.button("⚖️ Perfect Balance", use_container_width=True): run_draft("balanced")
                if col2.button("🔫 KD Balance", use_container_width=True): run_draft("kd_balanced")
                if col3.button("🎲 Chaos Mode", use_container_width=True): run_draft("chaos")
        else:
            render_waiting_screen()
    else:
        t1_unsorted, t2_unsorted, avg1, avg2, _ = st.session_state.final_teams 
        name_a, name_b = st.session_state.assigned_names
        # Decide which metric to sort by for display
        if st.session_state.get("draft_mode") == "kd_balanced":
             # Use fillna logic similar to logic.py or trust database.py's fillna
             score_map = dict(zip(player_df['name'], player_df['avg_kd']))
        else:
             score_map = dict(zip(player_df['name'], player_df['overall']))
             
        t1 = sorted(t1_unsorted, key=lambda x: score_map.get(x, 0), reverse=True)
        t2 = sorted(t2_unsorted, key=lambda x: score_map.get(x, 0), reverse=True)
        
        if st.session_state.admin_authenticated:
            with st.expander("🛠️ Draft Options"):
                rc1, rc2, rc3 = st.columns(3)
                with rc1:
                    if st.button("⚖️ Reroll (Balanced)", use_container_width=True): 
                        st.session_state.draft_mode = "balanced"
                        st.session_state.trigger_reroll = True
                        st.rerun()
                with rc2:
                    if st.button("🔫 Reroll (KD)", use_container_width=True): 
                        st.session_state.draft_mode = "kd_balanced"
                        st.session_state.trigger_reroll = True
                        st.rerun()
                with rc3:
                    if st.button("🎲 Reroll (Chaos)", use_container_width=True): 
                        st.session_state.draft_mode = "balanced" # Chaos uses balanced metric but random pick
                        st.session_state.trigger_reroll = True
                        st.rerun()
                
                # Secondary row for utility
                rc_sub, rc_reset = st.columns(2)
                with rc_sub:
                     if st.button("🏃 Substitute Players", help="Unlock draft to swap players but KEEP the current map/veto.", use_container_width=True):
                         st.session_state.preserved_map_pick = st.session_state.get("global_map_pick")
                         clear_draft_state() # Clear DB so app.py doesn't auto-load old teams
                         st.session_state.teams_locked = False
                         st.session_state.revealed = False
                         st.rerun()
                with rc_reset:
                    if st.button("🔄 Full Reset", type="primary", use_container_width=True):
                        if 'skeez_nickname' in st.session_state: del st.session_state.skeez_nickname
                        clear_draft_state(); clear_lobby_link(); st.session_state.clear(); st.session_state.maps_sent_to_discord = False; st.rerun()


        active_lobby, cybershoke_mid = get_lobby_link()
        is_creating = st.session_state.get("lobby_creating", False)

        if st.session_state.global_map_pick and not active_lobby and not is_creating:
             st.session_state.lobby_creating = True # Lock
             with st.spinner("🤖 Automatically creating Cybershoke lobby..."):
                 try:
                     current_admin = st.session_state.get("admin_user", "Skeez")
                     auto_link, res_mid = create_cybershoke_lobby_api(admin_name=current_admin)
                     if auto_link:
                         set_lobby_link(auto_link, res_mid)
                         # REMOVED AUTO SEND HERE
                 finally:
                     st.session_state.lobby_creating = False # Unlock
                     st.rerun()
        elif st.session_state.global_map_pick and not active_lobby and is_creating:
            st.info("Creating server... please wait.")

        if active_lobby and st.session_state.global_map_pick:
            st.markdown(f"""<div class="cs-box"><div class="cs-title">🚀 CYBERSHOKE LOBBY READY</div><p style="color:white; font-family: monospace; font-size: 1.1em;">{active_lobby} <br> <span style="color: #FFD700; font-weight: bold;">Password: kimkim</span></p><a href="{active_lobby}" target="_blank"><button style="background-color: #00E500; color: black; border: none; padding: 10px 20px; font-weight: bold; border-radius: 5px; cursor: pointer; width: 100%;">▶️ JOIN SERVER</button></a></div>""", unsafe_allow_html=True)
            
            # --- MANUAL BROADCAST BUTTON ---
            if st.session_state.admin_authenticated:
                bc1, bc2 = st.columns(2)
                if bc1.button("📢 Broadcast to Discord", type="primary", use_container_width=True):
                    maps = st.session_state.global_map_pick.split(",")
                    send_full_match_info(name_a, t1, name_b, t2, maps, active_lobby)
                    st.toast("✅ Sent to Discord!")
                
                if bc2.button("✅️ Create New Cybershoke Lobby", use_container_width=True): clear_lobby_link(); st.rerun()

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
                             st.session_state.audio_cue = "captain_pick"
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
                             st.session_state.audio_cue = "captain_pick"
                             st.toast(f"Captain changed to {new_cap}"); st.rerun()
        
        if st.session_state.global_map_pick:
             st.divider()
             st.markdown("<h4 style='text-align: center; color: #FFD700;'>🗺️ MAP QUEUE</h4>", unsafe_allow_html=True)
             picked_maps = st.session_state.global_map_pick.split(",")
             if picked_maps and picked_maps[0] != '':
                 # REMOVED AUTO SEND HERE
                 m_cols = st.columns(len(picked_maps))
                 for i, m_name in enumerate(picked_maps):
                     with m_cols[i]:
                         st.markdown(f"""<div class="map-box-container"><div class="map-order">MATCH #{i+1}</div><div class="map-name">{m_name}</div></div>""", unsafe_allow_html=True)
                         st.image(MAP_LOGOS[m_name], width=120)

        current_votes = get_vote_status()
        cap1_name, cap2_name = None, None
        if not current_votes.empty:
            cap1_name = current_votes.iloc[0]['captain_name']
            cap2_name = current_votes.iloc[1]['captain_name']

        def format_player(name):
            # Skeez Nickname Logic
            display_name = name
            if name == "Skeez":
                if "skeez_nickname" not in st.session_state:
                    st.session_state.skeez_nickname = random.choice(SKEEZ_TITLES)
                display_name = f"{st.session_state.skeez_nickname} (Skeez)"
            
            # KD Display Logic
            if st.session_state.get("draft_mode") == "kd_balanced":
                # Find KD
                try:
                    p_kd = player_df[player_df['name'] == name]['avg_kd'].iloc[0]
                    display_name = f"{display_name} ({p_kd})"
                except:
                    pass

            if name == cap1_name or name == cap2_name: return f"👑 {display_name}"
            return display_name

        if not st.session_state.revealed:
            if 'draft_pins' not in st.session_state:
                c1_pick, c2_pick = pick_captains(t1, t2)
                t1_token, t2_token = str(uuid.uuid4()), str(uuid.uuid4())
                st.session_state.draft_pins = {c1_pick: t1_token, c2_pick: t2_token}
                set_draft_pins(c1_pick, t1_token, c2_pick, t2_token)
                cap1_name, cap2_name = c1_pick, c2_pick

            for i in range(5):
                time.sleep(0.4); p1_holders[i].info(format_player(t1[i]))
                time.sleep(0.4); p2_holders[i].warning(format_player(t2[i]))
            
            st.session_state.revealed = True
            st.session_state.audio_cue = "captain_pick"
            st.rerun()
        else:
            for i in range(5):
                p1_holders[i].info(format_player(t1[i]))
                p2_holders[i].warning(format_player(t2[i]))

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

# views/mixer.py
import streamlit as st
import random
import time
import uuid
import sqlite3
from constants import TEAM_NAMES, MAP_POOL, MAP_LOGOS
from database import (save_draft_state, load_draft_state, clear_draft_state, 
                      update_draft_map, update_elo, get_vote_status, set_draft_pins,
                      init_veto_state, get_veto_state)
from logic import get_best_combinations, pick_captains, cycle_new_captain
from cybershoke import create_cybershoke_lobby_api, set_lobby_link, get_lobby_link, clear_lobby_link
from discord_bot import send_full_match_info # <--- Manual Broadcast Function
from utils import generate_qr, get_local_ip

ROOMMATES = ["Chajra", "Ghoufa"]
QR_BASE_URL = "https://unbalanced-wac3gydqklzbeeuomp6adp.streamlit.app/"

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
    st.markdown(f"""<div class="turn-indicator">{phase} <br>Current Turn: <span style="color: #4da6ff;">{turn_captain}</span></div>""", unsafe_allow_html=True)
    if prot: st.write(f"**Protected:** {', '.join(prot)}")

    cols = st.columns(7)
    for i, m in enumerate(MAP_POOL):
        with cols[i]:
            is_avail = m in rem
            is_prot = m in prot
            opacity = "1.0" if is_avail or is_prot else "0.2"
            border = "2px solid #00E500" if is_prot else "1px solid #333"
            st.markdown(f"""<div style="opacity: {opacity}; border: {border}; padding: 5px; border-radius: 5px; text-align: center;"><img src="{MAP_LOGOS.get(m, '')}" style="width: 100%; border-radius: 5px;"><div style="font-size: 0.8em; font-weight: bold; margin-top: 5px; color: white;">{m}</div></div>""", unsafe_allow_html=True)

@st.fragment(run_every=2)
def render_voting_fragment(t1, t2, name_a, name_b):
    st.subheader("📲 Captains: Scan to Vote")
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
                    img = generate_qr(f"{QR_BASE_URL}/?vote_token={c_token}")
                    st.image(img, width=400, caption="Scan to Vote")
                else: st.success("🗳️ VOTE RECEIVED")
        with qr_c2:
            if not row_t2.empty:
                r = row_t2.iloc[0]
                c_name, c_token, c_vote = r['captain_name'], r['pin'], r['vote']
                st.markdown(f"**{c_name}**")
                if c_vote == "Waiting":
                    img = generate_qr(f"{QR_BASE_URL}/?vote_token={c_token}")
                    st.image(img, width=400, caption="Scan to Vote")
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
                
                def run_draft(mode="balanced"):
                    all_combos = get_best_combinations(selected, force_split=top_2, force_together=ROOMMATES)
                    ridx = 0 if mode == "balanced" else random.randint(1, min(50, len(all_combos) - 1))
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

                if col1.button("⚖️ Perfect Balance", use_container_width=True): run_draft("balanced")
                if col2.button("🎲 Chaos Mode", use_container_width=True): run_draft("chaos")
        else:
            render_waiting_screen()
    else:
        t1_unsorted, t2_unsorted, avg1, avg2, _ = st.session_state.final_teams 
        name_a, name_b = st.session_state.assigned_names
        score_map = dict(zip(player_df['name'], player_df['overall']))
        t1 = sorted(t1_unsorted, key=lambda x: score_map.get(x, 0), reverse=True)
        t2 = sorted(t2_unsorted, key=lambda x: score_map.get(x, 0), reverse=True)
        
        if st.session_state.admin_authenticated:
            with st.expander("🛠️ Draft Options"):
                rc1, rc2, rc3 = st.columns(3)
                if rc1.button("⚖️ Reroll (Balanced)", use_container_width=True): st.session_state.trigger_reroll = True; st.rerun()
                if rc2.button("🎲 Reroll (Chaos)", use_container_width=True): st.session_state.trigger_reroll = True; st.rerun()
                if rc3.button("🔄 Full Reset", type="primary", use_container_width=True):
                    clear_draft_state(); clear_lobby_link(); st.session_state.clear(); st.session_state.maps_sent_to_discord = False; st.rerun()

        active_lobby = get_lobby_link()
        is_creating = st.session_state.get("lobby_creating", False)

        if st.session_state.global_map_pick and not active_lobby and not is_creating:
             st.session_state.lobby_creating = True # Lock
             with st.spinner("🤖 Automatically creating Cybershoke lobby..."):
                 try:
                     auto_link = create_cybershoke_lobby_api()
                     if auto_link:
                         set_lobby_link(auto_link)
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
                
                if bc2.button("🗑️ Clear Link (Admin)", use_container_width=True): clear_lobby_link(); st.rerun()

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
                time.sleep(0.4); p1_holders[i].info(format_player(t1[i]))
                time.sleep(0.4); p2_holders[i].warning(format_player(t2[i]))
            st.session_state.revealed = True; st.rerun()
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

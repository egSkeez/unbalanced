# app.py
import streamlit as st
import random
import time
import sqlite3
import pandas as pd
import altair as alt
from streamlit_autorefresh import st_autorefresh
from constants import SKEEZ_TITLES, TEAM_NAMES, MAP_POOL, MAP_LOGOS
from database import init_db, get_player_stats, update_elo, set_draft_pins, submit_vote, get_vote_status, get_player_secret, save_draft_state, load_draft_state, clear_draft_state, update_draft_map
from logic import get_best_combinations, pick_captains
from wheel import render_bench_wheel
from cybershoke import init_cybershoke_db, set_lobby_link, get_lobby_link, clear_lobby_link

# Initialize Databases
init_db()
init_cybershoke_db()

st.set_page_config(page_title="CS2 Pro Balancer", layout="centered")

st.markdown("""
<style>
    [data-testid="stVerticalBlock"] h3 { min-height: 110px; display: flex; align-items: center; text-align: center; justify-content: center; font-size: 1.5rem !important; }
    [data-testid="stImage"] img { max-height: 120px; width: auto; margin: 0 auto; }
    .team-header-blue { color: #4da6ff; border-bottom: 2px solid #4da6ff; padding-bottom: 5px; text-align: center; }
    .team-header-orange { color: #ff9f43; border-bottom: 2px solid #ff9f43; padding-bottom: 5px; text-align: center; }
    .cs-box { border: 2px solid #00E500; background-color: #0e1117; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px; }
    .cs-title { color: #00E500; font-weight: bold; font-size: 1.2em; margin-bottom: 10px; }
    
    /* Map Box Styling */
    .map-box-container { text-align: center; border: 1px solid #333; padding: 10px; border-radius: 8px; background-color: #1E1E1E; }
    .map-order { color: #FFD700; font-weight: bold; font-size: 0.9em; margin-bottom: 5px; }
    .map-name { color: white; font-weight: bold; font-size: 1.1em; }
</style>
""", unsafe_allow_html=True)

# --- GLOBAL SYNC CHECK ---
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

# Initialize Session State
if 'admin_authenticated' not in st.session_state: st.session_state.admin_authenticated = False
if 'teams_locked' not in st.session_state: st.session_state.teams_locked = False
if 'revealed' not in st.session_state: st.session_state.revealed = False
if 'veto_maps' not in st.session_state: st.session_state.veto_maps = MAP_POOL.copy()
if 'protected_maps' not in st.session_state: st.session_state.protected_maps = []
if 'turn' not in st.session_state: st.session_state.turn = None
if 'global_map_pick' not in st.session_state: st.session_state.global_map_pick = None

player_df = get_player_stats()

tabs = st.tabs(["🎮 Mixer & Veto", "🎡 Bench Wheel", "🏆 Leaderboard", "📜 History", "⚙️ Admin"])

# --- TAB: MIXER & VETO ---
with tabs[0]:
    st.title("🎮 CS2 Draft & Veto")
    
    # 1. Selection Phase
    if not st.session_state.teams_locked:
        current_sel = st.session_state.get("current_selection", [])
        st.write(f"**Players Selected:** `{len(current_sel)}/10`")
        
        selected = st.multiselect("Select 10 Players:", options=player_df['name'].tolist(), key="current_selection", label_visibility="collapsed")

        if len(selected) == 10:
            col1, col2 = st.columns(2)
            if col1.button("⚖️ Perfect Balance", use_container_width=True):
                all_combos = get_best_combinations(selected)
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
                all_combos = get_best_combinations(selected)
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
        # --- LOCKED DRAFT VIEW ---
        
        # Only Auto-Refresh if NOT Admin (Admins have manual control)
        if st.session_state.revealed and not st.session_state.admin_authenticated:
            st_autorefresh(interval=4000, key="global_sync")

        t1_unsorted, t2_unsorted, avg1, avg2, _ = st.session_state.final_teams 
        name_a, name_b = st.session_state.assigned_names
        
        # --- 1. DRAFT CONTROLS ---
        with st.expander("🛠️ Draft Options (Reroll / Reset)"):
            rc1, rc2, rc3 = st.columns(3)
            if rc1.button("⚖️ Reroll (Balanced)", use_container_width=True):
                current_players = t1_unsorted + t2_unsorted
                all_combos = get_best_combinations(current_players)
                nt1, nt2, na1, na2, ngap = all_combos[0]
                nn_a, nn_b = random.sample(TEAM_NAMES, 2)
                save_draft_state(nt1, nt2, nn_a, nn_b, na1, na2)
                st.session_state.final_teams = all_combos[0]
                st.session_state.assigned_names = (nn_a, nn_b)
                st.session_state.revealed = False
                st.session_state.global_map_pick = None
                if 'draft_pins' in st.session_state: del st.session_state.draft_pins
                st.rerun()
                
            if rc2.button("🎲 Reroll (Chaos)", use_container_width=True):
                current_players = t1_unsorted + t2_unsorted
                all_combos = get_best_combinations(current_players)
                ridx = random.randint(1, min(50, len(all_combos) - 1))
                nt1, nt2, na1, na2, ngap = all_combos[ridx]
                nn_a, nn_b = random.sample(TEAM_NAMES, 2)
                save_draft_state(nt1, nt2, nn_a, nn_b, na1, na2)
                st.session_state.final_teams = all_combos[ridx]
                st.session_state.assigned_names = (nn_a, nn_b)
                st.session_state.revealed = False
                st.session_state.global_map_pick = None
                if 'draft_pins' in st.session_state: del st.session_state.draft_pins
                st.rerun()
                
            if rc3.button("🔄 Full Reset", type="primary", use_container_width=True):
                clear_draft_state()
                clear_lobby_link()
                st.session_state.clear()
                st.rerun()

        # --- 2. ACTIVE LOBBY LINK (CONDITIONAL VISIBILITY) ---
        # Only show if the maps are finalized
        active_lobby = get_lobby_link()
        if active_lobby and st.session_state.global_map_pick:
            st.markdown(f"""
                <div class="cs-box">
                    <div class="cs-title">🚀 CYBERSHOKE LOBBY READY | PASSWORD: kimkim</div>
                    <a href="{active_lobby}" target="_blank">
                        <button style="background-color: #00E500; color: black; border: none; padding: 10px 20px; font-weight: bold; border-radius: 5px; cursor: pointer; width: 100%;">
                            ▶️ JOIN SERVER
                        </button>
                    </a>
                </div>
            """, unsafe_allow_html=True)
            # Removed the Clear Link button from here as requested

        # Sorting
        score_map = dict(zip(player_df['name'], player_df['overall']))
        t1 = sorted(t1_unsorted, key=lambda x: score_map.get(x, 0), reverse=True)
        t2 = sorted(t2_unsorted, key=lambda x: score_map.get(x, 0), reverse=True)

        sum1 = round(avg1 * 5, 2)
        sum2 = round(avg2 * 5, 2)
        gap = round(abs(sum1 - sum2), 2)
        
        indicator_a = " ⭐" if sum1 > sum2 else ""
        indicator_b = " ⭐" if sum2 > sum1 else ""

        st.divider()
        c1, c2 = st.columns(2)
        with c1: 
            st.markdown(f"<h3 class='team-header-blue'>🟦 {name_a}</h3>", unsafe_allow_html=True)
            st.markdown(f"<div style='text-align: center; font-weight: bold;'>Total Power: {sum1}{indicator_a}</div>", unsafe_allow_html=True)
            p1_holders = [st.empty() for _ in range(5)]
        with c2: 
            st.markdown(f"<h3 class='team-header-orange'>🟧 {name_b}</h3>", unsafe_allow_html=True)
            st.markdown(f"<div style='text-align: center; font-weight: bold;'>Total Power: {sum2}{indicator_b}</div>", unsafe_allow_html=True)
            p2_holders = [st.empty() for _ in range(5)]

        if 'skeez_titles_session' not in st.session_state:
            st.session_state.skeez_titles_session = [random.choice(SKEEZ_TITLES) for _ in range(10)]

        current_votes = get_vote_status()
        cap1_name, cap2_name = None, None
        
        if not current_votes.empty:
            cap1_name = current_votes.iloc[0]['captain_name']
            cap2_name = current_votes.iloc[1]['captain_name']
        elif 'draft_pins' in st.session_state:
            caps = list(st.session_state.draft_pins.keys())
            cap1_name, cap2_name = caps[0], caps[1]

        def format_player(name, idx, is_skeez_team):
            display_name = name
            if name == "Skeez":
                title_idx = idx if is_skeez_team == 1 else idx + 5
                display_name = f"{st.session_state.skeez_titles_session[title_idx]} (Skeez)"
            if name == cap1_name or name == cap2_name:
                return f"👑 {display_name}"
            return display_name

        if not st.session_state.revealed:
            if 'draft_pins' not in st.session_state:
                c1_pick, c2_pick = pick_captains(t1, t2)
                w1, w2 = get_player_secret(c1_pick), get_player_secret(c2_pick)
                st.session_state.draft_pins = {c1_pick: w1, c2_pick: w2}
                set_draft_pins(c1_pick, w1, c2_pick, w2)
                cap1_name, cap2_name = c1_pick, c2_pick

            for i in range(5):
                time.sleep(0.4)
                p1_holders[i].info(format_player(t1[i], i, 1))
                time.sleep(0.4)
                p2_holders[i].warning(format_player(t2[i], i, 2))
            st.session_state.revealed = True
            st.rerun()
        else:
            for i in range(5):
                p1_holders[i].info(format_player(t1[i], i, 1))
                p2_holders[i].warning(format_player(t2[i], i, 2))

        st.divider()

        t1_stats = player_df[player_df['name'].isin(t1)][['aim', 'util', 'team_play']].sum()
        t2_stats = player_df[player_df['name'].isin(t2)][['aim', 'util', 'team_play']].sum()
        
        st.subheader("📊 Performance Breakdown")
        
        def render_comparision_row(label, val1, val2):
            row_c1, row_c2, row_c3 = st.columns([1, 4, 1])
            with row_c1:
                st.markdown(f"<h3 style='text-align: right; color: #4da6ff; margin:0;'>{int(val1)}</h3>", unsafe_allow_html=True)
            with row_c2:
                st.markdown(f"<div style='text-align: center; font-weight: bold; margin-bottom: 5px;'>{label}</div>", unsafe_allow_html=True)
                total = val1 + val2
                p1_pct = (val1 / total) * 100 if total > 0 else 50
                p2_pct = (val2 / total) * 100 if total > 0 else 50
                st.markdown(f"""
                    <div style="display: flex; width: 100%; height: 12px; border-radius: 6px; overflow: hidden;">
                        <div style="width: {p1_pct}%; background-color: #4da6ff;"></div>
                        <div style="width: {p2_pct}%; background-color: #ff9f43;"></div>
                    </div>
                """, unsafe_allow_html=True)
            with row_c3:
                st.markdown(f"<h3 style='text-align: left; color: #ff9f43; margin:0;'>{int(val2)}</h3>", unsafe_allow_html=True)

        render_comparision_row("🎯 AIM", t1_stats['aim'], t2_stats['aim'])
        st.write("") 
        render_comparision_row("🧠 UTILITY", t1_stats['util'], t2_stats['util'])
        st.write("") 
        render_comparision_row("🤝 TEAM PLAY", t1_stats['team_play'], t2_stats['team_play'])
        
        st.markdown(f"<br><div style='text-align: center; color: #77dd77; font-size: 0.9em;'>Total Metric Gap: {gap}</div>", unsafe_allow_html=True)
        st.divider()

        # --- VOTING & VETO ---
        if st.session_state.revealed:
            if 'draft_pins' not in st.session_state:
                if not current_votes.empty:
                    c1_db = current_votes.iloc[0]['captain_name']
                    c2_db = current_votes.iloc[1]['captain_name']
                    st.session_state.draft_pins = {c1_db: "HIDDEN", c2_db: "HIDDEN"}
                else:
                    c1_pick, c2_pick = pick_captains(t1, t2)
                    w1, w2 = get_player_secret(c1_pick), get_player_secret(c2_pick)
                    st.session_state.draft_pins = {c1_pick: w1, c2_pick: w2}
                    set_draft_pins(c1_pick, w1, c2_pick, w2)

            st.subheader("🕵️ Captains' Secret Vote")
            
            v_df = get_vote_status()
            if not v_df.empty:
                cap_name_1 = v_df.iloc[0]['captain_name']
                cap_name_2 = v_df.iloc[1]['captain_name']
                st.info(f"Captains: **{cap_name_1}** and **{cap_name_2}**")

                with st.expander("🔑 Open Voting Portal"):
                    in_secret = st.text_input("Enter your Secret Word", type="password", key="v_secret")
                    vcol1, vcol2 = st.columns(2)
                    if vcol1.button("✅ Approve Draft", use_container_width=True):
                        if submit_vote(in_secret.strip(), "Approve"): 
                            st.success("Vote cast!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Invalid Secret Word!")
                    if vcol2.button("❌ Request Reroll", use_container_width=True):
                        if submit_vote(in_secret.strip(), "Reroll"): 
                            st.warning("Reroll requested!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Invalid Secret Word!")

                v1, v2 = v_df.iloc[0]['vote'], v_df.iloc[1]['vote']
                s1, s2 = st.columns(2)
                s1.metric(f"Captain: {cap_name_1}", "READY" if v1 != "Waiting" else "THINKING...")
                s2.metric(f"Captain: {cap_name_2}", "READY" if v2 != "Waiting" else "THINKING...")

                if v1 != "Waiting" and v2 != "Waiting":
                    if v1 == "Approve" and v2 == "Approve":
                        st.success("🎉 Teams Approved! Proceed to Map Veto.")
                        
                        # --- GLOBAL MAP DISPLAY (If already picked) ---
                        if st.session_state.global_map_pick:
                             st.success("✅ MAP VETO COMPLETE")
                             
                             # PARSE CSV MAPS
                             picked_maps = st.session_state.global_map_pick.split(",")
                             
                             # Display 3 Maps Ordered
                             m_cols = st.columns(len(picked_maps))
                             for i, m_name in enumerate(picked_maps):
                                 with m_cols[i]:
                                     st.markdown(f"""
                                     <div class="map-box-container">
                                        <div class="map-order">PICK #{i+1}</div>
                                        <div class="map-name">{m_name}</div>
                                     </div>
                                     """, unsafe_allow_html=True)
                                     st.image(MAP_LOGOS[m_name], use_container_width=True)
                             
                             st.divider()
                             rc1, rc2 = st.columns(2)
                             if rc1.button(f"🏆 {name_a} Won", use_container_width=True):
                                update_elo(t1, t2, name_a, name_b, 1, st.session_state.global_map_pick)
                                clear_draft_state()
                                clear_lobby_link() 
                                st.session_state.clear(); st.rerun()
                             if rc2.button(f"🏆 {name_b} Won", use_container_width=True):
                                update_elo(t1, t2, name_a, name_b, 2, st.session_state.global_map_pick)
                                clear_draft_state()
                                clear_lobby_link()
                                st.session_state.clear(); st.rerun()

                        else:
                            # --- VETO LOGIC (ADMIN ONLY) ---
                            if st.session_state.admin_authenticated:
                                if st.session_state.turn is None:
                                    if st.button("Flip Coin for Veto", use_container_width=True):
                                        st.session_state.turn = random.choice([name_a, name_b]); st.rerun()
                                elif len(st.session_state.protected_maps) < 2:
                                     st.subheader(f"🛡️ Protection: {st.session_state.turn}")
                                     cols = st.columns(7) 
                                     for i, m in enumerate(st.session_state.veto_maps):
                                         with cols[i]:
                                             st.image(MAP_LOGOS[m], use_container_width=True)
                                             if st.button(m, key=f"p_{m}"):
                                                 st.session_state.protected_maps.append(m)
                                                 st.session_state.veto_maps.remove(m)
                                                 st.session_state.turn = name_b if st.session_state.turn == name_a else name_a; st.rerun()
                                
                                elif len(st.session_state.veto_maps) > 1:
                                     st.subheader(f"🗳️ Banning: {st.session_state.turn}")
                                     cols = st.columns(7) 
                                     for i, m in enumerate(st.session_state.veto_maps):
                                         with cols[i]:
                                             st.image(MAP_LOGOS[m], use_container_width=True)
                                             if st.button(m, key=f"b_{m}"):
                                                 st.session_state.veto_maps.remove(m)
                                                 st.session_state.turn = name_b if st.session_state.turn == name_a else name_a; st.rerun()
                                else:
                                    # SAVE ALL 3 MAPS
                                    # Order: Pick 1, Pick 2, Decider (Remaining)
                                    final_order = st.session_state.protected_maps + st.session_state.veto_maps
                                    
                                    # Save list as CSV
                                    update_draft_map(final_order)
                                    st.session_state.global_map_pick = ",".join(final_order)
                                    st.rerun()
                            else:
                                st.info("⏳ Waiting for Admin/Captains to Veto Maps...")

                    else:
                        st.error("🚨 A Reroll was requested. Randomizing new teams...")
                        set_draft_pins("Resetting1", "dummy", "Resetting2", "dummy") 
                        time.sleep(2)
                        del st.session_state.draft_pins
                        del st.session_state.skeez_titles_session
                        st.session_state.revealed = False
                        
                        all_combos = get_best_combinations([p for p in t1+t2])
                        ridx = random.randint(1, min(50, len(all_combos)-1))
                        nt1, nt2, na1, na2, ngap = all_combos[ridx]
                        save_draft_state(nt1, nt2, name_a, name_b, na1, na2)
                        st.session_state.final_teams = all_combos[ridx]
                        st.rerun()

            # --- ADMIN CYBERSHOKE CREATE TOOL ---
            if st.session_state.admin_authenticated and st.session_state.global_map_pick and not active_lobby:
                st.divider()
                st.markdown("""<div class="cs-box"><div class="cs-title">🛠️ Create Cybershoke Lobby</div>""", unsafe_allow_html=True)
                
                # Show DECIDER map for server config (last map in list)
                decider_map = st.session_state.global_map_pick.split(",")[-1]
                st.code(f"Decider Map: {decider_map}\nRegion: France\nPassword: kimkim", language="text")
                
                st.link_button("🌐 Open Cybershoke Create Page", "https://cybershoke.net/matches/create", use_container_width=True)
                c_link = st.text_input("Paste Connect Link/IP here:", placeholder="e.g. 192.168.1.1:27015")
                if st.button("✅ Set Server Link", use_container_width=True):
                    if c_link:
                        set_lobby_link(c_link)
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

# --- TAB: BENCH WHEEL ---
with tabs[1]:
    all_player_names = player_df['name'].tolist()
    render_bench_wheel(all_player_names)

# --- TAB: RANKINGS ---
with tabs[2]:
    st.title("🏆 Rankings")
    stats_df = get_player_stats()
    st.dataframe(stats_df[['name', 'W', 'D', 'overall']], use_container_width=True, hide_index=True)

# --- TAB: HISTORY ---
with tabs[3]:
    st.title("📜 History")
    conn = sqlite3.connect('cs2_history.db')
    hist_df = pd.read_sql_query("SELECT * FROM matches ORDER BY date DESC", conn)
    conn.close()
    for _, row in hist_df.iterrows():
        winner = row['team1_name'] if row['winner_idx'] == 1 else row['team2_name']
        with st.expander(f"🎮 {row['date'].split()[0]} | {winner} on {row['map']}"):
            c_a, c_b = st.columns(2)
            with c_a:
                st.write(f"**🟦 {row['team1_name']}**")
                for p in row['team1_players'].split(", "): st.write(f"• {p}")
            with c_b:
                st.write(f"**🟧 {row['team2_name']}**")
                for p in row['team2_players'].split(", "): st.write(f"• {p}")

# --- TAB: ADMIN ---
with tabs[4]:
    if not st.session_state.admin_authenticated:
        st.title("🔐 Admin Login")
        with st.form("admin_login_form"):
            pwd_input = st.text_input("Enter Admin Password", type="password")
            submitted = st.form_submit_button("Unlock Management")
            if submitted:
                if pwd_input == "2567":
                    st.session_state.admin_authenticated = True
                    st.success("Access Granted")
                    st.rerun()
                else:
                    st.error("Incorrect Password")
    else:
        st.title("⚙️ Roster & Lobby Management")
        if st.button("Logout Admin"):
            st.session_state.admin_authenticated = False
            st.rerun()
        
        # --- ADMIN LOBBY MANAGER ---
        st.subheader("🚀 Session & Lobby Manager")
        
        st.markdown("**Cybershoke / Server Link**")
        curr_link = get_lobby_link()
        admin_link_in = st.text_input("Set Server Link", value=curr_link if curr_link else "", placeholder="Paste link here...")
        
        l_col1, l_col2 = st.columns(2)
        if l_col1.button("✅ Broadcast Link"):
            set_lobby_link(admin_link_in)
            st.success("Link broadcasted to all screens!")
        if l_col2.button("🗑️ Clear Link"):
            clear_lobby_link()
            st.success("Link removed.")
            
        st.divider()
        st.subheader("⚠️ Danger Zone")
        if st.button("🛑 RESET WHOLE SESSION", type="primary"):
            clear_draft_state()
            clear_lobby_link()
            st.session_state.clear()
            st.rerun()
        # --------------------------------

        st.divider()
        st.subheader("📝 Player Editor")
        all_p = get_player_stats()
        target_name = st.selectbox("Select Player to Manage", options=[""] + all_p['name'].tolist())
        
        if target_name:
            p_row = all_p[all_p['name'] == target_name].iloc[0]
            with st.form("edit_form"):
                new_aim = st.slider("Aim", 1.0, 10.0, float(p_row['aim']))
                new_util = st.slider("Util", 1.0, 10.0, float(p_row['util']))
                new_team = st.slider("Team Play", 1.0, 10.0, float(p_row['team_play']))
                new_secret = st.text_input("Secret Word", value=str(p_row['secret_word']))
                if st.form_submit_button("💾 Save Changes"):
                    conn = sqlite3.connect('cs2_history.db')
                    conn.execute("UPDATE players SET aim=?, util=?, team_play=?, secret_word=? WHERE name=?", 
                                 (new_aim, new_util, new_team, new_secret, target_name))
                    conn.commit(); conn.close()
                    st.success("Updated!"); time.sleep(1); st.rerun()
                if st.form_submit_button("🗑️ Remove Player"):
                    conn = sqlite3.connect('cs2_history.db'); conn.execute("DELETE FROM players WHERE name=?", (target_name,)); conn.commit(); conn.close()
                    st.warning("Deleted!"); time.sleep(1); st.rerun()
        st.divider()
        with st.form("add_form"):
            st.subheader("Add New Player")
            n_name = st.text_input("Player Name")
            n_secret = st.text_input("Secret Word")
            n_a = st.slider("Aim Score", 1.0, 10.0, 5.0)
            n_u = st.slider("Util Score", 1.0, 10.0, 5.0)
            n_t = st.slider("Team Play Score", 1.0, 10.0, 5.0)
            if st.form_submit_button("➕ Add to Roster"):
                if n_name and n_secret:
                    conn = sqlite3.connect('cs2_history.db'); conn.execute("INSERT OR IGNORE INTO players (name, elo, aim, util, team_play, secret_word) VALUES (?, 1200, ?, ?, ?, ?)", (n_name, n_a, n_u, n_t, n_secret)); conn.commit(); conn.close()
                    st.success("Player Added!"); time.sleep(1); st.rerun()

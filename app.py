import streamlit as st
import random
import time
import sqlite3
import pandas as pd
from streamlit_autorefresh import st_autorefresh # Required for real-time sync
from constants import SKEEZ_TITLES, TEAM_NAMES, MAP_POOL, MAP_LOGOS
from database import init_db, get_player_stats, update_elo, set_draft_pins, submit_vote, get_vote_status
from logic import get_best_combinations, pick_captains
from wheel import render_bench_wheel

init_db()

st.set_page_config(page_title="CS2 Pro Balancer & ELO", layout="centered")

st.markdown("""
<style>
    [data-testid="stVerticalBlock"] h3 { min-height: 110px; display: flex; align-items: center; text-align: center; justify-content: center; font-size: 1.5rem !important; }
    [data-testid="stImage"] img { max-height: 120px; width: auto; margin: 0 auto; }
</style>
""", unsafe_allow_html=True)

tabs = st.tabs(["🎮 Mixer & Veto", "🎡 Bench Wheel", "🏆 Leaderboard", "📜 History", "⚙️ Admin"])

# --- TAB: MIXER & VETO ---
with tabs[0]:
    st.title("🎮 CS2 Unbalanced Team Draft")
    
    # Initialize session states
    if 'veto_maps' not in st.session_state: st.session_state.veto_maps = MAP_POOL.copy()
    if 'protected_maps' not in st.session_state: st.session_state.protected_maps = []
    if 'turn' not in st.session_state: st.session_state.turn = None
    if 'teams_locked' not in st.session_state: st.session_state.teams_locked = False
    if 'revealed' not in st.session_state: st.session_state.revealed = False
    if 'final_teams' not in st.session_state: st.session_state.final_teams = None
    if 'assigned_names' not in st.session_state: st.session_state.assigned_names = ("Team A", "Team B")
    if 'chaos_level' not in st.session_state: st.session_state.chaos_level = 0

    player_df = get_player_stats()
    current_sel = st.session_state.get("current_selection", [])
    st.write(f"**Players Selected:** `{len(current_sel)}/10`")
    
    selected = st.multiselect("Select 10 Players:", options=player_df['name'].tolist(), key="current_selection", label_visibility="collapsed")

    if len(selected) == 10:
        col1, col2 = st.columns(2)
        if col1.button("⚖️ Perfect Balance", use_container_width=True):
            all_combos = get_best_combinations(selected)
            st.session_state.final_teams = all_combos[0] # Returns (t1, t2, avg1, avg2, gap)
            st.session_state.assigned_names = random.sample(TEAM_NAMES, 2)
            st.session_state.teams_locked = True
            st.session_state.revealed = False
            st.session_state.chaos_level = 0
            if 'draft_pins' in st.session_state: del st.session_state.draft_pins # Clear old pins
            st.rerun()
            
        if col2.button("🎲 Chaos Mode", use_container_width=True):
            all_combos = get_best_combinations(selected)
            st.session_state.chaos_level = min(st.session_state.chaos_level + 5, len(all_combos) - 1)
            st.session_state.final_teams = all_combos[st.session_state.chaos_level]
            st.session_state.assigned_names = random.sample(TEAM_NAMES, 2)
            st.session_state.teams_locked = True
            st.session_state.revealed = False
            if 'draft_pins' in st.session_state: del st.session_state.draft_pins # Clear old pins
            st.rerun()

    if st.session_state.teams_locked:
        # HEARTBEAT: Refresh every 3 seconds so the main screen sees phone votes
        st_autorefresh(interval=3000, key="votedetector")

        t1, t2, avg1, avg2, _ = st.session_state.final_teams 
        name_a, name_b = st.session_state.assigned_names
        st.divider()
        
        indicator_a = " ⭐ (Stronger)" if avg1 > avg2 else ""
        indicator_b = " ⭐ (Stronger)" if avg2 > avg1 else ""
        
        c1, c2 = st.columns(2)
        with c1: 
            st.subheader(f"🟦 {name_a}")
            st.markdown(f"**Average Metric: `{avg1}`{indicator_a}**")
            p1_holders = [st.empty() for _ in range(5)]
        with c2: 
            st.subheader(f"🟧 {name_b}")
            st.markdown(f"**Average Metric: `{avg2}`{indicator_b}**")
            p2_holders = [st.empty() for _ in range(5)]

        # Reveal Logic
        if not st.session_state.revealed:
            for i in range(5):
                time.sleep(0.4)
                disp_a = f"**{random.choice(SKEEZ_TITLES)} (Skeez)**" if t1[i] == "Skeez" else f"**{t1[i]}**"
                p1_holders[i].info(disp_a)
                time.sleep(0.4)
                disp_b = f"**{random.choice(SKEEZ_TITLES)} (Skeez)**" if t2[i] == "Skeez" else f"**{t2[i]}**"
                p2_holders[i].warning(disp_b)
            st.session_state.revealed = True
        else:
            for i in range(5):
                p1_holders[i].info(f"**{random.choice(SKEEZ_TITLES)} (Skeez)**" if t1[i] == "Skeez" else f"**{t1[i]}**")
                p2_holders[i].warning(f"**{random.choice(SKEEZ_TITLES)} (Skeez)**" if t2[i] == "Skeez" else f"**{t2[i]}**")

        gap = round(abs((avg1*5) - (avg2*5)), 2)
        st.markdown(f"<h3 style='text-align: center; color: #77dd77;'>Total Metric Gap: {gap}</h3>", unsafe_allow_html=True)
        st.divider()

        # --- ANONYMOUS VOTING SECTION ---
        if 'draft_pins' not in st.session_state:
            cap1, cap2 = pick_captains(t1, t2)
            p1, p2 = str(random.randint(1000, 9999)), str(random.randint(1000, 9999))
            st.session_state.draft_pins = {cap1: p1, cap2: p2}
            set_draft_pins(cap1, p1, cap2, p2)

        st.subheader("🕵️ Anonymous Captain Approval")
        caps = list(st.session_state.draft_pins.keys())
        st.warning(f"Captains: **{caps[0]}** (PIN: `{st.session_state.draft_pins[caps[0]]}`) | **{caps[1]}** (PIN: `{st.session_state.draft_pins[caps[1]]}`)")
        
        # Mobile Voting Portal
        with st.expander("🔑 Open Voting Portal (For Captains)"):
            in_pin = st.text_input("Enter 4-Digit PIN", type="password", key="v_pin")
            vcol1, vcol2 = st.columns(2)
            if vcol1.button("✅ Approve Draft", use_container_width=True):
                if submit_vote(in_pin, "Approve"): st.success("Vote cast!"); time.sleep(1); st.rerun()
            if vcol2.button("❌ Request Reroll", use_container_width=True):
                if submit_vote(in_pin, "Reroll"): st.warning("Reroll requested!"); time.sleep(1); st.rerun()

        # Check Vote Status
        v_df = get_vote_status()
        v1, v2 = v_df.iloc[0]['vote'], v_df.iloc[1]['vote']
        
        s1, s2 = st.columns(2)
        s1.metric(f"Captain: {v_df.iloc[0]['captain_name']}", "READY" if v1 != "Waiting" else "THINKING...")
        s2.metric(f"Captain: {v_df.iloc[1]['captain_name']}", "READY" if v2 != "Waiting" else "THINKING...")

        if v1 != "Waiting" and v2 != "Waiting":
            if v1 == "Approve" and v2 == "Approve":
                st.success("🎉 Teams Approved! Proceed to Map Veto.")
                
                # --- MAP VETO SYSTEM (Unlocks only on approval) ---
                if st.session_state.turn is None:
                    if st.button("Flip Coin for Veto", use_container_width=True):
                        st.session_state.turn = random.choice([name_a, name_b]); st.rerun()
                elif len(st.session_state.protected_maps) < 2:
                    st.subheader(f"🛡️ Protection: {st.session_state.turn}")
                    cols = st.columns(len(st.session_state.veto_maps))
                    for i, m in enumerate(st.session_state.veto_maps):
                        with cols[i]:
                            st.image(MAP_LOGOS[m], use_container_width=True)
                            if st.button(m, key=f"p_{m}"):
                                st.session_state.protected_maps.append(m)
                                st.session_state.veto_maps.remove(m)
                                st.session_state.turn = name_b if st.session_state.turn == name_a else name_a; st.rerun()
                elif len(st.session_state.veto_maps) > 1:
                    st.subheader(f"🗳️ Banning: {st.session_state.turn}")
                    cols = st.columns(len(st.session_state.veto_maps))
                    for i, m in enumerate(st.session_state.veto_maps):
                        with cols[i]:
                            st.image(MAP_LOGOS[m], use_container_width=True)
                            if st.button(m, key=f"b_{m}"):
                                st.session_state.veto_maps.remove(m)
                                st.session_state.turn = name_b if st.session_state.turn == name_a else name_a; st.rerun()
                else:
                    final_three = st.session_state.protected_maps + st.session_state.veto_maps
                    m_cols = st.columns(3)
                    for i, m in enumerate(final_three):
                        with m_cols[i]:
                            st.success(f"Map {i+1}: {m}")
                            st.image(MAP_LOGOS[m])
                    st.divider()
                    rc1, rc2 = st.columns(2)
                    if rc1.button(f"🏆 {name_a} Won", use_container_width=True):
                        update_elo(t1, t2, name_a, name_b, 1, final_three[0]); st.session_state.clear(); st.rerun()
                    if rc2.button(f"🏆 {name_b} Won", use_container_width=True):
                        update_elo(t1, t2, name_a, name_b, 2, final_three[0]); st.session_state.clear(); st.rerun()
            else:
                st.error("🚨 Anonymously requested Reroll. Generating new teams...")
                time.sleep(3)
                del st.session_state.draft_pins
                all_combos = get_best_combinations(selected)
                st.session_state.chaos_level += 1
                st.session_state.final_teams = all_combos[st.session_state.chaos_level]
                st.session_state.revealed = False
                st.rerun()

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
    st.title("⚙️ Roster Management")
    all_p = get_player_stats()
    target_name = st.selectbox("Select Player to Manage", options=[""] + all_p['name'].tolist())
    
    if target_name:
        p_row = all_p[all_p['name'] == target_name].iloc[0]
        with st.form("edit_form"):
            new_aim = st.slider("Aim", 1.0, 10.0, float(p_row['aim']))
            new_util = st.slider("Util", 1.0, 10.0, float(p_row['util']))
            new_team = st.slider("Team Play", 1.0, 10.0, float(p_row['team_play']))
            if st.form_submit_button("💾 Save Changes"):
                conn = sqlite3.connect('cs2_history.db'); conn.execute("UPDATE players SET aim=?, util=?, team_play=? WHERE name=?", (new_aim, new_util, new_team, target_name)); conn.commit(); conn.close()
                st.success("Updated!"); time.sleep(1); st.rerun()
            if st.form_submit_button("🗑️ Remove Player"):
                conn = sqlite3.connect('cs2_history.db'); conn.execute("DELETE FROM players WHERE name=?", (target_name,)); conn.commit(); conn.close()
                st.warning("Deleted!"); time.sleep(1); st.rerun()
    st.divider()
    with st.form("add_form"):
        st.subheader("Add New Player")
        new_name = st.text_input("Player Name")
        a = st.slider("Aim Score", 1.0, 10.0, 5.0); u = st.slider("Util Score", 1.0, 10.0, 5.0); t = st.slider("Team Play Score", 1.0, 10.0, 5.0)
        if st.form_submit_button("➕ Add to Roster"):
            if new_name:
                conn = sqlite3.connect('cs2_history.db'); conn.execute("INSERT OR IGNORE INTO players (name, elo, aim, util, team_play) VALUES (?, 1200, ?, ?, ?)", (new_name, a, u, t)); conn.commit(); conn.close()
                st.success("Player Added!"); time.sleep(1); st.rerun()

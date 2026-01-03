# app.py
import streamlit as st
import random
import time
import sqlite3
import pandas as pd
import altair as alt  # Required for the bar chart
from streamlit_autorefresh import st_autorefresh
from constants import SKEEZ_TITLES, TEAM_NAMES, MAP_POOL, MAP_LOGOS
from database import init_db, get_player_stats, update_elo, set_draft_pins, submit_vote, get_vote_status, get_player_secret
from logic import get_best_combinations, pick_captains
from wheel import render_bench_wheel

# Initialize Database
init_db()

st.set_page_config(page_title="CS2 Pro Balancer", layout="centered")

# Custom CSS for styling
st.markdown("""
<style>
    [data-testid="stVerticalBlock"] h3 { min-height: 110px; display: flex; align-items: center; text-align: center; justify-content: center; font-size: 1.5rem !important; }
    [data-testid="stImage"] img { max-height: 120px; width: auto; margin: 0 auto; }
</style>
""", unsafe_allow_html=True)

# Initialize Essential Session States
if 'admin_authenticated' not in st.session_state: st.session_state.admin_authenticated = False
if 'teams_locked' not in st.session_state: st.session_state.teams_locked = False
if 'revealed' not in st.session_state: st.session_state.revealed = False
if 'veto_maps' not in st.session_state: st.session_state.veto_maps = MAP_POOL.copy()
if 'protected_maps' not in st.session_state: st.session_state.protected_maps = []
if 'turn' not in st.session_state: st.session_state.turn = None

tabs = st.tabs(["🎮 Mixer & Veto", "🎡 Bench Wheel", "🏆 Leaderboard", "📜 History", "⚙️ Admin"])

# --- TAB: MIXER & VETO ---
with tabs[0]:
    st.title("🎮 CS2 Draft & Veto")
    
    player_df = get_player_stats()
    current_sel = st.session_state.get("current_selection", [])
    st.write(f"**Players Selected:** `{len(current_sel)}/10`")
    
    selected = st.multiselect("Select 10 Players:", options=player_df['name'].tolist(), key="current_selection", label_visibility="collapsed")

    if len(selected) == 10:
        col1, col2 = st.columns(2)
        if col1.button("⚖️ Perfect Balance", use_container_width=True):
            all_combos = get_best_combinations(selected)
            st.session_state.final_teams = all_combos[0]
            st.session_state.assigned_names = random.sample(TEAM_NAMES, 2)
            st.session_state.teams_locked = True
            st.session_state.revealed = False
            if 'draft_pins' in st.session_state: del st.session_state.draft_pins
            if 'skeez_titles_session' in st.session_state: del st.session_state.skeez_titles_session
            st.rerun()
            
        if col2.button("🎲 Chaos Mode", use_container_width=True):
            all_combos = get_best_combinations(selected)
            # Pick a random combo from top 50 for variety
            ridx = random.randint(1, min(50, len(all_combos) - 1))
            st.session_state.final_teams = all_combos[ridx]
            st.session_state.assigned_names = random.sample(TEAM_NAMES, 2)
            st.session_state.teams_locked = True
            st.session_state.revealed = False
            if 'draft_pins' in st.session_state: del st.session_state.draft_pins
            if 'skeez_titles_session' in st.session_state: del st.session_state.skeez_titles_session
            st.rerun()

    if st.session_state.teams_locked:
        # 1. Sync Refresh (Starts only after reveal)
        if st.session_state.revealed:
            st_autorefresh(interval=3000, key="votedetector")

        t1, t2, avg1, avg2, _ = st.session_state.final_teams 
        name_a, name_b = st.session_state.assigned_names
        
        # Skill Calculations
        sum1 = round(avg1 * 5, 2)
        sum2 = round(avg2 * 5, 2)
        gap = round(abs(sum1 - sum2), 2)
        
        indicator_a = " ⭐ (Stronger)" if sum1 > sum2 else ""
        indicator_b = " ⭐ (Stronger)" if sum2 > sum1 else ""

        st.divider()
        c1, c2 = st.columns(2)
        with c1: 
            st.subheader(f"🟦 {name_a}")
            st.markdown(f"**Team Total: `{sum1}`{indicator_a}**")
            p1_holders = [st.empty() for _ in range(5)]
        with c2: 
            st.subheader(f"🟧 {name_b}")
            st.markdown(f"**Team Total: `{sum2}`{indicator_b}**")
            p2_holders = [st.empty() for _ in range(5)]

        if 'skeez_titles_session' not in st.session_state:
            st.session_state.skeez_titles_session = [random.choice(SKEEZ_TITLES) for _ in range(10)]

        # 2. Reveal Animation
        if not st.session_state.revealed:
            for i in range(5):
                time.sleep(0.4)
                title_a = st.session_state.skeez_titles_session[i]
                p1_holders[i].info(f"**{title_a} (Skeez)**" if t1[i] == "Skeez" else f"**{t1[i]}**")
                time.sleep(0.4)
                title_b = st.session_state.skeez_titles_session[i+5]
                p2_holders[i].warning(f"**{title_b} (Skeez)**" if t2[i] == "Skeez" else f"**{t2[i]}**")
            st.session_state.revealed = True
            st.rerun()
        else:
            for i in range(5):
                title_a = st.session_state.skeez_titles_session[i]
                p1_holders[i].info(f"**{title_a} (Skeez)**" if t1[i] == "Skeez" else f"**{t1[i]}**")
                title_b = st.session_state.skeez_titles_session[i+5]
                p2_holders[i].warning(f"**{title_b} (Skeez)**" if t2[i] == "Skeez" else f"**{t2[i]}**")

        st.markdown(f"<h3 style='text-align: center; color: #77dd77;'>Total Metric Gap: {gap}</h3>", unsafe_allow_html=True)
        
        # --- VISUAL POWER CHART ---
        chart_df = pd.DataFrame({
            'Team': [name_a, name_b],
            'Power': [sum1, sum2],
            'Color': ['#2C74B3', '#FF8B13'] 
        })
        chart = alt.Chart(chart_df).mark_bar().encode(
            x=alt.X('Power', scale=alt.Scale(domain=[0, max(sum1, sum2) * 1.15])),
            y=alt.Y('Team', sort=None, axis=alt.Axis(title=None)),
            color=alt.Color('Color', scale=None),
            tooltip=['Team', 'Power']
        ).properties(height=100)
        st.altair_chart(chart, use_container_width=True)
        # -------------------------------

        st.divider()

        # 3. SECRET WORD VOTING
        if st.session_state.revealed:
            if 'draft_pins' not in st.session_state:
                cap1, cap2 = pick_captains(t1, t2)
                w1, w2 = get_player_secret(cap1), get_player_secret(cap2)
                st.session_state.draft_pins = {cap1: w1, cap2: w2}
                set_draft_pins(cap1, w1, cap2, w2)

            st.subheader("🕵️ Captains' Secret Vote")
            caps = list(st.session_state.draft_pins.keys())
            st.info(f"Captains: **{caps[0]}** and **{caps[1]}**")
            
            with st.expander("🔑 Open Voting Portal"):
                in_secret = st.text_input("Enter your Secret Word", type="password", key="v_secret")
                vcol1, vcol2 = st.columns(2)
                if vcol1.button("✅ Approve Draft", use_container_width=True):
                    if submit_vote(in_secret, "Approve"): st.success("Vote cast!"); time.sleep(1); st.rerun()
                if vcol2.button("❌ Request Reroll", use_container_width=True):
                    if submit_vote(in_secret, "Reroll"): st.warning("Reroll requested!"); time.sleep(1); st.rerun()

            v_df = get_vote_status()
            if not v_df.empty:
                v1, v2 = v_df.iloc[0]['vote'], v_df.iloc[1]['vote']
                s1, s2 = st.columns(2)
                s1.metric(f"Captain: {v_df.iloc[0]['captain_name']}", "READY" if v1 != "Waiting" else "THINKING...")
                s2.metric(f"Captain: {v_df.iloc[1]['captain_name']}", "READY" if v2 != "Waiting" else "THINKING...")

                if v1 != "Waiting" and v2 != "Waiting":
                    if v1 == "Approve" and v2 == "Approve":
                        st.success("🎉 Teams Approved! Proceed to Map Veto.")
                        
                        # --- MAP VETO SYSTEM ---
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
                        st.error("🚨 A Reroll was requested. Randomizing new teams...")
                        time.sleep(2)
                        del st.session_state.draft_pins
                        del st.session_state.skeez_titles_session
                        st.session_state.revealed = False
                        all_combos = get_best_combinations(selected)
                        st.session_state.final_teams = all_combos[random.randint(1, min(50, len(all_combos)-1))]
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
    if not st.session_state.admin_authenticated:
        st.title("🔐 Admin Login")
        pwd_input = st.text_input("Enter Admin Password", type="password")
        if st.button("Unlock Management"):
            if pwd_input == "An25671527!":
                st.session_state.admin_authenticated = True
                st.success("Access Granted")
                st.rerun()
            else:
                st.error("Incorrect Password")
    else:
        st.title("⚙️ Roster Management")
        if st.button("Logout Admin"):
            st.session_state.admin_authenticated = False
            st.rerun()
            
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

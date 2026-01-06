# views/bench.py
import streamlit as st
import random
from wheel import render_bench_wheel

def render_bench_tab(player_df):
    if "wheel_players" not in st.session_state:
        if st.session_state.get("teams_locked") and st.session_state.get("final_teams"):
            t1, t2, _, _, _ = st.session_state.final_teams
            st.session_state.wheel_players = t1 + t2
        elif "current_selection" in st.session_state and st.session_state.current_selection:
            st.session_state.wheel_players = list(st.session_state.current_selection)
        else:
            st.session_state.wheel_players = player_df['name'].tolist()

    if "winner_label" not in st.session_state:
        st.session_state.winner_label = "Winner"

    st.markdown("### 🎡 Bench Wheel Settings")
    st.session_state.winner_label = st.text_input("Winner Text Label", value="nik el bank")
    
    current_pool = st.session_state.wheel_players
    target_win = None
    
    if st.button("🎡 SPIN & REMOVE", use_container_width=True, type="primary"):
        if current_pool:
            winner = random.choice(current_pool)
            target_win = winner
            st.session_state.last_spin_pool = list(current_pool)
            st.session_state.last_spin_target = winner
            st.session_state.wheel_players.remove(winner)
        else:
            st.warning("No players left in the wheel!")

    if st.button("Reset to Current Draft"):
        if st.session_state.get("teams_locked") and st.session_state.get("final_teams"):
            t1, t2, _, _, _ = st.session_state.final_teams
            st.session_state.wheel_players = t1 + t2
            if "last_spin_pool" in st.session_state: del st.session_state.last_spin_pool
            if "last_spin_target" in st.session_state: del st.session_state.last_spin_target
        else:
            st.warning("No active draft found.")
        st.rerun()

    col_add1, col_add2 = st.columns([3, 1])
    new_p = col_add1.text_input("Add Player Name", key="new_wheel_player")
    if col_add2.button("Add"):
        if new_p and new_p not in st.session_state.wheel_players:
            st.session_state.wheel_players.append(new_p)
            st.rerun()

    to_remove = st.multiselect("Remove Players", st.session_state.wheel_players)
    if to_remove:
        if st.button("Remove Selected"):
            st.session_state.wheel_players = [p for p in st.session_state.wheel_players if p not in to_remove]
            st.rerun()

    st.divider()
    
    if "last_spin_target" in st.session_state and st.session_state.last_spin_target:
        render_bench_wheel(st.session_state.last_spin_pool, 
                           winner_label=st.session_state.winner_label, 
                           target_winner=st.session_state.last_spin_target)
        st.caption(f"Players remaining: {len(st.session_state.wheel_players)}")
    else:
        render_bench_wheel(st.session_state.wheel_players, winner_label=st.session_state.winner_label)

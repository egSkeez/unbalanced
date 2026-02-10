# app.py
import streamlit as st
import random
from database import init_db, get_player_stats, save_draft_state, load_draft_state, clear_draft_state, get_roommates, get_vote_status
from cybershoke import init_cybershoke_db
from logic import get_best_combinations
from utils import render_custom_css
# Import Views
from views.mobile import render_mobile_vote_page
from views.mixer import render_mixer_tab
from views.bench import render_bench_tab
from views.history import render_history_tab
from views.admin import render_admin_tab
from views.stats import render_stats_tab
from views.trophies import render_trophies_tab

# --- MAIN ENTRY POINT ---
# ROOMMATES config is now dynamic via get_roommates()

if "vote_token" in st.query_params:
    render_mobile_vote_page(st.query_params["vote_token"])
    st.stop() 

init_db()
init_cybershoke_db()

# Initialize match statistics tables
from match_stats_db import init_match_stats_tables
from migrate_ratings import check_and_migrate
init_match_stats_tables()
check_and_migrate()

# Initialize match registry
from match_registry import init_match_registry
init_match_registry()

st.set_page_config(page_title="CS2 Pro Balancer", layout="centered")
render_custom_css()

player_df = get_player_stats()

# --- INITIALIZE SESSION STATE ---
if "admin_user" in st.query_params:
    st.session_state.admin_authenticated = True
    st.session_state.admin_user = st.query_params["admin_user"]
if 'admin_authenticated' not in st.session_state: st.session_state.admin_authenticated = False
if 'admin_user' not in st.session_state: st.session_state.admin_user = None
if 'teams_locked' not in st.session_state: st.session_state.teams_locked = False
if 'revealed' not in st.session_state: st.session_state.revealed = False
if 'global_map_pick' not in st.session_state: st.session_state.global_map_pick = None
if 'maps_sent_to_discord' not in st.session_state: st.session_state.maps_sent_to_discord = False

# REROLL LOGIC (Moved to main app because it affects session state heavily)
if st.session_state.get("trigger_reroll", False):
    st.session_state.trigger_reroll = False
    current_players = [p for p in player_df['name'] if p in st.session_state.get("current_selection", [])]
    if not current_players:
         t1, t2, _, _, _ = st.session_state.final_teams
         current_players = t1 + t2
    score_map = dict(zip(player_df['name'], player_df['overall']))
    
    # Force split existing captains if they exist
    force_captains = []
    if "draft_pins" in st.session_state and st.session_state.draft_pins:
        force_captains = list(st.session_state.draft_pins.keys())

    metric = "avg_kd" if st.session_state.get("draft_mode") == "kd_balanced" else "overall"
    roommates = get_roommates()
    all_combos = get_best_combinations(current_players, force_split=force_captains, force_together=roommates, metric=metric)
    ridx = random.randint(1, min(50, len(all_combos) - 1))
    nt1, nt2, na1, na2, ngap = all_combos[ridx]
    save_draft_state(nt1, nt2, st.session_state.assigned_names[0], st.session_state.assigned_names[1], na1, na2, mode=st.session_state.get("draft_mode", "balanced"))
    st.session_state.final_teams = all_combos[ridx]
    st.session_state.revealed = False
    st.session_state.maps_sent_to_discord = False
    st.rerun()

# CHECK DB STATE
if 'teams_locked' not in st.session_state or not st.session_state.teams_locked:
    saved_draft = load_draft_state()
    if saved_draft:
        t1, t2, n_a, n_b, a1, a2, db_map, _, _, mode = saved_draft
        st.session_state.final_teams = (t1, t2, a1, a2, 0)
        st.session_state.assigned_names = (n_a, n_b)
        st.session_state.teams_locked = True
        st.session_state.revealed = True
        if db_map: st.session_state.global_map_pick = db_map
        st.session_state.draft_mode = mode
        
        # RESTORE PINS IF MISSING (e.g. Refresh)
        if 'draft_pins' not in st.session_state:
            v_df = get_vote_status()
            if not v_df.empty:
                # Ensure unique captains only (though DB ensures primary key)
                st.session_state.draft_pins = dict(zip(v_df['captain_name'], v_df['pin']))

if st.session_state.get("veto_complete_trigger", False):
    st.session_state.veto_complete_trigger = False
    saved = load_draft_state()
    if saved: st.session_state.global_map_pick = saved[6]
    st.rerun()

# --- TABS ---
tabs = st.tabs(["🎮 Mixer & Veto", "🎡 Bench Wheel", "📜 History", "📊 Stats", "🏆 Trophies", "⚙️ Admin"])

with tabs[0]:
    render_mixer_tab(player_df)

with tabs[1]:
    render_bench_tab(player_df)

with tabs[2]:
    render_history_tab()

with tabs[3]:
    render_stats_tab()

with tabs[4]:
    render_trophies_tab()

with tabs[5]:
    render_admin_tab()

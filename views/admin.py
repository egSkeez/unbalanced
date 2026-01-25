# views/admin.py
import streamlit as st
import sqlite3
import time
from database import get_player_stats, clear_draft_state, load_draft_state
from cybershoke import get_lobby_link, set_lobby_link, clear_lobby_link, create_cybershoke_lobby_api
from discord_bot import send_full_match_info, send_lobby_to_discord
from demo_download import download_demo
from demo_analysis import analyze_demo_file
from match_stats_db import save_match_stats
import os

def render_admin_tab():
    # Ensure session state keys exist to prevent KeyErrors
    if 'admin_authenticated' not in st.session_state:
        st.session_state.admin_authenticated = False
    if 'admin_user' not in st.session_state:
        st.session_state.admin_user = None

    # Logic
    if not st.session_state.admin_authenticated:
        st.title("🔐 Admin Login")
        with st.form("admin_login_form"):
            st.write("Please log in to access admin tools.")
            admin_user = st.selectbox("Who are you?", ["Skeez", "Ghoufa", "Kim"])
            pwd_input = st.text_input("Enter Admin Password", type="password")
            
            if st.form_submit_button("Login"):
                if (admin_user=="Skeez" and pwd_input=="2567") or \
                   (admin_user=="Ghoufa" and pwd_input=="ghoufa123") or \
                   (admin_user=="Kim" and pwd_input=="kim123"):
                    st.session_state.admin_authenticated = True
                    st.session_state.admin_user = admin_user
                    # Add to query params to persist refresh
                    st.query_params["admin_user"] = admin_user
                    st.rerun()
                else:
                    st.error("Incorrect Password")
    else:
        st.title(f"⚙️ Management ({st.session_state.admin_user})")
        
        col_logout, _ = st.columns([1, 4])
        if col_logout.button("Logout"):
            st.session_state.admin_authenticated = False
            st.session_state.admin_user = None
            st.query_params.clear()
            st.rerun()

        # Tabs for better organization
        tab_lobby, tab_queue, tab_demos, tab_players, tab_danger = st.tabs([
            "🚀 Lobby", "🔄 Match Queue", "🎥 Demo Analyzer", "👥 Players", "⚠️ Danger Zone"
        ])

        # --- Tab 1: Lobby & Session ---
        with tab_lobby:
            st.subheader("Session & Lobby")
            curr_link, _ = get_lobby_link() # Unpack tuple (link, id)
            
            # --- ROW 1: Manual Link Management ---
            col_l1, col_l2 = st.columns([3, 1])
            with col_l1:
                admin_link_in = st.text_input("Set Server Link", value=curr_link if curr_link else "", key="admin_lobby_input")
            with col_l2:
                if st.button("✅ Save Link", use_container_width=True):
                    set_lobby_link(admin_link_in)
                    st.success("Link saved!")
                    time.sleep(1); st.rerun()

            st.markdown("---")
            
            # --- ROW 2: Cybershoke Actions ---
            st.subheader("🤖 Cybershoke Integration")
            
            col_cs1, col_cs2 = st.columns(2)
            
            with col_cs1:
                st.write("**Server Actions**")
                if st.button("⚡ Create NEW Cybershoke Lobby", type="primary", use_container_width=True):
                     with st.spinner("Talking to Cybershoke API..."):
                         new_link, new_id = create_cybershoke_lobby_api(admin_name=st.session_state.admin_user)
                         if new_link:
                             set_lobby_link(new_link, new_id)
                             st.success(f"Lobby Created! ID: {new_id}")
                             time.sleep(1); st.rerun()
                         else:
                             st.error("Failed to create lobby. Check API/Cookies.")

            with col_cs2:
                st.write("**Discord Broadcast**")
                
                # Button 1: Send Lobby Only
                if st.button("🔗 Send LOBBY to Discord", use_container_width=True):
                    if curr_link:
                        send_lobby_to_discord(curr_link)
                        st.success("Sent lobby link to Discord!")
                    else:
                        st.error("No lobby link set!")

                # Button 2: Send Full Draft
                if st.button("📢 Send DRAFT to Discord", use_container_width=True):
                    # Try to retrieve draft state
                    state = load_draft_state() # (t1, t2, na, nb, avg1, avg2, map, lobby, mid)
                    if state:
                        t1, t2, na, nb, _, _, current_map, s_lobby, _ = state
                        # Ensure we use the current lobby link from DB/Input
                        s_lobby = curr_link 
                        
                        # Maps string handling
                        maps_to_send = current_map if current_map else "Unknown"
                        
                        send_full_match_info(na, t1, nb, t2, maps_to_send, s_lobby)
                        st.success("Sent full match info to Discord!")
                    else:
                        st.error("No active draft found in database!")

        # --- Tab 2: Match Queue Processor ---
        with tab_queue:
            st.subheader("Match Queue Processor")
        
            # Imports for this section
            from match_registry import add_match_to_registry, get_pending_matches, get_recent_registry_entries, get_match_status
            from match_processor import process_match_queue

            col_q1, col_q2 = st.columns([2, 1])
            
            with col_q1:
                new_queue_id = st.text_input("Add Match ID to Queue", placeholder="e.g. 5394408")
                if st.button("➕ Add to Queue"):
                    if new_queue_id.strip():
                        curr_status = get_match_status(new_queue_id)
                        if curr_status:
                            st.error(f"Match {new_queue_id} already exists (Status: {curr_status})")
                        else:
                            if add_match_to_registry(new_queue_id, source="manual_admin"):
                                st.success(f"Added {new_queue_id} to queue!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Failed to add match.")
                    else:
                        st.warning("Please enter an ID.")

            with col_q2:
                pending = get_pending_matches()
                st.metric("Pending Matches", len(pending))
                
                if st.button("🔄 Process All Pending", type="primary", disabled=(len(pending)==0)):
                    with st.spinner("Processing queue..."):
                        summary, logs = process_match_queue(admin_name=st.session_state.admin_user)
                        st.success(summary)
                        if logs:
                            with st.expander("Processing Logs", expanded=True):
                                for log in logs:
                                    st.write(log)
                        time.sleep(2)
                        st.rerun()

            # Status Table
            st.write("Recent Activity:")
            recent_df = get_recent_registry_entries(10)
            st.dataframe(recent_df, use_container_width=True, hide_index=True)

        # --- Tab 3: Match Demos ---
        with tab_demos:
            st.subheader("Match Demos")
            # Default match ID from lobby link if possible
            # Re-fetch curr_link here or just use it (it hasn't changed unless broadcasted in other tab, forcing rerun)
            curr_link_demo = get_lobby_link()
            default_mid = "5394408"
            if curr_link_demo and "match/" in curr_link_demo:
                try:
                    default_mid = curr_link_demo.split("match/")[1].split("/")[0]
                except:
                    pass
            
            demo_mid = st.text_input("Match ID", value=default_mid)
            
            manual_url = st.text_input("Manual Demo URL (Optional - if auto fails)", help="Right click 'Download Demo' on Cybershoke and paste link here")
            
            if st.button("⬇️ Download & Analyze"):
                with st.spinner("Processing... This may take a minute..."):
                    # 1. Download
                    target_url = manual_url if manual_url.strip() else None
                    success, msg = download_demo(demo_mid, st.session_state.admin_user, direct_url=target_url)
                    
                    if success:
                        st.success(msg)
                        # 2. Automatically Analyze
                        st.info("Parsing match statistics...")
                        expected_filename = f"demos/match_{demo_mid}.dem"
                        if os.path.exists(expected_filename):
                            try:
                                score_res, stats_res, map_name, score_t, score_ct = analyze_demo_file(expected_filename)
                                if stats_res is not None:
                                    # Save to database
                                    match_id = f"match_{demo_mid}"
                                    save_match_stats(match_id, demo_mid, score_res, stats_res, map_name, score_t, score_ct)
                                    
                                    # Display match header
                                    st.subheader(f"📍 {map_name} | {score_res}")
                                    st.dataframe(stats_res, use_container_width=True, hide_index=True)
                                    st.success("✅ Statistics saved to database!")
                                    
                                    # Store in session state to persist
                                    st.session_state['last_stats_score'] = score_res
                                    st.session_state['last_stats_df'] = stats_res
                                    st.session_state['last_stats_map'] = map_name
                                else:
                                    st.error(f"Analysis failed: {score_res}")
                            finally:
                                # Cleanup demo file
                                if os.path.exists(expected_filename):
                                    os.remove(expected_filename)
                                    st.toast(f"Deleted temporary demo file: {expected_filename}")
                    else:
                        st.error(msg)
            
            # Persist display if available
            if 'last_stats_df' in st.session_state:
                 st.divider()
                 map_name = st.session_state.get('last_stats_map', 'Unknown')
                 st.subheader(f"📍 {map_name} | {st.session_state.get('last_stats_score', '')}")
                 st.dataframe(st.session_state['last_stats_df'], use_container_width=True, hide_index=True)
                 
                 if st.button("Clear Results"):
                     del st.session_state['last_stats_df']
                     del st.session_state['last_stats_score']
                     if 'last_stats_map' in st.session_state:
                         del st.session_state['last_stats_map']
                     st.rerun()

        # --- Tab 4: Player Management ---
        with tab_players:
            st.subheader("Player Roster")
            try:
                df = get_player_stats()
                st.dataframe(df[['name', 'avg_kd', 'aim', 'util', 'team_play', 'W', 'D', 'Winrate', 'overall']], use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"Error loading player stats: {e}")
            
            st.divider()
            st.subheader("Player Editor")
            all_p = get_player_stats()
            target_name = st.selectbox("Select Player to Edit", [""] + all_p['name'].tolist())
            
            if target_name:
                p_row = all_p[all_p['name'] == target_name].iloc[0]
                with st.form("edit_form"):
                    st.write(f"Editing: **{target_name}**")
                    new_aim = st.slider("Aim", 1.0, 10.0, float(p_row['aim']))
                    new_util = st.slider("Util", 1.0, 10.0, float(p_row['util']))
                    new_team = st.slider("Team Play", 1.0, 10.0, float(p_row['team_play']))
                    
                    if st.form_submit_button("💾 Save Changes"):
                        conn = sqlite3.connect('cs2_history.db')
                        conn.execute("UPDATE players SET aim=?, util=?, team_play=? WHERE name=?", (new_aim, new_util, new_team, target_name))
                        conn.commit()
                        conn.close()
                        st.success("Saved!")
                        time.sleep(1)
                        st.rerun()
                
                if st.button("🗑️ Delete Player"):
                    conn = sqlite3.connect('cs2_history.db')
                    conn.execute("DELETE FROM players WHERE name=?", (target_name,))
                    conn.commit()
                    conn.close()
                    st.warning(f"Deleted {target_name}")
                    time.sleep(1)
                    st.rerun()
            
            with st.form("add_form"):
                st.write("Add New Player")
                n_name = st.text_input("Name")
                n_a = st.slider("Aim", 1.0, 10.0, 5.0)
                n_u = st.slider("Util", 1.0, 10.0, 5.0)
                n_t = st.slider("Team", 1.0, 10.0, 5.0)
                
                if st.form_submit_button("➕ Add Player"):
                    if n_name:
                        conn = sqlite3.connect('cs2_history.db')
                        # ELO column still exists in DB but we don't use it anymore, default to 1200
                        conn.execute("INSERT OR IGNORE INTO players (name, elo, aim, util, team_play, secret_word) VALUES (?, 1200, ?, ?, ?, ?)", (n_name, n_a, n_u, n_t, "cs2pro"))
                        conn.commit()
                        conn.close()
                        st.success(f"Added {n_name}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Name is required.")

        # --- Tab 5: Danger Zone ---
        with tab_danger:
            st.subheader("Danger Zone")
            if st.button("🛑 RESET WHOLE SESSION", type="primary"):
                clear_draft_state()
                clear_lobby_link()
                st.session_state.clear()
                st.session_state.maps_sent_to_discord = False
                st.rerun()

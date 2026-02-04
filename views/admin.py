# views/admin.py
import streamlit as st
import sqlite3
import time
from database import get_player_stats, clear_draft_state, load_draft_state, get_roommates, set_roommates
from cybershoke import get_lobby_link, set_lobby_link, clear_lobby_link, create_cybershoke_lobby_api
from discord_bot import send_full_match_info, send_lobby_to_discord
from demo_download import download_demo
from demo_analysis import analyze_demo_file
from match_stats_db import save_match_stats, get_all_lobbies, update_lobby_status, add_lobby
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
        tab_lobby, tab_history_admin, tab_queue, tab_demos, tab_players, tab_danger = st.tabs([
            "🚀 Lobby", "📜 Lobby History", "🔄 Match Queue", "🎥 Demo Analyzer", "👥 Players", "⚠️ Danger Zone"
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
                    state = load_draft_state() # (t1, t2, na, nb, avg1, avg2, map, lobby, mid, mode)
                    if state:
                        t1, t2, na, nb, _, _, current_map, s_lobby, _, _ = state
                        # Ensure we use the current lobby link from DB/Input
                        s_lobby = curr_link 
                        
                        # Maps string handling
                        maps_to_send = current_map if current_map else "Unknown"
                        
                        send_full_match_info(na, t1, nb, t2, maps_to_send, s_lobby)
                        st.success("Sent full match info to Discord!")
                    else:
                        st.error("No active draft found in database!")

            st.markdown("---")
            st.markdown("---")
            st.subheader("👯 Roommates (Force Together)")
            st.info("Define groups of players who MUST be on the same team (e.g. they are in the same room). You can have multiple separate groups.")
            
            raw_roommates = get_roommates()
            # Normalize to list of lists for UI handling
            roommate_groups = []
            if raw_roommates:
                if isinstance(raw_roommates[0], list):
                    roommate_groups = raw_roommates
                else: 
                    # Legacy: single list
                    roommate_groups = [raw_roommates]
            
            try:
                p_stats = get_player_stats()
                all_players_list = p_stats['name'].tolist()
            except:
                all_players_list = []

            # Display Existing Groups
            groups_to_keep = []
            updated = False
            
            if roommate_groups:
                st.write("**Active Groups:**")
                for i, group in enumerate(roommate_groups):
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        st.code(f"Group {i+1}: {', '.join(group)}")
                    with c2:
                        if st.button("🗑️", key=f"del_g_{i}", help="Remove this group"):
                            updated = True
                        else:
                            groups_to_keep.append(group)
            
            if updated:
                set_roommates(groups_to_keep)
                st.rerun()

            # Add New Group
            with st.expander("➕ Add New Roommate Group"):
                new_group = st.multiselect(
                    "Select players for this group:",
                    options=all_players_list,
                    key="new_rm_group"
                )
                
                if st.button("Add Group"):
                    if len(new_group) >= 2:
                        # Check for duplicates? For now, just allow it, logic handles it.
                        groups_to_keep.append(new_group)
                        set_roommates(groups_to_keep)
                        st.success("Group Added!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.warning("Select at least 2 players.")


        # --- Tab 1.5: Lobby History ---
        with tab_history_admin:
            st.subheader("📜 Cybershoke Lobby History")
            
            # Refresh button
            if st.button("🔄 Refresh History"):
                st.rerun()

            all_lobbies = get_all_lobbies()
            
            if not all_lobbies.empty:
                # Display Summary
                st.dataframe(all_lobbies, use_container_width=True, hide_index=True)
                
                st.divider()
                st.subheader("🛠️ Management")
                
                # Action Selection
                selected_lobby = st.selectbox("Select Lobby to Manage", all_lobbies['lobby_id'].tolist())
                
                if selected_lobby:
                    row = all_lobbies[all_lobbies['lobby_id'] == str(selected_lobby)].iloc[0]
                    st.info(f"Selected: **{selected_lobby}** | Created: {row['created_at']} | Status: {row['analysis_status']}")
                    
                    col_h1, col_h2, col_h3 = st.columns(3)
                    
                    with col_h1:
                        if st.button("📥 Download & Analyze", type="primary", use_container_width=True):
                             with st.spinner(f"Processing Lobby {selected_lobby}..."):
                                 # 1. Download
                                 success, msg = download_demo(str(selected_lobby), st.session_state.admin_user)
                                 
                                 if success:
                                     # 2. Analyze
                                     expected_filename = f"demos/match_{selected_lobby}.dem"
                                     if os.path.exists(expected_filename):
                                         try:
                                             st.text("Analyzing demo file...")
                                             score_res, stats_res, map_name, score_t, score_ct = analyze_demo_file(expected_filename)
                                             
                                             if stats_res is not None:
                                                 # Save stats
                                                 match_id = f"match_{selected_lobby}"
                                                 save_match_stats(match_id, str(selected_lobby), score_res, stats_res, map_name, score_t, score_ct)
                                                 
                                                 # Update Lobby Status
                                                 update_lobby_status(selected_lobby, has_demo=1, status='analyzed')
                                                 
                                                 st.success(f"Analyzed & Saved! Result: {score_res}")
                                             else:
                                                  st.error("Analysis failed (parse error).")
                                                  update_lobby_status(selected_lobby, status='error')
                                         except Exception as e:
                                             st.error(f"Error during analysis: {e}")
                                             update_lobby_status(selected_lobby, status='error')
                                         finally:
                                             if os.path.exists(expected_filename):
                                                 os.remove(expected_filename)
                                     else:
                                         st.error("Demo file not found after download reported success.")
                                 else:
                                     st.error(f"Download failed: {msg}")
                                 
                                 time.sleep(2)
                                 st.rerun()

                    with col_h2:
                        if st.button("🚫 Mark 'No Demo'", use_container_width=True):
                            update_lobby_status(selected_lobby, has_demo=-1, status='no_demo')
                            st.success("Marked as having no demo.")
                            time.sleep(1)
                            st.rerun()
                            
                    with col_h3:
                        if st.button("📝 Add New ID Manually", use_container_width=True):
                            # Opens expando/input below ? Or just use a text input nearby
                            pass # Handled by separate input block below
            else:
                st.info("No lobbies recorded yet.")

            st.divider()
            with st.expander("Manually Track a Lobby ID"):
                man_id = st.text_input("Enter Cybershoke Lobby ID (numbers only)")
                if st.button("Add to History"):
                    if man_id.strip():
                        add_lobby(man_id.strip())
                        st.success(f"Added {man_id}")
                        time.sleep(1)
                        st.rerun()

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
            
            col_d1, col_d2, col_d3 = st.columns(3)
            
            with col_d1:
                if st.button("🌐 Web Analysis via Lobby URL", use_container_width=True):
                    with st.spinner("Fetching stats from Cybershoke Web..."):
                        from cybershoke import get_lobby_player_stats
                        web_stats, web_score, web_map = get_lobby_player_stats(demo_mid)
                        
                        if web_stats:
                            # Create a rich DataFrame from the web stats
                            w_data = []
                            for p, details in web_stats.items():
                                k = details['kills']
                                d = details['deaths']
                                a = details['assists']
                                hs = details['headshots']
                                
                                kd = k / d if d > 0 else k
                                hs_p = (hs / k * 100) if k > 0 else 0
                                score_val = k*2 + a # Simple scoring
                                
                                w_data.append({
                                    "Player": p, 
                                    "Kills": k, 
                                    "Deaths": d, 
                                    "Assists": a, 
                                    "K/D": round(kd, 2), 
                                    "Score": score_val, 
                                    "HS%": round(hs_p, 1), 
                                    "ADR": 0 # Not available from web
                                })
                            
                            import pandas as pd
                            res_df = pd.DataFrame(w_data).sort_values("Score", ascending=False)
                            
                            # Save simple stats
                            match_id = f"match_{demo_mid}"
                            # We can use the web_score (e.g. 13 - 5) for storage
                            try:
                                t_s = int(web_score.split("-")[0].strip())
                                ct_s = int(web_score.split("-")[1].strip())
                            except:
                                t_s, ct_s = 0, 0
                                
                            save_match_stats(match_id, demo_mid, web_score, res_df, web_map, t_s, ct_s)
                            
                            st.success(f"Fetched stats from Web! ({web_score})")
                            st.session_state['last_stats_score'] = web_score
                            st.session_state['last_stats_df'] = res_df
                            st.session_state['last_stats_map'] = web_map
                            st.rerun()
                        else:
                            st.error("Could not fetch web stats. Check ID or Cookies.")

            with col_d2:
                if st.button("🎥 Demo Analysis (File Only)", use_container_width=True):
                    with st.spinner("Downloading & Analyzing Demo..."):
                        # Logic: Download -> Analyze -> Save (No Verification)
                        target_url = manual_url if manual_url.strip() else None
                        success, msg = download_demo(demo_mid, st.session_state.admin_user, direct_url=target_url)
                        
                        if success:
                            expected_filename = f"demos/match_{demo_mid}.dem"
                            if os.path.exists(expected_filename):
                                try:
                                    score_res, stats_res, map_name, score_t, score_ct = analyze_demo_file(expected_filename)
                                    if stats_res is not None:
                                        match_id = f"match_{demo_mid}"
                                        save_match_stats(match_id, demo_mid, score_res, stats_res, map_name, score_t, score_ct)
                                        
                                        st.success("Analyzed Demo Successfully!")
                                        st.session_state['last_stats_score'] = score_res
                                        st.session_state['last_stats_df'] = stats_res
                                        st.session_state['last_stats_map'] = map_name
                                        st.rerun()
                                    else:
                                        st.error(f"Analysis failed: {score_res}")
                                finally:
                                    if os.path.exists(expected_filename):
                                        os.remove(expected_filename)
                        else:
                            st.error(msg)
            
            with col_d3:
                if st.button("⚡ Full Analysis (Web + Demo)", type="primary", use_container_width=True):
                    with st.spinner("Running Full Analysis & Verification..."):
                         # Logic: Download -> Analyze -> Overwrite Key Stats with Web -> Save
                        target_url = manual_url if manual_url.strip() else None
                        dl_success, dl_msg = download_demo(demo_mid, st.session_state.admin_user, direct_url=target_url)
                        
                        if dl_success:
                            expected_filename = f"demos/match_{demo_mid}.dem"
                            if os.path.exists(expected_filename):
                                try:
                                    # 1. Analyze Demo (for ADR, Utility, Entry, etc.)
                                    score_res, stats_res, map_name, score_t, score_ct = analyze_demo_file(expected_filename)
                                    
                                    if stats_res is not None:
                                        # 2. Fetch Web Stats (Source of Truth for K/D/A/HS/Score)
                                        from cybershoke import get_lobby_player_stats
                                        web_stats, w_score, w_map = get_lobby_player_stats(demo_mid)
                                        
                                        overWrittenCount = 0
                                        if web_stats:
                                            # Prioritize Web Score/Map
                                            if w_score and w_score != "Unknown":
                                                score_res = w_score
                                                try:
                                                    score_t = int(w_score.split("-")[0].strip())
                                                    score_ct = int(w_score.split("-")[1].strip())
                                                except:
                                                    pass
                                            if w_map and w_map != "Unknown":
                                                map_name = w_map

                                            # Overwrite Stats
                                            for index, row in stats_res.iterrows():
                                                p_name = row['Player']
                                                if p_name in web_stats:
                                                    w_det = web_stats[p_name]
                                                    
                                                    # Force values from Web
                                                    stats_res.at[index, 'Kills'] = w_det['kills']
                                                    stats_res.at[index, 'Deaths'] = w_det['deaths']
                                                    stats_res.at[index, 'Assists'] = w_det['assists']
                                                    stats_res.at[index, 'Headshots'] = w_det['headshots']
                                                    
                                                    # Recalculate derived
                                                    new_k = w_det['kills']
                                                    new_d = w_det['deaths']
                                                    new_hs = w_det['headshots']
                                                    
                                                    stats_res.at[index, 'K/D'] = round(new_k / new_d, 2) if new_d > 0 else new_k
                                                    stats_res.at[index, 'HS%'] = round((new_hs / new_k * 100), 1) if new_k > 0 else 0
                                                    
                                                    overWrittenCount += 1
                                            
                                            st.toast(f"Updated stats for {overWrittenCount} players using Web Data")
                                        
                                        # 3. Save
                                        match_id = f"match_{demo_mid}"
                                        save_match_stats(match_id, demo_mid, score_res, stats_res, map_name, score_t, score_ct)
                                        
                                        st.success("✅ Full Analysis Complete (Web Data Prioritized)!")
                                        st.session_state['last_stats_score'] = score_res
                                        st.session_state['last_stats_df'] = stats_res
                                        st.session_state['last_stats_map'] = map_name
                                        st.rerun()
                                    else:
                                        st.error(f"Analysis failed: {score_res}")
                                finally:
                                     if os.path.exists(expected_filename):
                                        os.remove(expected_filename)
                        else:
                            st.error(dl_msg)
            
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

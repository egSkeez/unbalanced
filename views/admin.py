# views/admin.py
import streamlit as st
import sqlite3
import time
from database import get_player_stats, clear_draft_state
from cybershoke import get_lobby_link, set_lobby_link, clear_lobby_link

def render_admin_tab():
    if not st.session_state.admin_authenticated:
        st.title("🔐 Admin Login")
        with st.form("admin_login_form"):
            admin_user = st.selectbox("Who are you?", ["Skeez", "Ghoufa", "Kim"])
            pwd_input = st.text_input("Enter Admin Password", type="password")
            if st.form_submit_button("Login"):
                if (admin_user=="Skeez" and pwd_input=="2567") or (admin_user=="Ghoufa" and pwd_input=="ghoufa123") or (admin_user=="Kim" and pwd_input=="kim123"):
                    st.session_state.admin_authenticated = True
                    st.session_state.admin_user = admin_user
                    st.query_params["admin_user"] = admin_user
                    st.rerun()
                else: st.error("Incorrect Password")
    else:
        st.title(f"⚙️ Management ({st.session_state.admin_user})")
        if st.button("Logout"):
            st.session_state.admin_authenticated = False
            st.query_params.clear()
            st.rerun()

        st.subheader("📊 Player Roster")
        st.dataframe(get_player_stats()[['name', 'elo', 'aim', 'util', 'team_play', 'W', 'D', 'overall']], use_container_width=True, hide_index=True)
        
        st.subheader("🚀 Session & Lobby")
        curr_link = get_lobby_link()
        admin_link_in = st.text_input("Set Server Link", value=curr_link if curr_link else "")
        if st.button("✅ Broadcast Link"):
            set_lobby_link(admin_link_in)
            st.success("Done!")
        
        st.divider()
        st.subheader("⚠️ Danger Zone")
        if st.button("🛑 RESET WHOLE SESSION", type="primary"):
            clear_draft_state()
            clear_lobby_link()
            st.session_state.clear()
            st.session_state.maps_sent_to_discord = False
            st.rerun()

        st.divider()
        st.subheader("📝 Player Editor")
        all_p = get_player_stats()
        target_name = st.selectbox("Select Player", [""] + all_p['name'].tolist())
        if target_name:
            p_row = all_p[all_p['name'] == target_name].iloc[0]
            with st.form("edit_form"):
                new_aim = st.slider("Aim", 1.0, 10.0, float(p_row['aim']))
                new_util = st.slider("Util", 1.0, 10.0, float(p_row['util']))
                new_team = st.slider("Team Play", 1.0, 10.0, float(p_row['team_play']))
                if st.form_submit_button("💾 Save"):
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
                st.rerun()
        
        with st.form("add_form"):
            st.write("Add New Player")
            n_name = st.text_input("Name")
            n_a = st.slider("Aim",1.0,10.0,5.0)
            n_u = st.slider("Util",1.0,10.0,5.0)
            n_t = st.slider("Team",1.0,10.0,5.0)
            if st.form_submit_button("➕ Add"):
                conn = sqlite3.connect('cs2_history.db')
                conn.execute("INSERT OR IGNORE INTO players (name, elo, aim, util, team_play, secret_word) VALUES (?, 1200, ?, ?, ?, ?)", (n_name, n_a, n_u, n_t, "cs2pro"))
                conn.commit()
                conn.close()
                st.rerun()

# views/mobile.py
import streamlit as st
import sqlite3
import time
from constants import MAP_LOGOS
from database import submit_vote, get_veto_state, load_draft_state, update_draft_map, init_veto_state, update_veto_turn

def render_mobile_vote_page(token):
    st.set_page_config(page_title="Captain Portal", layout="centered")
    
    # --- NEW: Check if this user just requested a reroll ---
    if st.session_state.get("reroll_submitted", False):
        st.success("✅ Reroll Requested Successfully!")
        st.info("The draft is being reset on the main screen.")
        st.markdown("### 📲 Please scan the NEW QR code.")
        return

    st.markdown("""
    <style>
        .stButton button { width: 100%; font-weight: bold; border-radius: 8px; min-height: 50px; }
        h2 { color: #FFD700; text-shadow: 0 0 10px #FFD700; }
    </style>
    """, unsafe_allow_html=True)

    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("SELECT captain_name, vote FROM current_draft_votes WHERE pin=?", (token,))
    row = c.fetchone()
    conn.close()

    if not row:
        st.error("❌ Token Expired")
        st.info("The draft has likely been reset or rerolled. Please scan the new QR code on the host screen.")
        return

    cap_name, current_vote = row
    st.markdown(f"<h3 style='text-align:center;'>👑 {cap_name}</h3>", unsafe_allow_html=True)

    # --- SHOW TEAM MEMBERS FOR THIS CAPTAIN ---
    saved = load_draft_state()
    if saved:
        t1_json, t2_json, n_a, n_b, _, _, _, _, _, _ = saved
        
        st.markdown("### ⚔️ Matchup")
        
        # Display both teams side-by-side
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**🔵 {n_a}**")
            for p in t1_json:
                st.markdown(f"{p}")
                
        with c2:
            st.markdown(f"**🔴 {n_b}**")
            for p in t2_json:
                st.markdown(f"{p}")
        
        st.divider()
        
    if current_vote == "Waiting":
        st.info("Draft Pending Approval")
        col1, col2 = st.columns(2)
        if col1.button("✅ APPROVE", use_container_width=True):
            submit_vote(token, "Approve")
            st.rerun()
        if col2.button("❌ REROLL", use_container_width=True):
            submit_vote(token, "Reroll")
            # --- NEW: Set flag so next refresh shows success message ---
            st.session_state.reroll_submitted = True
            st.rerun()
        return

    if current_vote == "Approve":
        st.success("✅ You have approved the draft.")
        st.info("⏳ Waiting for the other captain to confirm...")
        st.caption("Auto-refreshing...")
        time.sleep(2)
        st.rerun()
        return

    rem, prot, turn_team = get_veto_state()
    
    if not rem: 
        saved = load_draft_state()
        if saved:
             final_maps_str = saved[6]
             if final_maps_str:
                 st.divider()
                 st.success("✅ VETO COMPLETE")
                 st.markdown(f"<h2 style='text-align:center;'>MAP: {final_maps_str}</h2>", unsafe_allow_html=True)
                 maps = final_maps_str.split(",")
                 for m in maps:
                     st.image(MAP_LOGOS.get(m, ""), use_container_width=True)
                 time.sleep(10)
                 st.rerun()
             else:
                 st.info("Waiting for host to confirm map...")
                 time.sleep(3)
                 st.rerun()
        return

    saved = load_draft_state()
    if not saved: return
    t1_json, t2_json, n_a, n_b, _, _, _, _, _, _ = saved
    
    my_team_name = n_a if cap_name in t1_json else n_b
    opp_team_name = n_b if my_team_name == n_a else n_a

    st.divider()
    if turn_team == my_team_name:
        is_protection_phase = (len(prot) < 2)
        action_text = "PICK (PROTECT)" if is_protection_phase else "BAN (REMOVE)"
        bg_color = "#2aa02a" if is_protection_phase else "#ff4444"
        
        st.markdown(f"""
        <div style="background-color: {bg_color}; padding: 15px; border-radius: 10px; margin-bottom: 20px; text-align: center; border: 2px solid white;">
            <h2 style="color: white; margin: 0; text-shadow: 1px 1px 2px black;">{action_text}</h2>
            <p style="color: white; margin: 0;">Tap a map below to {action_text.split()[0]}</p>
        </div>
        """, unsafe_allow_html=True)

        cols = st.columns(2)
        for i, m in enumerate(rem):
            with cols[i % 2]:
                st.markdown(f"""<div style="display: flex; justify-content: center; margin-bottom: 5px;">
                    <img src="{MAP_LOGOS.get(m, '')}" style="width: 80px; border-radius: 5px;">
                    </div>""", unsafe_allow_html=True)
                
                # Use a unique key for every button state to avoid conflicts
                if st.button(f"{m}", key=f"btn_{m}_{i}", use_container_width=True, type="primary" if is_protection_phase else "secondary"):
                    if is_protection_phase: prot.append(m)
                    rem.remove(m)
                    if len(rem) == 1 and not is_protection_phase:
                        final_map = rem[0]
                        final_three = prot + [final_map]
                        update_draft_map(final_three)
                        init_veto_state([], "") 
                    else:
                        update_veto_turn(rem, prot, opp_team_name)
                    st.rerun()
    else:
        st.warning(f"⏳ Opponent is thinking...")
        st.caption("Waiting for their move...")
        time.sleep(2)
        st.rerun()

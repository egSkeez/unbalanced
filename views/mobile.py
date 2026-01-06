# views/mobile.py
import streamlit as st
import sqlite3
import time
from constants import MAP_LOGOS
from database import submit_vote, get_veto_state, load_draft_state, update_draft_map, init_veto_state, update_veto_turn

def render_mobile_vote_page(token):
    st.set_page_config(page_title="Captain Portal", layout="centered")
    
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
        st.error("❌ Invalid Token.")
        st.info("The draft may have been reset. Please ask the host to refresh.")
        return

    cap_name, current_vote = row
    st.markdown(f"<h3 style='text-align:center;'>👑 {cap_name}</h3>", unsafe_allow_html=True)

    if current_vote == "Waiting":
        st.info("Draft Pending Approval")
        col1, col2 = st.columns(2)
        if col1.button("✅ APPROVE", use_container_width=True):
            submit_vote(token, "Approve")
            st.rerun()
        if col2.button("❌ REROLL", use_container_width=True):
            submit_vote(token, "Reroll")
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
    t1_json, t2_json, n_a, n_b, _, _, _, _ = saved
    
    my_team_name = n_a if cap_name in t1_json else n_b
    opp_team_name = n_b if my_team_name == n_a else n_a

    st.divider()
    if turn_team == my_team_name:
        st.markdown(f"<h4 style='color:#4da6ff; text-align:center;'>👉 YOUR TURN</h4>", unsafe_allow_html=True)
        is_protection_phase = (len(prot) < 2)
        action_text = "PICK" if is_protection_phase else "BAN"
        btn_color = "primary" if is_protection_phase else "secondary"
        st.write(f"**Action: {action_text}**")
        cols = st.columns(2)
        for i, m in enumerate(rem):
            with cols[i % 2]:
                st.image(MAP_LOGOS.get(m, ""), width=50) 
                if st.button(f"{action_text} {m}", key=f"mob_{m}", type=btn_color, use_container_width=True):
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

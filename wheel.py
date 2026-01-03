# wheel.py
import streamlit as st
import random
import time

def render_bench_wheel(all_players):
    st.subheader("🎡 The Bench Wheel")
    
    # --- State Management ---
    if 'wheel_pool' not in st.session_state:
        st.session_state.wheel_pool = []
    if 'last_picked' not in st.session_state:
        st.session_state.last_picked = None
    if 'is_spinning' not in st.session_state:
        st.session_state.is_spinning = False

    # Selection: We use this to ADD players to the pool
    # The key "wheel_selector" prevents the 'not selected' bug
    selected_names = st.multiselect(
        "Who is in the rotation? (11th player included)", 
        options=all_players,
        key="wheel_selector"
    )

    # Manual override to sync the pool with the selector
    if st.button("✅ Confirm/Update Rotation List"):
        st.session_state.wheel_pool = list(selected_names)
        st.success(f"Added {len(selected_names)} players to the wheel!")

    st.divider()

    # --- Wheel UI & Animation ---
    if len(st.session_state.wheel_pool) > 0:
        col1, col2 = st.columns([2, 1])
        
        with col2:
            st.write("**Remaining in Wheel:**")
            for p in st.session_state.wheel_pool:
                st.caption(f"• {p}")

        with col1:
            if st.button("🔥 SPIN THE WHEEL", use_container_width=True, type="primary"):
                st.session_state.is_spinning = True
                
                # Visual Animation Placeholder
                wheel_placeholder = st.empty()
                
                # Spin effect: Fast cycling through names
                spin_duration = 20
                for i in range(spin_duration):
                    # Speed up/slow down simulation
                    wait_time = 0.05 + (i * 0.01)
                    current_temp = random.choice(st.session_state.wheel_pool)
                    
                    # CSS Styling for the "Spinning" look
                    wheel_placeholder.markdown(f"""
                        <div style="
                            border: 5px solid #FF4B4B;
                            border-radius: 15px;
                            padding: 20px;
                            text-align: center;
                            background-color: #262730;
                        ">
                            <h1 style="color: #FF4B4B; font-family: monospace;">🌀 {current_temp} 🌀</h1>
                        </div>
                    """, unsafe_allow_html=True)
                    time.sleep(wait_time)
                
                # Final Result
                winner = random.choice(st.session_state.wheel_pool)
                st.session_state.last_picked = winner
                st.session_state.wheel_pool.remove(winner)
                st.session_state.is_spinning = False
                st.balloons()
                st.rerun()

    else:
        st.info("Please select players and click 'Confirm' to start the wheel.")

    # --- Result Display ---
    if st.session_state.last_picked and not st.session_state.is_spinning:
        st.markdown(f"""
            <div style="background-color: #ff4b4b33; padding: 20px; border-radius: 10px; border: 2px solid #FF4B4B; text-align: center;">
                <h2 style="margin:0;">🚫 BENCHED: {st.session_state.last_picked} 🚫</h2>
            </div>
        """, unsafe_allow_html=True)

    if st.button("♻️ Reset Entire Wheel", use_container_width=True):
        st.session_state.wheel_pool = []
        st.session_state.last_picked = None
        st.rerun()

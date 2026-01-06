# views/history.py
import streamlit as st
import pandas as pd
import sqlite3
import json

def render_history_tab():
    st.title("📜 History")
    conn = sqlite3.connect('cs2_history.db')
    hist_df = pd.read_sql_query("SELECT * FROM matches ORDER BY date DESC", conn)
    conn.close()
    
    if hist_df.empty:
        st.info("No matches played yet.")
    else:
        for _, row in hist_df.iterrows():
            winner = row['team1_name'] if row['winner_idx'] == 1 else row['team2_name']
            with st.expander(f"🎮 {row['date'].split()[0]} | {winner} on {row['map']}"):
                c_a, c_b = st.columns(2)
                with c_a: st.write(f"**🟦 {row['team1_name']}**"); st.write(row['team1_players'])
                with c_b: st.write(f"**🟧 {row['team2_name']}**"); st.write(row['team2_players'])

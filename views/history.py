# views/history.py
import streamlit as st
import pandas as pd
from match_stats_db import get_recent_matches, get_match_scoreboard

def render_history_tab():
    st.title("📜 Match History (Parsed Demos)")
    
    # Fetch matched from the Parsed DB
    matches_df = get_recent_matches(limit=20)
    
    if matches_df.empty:
        st.info("No parsed matches found.")
        return

    for _, match in matches_df.iterrows():
        mid = match['match_id']
        score = match['score']
        m_map = match['map']
        date = match['date_analyzed']
        
        # Display Header
        with st.expander(f"🎮 {date} | {m_map} | {score}"):
            # Add Direct Link to Lobby
            lobby_url = match.get('lobby_url')
            if lobby_url:
                st.link_button("🌐 View Match Lobby", lobby_url)
            
            # Fetch details
            stats = get_match_scoreboard(mid)
            
            if stats.empty:
                st.warning("No player stats found for this match.")
                continue
                
            # Split by Team (2 = T / 3 = CT usually depending on side swap, but we group by ID)
            # We'll just group by team number
            teams = stats['player_team'].unique()
            
            # Create columns for teams
            cols = st.columns(len(teams)) if len(teams) > 0 else [st.container()]
            
            for i, team_id in enumerate(sorted(teams)):
                team_stats = stats[stats['player_team'] == team_id].copy()
                
                # Clean up display columns
                display_cols = ['player_name', 'kills', 'deaths', 'assists', 'adr', 'rating', 'util_damage', 'flash_assists', 'entry_kills']
                
                with cols[i] if i < len(cols) else st.container():
                    team_name = "Terrorists" if team_id == 2 else "CTs" if team_id == 3 else f"Team {team_id}"
                    st.subheader(f"{team_name} ({len(team_stats)})")
                    
                    display_df = team_stats[display_cols].copy()
                    display_df['rating'] = display_df['rating'].fillna('—')
                    
                    st.dataframe(
                        display_df.style.format({
                            'adr': "{:.1f}",
                            'util_damage': "{:.0f}"
                        }, na_rep='—'),
                        use_container_width=True,
                        hide_index=True
                    )

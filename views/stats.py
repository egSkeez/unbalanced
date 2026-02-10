
import streamlit as st
from match_stats_db import get_player_aggregate_stats, get_recent_matches
from database import get_player_stats
import sqlite3
import pandas as pd
from season_logic import get_current_season_info, get_all_seasons
from datetime import date

def render_stats_tab():
    st.title("📊 Match Statistics")
    
    # --- SEASON FILTER ---
    seasons = get_all_seasons()
    # Add "All Time"
    season_options = ["Season 2 (Demos)", "Season 1 (Manual)", "All Time"]
    
    col_filter, _ = st.columns([1, 2])
    with col_filter:
        selected_season_label = st.selectbox("📅 Filter by Season", season_options, index=0)
    
    if selected_season_label == "All Time":
        start_date, end_date = None, None
        mode = "ALL"
    elif selected_season_label == "Season 1 (Manual)":
        start_date, end_date = seasons["Season 1 (Manual)"]
        mode = "MANUAL"
    else:
        start_date, end_date = seasons["Season 2 (Demos)"]
        mode = "DEMO"
        
    
    tab1, tab2, tab3 = st.tabs(["🏆 Leaderboard", "👤 Player Stats", "📋 Recent Matches"])
    
    with tab1:
        st.subheader("🏆 Player Leaderboard")
        st.caption(f"Showing stats for: {selected_season_label}")
        
        if mode == "MANUAL":
            # --- SEASON 1 LOGIC (Manual DB) ---
            try:
                # Reuse existing manual function
                manual_df = get_player_stats() 
                # Rename cols to match expected format or display as is
                # Manual DF has: name, avg_kd, aim, util, team_play, W, D, Matches, Winrate, overall
                
                # Filter for active players just in case
                manual_df = manual_df[manual_df['Matches'] > 0].sort_values("overall", ascending=False)
                
                st.markdown("### 🥇 Top 3 Players (Season 1)")
                top3 = manual_df.head(3)
                
                if not top3.empty:
                    medals = ["🥇", "🥈", "🥉"]
                    colors = [
                        "linear-gradient(135deg, #FFD700 0%, #FFA500 100%)",
                        "linear-gradient(135deg, #C0C0C0 0%, #808080 100%)",
                        "linear-gradient(135deg, #CD7F32 0%, #8B4513 100%)"
                    ]
                    for idx in range(len(top3)):
                        player = top3.iloc[idx]
                        st.markdown(f"""
                        <div style="background: {colors[idx]}; padding: 20px; border-radius: 15px; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                            <h2 style="color: white; margin: 0;">{medals[idx]} {player['name']}</h2>
                            <p style="color: #f0f0f0; margin: 5px 0; font-size: 18px;">
                                Rating: {round(player['overall'], 1)} | K/D: {player['avg_kd']} | WR: {player['Winrate']}%
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
                        col1, col2, col3, col4 = st.columns(4)
                        with col1: st.metric("Matches", int(player['Matches']))
                        with col2: st.metric("Wins", int(player['W']))
                        with col3: st.metric("Draws", int(player['D']))
                        with col4: st.metric("Winrate", f"{player['Winrate']}%")
                        st.markdown("---")
                
                st.dataframe(manual_df[['name', 'Matches', 'W', 'D', 'Winrate', 'avg_kd', 'overall']], use_container_width=True, hide_index=True)
                
            except Exception as e:
                st.error(f"Error loading Season 1 stats: {e}")
                
        else:
            # --- SEASON 2 / DEMO LOGIC ---
            try:
                conn = sqlite3.connect('cs2_history.db')
                
                # Date filter construction
                date_filter_sql = ""
                params = []
                if start_date:
                    date_filter_sql += " AND date(md.date_analyzed) >= date(?)"
                    params.append(str(start_date))
                if end_date:
                    date_filter_sql += " AND date(md.date_analyzed) <= date(?)"
                    params.append(str(end_date))
                
                leaderboard_query = f'''
                    SELECT 
                        pms.player_name,
                        COUNT(*) as matches,
                        ROUND(AVG(pms.score), 1) as avg_score,
                        ROUND(AVG(NULLIF(pms.adr, 0)), 1) as avg_adr,
                        ROUND(AVG(NULLIF(pms.rating, 0)), 2) as rating,
                        ROUND(SUM(pms.kills) * 1.0 / NULLIF(SUM(pms.deaths), 0), 2) as kd_ratio,
                        ROUND(AVG(NULLIF(pms.headshot_pct, 0)), 1) as avg_hs_pct,
                        SUM(pms.kills) as total_kills,
                        COUNT(CASE WHEN pms.match_result = 'W' THEN 1 END) as wins,
                        COUNT(CASE WHEN pms.match_result = 'L' THEN 1 END) as losses
                    FROM player_match_stats pms
                    JOIN match_details md ON pms.match_id = md.match_id
                    WHERE pms.rating IS NOT NULL {date_filter_sql}
                    GROUP BY pms.player_name
                    HAVING matches >= 1
                    ORDER BY rating DESC
                '''
                leaderboard = pd.read_sql_query(leaderboard_query, conn, params=params)
                conn.close()
                
                if not leaderboard.empty:
                    leaderboard['Matches'] = leaderboard['matches']
                    leaderboard['Winrate'] = 0.0
                    valid = leaderboard['Matches'] > 0
                    leaderboard.loc[valid, 'Winrate'] = (leaderboard.loc[valid, 'wins'] / leaderboard.loc[valid, 'Matches'] * 100).round(1)
                    
                    st.markdown("### 🥇 Top 5 Players (Season 2) - Sorted by Rating")
                    eligible_top_5 = leaderboard[leaderboard['matches'] >= 2].head(5) # Lowered threshold to 2 for now
                    
                    if not eligible_top_5.empty:
                        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
                        colors = [
                            "linear-gradient(135deg, #FFD700 0%, #FFA500 100%)", # Gold
                            "linear-gradient(135deg, #C0C0C0 0%, #808080 100%)", # Silver
                            "linear-gradient(135deg, #CD7F32 0%, #8B4513 100%)", # Bronze
                            "linear-gradient(135deg, #606c88 0%, #3f4c6b 100%)", # Slate
                            "linear-gradient(135deg, #2b5876 0%, #4e4376 100%)"  # Deep Blue
                        ]
                        for idx in range(len(eligible_top_5)):
                            player = eligible_top_5.iloc[idx]
                            st.markdown(f"""
                            <div style="background: {colors[idx]}; padding: 20px; border-radius: 15px; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                                <h2 style="color: white; margin: 0;">{medals[idx]} {player['player_name']}</h2>
                                <p style="color: #f0f0f0; margin: 5px 0; font-size: 18px;">
                                    Rating: {player['rating']} | K/D: {player['kd_ratio']} | ADR: {player['avg_adr']}
                                </p>
                            </div>
                            """, unsafe_allow_html=True)
                            col1, col2, col3, col4 = st.columns(4)
                            with col1: st.metric("Matches", int(player['matches']))
                            with col2: st.metric("Winrate", f"{player['Winrate']}%")
                            with col3: st.metric("HS%", f"{player['avg_hs_pct']}%")
                            with col4: st.metric("ADR", f"{player['avg_adr']}")
                            st.markdown("---")
                    
                    st.dataframe(
                        leaderboard[['player_name', 'Matches', 'rating', 'kd_ratio', 'avg_adr', 'avg_hs_pct', 'Winrate']]
                        .rename(columns={'player_name': 'Player', 'rating': 'Rating', 'kd_ratio': 'K/D', 'avg_adr': 'ADR', 'avg_hs_pct': 'HS%'}), 
                        use_container_width=True, hide_index=True
                    )
                else:
                    st.info("No stats found for this season.")
            except Exception as e:
                st.error(f"Error loading demo stats: {e}")

    with tab2:
        st.subheader("👤 Player Performance Details")
        # Logic to fetch player list depends on mode
        conn = sqlite3.connect('cs2_history.db')
        if mode == "MANUAL":
            pl_df = pd.read_sql_query("SELECT name as player_name FROM players", conn)
        else:
            pl_df = pd.read_sql_query("SELECT DISTINCT player_name FROM player_match_stats ORDER BY player_name", conn)
        conn.close()
        
        selected_player = st.selectbox("Select Player", pl_df['player_name'].tolist() if not pl_df.empty else [])
        
        if selected_player:
            if mode == "MANUAL":
                # Manual Stats Card
                try:
                    p_data = get_player_stats()
                    row = p_data[p_data['name'] == selected_player]
                    if not row.empty:
                        r = row.iloc[0]
                        st.markdown(f"""
                        <div style="background: linear-gradient(135deg, #43cea2 0%, #185a9d 100%); padding: 30px; border-radius: 15px; margin-bottom: 20px;">
                            <h1 style="color: white; margin: 0;">{selected_player}</h1>
                            <p style="color: #e0e0e0; margin: 5px 0; font-size: 20px;">
                                {int(r['Matches'])} Matches (S1) | 🏆 {r['Winrate']}% Winrate
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
                except:
                    st.warning("Could not load manual stats.")
            else:
                # Demo Stats Card
                stats = get_player_aggregate_stats(selected_player, start_date=start_date, end_date=end_date)
                if not stats.empty and stats['matches_played'].iloc[0] > 0:
                    winrate = stats['winrate_pct'].iloc[0]
                    rating_val = stats['avg_rating'].iloc[0]
                    rating_display = rating_val if pd.notna(rating_val) else 'N/A'
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 15px; margin-bottom: 20px;">
                        <h1 style="color: white; margin: 0;">{selected_player}</h1>
                        <p style="color: #e0e0e0; margin: 5px 0; font-size: 20px;">
                            {int(stats['matches_played'].iloc[0])} Matches | 🏆 {winrate}% Winrate | ⭐ {rating_display} Rating
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    c1, c2, c3, c4 = st.columns(4)
                    with c1: st.metric("Rating 2.0", rating_display)
                    with c2: st.metric("K/D", stats['overall_kd'].iloc[0])
                    with c3: st.metric("ADR", stats['avg_adr'].iloc[0])
                    with c4: st.metric("HS%", f"{stats['avg_hs_pct'].iloc[0]}%")
                    
                    st.divider()
                    
                    # --- EXTENDED STATS GRID ---
                    st.subheader("📊 Detailed Performance")
                    
                    # Helper for stat card
                    def stat_card(icon, label, value, color="#FFF"):
                        st.markdown(f"""
                        <div style="
                            background: rgba(255,255,255,0.05); 
                            border-radius: 10px; 
                            padding: 15px; 
                            text-align: center;
                            border: 1px solid #333;
                        ">
                            <div style="font-size: 24px; margin-bottom: 5px;">{icon}</div>
                            <div style="color: #888; font-size: 12px; text-transform: uppercase; font-weight: bold;">{label}</div>
                            <div style="color: {color}; font-size: 18px; font-weight: bold;">{value}</div>
                        </div>
                        """, unsafe_allow_html=True)

                    s = stats.iloc[0]
                    
                    # Row 1: Combat
                    st.caption("⚔️ Combat")
                    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
                    with r1c1: stat_card("👑", "Entry Kills", int(s['total_entry_kills']), "#FFD700")
                    with r1c2: stat_card("🔥", "Clutches", int(s['total_clutches']), "#FF4B2B")
                    with r1c3: stat_card("🧱", "Wallbangs/Multi", int(s.get('multi_3k', 0) + s.get('multi_4k', 0) + s.get('multi_5k', 0)), "#DDD") # Placeholder until detail available
                    with r1c4: stat_card("💀", "Entry Deaths", int(s['total_entry_deaths']), "#e74c3c")
                    
                    # Row 2: Utility
                    st.caption("💣 Utility & Support")
                    r2c1, r2c2, r2c3, r2c4 = st.columns(4)
                    with r2c1: stat_card("💥", "Util Dmg", int(s['total_util_dmg']), "#00C6FF")
                    with r2c2: stat_card("🔦", "Enemies Flashed", int(s['total_enemies_flashed']), "#FFF")
                    with r2c3: stat_card("🤝", "Flash Assists", int(s['total_flash_assists']), "#38ef7d")
                    with r2c4: stat_card("🌱", "Plants", int(s['total_plants']), "#ffa751")
                    
                    # Row 3: Objectives
                    st.caption("🛡️ Objectives")
                    r3c1, r3c2, r3c3 = st.columns(3)
                    with r3c1: stat_card("✂️", "Defuses", int(s['total_defuses']), "#00b09b")
                    with r3c2: stat_card("🎣", "Rounds Last Alive", "?", "#888") # Need to fetch valid aggregate if present
                    with r3c3: stat_card("💰", "Avg Spent", "?", "#888") # Need valid agg
                    
                    st.divider()
                    st.subheader("Match History (Colored W/L)")
                    
                    conn = sqlite3.connect('cs2_history.db')
                    
                    date_filter_sub = ""
                    p_sub = [selected_player]
                    if start_date: 
                        date_filter_sub += " AND date(md.date_analyzed) >= date(?)"
                        p_sub.append(str(start_date))
                    if end_date:
                        date_filter_sub += " AND date(md.date_analyzed) <= date(?)"
                        p_sub.append(str(end_date))

                    hist_query = f'''
                        SELECT 
                            md.map as "Map",
                            md.score_t || '-' || md.score_ct as "Score",
                            pms.match_result as "Res",
                            pms.rating as "Rating",
                            pms.kills as "K",
                            pms.deaths as "D",
                            pms.adr as "ADR",
                            pms.kd_ratio as "K/D",
                            DATE(md.date_analyzed) as "Date",
                            md.lobby_url as "Lobby"
                        FROM player_match_stats pms
                        JOIN match_details md ON pms.match_id = md.match_id
                        WHERE pms.player_name = ?
                        {date_filter_sub}
                        ORDER BY md.date_analyzed DESC
                    '''
                    hist = pd.read_sql_query(hist_query, conn, params=p_sub)
                    conn.close()
                    
                    if not hist.empty:
                        def color_result(val):
                            color = 'white'
                            if val == 'W': color = '#2ecc71' # Green
                            elif val == 'L': color = '#e74c3c' # Red
                            elif val in ['D', 'T']: color = '#f1c40f' # Yellow/Tie
                            return f'color: {color}; font-weight: bold;'

                        st.dataframe(
                            hist.style.map(color_result, subset=['Res']), 
                            use_container_width=True, 
                            hide_index=True,
                            column_config={
                                "Lobby": st.column_config.LinkColumn("Lobby", display_text="View Lobby"),
                                "Rating": st.column_config.NumberColumn("Rating", format="%.2f"),
                                "K/D": st.column_config.NumberColumn("K/D", format="%.2f")
                            }
                        )
                    else: st.info("No matches found.")
                else: st.info("No stats for this period.")

    with tab3:
        st.subheader("📋 Recent Matches")
        # Reuse filter logic logic
        if mode == "MANUAL":
            st.info("Showing recent Season 1 matches (Manual List not fully implemented in UI history, check logic)")
            # Fallback to general manual match fetch if needed, but 'matches' table doesn't have robust date filtering usually
        else:
            try:
                conn = sqlite3.connect('cs2_history.db')
                
                df_dates = ""
                p_dates = []
                if start_date: df_dates += " AND date(date_analyzed) >= date(?)"; p_dates.append(str(start_date))
                if end_date: df_dates += " AND date(date_analyzed) <= date(?)"; p_dates.append(str(end_date))
                
                recent_query = f'''
                    SELECT map as "Map", 
                           CAST(score_t AS TEXT) || '-' || CAST(score_ct AS TEXT) as "Score",
                           date_analyzed as "Date",
                           lobby_url as "Lobby"
                    FROM match_details
                    WHERE 1=1 {df_dates}
                    ORDER BY date_analyzed DESC
                    LIMIT 20
                '''
                recent = pd.read_sql_query(recent_query, conn, params=p_dates)
                conn.close()
                st.dataframe(
                    recent, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "Lobby": st.column_config.LinkColumn("Lobby", display_text="View on Cybershoke")
                    }
                )
            except:
                pass
    


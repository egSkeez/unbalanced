import streamlit as st
import sqlite3
import pandas as pd
from match_stats_db import get_recent_matches, get_season_stats_dump
from season_logic import get_current_season_info

def get_match_extended_stats(match_id):
    conn = sqlite3.connect('cs2_history.db')
    query = "SELECT * FROM player_match_stats WHERE match_id = ?"
    df = pd.read_sql_query(query, conn, params=(match_id,))
    conn.close()
    return df

def render_trophy_card(icon, title, player_name, value, unit="", color="linear-gradient(135deg, #FFD700, #FDB931)", text_color="#FFD700"):
    """
    Renders a premium-looking trophy card.
    """
    st.markdown(f"""
    <div style="
        background: #1A1A1A;
        border-radius: 16px; 
        padding: 20px; 
        text-align: center;
        margin-bottom: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
        border: 1px solid #333;
        position: relative;
        overflow: hidden;
    ">
        <div style="
            position: absolute; top: 0; left: 0; width: 100%; height: 4px;
            background: {color};
        "></div>
        <div style="font-size: 3em; margin-bottom: 10px; filter: drop-shadow(0 0 10px rgba(255,255,255,0.1));">{icon}</div>
        <div style="
            color: #888; 
            font-size: 0.8em; 
            font-weight: 700; 
            text-transform: uppercase; 
            letter-spacing: 1px;
            margin-bottom: 5px;
        ">{title}</div>
        <div style="
            color: white; 
            font-size: 1.3em; 
            font-weight: 800; 
            margin: 5px 0;
            text-shadow: 0 2px 4px rgba(0,0,0,0.5);
        ">{player_name}</div>
        <div style="
            color: {text_color}; 
            font-size: 1.1em; 
            font-weight: 600;
            font-family: 'Courier New', monospace;
            background: rgba(255,255,255,0.05);
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            margin-top: 5px;
        ">{value} {unit}</div>
    </div>
    """, unsafe_allow_html=True)

def render_trophies_tab():
    st.subheader("🏆 Hall of Fame")
    
    # Season Info
    s_name, s_start, s_end = get_current_season_info()
    
    # Mode Selection
    mode = st.radio("View Mode", ["Match Analysis", f"{s_name} Leaderboard"], horizontal=True, label_visibility="collapsed")
    
    if "Leaderboard" in mode:
        st.caption(f"📅 **{s_name}** ({s_start.strftime('%b %d')} - {s_end.strftime('%b %d')}) | *Minimum 3 matches played*")
        
        df = get_season_stats_dump(s_start, s_end)
        
        if df.empty:
            st.info("No players meet the qualification criteria (3+ matches) yet.")
            return

        # --- SEASON TROPHIES (Based on AVERAGES) ---
        trophies = []
        
        # Helper to add season trophy
        def add_s_trophy(col, title, icon, unit, grad, txt_color, reverse=False):
            if col in df.columns:
                if reverse:
                    # For lowest val (e.g. 3atba winrate)
                    winner = df.loc[df[col].idxmin()]
                else:
                    winner = df.loc[df[col].idxmax()]
                
                val = winner[col]
                # Only show if value is meaningful (e.g. > 0, or valid constraint)
                if val > 0 or (reverse and val >= 0):
                    fmt_val = f"{val:.1f}"
                    # If unit is cash, format $
                    if "$" in unit: fmt_val = f"${val:,.0f}"
                    trophies.append((title, icon, winner['player_name'], fmt_val, unit, grad, txt_color))

        # 1. NEW: The Terminator (Most Kills)
        add_s_trophy('avg_kills', "The Terminator", "🤖", "kills/game", "linear-gradient(135deg, #2b5876, #4e4376)", "#a8c0ff")
        
        # 2. NEW: Iniesta (Most Assists)
        add_s_trophy('avg_assists', "Iniesta", "⚽", "ast/game", "linear-gradient(135deg, #1D976C, #93F9B9)", "#1D976C")
        
        # 3. Entry King (Avg Entries)
        add_s_trophy('avg_entries', "Entry King", "👑", "ent/game", "linear-gradient(135deg, #FFD700, #FDB931)", "#FFD700")

        # 4. NEW: Headshot Machine (HS%)
        add_s_trophy('avg_hs_pct', "Headshot Machine", "🤯", "%", "linear-gradient(135deg, #f12711, #f5af19)", "#f5af19")
        
        # 5. NEW: Ambouba (Most Flashes)
        add_s_trophy('avg_flashed', "Ambouba", "🔦", "flash/game", "linear-gradient(135deg, #E0EAFC, #CFDEF3)", "#FFF")
        
        # 5b. NEW: Utility King (Avg Util Dmg)
        add_s_trophy('avg_util_dmg', "Utility King", "🧨", "dmg/game", "linear-gradient(135deg, #cc2b5e, #753a88)", "#cc2b5e")
        
        # 5c. NEW: Blind Master (Flash Assists)
        add_s_trophy('avg_flash_assists', "Blind Master", "🕶️", "fa/game", "linear-gradient(135deg, #42275a, #734b6d)", "#734b6d")
        
        # 5d. NEW: The Planter (Avg Plants)
        add_s_trophy('avg_plants', "The Planter", "🌱", "plants/game", "linear-gradient(135deg, #F2994A, #F2C94C)", "#F2994A")
        
        # 5e. NEW: Ninja (Avg Defuses)
        add_s_trophy('avg_defuses', "The Ninja", "✂️", "defs/game", "linear-gradient(135deg, #11998e, #38ef7d)", "#11998e")
        
        # 6. Master Baiter relative to team? No just absolute avg rounds last alive
        add_s_trophy('avg_bait_rounds', "Master Baiter", "🎣", "baits/game", "linear-gradient(135deg, #00C6FF, #0072FF)", "#00C6FF")
        
        # 7. NEW: 3atba (Least Winrate) - Reverse calc
        # Find min winrate
        add_s_trophy('winrate', "3atba", "🧱", "% Win", "linear-gradient(135deg, #434343, #000000)", "#AAA", reverse=True)
        
        # 8. Clutch God (Total)
        if 'total_clutches' in df.columns and df['total_clutches'].sum() > 0:
            clutcher = df.loc[df['total_clutches'].idxmax()]
            trophies.append(("Clutch God", "🔥", clutcher['player_name'], str(clutcher['total_clutches']), "Clutches", 
                           "linear-gradient(135deg, #8E2DE2, #4A00E0)", "#8E2DE2"))

        # Render Grid
        cols = st.columns(3)
        for i, t in enumerate(trophies):
            with cols[i % 3]:
                # Tuple is: (title, icon, name, value, unit, grad, color)
                render_trophy_card(t[1], t[0], t[2], t[3], t[4], t[5], t[6])
        
        st.divider()
        st.subheader("📈 Season Rankings")
        
        # Display Leaderboard
        disp_df = df.copy()
        disp_df['KD'] = (disp_df['total_kills'] / disp_df['total_deaths'].replace(0, 1)).round(2)
        disp_df = disp_df.rename(columns={
            'player_name': 'Player',
            'matches_played': 'Matches',
            'avg_adr': 'ADR',
            'avg_hs_pct': 'HS%',
            'avg_assists': 'Ast/G',
            'avg_entries': 'Ent/G',
            'winrate': 'Win%',
            'total_clutches': 'Clutches'
        })
        
        cols_to_show = ['Player', 'Matches', 'Win%', 'KD', 'ADR', 'HS%', 'Ast/G', 'Ent/G', 'Clutches']
        # Round floats
        for c in cols_to_show:
            if c in disp_df.columns and disp_df[c].dtype == 'float64':
                disp_df[c] = disp_df[c].round(1)

        st.dataframe(
            disp_df[cols_to_show].sort_values('KD', ascending=False),
            use_container_width=True,
            hide_index=True
        )

    else:
        # --- MATCH VIEW ---
        recent = get_recent_matches(limit=20)
        if recent.empty:
            st.info("No analyzed matches found.")
            return

        options = {}
        for _, row in recent.iterrows():
            label = f"{row['map']} | {row['score']} | {row['date_analyzed']}"
            options[label] = row['match_id']
            
        sel_label = st.selectbox("Select Match", list(options.keys()))
        match_id = options[sel_label]
        
        df = get_match_extended_stats(match_id)
        if df.empty:
            st.warning("No extended stats found for this match.")
            return

        trophies = []
        
        # Helper for appending
        def add_trophy(title, icon, col, unit, grad, txt):
            if col in df.columns and df[col].sum() > 0:
                winner = df.loc[df[col].idxmax()]
                val = winner[col]
                # Format money
                if 'spent' in col: val = f"${val:,}"
                trophies.append((title, icon, winner['player_name'], val, unit, grad, txt))

        add_trophy("Entry King", "👑", "entry_kills", "Opens", "linear-gradient(135deg, #FFD700, #FDB931)", "#FFD700")
        add_trophy("First Death", "🩸", "entry_deaths", "Deaths", "linear-gradient(135deg, #FF416C, #FF4B2B)", "#FF4B2B")
        add_trophy("Master Baiter", "🎣", "rounds_last_alive", "Rounds", "linear-gradient(135deg, #00C6FF, #0072FF)", "#00C6FF")
        add_trophy("Big Spender", "💸", "total_spent", "", "linear-gradient(135deg, #11998e, #38ef7d)", "#38ef7d")
        add_trophy("Clutch God", "🧱", "clutch_wins", "Wins", "linear-gradient(135deg, #8E2DE2, #4A00E0)", "#8E2DE2")
        
        # New Match Trophies
        add_trophy("Utility King", "🧨", "util_damage", "Dmg", "linear-gradient(135deg, #cc2b5e, #753a88)", "#cc2b5e")
        add_trophy("Blind Master", "🕶️", "flash_assists", "Assists", "linear-gradient(135deg, #42275a, #734b6d)", "#734b6d")
        add_trophy("The Planter", "🌱", "bomb_plants", "Plants", "linear-gradient(135deg, #F2994A, #F2C94C)", "#F2994A")
        
        # Render Grid
        cols = st.columns(3)
        for i, t in enumerate(trophies):
            with cols[i % 3]:
                render_trophy_card(t[1], t[0], t[2], t[3], t[4], t[5], t[6])
                
        st.divider()
        st.subheader("📊 Match Details")
        display_cols = ['player_name', 'kills', 'deaths', 'assists', 'adr', 'entry_kills', 'rounds_last_alive', 'total_spent', 'headshot_pct']
        existing = [c for c in display_cols if c in df.columns]
        st.dataframe(df[existing].sort_values('kills', ascending=False), use_container_width=True, hide_index=True)

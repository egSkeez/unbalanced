
import pandas as pd
from demoparser2 import DemoParser
import traceback

def analyze_demo_file(demo_path):
    """
    Analyzes a .dem file and returns:
    - score_str: String describing match result
    - stats_df: DataFrame with player stats
    - map_name: Map name
    - score_t: T side score
    - score_ct: CT side score
    """
    try:
        parser = DemoParser(demo_path)
    except Exception as e:
        error_msg = f"Error opening demo: {str(e)}"
        print(error_msg)
        return error_msg, None, "Unknown", 0, 0

    score_str = "Score not found"
    map_name = "Unknown"
    score_t, score_ct = 0, 0
    
    # --- GET MAP NAME ---
    try:
        header = parser.parse_header()
        if 'map_name' in header:
            map_name = header['map_name']
            if map_name.startswith('de_'):
                map_name = map_name[3:].capitalize()
        print(f"Map: {map_name}")
    except Exception as e:
        print(f"Warning: Could not parse map name: {e}")
    
    # --- GET SCORES & ROUNDS ---
    # --- GET SCORES & ROUNDS ---
    try:
        # Method 1: Parse Round Events (Fallback/Total Rounds)
        rounds_ret = parser.parse_events(["round_end"])
        total_rounds = 0
        if rounds_ret:
             if isinstance(rounds_ret, list) and len(rounds_ret) > 0 and isinstance(rounds_ret[0], tuple):
                 rounds = rounds_ret[0][1]
             else:
                 rounds = pd.DataFrame(rounds_ret)

             if not rounds.empty:
                 total_rounds = len(rounds)
                 # naive fallback
                 if 'winner' in rounds.columns:
                     score_t = len(rounds[rounds['winner'] == 2])
                     score_ct = len(rounds[rounds['winner'] == 3])

        # Method 2: Parse CCSTeam Scores (Source of Truth)
        print("Parsing team scores from ticks...")
        team_props = ["CCSTeam.m_iScore", "CCSTeam.m_iTeamNum"]
        df_teams = parser.parse_ticks(team_props)
        
        if not df_teams.empty:
            max_tick = df_teams['tick'].max()
            final_teams = df_teams[df_teams['tick'] == max_tick]
            
            # Team 2 = T, Team 3 = CT
            t_row = final_teams[final_teams['CCSTeam.m_iTeamNum'] == 2]
            ct_row = final_teams[final_teams['CCSTeam.m_iTeamNum'] == 3]
            
            if not t_row.empty:
                score_t = int(t_row.iloc[0]['CCSTeam.m_iScore'])
            if not ct_row.empty:
                score_ct = int(ct_row.iloc[0]['CCSTeam.m_iScore'])
                
        score_str = f"T {score_t} - {score_ct} CT"
        print(f"Final Score: {score_str}, Total Rounds: {total_rounds}")

    except Exception as e:
        score_str = f"Score error: {str(e)}"
        print(f"Warning: {score_str}")

    # 2. STATS (Tick-based)
    try:
        print("Parsing player stats from ticks...")
        # Possible paths for cash spent
        cash_props_to_try = [
            "CCSPlayerController.m_iMatchStats_CashSpent_Total", 
            "CCSPlayerController.m_iTotalCashSpent",
            "CCSPlayerController.m_pInGameMoneyServices.m_iTotalCashSpent",
            "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iTotalCashSpent"
        ]
        
        cols = {
            "name": "CCSPlayerController.m_iszPlayerName",
            "steamid": "CCSPlayerController.m_steamID",
            "kills": "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iKills",
            "deaths": "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iDeaths",
            "assists": "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iAssists",
            "score": "CCSPlayerController.m_iScore",
            "damage": "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iDamage",
            "util_dmg": "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iUtilityDamage",
            "ef": "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iEnemiesFlashed",
            "hs": "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iHeadShotKills",
            "team": "CCSPlayerController.m_iTeamNum"
        }
        
        # Add all potential cash props to query
        wanted_props = list(cols.values()) + cash_props_to_try
        
        print(f"Querying {len(wanted_props)} properties from demo...")
        df_ticks = parser.parse_ticks(wanted_props)
        print(f"Retrieved {len(df_ticks)} tick records")
        
        # Identify valid cash prop
        valid_cash_prop = None
        if not df_ticks.empty:
            for p in cash_props_to_try:
                if p in df_ticks.columns and df_ticks[p].sum() > 0: # Check if data actually exists
                    valid_cash_prop = p
                    break
        print(f"Cash spent property found: {valid_cash_prop}")

        # --- PRE-PROCESS TEAMS ---
        # Map Player Name -> Team based on tick data (most reliable)
        name_to_team = {}
        if not df_ticks.empty:
            max_tick = df_ticks['tick'].max()
            final_state_pre = df_ticks[df_ticks['tick'] == max_tick]
            if cols['name'] in final_state_pre.columns and cols['team'] in final_state_pre.columns:
                for _, row in final_state_pre.iterrows():
                    n = row[cols['name']]
                    t = row[cols['team']]
                    if t in [2, 3]:
                        name_to_team[n] = t

        # --- EVENT PARSING ---
        print("Parsing events for complex stats (Entries, Clutches, Baiting)...")
        # Added round_announce_match_start to filter warmup
        events = parser.parse_events(["round_start", "round_end", "player_death", "round_announce_match_start"])
        
        # Convert to DF safely
        def get_event_df(evt_name):
            for e in events:
                if e[0] == evt_name:
                    return pd.DataFrame(e[1])
            return pd.DataFrame()

        round_starts = get_event_df("round_start")
        round_ends = get_event_df("round_end")
        deaths = get_event_df("player_death")
        match_start = get_event_df("round_announce_match_start")
        
        # Initialize extended stats
        ext_stats = {} 
        
        # Determine valid match window (filter out warmup)
        start_tick = 0
        if not match_start.empty:
            start_tick = match_start['tick'].max()
        elif not round_starts.empty:
             # Fallback: Start from first round_start? Or just 0.
             start_tick = round_starts['tick'].min()
        
        print(f"Analysis Start Tick: {start_tick}")
        
        if not deaths.empty:
            deaths = deaths[deaths['tick'] >= start_tick].sort_values('tick')
            print(f"Total Deaths to process: {len(deaths)}")
            
            # Create rounds timeline
            rounds_ranges = [] # (start_tick, end_tick, winner_team)
            
            if not round_ends.empty:
                 real_ends = round_ends[round_ends['tick'] >= start_tick].sort_values('tick')
                 last_end = start_tick
                 for _, r in real_ends.iterrows():
                     winner = r.get('winner', 0)
                     rounds_ranges.append((last_end, r['tick'], winner))
                     last_end = r['tick']
            else:
                 # Fallback if no round_end (shouldn't happen in valid demos)
                 # Use round_start intervals
                 if not round_starts.empty:
                     real_starts = round_starts[round_starts['tick'] >= start_tick].sort_values('tick')
                     ticks = real_starts['tick'].tolist()
                     for i in range(len(ticks)-1):
                         rounds_ranges.append((ticks[i], ticks[i+1], 0))
            
            print(f"Identified {len(rounds_ranges)} rounds for stats analysis.")
            
            # Track player stats per round
            for r_start, r_end, r_winner in rounds_ranges:
                # Get deaths in this round
                r_deaths = deaths[(deaths['tick'] >= r_start) & (deaths['tick'] <= r_end)].copy()
                
                if r_deaths.empty: continue
                
                # --- ENTRY KILL LOGIC ---
                first_death = r_deaths.iloc[0]
                attacker = first_death.get('attacker_name', None)
                victim = first_death.get('user_name', None)
                
                if attacker and str(attacker) != "None":
                    ext_stats.setdefault(attacker, {'entries': 0, 'entry_deaths': 0, 'last_alive': 0})['entries'] += 1
                if victim and str(victim) != "None":
                    ext_stats.setdefault(victim, {'entries': 0, 'entry_deaths': 0, 'last_alive': 0})['entry_deaths'] += 1
                
                # --- BAITER LOGIC ---
                # Find unique teams from deaths
                t2_deaths = []
                t3_deaths = []
                
                for _, d in r_deaths.iterrows():
                    u_name = d.get('user_name')
                    # Use map if available, else fallback to event data
                    u_team = name_to_team.get(u_name, d.get('user_team_num', 0))
                    
                    if u_team == 2: t2_deaths.append(u_name)
                    elif u_team == 3: t3_deaths.append(u_name)
                
                if t2_deaths:
                    last_t = t2_deaths[-1] 
                    if str(last_t) != "None":
                        ext_stats.setdefault(last_t, {'entries': 0, 'entry_deaths': 0, 'last_alive': 0})['last_alive'] += 1
                
                if t3_deaths:
                    last_ct = t3_deaths[-1]
                    if str(last_ct) != "None":
                        ext_stats.setdefault(last_ct, {'entries': 0, 'entry_deaths': 0, 'last_alive': 0})['last_alive'] += 1
                
                # --- CLUTCH LOGIC (Approximate) ---
                # A clutch is awarded if a player wins the round as the LAST surviving member of their team.
                # Assumes 5v5 by default, but we can check if team_deaths count == total_team_size - 1.
                # We need to know team size. We can infer from `name_to_team` counts or just assume 4 deaths = clutch (standard 5v5).
                
                # Check Team 2 Wins
                if r_winner == 2:
                    # If 4+ people died on T side, the survivor(s) clutched?
                    # Strict clutch: Exactly 1 survivor.
                    # Problem: We only have death list. We don't have the survivor name easily unless we diff `name_to_team`.
                    
                    if len(t2_deaths) >= 4:
                        # Find the survivor
                        # Get all T players from map
                        all_t_players = [n for n, t in name_to_team.items() if t == 2]
                        survivors = [p for p in all_t_players if p not in t2_deaths]
                        
                        if len(survivors) == 1:
                            clutcher = survivors[0]
                            ext_stats.setdefault(clutcher, {'entries': 0, 'entry_deaths': 0, 'last_alive': 0, 'clutches': 0})['clutches'] += 1
                
                # Check Team 3 Wins
                elif r_winner == 3:
                     if len(t3_deaths) >= 4:
                        all_ct_players = [n for n, t in name_to_team.items() if t == 3]
                        survivors = [p for p in all_ct_players if p not in t3_deaths]
                        
                        if len(survivors) == 1:
                            clutcher = survivors[0]
                            ext_stats.setdefault(clutcher, {'entries': 0, 'entry_deaths': 0, 'last_alive': 0, 'clutches': 0})['clutches'] += 1
        
        if not df_ticks.empty:
            max_tick = df_ticks['tick'].max()
            final_state = df_ticks[df_ticks['tick'] == max_tick].copy()
            
            # Filter teams (2=T, 3=CT)
            if cols['team'] in final_state.columns:
               final_state = final_state[final_state[cols['team']].isin([2, 3])]
            
            print(f"Processing {len(final_state)} player records...")
            
            # Map back to simple names
            stats_df = pd.DataFrame()
            
            def get_col(df, key):
                 if key in cols and cols[key] in df.columns:
                     return df[cols[key]]
                 return 0

            stats_df['Player'] = get_col(final_state, 'name')
            stats_df['TeamNum'] = get_col(final_state, 'team')
            stats_df['Kills'] = get_col(final_state, 'kills')
            stats_df['Deaths'] = get_col(final_state, 'deaths')
            stats_df['Assists'] = get_col(final_state, 'assists')
            stats_df['Score'] = get_col(final_state, 'score')
            stats_df['Damage'] = get_col(final_state, 'damage')
            stats_df['UtilDmg'] = get_col(final_state, 'util_dmg')
            stats_df['Flashed'] = get_col(final_state, 'ef')
            stats_df['HS_Count'] = get_col(final_state, 'hs')
            
            # Use valid cash prop
            if valid_cash_prop:
                stats_df['TotalSpent'] = final_state[valid_cash_prop]
            else:
                stats_df['TotalSpent'] = 0

            # Deduplicate by player name (take max stats)
            if 'Player' in stats_df.columns:
                 stats_df = stats_df.groupby('Player').max().reset_index()
            
            # Merge dictionary stats
            def get_ext_val(name, key):
                return ext_stats.get(name, {}).get(key, 0)
            
            stats_df['EntryKills'] = stats_df['Player'].apply(lambda x: get_ext_val(x, 'entries'))
            stats_df['EntryDeaths'] = stats_df['Player'].apply(lambda x: get_ext_val(x, 'entry_deaths'))
            stats_df['BaiterRating'] = stats_df['Player'].apply(lambda x: get_ext_val(x, 'last_alive'))
            stats_df['ClutchWins'] = 0 # Placeholder for now
            stats_df['TeamFlashed'] = 0 # Placeholder

            # Derived Stats
            if not stats_df.empty:
                 stats_df['K/D'] = (stats_df['Kills'] / stats_df['Deaths'].replace(0, 1)).round(2)
                 stats_df['HS%'] = ((stats_df['HS_Count'] / stats_df['Kills'].replace(0, 1)) * 100).round(1)
                 
                 if total_rounds > 0:
                     stats_df['ADR'] = (stats_df['Damage'] / total_rounds).round(1)
                 else:
                     stats_df['ADR'] = 0.0
            
                 # Reorder columns
                 final_cols = ['Player', 'TeamNum', 'Kills', 'Deaths', 'Assists', 'K/D', 'ADR', 'HS%', 'Score', 'Damage', 'Flashed',
                               'TotalSpent', 'EntryKills', 'EntryDeaths', 'BaiterRating', 'ClutchWins', 'TeamFlashed']
                 for c in final_cols:
                     if c not in stats_df.columns: stats_df[c] = 0
                 
                 stats_df = stats_df[final_cols].sort_values("Score", ascending=False)
                 print(f"Successfully parsed stats for {len(stats_df)} players")
                 return score_str, stats_df, map_name, score_t, score_ct
            
        print("Warning: No tick data found")
        return score_str, None, map_name, score_t, score_ct

    except Exception as e:
        error_msg = f"Error parsing ticks: {str(e)}"
        print(error_msg)
        print(traceback.format_exc())
        return error_msg, None, map_name, score_t, score_ct

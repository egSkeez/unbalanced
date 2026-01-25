
import sqlite3
import pandas as pd

def init_match_stats_tables():
    """
    Creates tables for storing detailed match statistics from demo files.
    """
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    
    # Table for match metadata
    c.execute('''CREATE TABLE IF NOT EXISTS match_details
                 (match_id TEXT PRIMARY KEY,
                  cybershoke_id TEXT,
                  date_analyzed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  map TEXT,
                  score_t INTEGER,
                  score_ct INTEGER,
                  total_rounds INTEGER)''')
    
    # Table for player performance in each match
    c.execute('''CREATE TABLE IF NOT EXISTS player_match_stats
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  match_id TEXT,
                  player_name TEXT,
                  steamid TEXT,
                  kills INTEGER,
                  deaths INTEGER,
                  assists INTEGER,
                  score INTEGER,
                  damage INTEGER,
                  adr REAL,
                  headshot_kills INTEGER,
                  headshot_pct REAL,
                  util_damage INTEGER,
                  enemies_flashed INTEGER,
                  kd_ratio REAL,
                  
                  -- New Extended Stats
                  total_spent INTEGER,
                  entry_kills INTEGER,
                  entry_deaths INTEGER,
                  clutch_wins INTEGER,
                  rounds_last_alive INTEGER,
                  team_flashed INTEGER,
                  
                  FOREIGN KEY (match_id) REFERENCES match_details(match_id))''')
    
    # Create indexes for faster queries
    c.execute('''CREATE INDEX IF NOT EXISTS idx_player_match 
                 ON player_match_stats(player_name, match_id)''')
    c.execute('''CREATE INDEX IF NOT EXISTS idx_match_date 
                 ON match_details(date_analyzed)''')
                 
    # Migration: Add player_team and match_result if not exists
    try:
        c.execute("ALTER TABLE player_match_stats ADD COLUMN player_team INTEGER")
    except:
        pass
    try:
        c.execute("ALTER TABLE player_match_stats ADD COLUMN match_result TEXT")
    except:
        pass
    
    # Migrations for Extended Stats
    new_cols = ['total_spent', 'entry_kills', 'entry_deaths', 'clutch_wins', 'rounds_last_alive', 'team_flashed']
    for col in new_cols:
        try:
            c.execute(f"ALTER TABLE player_match_stats ADD COLUMN {col} INTEGER DEFAULT 0")
        except:
            pass
    
    conn.commit()
    conn.close()

def save_match_stats(match_id, cybershoke_id, score_str, stats_df, map_name="Unknown", score_t=0, score_ct=0):
    """
    Saves match statistics to the database.
    
    Args:
        match_id: Unique identifier for this match (e.g., "match_5394408")
        cybershoke_id: The Cybershoke match ID
        score_str: Score string like "T 13 - 10 CT"
        stats_df: DataFrame with player statistics
        map_name: Map name if available
        score_t: T side score (optional, will parse from score_str if not provided)
        score_ct: CT side score (optional, will parse from score_str if not provided)
    """
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    
    # Use provided scores or parse from string
    if score_t == 0 and score_ct == 0:
        try:
            if "T" in score_str and "CT" in score_str:
                parts = score_str.split("-")
                score_t = int(parts[0].replace("T", "").strip())
                score_ct = int(parts[1].replace("CT", "").strip())
        except:
            pass
    
    total_rounds = score_t + score_ct
    
    # Delete existing match first to ensure fresh timestamp
    c.execute("DELETE FROM match_details WHERE match_id = ?", (match_id,))
    
    # Insert new match details with current timestamp
    c.execute('''INSERT INTO match_details 
                 (match_id, cybershoke_id, map, score_t, score_ct, total_rounds)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (match_id, cybershoke_id, map_name, score_t, score_ct, total_rounds))
    
    # Delete existing player stats for this match (if re-analyzing)
    c.execute("DELETE FROM player_match_stats WHERE match_id = ?", (match_id,))
    
    # Insert player stats
    for _, row in stats_df.iterrows():
        # Determine Result
        p_team = row.get('TeamNum', 0)
        result = 'T' # Tie default
        
        if score_t > score_ct:
            result = 'W' if p_team == 2 else 'L'
        elif score_ct > score_t:
            result = 'W' if p_team == 3 else 'L'
        else:
            result = 'D' # Draw
            
        c.execute('''INSERT INTO player_match_stats 
                     (match_id, player_name, steamid, kills, deaths, assists, score, 
                      damage, adr, headshot_kills, headshot_pct, util_damage, 
                      enemies_flashed, kd_ratio, player_team, match_result,
                      total_spent, entry_kills, entry_deaths, clutch_wins, rounds_last_alive, team_flashed)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (match_id,
                   row.get('Player', ''),
                   '',  # steamid not in current df
                   row.get('Kills', 0),
                   row.get('Deaths', 0),
                   row.get('Assists', 0),
                   row.get('Score', 0),
                   row.get('Damage', 0),
                   row.get('ADR', 0.0),
                   row.get('HS_Count', 0),
                   row.get('HS%', 0.0),
                   row.get('UtilDmg', 0),
                   row.get('Flashed', 0),
                   row.get('K/D', 0.0),
                   p_team,
                   result,
                   # New Stats
                   row.get('TotalSpent', 0),
                   row.get('EntryKills', 0),
                   row.get('EntryDeaths', 0),
                   row.get('ClutchWins', 0),
                   row.get('BaiterRating', 0),
                   row.get('TeamFlashed', 0)
                   ))
    
    conn.commit()
    conn.close()

def get_player_aggregate_stats(player_name, start_date=None, end_date=None):
    """
    Get aggregate statistics for a player, optionally filtered by date range (season).
    start_date and end_date should be strings 'YYYY-MM-DD' or date objects.
    """
    conn = sqlite3.connect('cs2_history.db')
    
    where_clause = "WHERE pms.player_name = ?"
    params = [player_name]
    
    if start_date:
        where_clause += " AND date(md.date_analyzed) >= date(?)"
        params.append(str(start_date))
    if end_date:
        where_clause += " AND date(md.date_analyzed) <= date(?)"
        params.append(str(end_date))
    
    query = f'''
        SELECT 
            COUNT(*) as matches_played,
            SUM(pms.kills) as total_kills,
            SUM(pms.deaths) as total_deaths,
            SUM(pms.assists) as total_assists,
            ROUND(AVG(pms.adr), 1) as avg_adr,
            ROUND(AVG(NULLIF(pms.headshot_pct, 0)), 1) as avg_hs_pct,
            ROUND(SUM(pms.kills) * 1.0 / NULLIF(SUM(pms.deaths), 0), 2) as overall_kd,
            
            -- Calculate Winrate from Match Result column
            COUNT(CASE WHEN pms.match_result = 'W' THEN 1 END) as wins,
            COUNT(CASE WHEN pms.match_result = 'L' THEN 1 END) as losses,
            COUNT(CASE WHEN pms.match_result = 'D' THEN 1 END) as draws
            
        FROM player_match_stats pms
        JOIN match_details md ON pms.match_id = md.match_id
        {where_clause}
    '''
    
    df = pd.read_sql_query(query, conn, params=params)
    
    # Calculate winrate %
    if not df.empty and df.iloc[0]['matches_played'] > 0:
        matches = df.iloc[0]['matches_played']
        wins = df.iloc[0]['wins']
        df['winrate_pct'] = round((wins / matches) * 100, 1)
    else:
        df['winrate_pct'] = 0.0

    conn.close()
    return df

def get_recent_matches(limit=10):
    """
    Get recent matches with basic info.
    """
    conn = sqlite3.connect('cs2_history.db')
    
    query = '''
        SELECT match_id, cybershoke_id, map, 
               CAST(score_t AS TEXT) || '-' || CAST(score_ct AS TEXT) as score,
               date_analyzed
        FROM match_details
        ORDER BY date_analyzed DESC
        LIMIT ?
    '''
    
    df = pd.read_sql_query(query, conn, params=(limit,))
    conn.close()
    return df

def get_season_stats_dump(start_date, end_date):
    """
    Get aggregated stats for ALL players within a date range.
    Used for Season Leaderboards.
    """
    conn = sqlite3.connect('cs2_history.db')
    
    query = '''
        SELECT 
            pms.player_name,
            COUNT(*) as matches_played,
            SUM(pms.kills) as total_kills,
            SUM(pms.deaths) as total_deaths,
            SUM(pms.assists) as total_assists,
            SUM(pms.entry_kills) as total_entries,
            SUM(pms.entry_deaths) as total_entry_deaths,
            SUM(pms.rounds_last_alive) as total_bait_rounds,
            SUM(pms.clutch_wins) as total_clutches,
            SUM(pms.total_spent) as total_spent_cash,
            SUM(pms.enemies_flashed) as total_flashed,
            AVG(pms.adr) as avg_adr,
            AVG(NULLIF(pms.headshot_pct, 0)) as avg_hs_pct,
            
            -- Winrate calc
            COUNT(CASE WHEN pms.match_result = 'W' THEN 1 END) as wins,
            COUNT(CASE WHEN pms.match_result = 'L' THEN 1 END) as losses
        FROM player_match_stats pms
        JOIN match_details md ON pms.match_id = md.match_id
        WHERE date(md.date_analyzed) >= date(?) 
          AND date(md.date_analyzed) <= date(?)
        GROUP BY pms.player_name
        HAVING matches_played >= 3
    '''
    
    df = pd.read_sql_query(query, conn, params=(start_date, end_date))
    
    # Calculate Averages for Rankings
    if not df.empty:
        df['avg_kills'] = df['total_kills'] / df['matches_played']
        df['avg_assists'] = df['total_assists'] / df['matches_played']
        df['avg_entries'] = df['total_entries'] / df['matches_played']
        df['avg_bait_rounds'] = df['total_bait_rounds'] / df['matches_played']
        df['avg_spent'] = df['total_spent_cash'] / df['matches_played']
        df['avg_flashed'] = df['total_flashed'] / df['matches_played']
        df['winrate'] = (df['wins'] / df['matches_played']) * 100
        
    conn.close()
    return df

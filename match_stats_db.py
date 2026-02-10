
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
                  rating REAL,
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
    new_cols = ['total_spent', 'entry_kills', 'entry_deaths', 'clutch_wins', 'rounds_last_alive', 'team_flashed',
                'flash_assists', 'bomb_plants', 'bomb_defuses', 'multi_kills', 'weapon_kills', 'rating']
    for col in new_cols:
        try:
            col_type = "TEXT" if "json" in col or "kills" in col and "entry" not in col else "INTEGER"
            # specific override for multi/weapon kills which are dicts -> text
            if col in ['multi_kills', 'weapon_kills']:
                col_type = "TEXT"
                
            c.execute(f"ALTER TABLE player_match_stats ADD COLUMN {col} {col_type} DEFAULT 0")
        except:
            pass
    
    # Table for tracking Cybershoke lobbies
    c.execute('''CREATE TABLE IF NOT EXISTS cybershoke_lobbies
                 (lobby_id TEXT PRIMARY KEY,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  has_demo INTEGER DEFAULT 0,  -- 0: Unknown, 1: Yes, -1: No
                  analysis_status TEXT DEFAULT 'pending', -- pending, analyzed, error, no_demo
                  notes TEXT)''')
    
    # Create unique index on cybershoke_id to prevent duplicate match analysis
    # Only applies to non-manual entries
    c.execute('''CREATE INDEX IF NOT EXISTS idx_cybershoke_id 
                 ON match_details(cybershoke_id)''')

    # Migration: Add lobby_url column if not exists
    try:
        c.execute("ALTER TABLE match_details ADD COLUMN lobby_url TEXT")
    except:
        pass

    conn.commit()
    conn.close()

def is_lobby_already_analyzed(cybershoke_id):
    """
    Checks if a match with this cybershoke_id has already been analyzed.
    Returns True if already exists, False otherwise.
    Ignores 'manual' entries.
    """
    if not cybershoke_id or cybershoke_id == 'manual':
        return False
    
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("SELECT match_id FROM match_details WHERE cybershoke_id = ?", (str(cybershoke_id),))
    result = c.fetchone()
    conn.close()
    
    return result is not None

def calculate_hltv_rating(row, total_rounds):
    """
    Calculates HLTV Rating 1.0
    Formula: (KillRating + 0.7 * SurvivalRating + MultiKillRating) / 2.7
    Returns None if essential stats (MultiKills) are missing.
    """
    if total_rounds == 0:
        return None
        
    kills = row.get('Kills', 0)
    deaths = row.get('Deaths', 0)
    
    # 3. MultiKill Rating
    # We need counts of 1k, 2k, 3k, 4k, 5k
    mk = row.get('MultiKills', None)
    if isinstance(mk, str):
        import json
        try:
            loaded = json.loads(mk)
            if isinstance(loaded, dict) and len(loaded) > 0:
                mk = loaded
            else:
                mk = None
        except:
            mk = None
    elif isinstance(mk, dict):
        if len(mk) == 0:
            mk = None
    else:
        mk = None
    
    # If MultiKills data is missing, we cannot compute a valid rating
    if mk is None:
        return None
    
    # 1. Kill Rating
    kpr = kills / total_rounds
    kill_rating = kpr / 0.679
    
    # 2. Survival Rating
    survival_rate = (total_rounds - deaths) / total_rounds
    survival_rating = survival_rate / 0.317
            
    # Counts
    def get_cnt(d, k):
        return int(d.get(str(k), 0)) + int(d.get(int(k), 0))

    k1 = get_cnt(mk, 1)
    k2 = get_cnt(mk, 2)
    k3 = get_cnt(mk, 3)
    k4 = get_cnt(mk, 4)
    k5 = get_cnt(mk, 5)
    
    # Value = (1K + 4*2K + 9*3K + 16*4K + 25*5K) / Rounds
    mk_val = (k1 + 4*k2 + 9*k3 + 16*k4 + 25*k5) / total_rounds
    mk_rating = mk_val / 1.277
    
    rating = (kill_rating + 0.7 * survival_rating + mk_rating) / 2.7
    return round(rating, 2)

def save_match_stats(match_id, cybershoke_id, score_str, stats_df, map_name="Unknown", score_t=0, score_ct=0, force_overwrite=False, lobby_url=None):
    """
    Saves match statistics to the database.
    If a match with the same cybershoke_id already exists, skips saving unless force_overwrite=True.
    Returns True if saved, False if skipped due to duplicate.
    """
    import json
    
    # Duplicate check: If cybershoke_id exists (and not 'manual'), skip unless forced
    if not force_overwrite and cybershoke_id and cybershoke_id != 'manual':
        if is_lobby_already_analyzed(cybershoke_id):
            print(f"⚠️ Match with cybershoke_id {cybershoke_id} already analyzed. Skipping duplicate.")
            return False
    
    conn = sqlite3.connect('cs2_history.db', timeout=30)
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
    
    # Build lobby URL if not provided but cybershoke_id is available
    if not lobby_url and cybershoke_id and cybershoke_id != 'manual':
        lobby_url = f"https://cybershoke.net/match/{cybershoke_id}"
    
    # Delete existing match first to ensure fresh timestamp (for overwrite case)
    c.execute("DELETE FROM match_details WHERE match_id = ?", (match_id,))
    
    # Also delete any match with same cybershoke_id if we're force overwriting
    if force_overwrite and cybershoke_id and cybershoke_id != 'manual':
        c.execute("DELETE FROM match_details WHERE cybershoke_id = ?", (str(cybershoke_id),))
    
    # Insert new match details with current timestamp
    c.execute('''INSERT INTO match_details 
                 (match_id, cybershoke_id, map, score_t, score_ct, total_rounds, lobby_url)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (match_id, cybershoke_id, map_name, score_t, score_ct, total_rounds, lobby_url))
    
    # Delete existing player stats for this match (if re-analyzing)
    c.execute("DELETE FROM player_match_stats WHERE match_id = ?", (match_id,))
    
    # Insert player stats
    # from database import update_player_steamid # Removed immediate call to avoid lock
    
    steam_id_updates = [] # Collect (name, steamid) to update later
    
    for _, row in stats_df.iterrows():
        # Determine Result
        p_team = row.get('TeamNum', 0)
        p_name = row.get('Player', '')
        p_steam = str(row.get('SteamID', ''))
        
        # Queue SteamID update
        if p_name and p_steam:
            steam_id_updates.append((p_name, p_steam))

        result = 'T' # Tie default
        
        if score_t > score_ct:
            result = 'W' if p_team == 2 else 'L'
        elif score_ct > score_t:
            result = 'W' if p_team == 3 else 'L'
        else:
            result = 'D' # Draw
            
        # Serialize JSON fields
        multi_kills_json = json.dumps(row.get('MultiKills', {}))
        weapon_kills_json = json.dumps(row.get('WeaponKills', {}))

        c.execute('''INSERT INTO player_match_stats 
                      (match_id, player_name, steamid, kills, deaths, assists, score, 
                       damage, adr, headshot_kills, headshot_pct, util_damage, 
                       enemies_flashed, kd_ratio, player_team, match_result,
                       total_spent, entry_kills, entry_deaths, clutch_wins, rounds_last_alive, team_flashed,
                       flash_assists, bomb_plants, bomb_defuses, multi_kills, weapon_kills, rating)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                   (match_id,
                    p_name,
                    p_steam,
                    row.get('Kills', 0),
                    row.get('Deaths', 0),
                    row.get('Assists', 0),
                    row.get('Score', 0),
                    row.get('Damage', 0),
                    row.get('ADR', 0.0),
                    row.get('Headshots', 0),     # Corrected from HS_Count
                    row.get('HS%', 0.0),
                    row.get('UtilityDamage', 0), # Corrected from UtilDmg
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
                    row.get('TeamFlashed', 0),
                    row.get('FlashAssists', 0),
                    row.get('BombPlants', 0),
                    row.get('BombDefuses', 0),
                    multi_kills_json,
                    weapon_kills_json,
                    calculate_hltv_rating(row, total_rounds)
                    ))
    
    conn.commit()
    conn.close()
    
    # Process Steam ID updates now that lock is released
    from database import update_player_steamid
    for name, steam in steam_id_updates:
        try:
            update_player_steamid(name, steam)
        except Exception as e:
            print(f"Failed to update steamid for {name}: {e}")
    
    return True  # Successfully saved

def get_player_aggregate_stats(player_name, start_date=None, end_date=None):
    """
    Get aggregate statistics for a player, optionally filtered by date range (season).
    Prefers SteamID for aggregation if available.
    """
    conn = sqlite3.connect('cs2_history.db')
    
    # 1. Try to find SteamID for this player
    c = conn.cursor()
    c.execute("SELECT steamid FROM players WHERE name = ?", (player_name,))
    row = c.fetchone()
    steamid = row[0] if row else None
    
    if steamid:
        # Match by SteamID OR Name (to catch legacy matches)
        where_clause = "WHERE (pms.steamid = ? OR pms.player_name = ?)"
        params = [steamid, player_name]
    else:
        # Fallback to name if no Steam ID linked
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
            ROUND(AVG(NULLIF(pms.rating, 0)), 2) as avg_rating,
            ROUND(AVG(NULLIF(pms.headshot_pct, 0)), 1) as avg_hs_pct,
            ROUND(SUM(pms.kills) * 1.0 / NULLIF(SUM(pms.deaths), 0), 2) as overall_kd,
            
            -- Extended Stats Aggregates
            SUM(pms.entry_kills) as total_entry_kills,
            SUM(pms.entry_deaths) as total_entry_deaths,
            SUM(pms.util_damage) as total_util_dmg,
            SUM(pms.flash_assists) as total_flash_assists,
            SUM(pms.enemies_flashed) as total_enemies_flashed,
            SUM(pms.bomb_plants) as total_plants,
            SUM(pms.bomb_defuses) as total_defuses,
            SUM(pms.clutch_wins) as total_clutches,
            
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
            SUM(pms.flash_assists) as total_flash_assists,
            SUM(pms.util_damage) as total_util_dmg,
            SUM(pms.bomb_plants) as total_plants,
            SUM(pms.bomb_defuses) as total_defuses,
            AVG(pms.adr) as avg_adr,
            AVG(NULLIF(pms.rating, 0)) as avg_rating,
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
        
        # New Averages
        df['avg_util_dmg'] = df['total_util_dmg'] / df['matches_played']
        df['avg_flash_assists'] = df['total_flash_assists'] / df['matches_played']
        df['avg_plants'] = df['total_plants'] / df['matches_played']
        df['avg_defuses'] = df['total_defuses'] / df['matches_played']
        
        df['winrate'] = (df['wins'] / df['matches_played']) * 100
        
    conn.close()
    return df

def add_lobby(lobby_id):
    """
    Adds a new Cybershoke lobby to the tracking table.
    """
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    try:
        # Use INSERT OR IGNORE to handle potential duplicates gracefully
        c.execute("INSERT OR IGNORE INTO cybershoke_lobbies (lobby_id) VALUES (?)", (str(lobby_id),))
        conn.commit()
    except Exception as e:
        print(f"Error adding lobby: {e}")
    finally:
        conn.close()

def get_all_lobbies():
    """
    Returns all tracked lobbies ordered by creation date (newest first).
    """
    conn = sqlite3.connect('cs2_history.db')
    query = "SELECT * FROM cybershoke_lobbies ORDER BY created_at DESC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def update_lobby_status(lobby_id, has_demo=None, status=None):
    """
    Updates the status or demo availability of a lobby.
    """
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    try:
        if has_demo is not None:
             c.execute("UPDATE cybershoke_lobbies SET has_demo = ? WHERE lobby_id = ?", (int(has_demo), str(lobby_id)))
        
        if status is not None:
            c.execute("UPDATE cybershoke_lobbies SET analysis_status = ? WHERE lobby_id = ?", (status, str(lobby_id)))
            
        conn.commit()
    except Exception as e:
        print(f"Error updating lobby: {e}")
    finally:
        conn.close()

def get_match_scoreboard(match_id):
    """
    Retrieves the full scoreboard (player stats) for a specific match.
    """
    conn = sqlite3.connect('cs2_history.db', timeout=30)
    query = '''
        SELECT 
            player_name, player_team, 
            kills, deaths, assists, 
            adr, rating, headshot_pct, score,
            util_damage, flash_assists, enemies_flashed,
            entry_kills, entry_deaths,
            total_spent,
            multi_kills, weapon_kills
        FROM player_match_stats
        WHERE match_id = ?
        ORDER BY score DESC
    '''
    df = pd.read_sql_query(query, conn, params=(str(match_id),))
    conn.close()
    return df

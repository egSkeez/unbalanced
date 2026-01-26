# database.py
import sqlite3
import pandas as pd
import json
from constants import PLAYERS_INIT

# --- DATABASE INITIALIZATION ---
def init_db():
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS players 
                 (name TEXT PRIMARY KEY, elo REAL, aim REAL, util REAL, team_play REAL, secret_word TEXT)''')
    
    try:
        c.execute("ALTER TABLE players ADD COLUMN secret_word TEXT DEFAULT 'cs2pro'")
    except:
        pass 

    c.execute('''CREATE TABLE IF NOT EXISTS matches 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, team1_name TEXT, team2_name TEXT,
                  team1_players TEXT, team2_players TEXT, winner_idx INTEGER, 
                  map TEXT, elo_diff REAL, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS current_draft_votes 
                 (captain_name TEXT PRIMARY KEY, pin TEXT, vote TEXT)''')

    # ADDED: current_lobby column
    c.execute('''CREATE TABLE IF NOT EXISTS active_draft_state 
                 (id INTEGER PRIMARY KEY, t1_json TEXT, t2_json TEXT, 
                  name_a TEXT, name_b TEXT, avg1 REAL, avg2 REAL, 
                  current_map TEXT, current_lobby TEXT, cybershoke_match_id TEXT, draft_mode TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS active_veto_state 
                 (id INTEGER PRIMARY KEY, remaining_maps TEXT, protected_maps TEXT, current_turn TEXT)''')

    # Migrations for existing DBs
    try:
        c.execute("ALTER TABLE active_draft_state ADD COLUMN current_map TEXT")
    except:
        pass

    try:
        c.execute("ALTER TABLE active_draft_state ADD COLUMN current_lobby TEXT")
    except:
        pass

    try:
        c.execute("ALTER TABLE active_draft_state ADD COLUMN cybershoke_match_id TEXT")
    except:
        pass

    try:
        c.execute("ALTER TABLE active_draft_state ADD COLUMN draft_mode TEXT")
    except:
        pass

    c.execute("SELECT COUNT(*) FROM players")
    
    # UPSERT Logic: Add new players if they don't exist
    for name, d in PLAYERS_INIT.items():
        c.execute("INSERT OR IGNORE INTO players (name, elo, aim, util, team_play, secret_word) VALUES (?, ?, ?, ?, ?, ?)", 
                  (name, d['elo'], d['aim'], d['util'], d['team'], "cs2pro"))
    
    c.execute("UPDATE players SET secret_word = lower(name) WHERE secret_word IS NULL OR secret_word = ''")
    conn.commit()
    conn.close()

# --- DRAFT STATE FUNCTIONS ---
def save_draft_state(t1, t2, name_a, name_b, avg1, avg2, mode="balanced"):
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("DELETE FROM active_draft_state") 
    # Initialize with NULL current_lobby and cybershoke_match_id
    c.execute("INSERT INTO active_draft_state (id, t1_json, t2_json, name_a, name_b, avg1, avg2, current_map, current_lobby, cybershoke_match_id, draft_mode) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
              (json.dumps(t1), json.dumps(t2), name_a, name_b, avg1, avg2, None, None, None, mode))
    conn.commit()
    conn.close()

def update_draft_map(map_data):
    val = ",".join(map_data) if isinstance(map_data, list) else map_data
    conn = sqlite3.connect('cs2_history.db')
    conn.execute("UPDATE active_draft_state SET current_map = ? WHERE id = 1", (val,))
    conn.commit()
    conn.close()

def load_draft_state():
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("SELECT t1_json, t2_json, name_a, name_b, avg1, avg2, current_map, current_lobby, cybershoke_match_id, draft_mode FROM active_draft_state WHERE id=1")
    row = c.fetchone()
    conn.close()
    if row:
        # Returns tuple including current_lobby at index 7 and match_id at index 8 and mode at 9
        # Handle cases where row might be shorter if schema wasn't fully updated (fallback)
        lobby = row[7] if len(row) > 7 else None
        cs_id = row[8] if len(row) > 8 else None
        mode = row[9] if len(row) > 9 else "balanced"
        return (json.loads(row[0]), json.loads(row[1]), row[2], row[3], row[4], row[5], row[6], lobby, cs_id, mode)
    return None

def clear_draft_state():
    conn = sqlite3.connect('cs2_history.db')
    conn.execute("DELETE FROM active_draft_state")
    conn.execute("DELETE FROM current_draft_votes")
    conn.execute("DELETE FROM active_veto_state")
    conn.commit()
    conn.close()

# --- VETO STATE FUNCTIONS ---
def init_veto_state(maps, turn_team):
    conn = sqlite3.connect('cs2_history.db')
    conn.execute("DELETE FROM active_veto_state")
    maps_str = ",".join(maps)
    conn.execute("INSERT INTO active_veto_state (id, remaining_maps, protected_maps, current_turn) VALUES (1, ?, ?, ?)",
                 (maps_str, "", turn_team))
    conn.commit()
    conn.close()

def get_veto_state():
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("SELECT remaining_maps, protected_maps, current_turn FROM active_veto_state WHERE id=1")
    row = c.fetchone()
    conn.close()
    if row:
        rem = row[0].split(",") if row[0] else []
        prot = row[1].split(",") if row[1] else []
        return rem, prot, row[2]
    return None, None, None

def update_veto_turn(remaining, protected, next_turn):
    conn = sqlite3.connect('cs2_history.db')
    rem_str = ",".join(remaining)
    prot_str = ",".join(protected)
    conn.execute("UPDATE active_veto_state SET remaining_maps=?, protected_maps=?, current_turn=? WHERE id=1",
                 (rem_str, prot_str, next_turn))
    conn.commit()
    conn.close()

# --- PLAYER & STATS FUNCTIONS ---
def get_player_stats():
    conn = sqlite3.connect('cs2_history.db')
    
    # Get base player data
    df = pd.read_sql_query("SELECT name, aim, util, team_play, secret_word FROM players", conn)
    
    # Calculate average K/D from match statistics
    kd_query = '''
        SELECT 
            player_name,
            ROUND(SUM(kills) * 1.0 / NULLIF(SUM(deaths), 0), 2) as avg_kd
        FROM player_match_stats
        GROUP BY player_name
    '''
    kd_df = pd.read_sql_query(kd_query, conn)
    
    # Merge K/D data with player data
    df = df.merge(kd_df, left_on='name', right_on='player_name', how='left')
    df['avg_kd'] = df['avg_kd'].fillna(1.0)  # Default to 1.0 if no matches
    df = df.drop('player_name', axis=1, errors='ignore')
    
    # Get W/D from matches
    try:
        matches = pd.read_sql_query("SELECT team1_players, team2_players, winner_idx FROM matches", conn)
    except:
        matches = pd.DataFrame()
    
    df['W'] = 0
    df['D'] = 0
    if not matches.empty:
        for _, match in matches.iterrows():
            t1 = [p.strip() for p in str(match['team1_players']).split(",")]
            t2 = [p.strip() for p in str(match['team2_players']).split(",")]
            if match['winner_idx'] == 1:
                df.loc[df['name'].isin(t1), 'W'] += 1
                df.loc[df['name'].isin(t2), 'D'] += 1
            else:
                df.loc[df['name'].isin(t2), 'W'] += 1
                df.loc[df['name'].isin(t1), 'D'] += 1
    
    # Calculate Winrate
    df['Matches'] = df['W'] + df['D']
    df['Winrate'] = 0.0
    valid_mask = df['Matches'] > 0
    df.loc[valid_mask, 'Winrate'] = (df.loc[valid_mask, 'W'] / df.loc[valid_mask, 'Matches'] * 100).round(1)

    # Calculate overall rating
    df['overall'] = (df['aim'] + df['util'] + df['team_play']) / 3
    
    conn.close()
    return df.sort_values(by="avg_kd", ascending=False)

def get_player_secret(name):
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("SELECT secret_word FROM players WHERE name = ?", (name,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else "UNKNOWN"

# --- VOTING & PIN FUNCTIONS ---
def set_draft_pins(cap1, word1, cap2, word2):
    conn = sqlite3.connect('cs2_history.db')
    conn.execute("DELETE FROM current_draft_votes")
    conn.execute("INSERT INTO current_draft_votes (captain_name, pin, vote) VALUES (?, ?, ?)", (cap1, word1, "Waiting"))
    conn.execute("INSERT INTO current_draft_votes (captain_name, pin, vote) VALUES (?, ?, ?)", (cap2, word2, "Waiting"))
    conn.commit()
    conn.close()

def submit_vote(secret_attempt, vote_choice):
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("UPDATE current_draft_votes SET vote = ? WHERE pin = ?", (vote_choice, secret_attempt))
    print(f"DEBUG: Updating vote for pin {secret_attempt} to {vote_choice}. Rows affected: {c.rowcount}")
    updated = c.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def get_vote_status():
    conn = sqlite3.connect('cs2_history.db')
    df = pd.read_sql_query("SELECT * FROM current_draft_votes ORDER BY captain_name", conn)
    conn.close()
    return df

# --- MATCH LOGGING ---
def update_elo(t1, t2, name_a, name_b, winner_idx, map_name):
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("INSERT INTO matches (team1_name, team2_name, team1_players, team2_players, winner_idx, map, elo_diff) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (name_a, name_b, ", ".join(t1), ", ".join(t2), winner_idx, map_name, 0.0))
    conn.commit()
    conn.close()

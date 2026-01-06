# database.py
import sqlite3
import pandas as pd
import json
from constants import PLAYERS_INIT

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

    c.execute('''CREATE TABLE IF NOT EXISTS active_draft_state 
                 (id INTEGER PRIMARY KEY, t1_json TEXT, t2_json TEXT, 
                  name_a TEXT, name_b TEXT, avg1 REAL, avg2 REAL, current_map TEXT)''')
    
    # NEW: Table for Live Veto Sync
    c.execute('''CREATE TABLE IF NOT EXISTS active_veto_state 
                 (id INTEGER PRIMARY KEY, remaining_maps TEXT, protected_maps TEXT, current_turn TEXT)''')

    try:
        c.execute("ALTER TABLE active_draft_state ADD COLUMN current_map TEXT")
    except:
        pass

    c.execute("SELECT COUNT(*) FROM players")
    if c.fetchone()[0] == 0:
        for name, d in PLAYERS_INIT.items():
            c.execute("INSERT INTO players VALUES (?, ?, ?, ?, ?, ?)", 
                      (name, d['elo'], d['aim'], d['util'], d['team'], "cs2pro"))
    
    c.execute("UPDATE players SET secret_word = lower(name)")
    conn.commit()
    conn.close()

# --- EXISTING DRAFT FUNCTIONS (Unchanged) ---
def save_draft_state(t1, t2, name_a, name_b, avg1, avg2):
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("DELETE FROM active_draft_state") 
    c.execute("INSERT INTO active_draft_state (id, t1_json, t2_json, name_a, name_b, avg1, avg2, current_map) VALUES (1, ?, ?, ?, ?, ?, ?, ?)",
              (json.dumps(t1), json.dumps(t2), name_a, name_b, avg1, avg2, None))
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
    c.execute("SELECT t1_json, t2_json, name_a, name_b, avg1, avg2, current_map FROM active_draft_state WHERE id=1")
    row = c.fetchone()
    conn.close()
    if row:
        return (json.loads(row[0]), json.loads(row[1]), row[2], row[3], row[4], row[5], row[6])
    return None

def clear_draft_state():
    conn = sqlite3.connect('cs2_history.db')
    conn.execute("DELETE FROM active_draft_state")
    conn.execute("DELETE FROM current_draft_votes")
    conn.execute("DELETE FROM active_veto_state") # Clear Veto too
    conn.commit()
    conn.close()

# --- NEW: VETO STATE FUNCTIONS ---
def init_veto_state(maps, turn_team):
    conn = sqlite3.connect('cs2_history.db')
    conn.execute("DELETE FROM active_veto_state")
    # Store lists as comma-separated strings
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

# --- EXISTING PLAYER/MATCH FUNCTIONS ---
def get_player_stats():
    conn = sqlite3.connect('cs2_history.db')
    df = pd.read_sql_query("SELECT *, (aim+util+team_play)/3 as overall FROM players ORDER BY elo DESC", conn)
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

    conn.close()
    return df.sort_values(by="overall", ascending=False)

def get_player_secret(name):
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("SELECT secret_word FROM players WHERE name = ?", (name,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else "UNKNOWN"

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
    updated = c.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def get_vote_status():
    conn = sqlite3.connect('cs2_history.db')
    df = pd.read_sql_query("SELECT * FROM current_draft_votes ORDER BY captain_name", conn)
    conn.close()
    return df

def update_elo(t1, t2, name_a, name_b, winner_idx, map_name):
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("INSERT INTO matches (team1_name, team2_name, team1_players, team2_players, winner_idx, map, elo_diff) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (name_a, name_b, ", ".join(t1), ", ".join(t2), winner_idx, map_name, 0.0))
    conn.commit()
    conn.close()

# database.py
import sqlite3
import pandas as pd
from constants import PLAYERS_INIT

def init_db():
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    # Create players table with secret_word column
    c.execute('''CREATE TABLE IF NOT EXISTS players 
                 (name TEXT PRIMARY KEY, elo REAL, aim REAL, util REAL, team_play REAL, secret_word TEXT)''')
    
    # MIGRATION: Add secret_word if it doesn't exist in an old DB
    try:
        c.execute("ALTER TABLE players ADD COLUMN secret_word TEXT DEFAULT 'password123'")
    except:
        pass # Column already exists

    c.execute('''CREATE TABLE IF NOT EXISTS matches 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, team1_name TEXT, team2_name TEXT,
                  team1_players TEXT, team2_players TEXT, winner_idx INTEGER, 
                  map TEXT, elo_diff REAL, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS current_draft_votes 
                 (captain_name TEXT PRIMARY KEY, pin TEXT, vote TEXT)''')
    
    c.execute("SELECT COUNT(*) FROM players")
    if c.fetchone()[0] == 0:
        for name, d in PLAYERS_INIT.items():
            c.execute("INSERT INTO players VALUES (?, ?, ?, ?, ?, ?)", 
                      (name, d['elo'], d['aim'], d['util'], d['team'], "cs2pro"))
    conn.commit()
    conn.close()

def get_player_stats():
    conn = sqlite3.connect('cs2_history.db')
    # We include secret_word in the pull for the Admin tab
    df = pd.read_sql_query("SELECT *, (aim+util+team_play)/3 as overall FROM players ORDER BY elo DESC", conn)
    
    # Calculate W/D
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
    # Check if the secret_attempt matches a 'pin' (which is now the secret word)
    c.execute("UPDATE current_draft_votes SET vote = ? WHERE pin = ?", (vote_choice, secret_attempt))
    updated = c.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def get_vote_status():
    conn = sqlite3.connect('cs2_history.db')
    df = pd.read_sql_query("SELECT * FROM current_draft_votes", conn)
    conn.close()
    return df

def update_elo(t1, t2, name_a, name_b, winner_idx, map_name):
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("INSERT INTO matches (team1_name, team2_name, team1_players, team2_players, winner_idx, map, elo_diff) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (name_a, name_b, ", ".join(t1), ", ".join(t2), winner_idx, map_name, 0.0))
    conn.commit()
    conn.close()

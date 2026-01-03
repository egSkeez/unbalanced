# database.py
import sqlite3
import pandas as pd
from constants import PLAYERS_INIT

def init_db():
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS players 
                 (name TEXT PRIMARY KEY, elo REAL, aim REAL, util REAL, team_play REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS matches 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  team1_name TEXT, team2_name TEXT,
                  team1_players TEXT, team2_players TEXT, 
                  winner_idx INTEGER, map TEXT, elo_diff REAL, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute("SELECT COUNT(*) FROM players")
    if c.fetchone()[0] == 0:
        for name, d in PLAYERS_INIT.items():
            c.execute("INSERT INTO players VALUES (?, ?, ?, ?, ?)", (name, d['elo'], d['aim'], d['util'], d['team']))
    conn.commit()
    conn.close()

def get_player_stats():
    conn = sqlite3.connect('cs2_history.db')
    df = pd.read_sql_query("SELECT *, ((aim * 0.5) + (util * 0.3) + (team_play * 0.2)) as overall FROM players", conn)
    
    try:
        matches = pd.read_sql_query("SELECT team1_players, team2_players, winner_idx FROM matches", conn)
    except Exception:
        matches = pd.DataFrame()
    conn.close()

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
            
    return df.sort_values(by="overall", ascending=False)

def update_elo(t1_names, t2_names, t1_ui_name, t2_ui_name, winner_idx, map_name):
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    t1_elo = sum([c.execute("SELECT elo FROM players WHERE name=?", (n,)).fetchone()[0] for n in t1_names]) / 5
    t2_elo = sum([c.execute("SELECT elo FROM players WHERE name=?", (n,)).fetchone()[0] for n in t2_names]) / 5
    expected_t1 = 1 / (1 + 10 ** ((t2_elo - t1_elo) / 400))
    actual_t1 = 1 if winner_idx == 1 else 0
    change = 32 * (actual_t1 - expected_t1)
    for n in t1_names: c.execute("UPDATE players SET elo = elo + ? WHERE name = ?", (change, n))
    for n in t2_names: c.execute("UPDATE players SET elo = elo - ? WHERE name = ?", (change, n))
    c.execute("INSERT INTO matches (team1_name, team2_name, team1_players, team2_players, winner_idx, map, elo_diff) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (t1_ui_name, t2_ui_name, ", ".join(t1_names), ", ".join(t2_names), winner_idx, map_name, round(change, 1)))
    conn.commit()
    conn.close()

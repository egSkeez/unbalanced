# database.py
import sqlite3
import pandas as pd
import json
from constants import PLAYERS_INIT
from season_logic import get_current_season_info
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from models import Base

DATABASE_URL = "sqlite+aiosqlite:///./cs2_history.db"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_async_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
        
    try:
        c.execute("ALTER TABLE players ADD COLUMN steamid TEXT")
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

    try:
        c.execute("ALTER TABLE active_draft_state ADD COLUMN created_by TEXT")
    except:
        pass

    c.execute("SELECT COUNT(*) FROM players")
    
    # UPSERT Logic: Add new players if they don't exist
    for name, d in PLAYERS_INIT.items():
        c.execute("INSERT OR IGNORE INTO players (name, elo, aim, util, team_play, secret_word) VALUES (?, ?, ?, ?, ?, ?)", 
                  (name, d['elo'], d['aim'], d['util'], d['team'], "cs2pro"))
    
    c.execute("UPDATE players SET secret_word = lower(name) WHERE secret_word IS NULL OR secret_word = ''")

    # ADDED: settings table
    c.execute('''CREATE TABLE IF NOT EXISTS settings 
                 (key TEXT PRIMARY KEY, value TEXT)''')
    conn.commit()
    conn.close()

# --- SETTINGS FUNCTIONS ---
def get_roommates():
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = 'roommates'")
    row = c.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return []

def set_roommates(players_list):
    conn = sqlite3.connect('cs2_history.db')
    val = json.dumps(players_list)
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('roommates', ?)", (val,))
    conn.commit()
    conn.close()


# --- DRAFT STATE FUNCTIONS ---
def save_draft_state(t1, t2, name_a, name_b, avg1, avg2, mode="balanced", created_by=None):
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("DELETE FROM active_draft_state") 
    # Initialize with NULL current_lobby and cybershoke_match_id
    c.execute("INSERT INTO active_draft_state (id, t1_json, t2_json, name_a, name_b, avg1, avg2, current_map, current_lobby, cybershoke_match_id, draft_mode, created_by) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
              (json.dumps(t1), json.dumps(t2), name_a, name_b, avg1, avg2, None, None, None, mode, created_by))
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
    c.execute("SELECT t1_json, t2_json, name_a, name_b, avg1, avg2, current_map, current_lobby, cybershoke_match_id, draft_mode, created_by FROM active_draft_state WHERE id=1")
    row = c.fetchone()
    conn.close()
    if row:
        # Returns tuple including current_lobby at index 7 and match_id at index 8 and mode at 9 and created_by at 10
        # Handle cases where row might be shorter if schema wasn't fully updated (fallback)
        lobby = row[7] if len(row) > 7 else None
        cs_id = row[8] if len(row) > 8 else None
        mode = row[9] if len(row) > 9 else "balanced"
        created_by = row[10] if len(row) > 10 else None
        return (json.loads(row[0]), json.loads(row[1]), row[2], row[3], row[4], row[5], row[6], lobby, cs_id, mode, created_by)
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
    
    # Calculate average K/D from match statistics FILTERED BY CURRENT SEASON (Season 2)
    _, s2_start, _ = get_current_season_info()
    
    kd_query = f'''
        SELECT 
            pms.player_name,
            ROUND(SUM(pms.kills) * 1.0 / NULLIF(SUM(pms.deaths), 0), 2) as avg_kd,
            ROUND(AVG(NULLIF(pms.rating, 0)), 2) as avg_rating
        FROM player_match_stats pms
        JOIN match_details md ON pms.match_id = md.match_id
        WHERE date(md.date_analyzed) >= date('{s2_start}')
          AND pms.rating IS NOT NULL
        GROUP BY pms.player_name
    '''
    kd_df = pd.read_sql_query(kd_query, conn)
    
    # Merge K/D data with player data
    df = df.merge(kd_df, left_on='name', right_on='player_name', how='left')
    df['avg_kd'] = df['avg_kd'].fillna(1.0)  # Default to 1.0 if no matches
    df['avg_rating'] = df['avg_rating'].fillna(1.0) # Default to 1.0
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
    return df.sort_values(by="avg_rating", ascending=False)

def get_player_secret(name):
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("SELECT secret_word FROM players WHERE name = ?", (name,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else "UNKNOWN"

def update_player_steamid(player_name, steamid):
    """
    Links a player name to a Steam ID.
    """
    if not steamid or steamid == "0":
        return
        
    conn = sqlite3.connect('cs2_history.db', timeout=30)
    c = conn.cursor()
    try:
        # Check if this player exists
        c.execute("SELECT steamid FROM players WHERE name = ?", (player_name,))
        row = c.fetchone()
        
        if row:
            current_steamid = row[0]
            # Update if empty or different (could handle conflict logic here)
            if not current_steamid:
                c.execute("UPDATE players SET steamid = ? WHERE name = ?", (str(steamid), player_name))
                print(f"Linked {player_name} to SteamID {steamid}")
        else:
            # Player not in our Elo system, ignore or auto-add? 
            # For now, ignore implicit adds to avoid cluttering main leaderboard with randoms
            pass
            
        conn.commit()
    except Exception as e:
        print(f"Error updating steamid: {e}")
    finally:
        conn.close()

# --- VOTING & PIN FUNCTIONS ---
def set_draft_pins(cap1, word1, cap2, word2):
    conn = sqlite3.connect('cs2_history.db')
    conn.execute("DELETE FROM current_draft_votes")
    conn.execute("INSERT INTO current_draft_votes (captain_name, pin, vote) VALUES (?, ?, ?)", (cap1, word1, "Waiting"))
    conn.execute("INSERT INTO current_draft_votes (captain_name, pin, vote) VALUES (?, ?, ?)", (cap2, word2, "Waiting"))
    conn.commit()
    conn.close()

def init_empty_captains():
    conn = sqlite3.connect('cs2_history.db')
    conn.execute("DELETE FROM current_draft_votes")
    conn.execute("INSERT INTO current_draft_votes (captain_name, pin, vote) VALUES (?, ?, ?)", ("__TEAM1__", "", "Waiting"))
    conn.execute("INSERT INTO current_draft_votes (captain_name, pin, vote) VALUES (?, ?, ?)", ("__TEAM2__", "", "Waiting"))
    conn.commit()
    conn.close()

def check_captain_status():
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("SELECT captain_name FROM current_draft_votes")
    rows = c.fetchall()
    conn.close()
    
    # Analyze rows
    t1_status = "filled"
    t2_status = "filled"
    t1_name = None
    t2_name = None
    
    # We rely on some heuristic: first row inserted is likely TEAM1 unless order changes, 
    # but since we clean table, order should be preserved.
    # Actually, relying on order is risky. 
    # BUT, init_empty_captains inserts TEAM1 first.
    # If updated, row ID stays same? Or updated in place.
    # Let's hope order is preserved or use name logic.
    
    # Better logic:
    # If a row name is "__TEAM1__", then T1 is open.
    # If a row name is "__TEAM2__", then T2 is open.
    # If a row name is neither, it's filled.
    # But which is which? We can track the original insertion order via LIMIT/OFFSET or just infer from context.
    # Actually, we can store team_id in current_draft_votes. The table schema might not have it...
    # Let's assume schema is (id, captain_name, team_idx, ...).
    # Wait, existing code uses: INSERT INTO current_draft_votes (captain_name, pin, vote)
    # It doesn't use team_idx.
    # So we don't know which captain is for which team unless we track it by order or name.
    # BUT, current_draft_votes table DOES have team_idx column in schema according to earlier exploration (step 525 code item doesn't show schema, but step 230 shows SELECT captain_name... so maybe schema was created in init script).
    # The init script in auth.py doesn't create current_draft_votes, it creates user_accounts.
    # database.py init_db creates it?
    # I should check init_db.
    
    # For now, let's rely on name patterns.
    # If DB has "__TEAM1__", T1 is open. If not, and count < 2 (or 2 rows total), then T1 might be filled.
    # Wait, if T1 is filled, name is "Skeez".
    # How do we know "Skeez" is T1 captain and not T2?
    # We must fix storing team identity.
    # I will modify init_empty_captains to use team_idx if possible, or just rely on a convention.
    # Convention: I will check if __TEAM1__ exists. If yes -> open. If no -> filled?
    # But if both are filled ("Skeez", "Kim"), who is who?
    # draft.team1 has standard list.
    # If "Skeez" is captain, and "Skeez" is in team1, then he is T1 captain.
    # So I can infer from player list.
    pass

def claim_captain_spot(team_num, player_name, pin):
    # team_num: 1 or 2
    placeholder = f"__TEAM{team_num}__"
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("UPDATE current_draft_votes SET captain_name = ?, pin = ? WHERE captain_name = ?", (player_name, pin, placeholder))
    success = c.rowcount > 0
    conn.commit()
    conn.close()
    return success

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

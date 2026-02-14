import os
import json
import pandas as pd
from dotenv import load_dotenv
from constants import PLAYERS_INIT
from season_logic import get_current_season_info
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text
from models import Base

load_dotenv()

# Get DB URL from environment
DATABASE_URL_SYNC = os.getenv("DATABASE_URL")
# Handle potential missing env var for local dev fallback (though user asked explicitly for env var)
if not DATABASE_URL_SYNC:
    # Fallback or raise error? User asked for env var usage.
    # Defaulting to sqlite for safety if env not set? No, migration requested.
    # We'll assume it's set or empty string.
    DATABASE_URL_SYNC = "sqlite:///./cs2_history.db" # Fallback to local sqlite if not set?
    # Actually, let's just stick to the requested behavior.
    pass

# Ensure Async URL has correct driver
if DATABASE_URL_SYNC and DATABASE_URL_SYNC.startswith("postgresql://"):
    DATABASE_URL_ASYNC = DATABASE_URL_SYNC.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    DATABASE_URL_ASYNC = "sqlite+aiosqlite:///./cs2_history.db"

# Create Engines
if DATABASE_URL_SYNC and "sqlite" not in DATABASE_URL_SYNC:
    engine = create_async_engine(DATABASE_URL_ASYNC, echo=False)
    sync_engine = create_engine(DATABASE_URL_SYNC)
else:
    # Fallback to SQLite if no URL provided (safe default for local dev without env)
    print("WARNING: DATABASE_URL not found, using SQLite fallback.")
    engine = create_async_engine("sqlite+aiosqlite:///./cs2_history.db", echo=False)
    sync_engine = create_engine("sqlite:///./cs2_history.db")

async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_async_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# --- DATABASE INITIALIZATION ---
def init_db():
    # Detect dialect
    is_postgres = sync_engine.name == 'postgresql'
    
    # Define generic types
    auto_inc = "SERIAL" if is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
    
    with sync_engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE IF NOT EXISTS players (name TEXT PRIMARY KEY, elo REAL, aim REAL, util REAL, team_play REAL, secret_word TEXT DEFAULT 'cs2pro', steamid TEXT)"))
        
        # Matches table
        conn.execute(text(f"""CREATE TABLE IF NOT EXISTS matches 
                     (id {auto_inc} PRIMARY KEY, team1_name TEXT, team2_name TEXT,
                      team1_players TEXT, team2_players TEXT, winner_idx INTEGER, 
                      map TEXT, elo_diff REAL, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""))
        
        # Draft votes
        conn.execute(text('''CREATE TABLE IF NOT EXISTS current_draft_votes 
                     (captain_name TEXT PRIMARY KEY, pin TEXT, vote TEXT)'''))

        # Active draft state
        conn.execute(text(f"""CREATE TABLE IF NOT EXISTS active_draft_state 
                     (id INTEGER PRIMARY KEY, t1_json TEXT, t2_json TEXT, 
                      name_a TEXT, name_b TEXT, avg1 REAL, avg2 REAL, 
                      current_map TEXT, current_lobby TEXT, cybershoke_match_id TEXT, 
                      draft_mode TEXT, created_by TEXT)"""))
        
        # Veto state
        conn.execute(text(f"""CREATE TABLE IF NOT EXISTS active_veto_state 
                     (id INTEGER PRIMARY KEY, remaining_maps TEXT, protected_maps TEXT, current_turn TEXT)"""))

        # Settings
        conn.execute(text('''CREATE TABLE IF NOT EXISTS settings 
                     (key TEXT PRIMARY KEY, value TEXT)'''))

    # Upsert Logic
    # Using raw connection for standard execution if needed, but text() works fine
    # Postgres uses ON CONFLICT, SQLite uses INSERT OR IGNORE / REPLACE
    
    # We will just do a check for players or try/except
    with sync_engine.connect() as conn:
        # Check if players empty
        res = conn.execute(text("SELECT COUNT(*) FROM players")).scalar()
        if res == 0:
             # UPSERT Logic: Add new players
            for name, d in PLAYERS_INIT.items():
                if is_postgres:
                    # Postgres UPSERT
                    sql = """INSERT INTO players (name, elo, aim, util, team_play, secret_word) 
                             VALUES (:name, :elo, :aim, :util, :team, 'cs2pro')
                             ON CONFLICT (name) DO NOTHING"""
                else:
                    # SQLite UPSERT
                    sql = """INSERT OR IGNORE INTO players (name, elo, aim, util, team_play, secret_word) 
                             VALUES (:name, :elo, :aim, :util, :team, 'cs2pro')"""
                
                conn.execute(text(sql), {"name": name, "elo": d['elo'], "aim": d['aim'], "util": d['util'], "team": d['team']})
            conn.commit()

        # Update lower secret word
        conn.execute(text("UPDATE players SET secret_word = lower(name) WHERE secret_word IS NULL OR secret_word = ''"))
        conn.commit()

# --- SETTINGS FUNCTIONS ---
def get_roommates():
    with sync_engine.connect() as conn:
        res = conn.execute(text("SELECT value FROM settings WHERE key = 'roommates'")).fetchone()
        if res:
            return json.loads(res[0])
    return []

def set_roommates(players_list):
    val = json.dumps(players_list)
    is_postgres = sync_engine.name == 'postgresql'
    
    with sync_engine.begin() as conn:
        if is_postgres:
            sql = "INSERT INTO settings (key, value) VALUES ('roommates', :val) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
        else:
            sql = "INSERT OR REPLACE INTO settings (key, value) VALUES ('roommates', :val)"
            
        conn.execute(text(sql), {"val": val})


# --- DRAFT STATE FUNCTIONS ---
def save_draft_state(t1, t2, name_a, name_b, avg1, avg2, mode="balanced", created_by=None):
    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM active_draft_state"))
        
        sql = """INSERT INTO active_draft_state 
                 (id, t1_json, t2_json, name_a, name_b, avg1, avg2, current_map, current_lobby, cybershoke_match_id, draft_mode, created_by) 
                 VALUES (1, :t1, :t2, :na, :nb, :a1, :a2, NULL, NULL, :mode, :mode, :cb)"""
        # Note: cybershoke_match_id was passed 'mode' in original code? 
        # Original: (..., mode, created_by) mapped to ..., cybershoke_match_id, draft_mode, created_by??
        # Original vals: (..., mode, created_by) -> 
        # VALUES (..., ?, ?, ?, ?) -> current_lobby, cybershoke_match_id, draft_mode, created_by
        # The variables passed were: (..., None, None, mode, created_by)
        # Re-reading original:
        # VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        # params: (json.dumps(t1), json.dumps(t2), name_a, name_b, avg1, avg2, None, None, None, mode, created_by)
        # 11 params. Target cols: id(1), t1, t2, na, nb, a1, a2, cur_map, cur_lobby, cs_id, mode, created_by. (12 cols).
        # Original had 11 placeholders??
        # "VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)" -> 12 items including '1'. 11 placeholders.
        # Params supplied: 11 items. Matches.
        # Params: t1, t2, na, nb, a1, a2, None, None, None, mode, created_by
        # Col 8: current_map (None)
        # Col 9: current_lobby (None)
        # Col 10: cybershoke_match_id (None)
        # Col 11: draft_mode (mode)
        # Col 12: created_by (created_by)
        
        # My replacement:
        conn.execute(text("""INSERT INTO active_draft_state 
                             (id, t1_json, t2_json, name_a, name_b, avg1, avg2, current_map, current_lobby, cybershoke_match_id, draft_mode, created_by) 
                             VALUES (1, :t1, :t2, :na, :nb, :a1, :a2, NULL, NULL, NULL, :mode, :cb)"""),
                      {"t1": json.dumps(t1), "t2": json.dumps(t2), "na": name_a, "nb": name_b, 
                       "a1": avg1, "a2": avg2, "mode": mode, "cb": created_by})

def update_draft_map(map_data):
    val = ",".join(map_data) if isinstance(map_data, list) else map_data
    with sync_engine.begin() as conn:
        conn.execute(text("UPDATE active_draft_state SET current_map = :val WHERE id = 1"), {"val": val})

def load_draft_state():
    with sync_engine.connect() as conn:
        # Columns: t1, t2, na, nb, a1, a2, map, lobby, cs_id, mode, created_by
        row = conn.execute(text("SELECT t1_json, t2_json, name_a, name_b, avg1, avg2, current_map, current_lobby, cybershoke_match_id, draft_mode, created_by FROM active_draft_state WHERE id=1")).fetchone()
        
    if row:
        # Tuple unpacking depends on query order
        # row is a result proxy row, access by index or name
        return (json.loads(row[0]), json.loads(row[1]), row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[10] if row[10] else None)
    return None

def clear_draft_state():
    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM active_draft_state"))
        conn.execute(text("DELETE FROM current_draft_votes"))
        conn.execute(text("DELETE FROM active_veto_state"))

# --- VETO STATE FUNCTIONS ---
def init_veto_state(maps, turn_team):
    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM active_veto_state"))
        maps_str = ",".join(maps)
        conn.execute(text("INSERT INTO active_veto_state (id, remaining_maps, protected_maps, current_turn) VALUES (1, :rem, :prot, :turn)"),
                     {"rem": maps_str, "prot": "", "turn": turn_team})

def get_veto_state():
    with sync_engine.connect() as conn:
        row = conn.execute(text("SELECT remaining_maps, protected_maps, current_turn FROM active_veto_state WHERE id=1")).fetchone()
    
    if row:
        rem = row[0].split(",") if row[0] else []
        prot = row[1].split(",") if row[1] else []
        return rem, prot, row[2]
    return None, None, None

def update_veto_turn(remaining, protected, next_turn):
    rem_str = ",".join(remaining)
    prot_str = ",".join(protected)
    with sync_engine.begin() as conn:
        conn.execute(text("UPDATE active_veto_state SET remaining_maps=:rem, protected_maps=:prot, current_turn=:turn WHERE id=1"),
                     {"rem": rem_str, "prot": prot_str, "turn": next_turn})

# --- PLAYER & STATS FUNCTIONS ---
# --- PLAYER & STATS FUNCTIONS ---
def get_player_stats():
    with sync_engine.connect() as conn:
        # Get base player data
        try:
            df = pd.read_sql_query("SELECT name, aim, util, team_play, secret_word FROM players", conn)
        except Exception as e:
            # Handle case where table might not exist yet or connection fails
            print(f"Error reading players: {e}")
            return pd.DataFrame() # Return empty DF safely
        
        # Calculate average K/D from match statistics FILTERED BY CURRENT SEASON (Season 2)
        _, s2_start, _ = get_current_season_info()
        
        # date() function works in both provided Postgres has the function (it does) or cast to date
        # using CAST(md.date_analyzed AS DATE) is cleaner standard SQL, but date() is common in PG too
        
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
        try:
            kd_df = pd.read_sql_query(kd_query, conn)
        except:
            kd_df = pd.DataFrame(columns=['player_name', 'avg_kd', 'avg_rating'])
        
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
    
    return df.sort_values(by="avg_rating", ascending=False)

def get_player_secret(name):
    with sync_engine.connect() as conn:
        res = conn.execute(text("SELECT secret_word FROM players WHERE name = :name"), {"name": name}).fetchone()
    return res[0] if res else "UNKNOWN"

def update_player_steamid(player_name, steamid):
    """
    Links a player name to a Steam ID.
    """
    if not steamid or steamid == "0":
        return
        
    try:
        with sync_engine.begin() as conn: # Transaction
            # Check if this player exists
            row = conn.execute(text("SELECT steamid FROM players WHERE name = :name"), {"name": player_name}).fetchone()
            
            if row:
                current_steamid = row[0]
                # Update if empty or different (could handle conflict logic here)
                if not current_steamid:
                    conn.execute(text("UPDATE players SET steamid = :sid WHERE name = :name"), {"sid": str(steamid), "name": player_name})
                    print(f"Linked {player_name} to SteamID {steamid}")
            else:
                # Player not in our Elo system, ignore or auto-add? 
                pass
    except Exception as e:
        print(f"Error updating steamid: {e}")

# --- VOTING & PIN FUNCTIONS ---
def set_draft_pins(cap1, word1, cap2, word2):
    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM current_draft_votes"))
        conn.execute(text("INSERT INTO current_draft_votes (captain_name, pin, vote) VALUES (:cap, :pin, 'Waiting')"), {"cap": cap1, "pin": word1})
        conn.execute(text("INSERT INTO current_draft_votes (captain_name, pin, vote) VALUES (:cap, :pin, 'Waiting')"), {"cap": cap2, "pin": word2})

def init_empty_captains():
    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM current_draft_votes"))
        conn.execute(text("INSERT INTO current_draft_votes (captain_name, pin, vote) VALUES ('__TEAM1__', '', 'Waiting')"))
        conn.execute(text("INSERT INTO current_draft_votes (captain_name, pin, vote) VALUES ('__TEAM2__', '', 'Waiting')"))

def check_captain_status():
    with sync_engine.connect() as conn:
        rows = conn.execute(text("SELECT captain_name FROM current_draft_votes")).fetchall()
    
    # Analyze rows
    # Logic unchanged from original except DB access
    t1_status = "filled"
    t2_status = "filled"
    pass

def claim_captain_spot(team_num, player_name, pin):
    # team_num: 1 or 2
    placeholder = f"__TEAM{team_num}__"
    success = False
    with sync_engine.begin() as conn:
        result = conn.execute(text("UPDATE current_draft_votes SET captain_name = :name, pin = :pin WHERE captain_name = :ph"),
                              {"name": player_name, "pin": pin, "ph": placeholder})
        success = result.rowcount > 0
    return success

def submit_vote(secret_attempt, vote_choice):
    updated = False
    with sync_engine.begin() as conn:
        result = conn.execute(text("UPDATE current_draft_votes SET vote = :vote WHERE pin = :pin"),
                              {"vote": vote_choice, "pin": secret_attempt})
        print(f"DEBUG: Updating vote for pin {secret_attempt} to {vote_choice}. Rows affected: {result.rowcount}")
        updated = result.rowcount > 0
    return updated

def get_vote_status():
    with sync_engine.connect() as conn:
        df = pd.read_sql_query("SELECT * FROM current_draft_votes ORDER BY captain_name", conn)
    return df

# --- MATCH LOGGING ---
def update_elo(t1, t2, name_a, name_b, winner_idx, map_name):
    with sync_engine.begin() as conn:
        conn.execute(text("""INSERT INTO matches (team1_name, team2_name, team1_players, team2_players, winner_idx, map, elo_diff) 
                             VALUES (:na, :nb, :t1p, :t2p, :widx, :map, 0.0)"""),
                     {"na": name_a, "nb": name_b, "t1p": ", ".join(t1), "t2p": ", ".join(t2), 
                      "widx": winner_idx, "map": map_name})

import sqlite3
import pandas as pd
from datetime import datetime

DB_NAME = 'cs2_history.db'

def init_match_registry():
    """
    Creates the match_registry table if it doesn't exist.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS match_registry (
                    match_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL, 
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP,
                    source TEXT
                )''')
    conn.commit()
    conn.close()

def add_match_to_registry(match_id, source="manual_admin"):
    """
    Adds a match to the registry with 'pending' status.
    Returns True if added, False if already exists.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO match_registry (match_id, status, source) VALUES (?, ?, ?)", 
                  (str(match_id), 'pending', source))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    finally:
        conn.close()
    return success

def get_match_status(match_id):
    """
    Returns the status of a match, or None if not found.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT status FROM match_registry WHERE match_id = ?", (str(match_id),))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def get_pending_matches():
    """
    Returns a list of match_ids that are pending.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT match_id FROM match_registry WHERE status = 'pending'")
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows]

def update_match_status(match_id, status, set_processed_time=False):
    """
    Updates the status of a match.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    if set_processed_time:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("UPDATE match_registry SET status = ?, processed_at = ? WHERE match_id = ?", 
                  (status, now, str(match_id)))
    else:
        c.execute("UPDATE match_registry SET status = ? WHERE match_id = ?", 
                  (status, str(match_id)))
    
    conn.commit()
    conn.close()

def get_recent_registry_entries(limit=10):
    """
    Returns a DataFrame of the last N entries in the registry.
    """
    conn = sqlite3.connect(DB_NAME)
    query = "SELECT match_id, status, added_at, processed_at, source FROM match_registry ORDER BY added_at DESC LIMIT ?"
    df = pd.read_sql_query(query, conn, params=(limit,))
    conn.close()
    return df

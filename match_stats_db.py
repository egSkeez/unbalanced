
import pandas as pd
from sqlalchemy import text as sa_text

from database import sync_engine

def _is_postgres():
    return sync_engine.name == 'postgresql'

def init_match_stats_tables():
    """
    Creates tables for storing detailed match statistics from demo files.
    IMPORTANT: On PostgreSQL, each ALTER TABLE migration MUST run in its own
    transaction. If an ALTER fails (e.g. column already exists), PG aborts
    the entire transaction, causing all subsequent statements to fail.
    """
    is_pg = _is_postgres()

    # Phase 1: Create tables and indexes (these use IF NOT EXISTS, so they're safe)
    with sync_engine.begin() as conn:
        # Table for match metadata
        conn.execute(sa_text('''CREATE TABLE IF NOT EXISTS match_details
                     (match_id TEXT PRIMARY KEY,
                      cybershoke_id TEXT,
                      date_analyzed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      map TEXT,
                      score_t INTEGER,
                      score_ct INTEGER,
                      total_rounds INTEGER)'''))

        # Table for player performance in each match
        if is_pg:
            conn.execute(sa_text('''CREATE TABLE IF NOT EXISTS player_match_stats
                         (id SERIAL PRIMARY KEY,
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
                          total_spent INTEGER,
                          entry_kills INTEGER,
                          entry_deaths INTEGER,
                          clutch_wins INTEGER,
                          rounds_last_alive INTEGER,
                          team_flashed INTEGER,
                          FOREIGN KEY (match_id) REFERENCES match_details(match_id))'''))
        else:
            conn.execute(sa_text('''CREATE TABLE IF NOT EXISTS player_match_stats
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
                          total_spent INTEGER,
                          entry_kills INTEGER,
                          entry_deaths INTEGER,
                          clutch_wins INTEGER,
                          rounds_last_alive INTEGER,
                          team_flashed INTEGER,
                          FOREIGN KEY (match_id) REFERENCES match_details(match_id))'''))

        # Table for tracking Cybershoke lobbies
        conn.execute(sa_text('''CREATE TABLE IF NOT EXISTS cybershoke_lobbies
                     (lobby_id TEXT PRIMARY KEY,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      has_demo INTEGER DEFAULT 0,
                      analysis_status TEXT DEFAULT 'pending',
                      notes TEXT)'''))

        # Create indexes for faster queries
        conn.execute(sa_text('''CREATE INDEX IF NOT EXISTS idx_player_match
                     ON player_match_stats(player_name, match_id)'''))
        conn.execute(sa_text('''CREATE INDEX IF NOT EXISTS idx_match_date
                     ON match_details(date_analyzed)'''))
        conn.execute(sa_text('''CREATE INDEX IF NOT EXISTS idx_cybershoke_id
                     ON match_details(cybershoke_id)'''))

    # Phase 2: Run ALTER TABLE migrations — each in its own transaction
    # so that a failure (column already exists) doesn't poison the rest.
    migration_cols = [
        ("player_match_stats", "player_team", "INTEGER"),
        ("player_match_stats", "match_result", "TEXT"),
        ("player_match_stats", "total_spent", "INTEGER DEFAULT 0"),
        ("player_match_stats", "entry_kills", "INTEGER DEFAULT 0"),
        ("player_match_stats", "entry_deaths", "INTEGER DEFAULT 0"),
        ("player_match_stats", "clutch_wins", "INTEGER DEFAULT 0"),
        ("player_match_stats", "rounds_last_alive", "INTEGER DEFAULT 0"),
        ("player_match_stats", "team_flashed", "INTEGER DEFAULT 0"),
        ("player_match_stats", "flash_assists", "INTEGER DEFAULT 0"),
        ("player_match_stats", "bomb_plants", "INTEGER DEFAULT 0"),
        ("player_match_stats", "bomb_defuses", "INTEGER DEFAULT 0"),
        ("player_match_stats", "multi_kills", "TEXT DEFAULT '0'"),
        ("player_match_stats", "weapon_kills", "TEXT DEFAULT '0'"),
        ("player_match_stats", "rating", "REAL DEFAULT 0"),
        ("match_details", "lobby_url", "TEXT"),
    ]
    for table, col, col_type in migration_cols:
        try:
            with sync_engine.begin() as conn:
                conn.execute(sa_text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                print(f"[MIGRATION] Added {table}.{col}")
        except Exception:
            pass  # column already exists — safe to ignore


def is_lobby_already_analyzed(cybershoke_id):
    """
    Checks if a match with this cybershoke_id has already been analyzed.
    Returns True if already exists, False otherwise.
    Ignores 'manual' entries.
    """
    if not cybershoke_id or cybershoke_id == 'manual':
        return False

    with sync_engine.connect() as conn:
        result = conn.execute(
            sa_text("SELECT match_id FROM match_details WHERE cybershoke_id = :cid"),
            {"cid": str(cybershoke_id)}
        ).fetchone()

    return result is not None

def calculate_hltv_rating(row, total_rounds):
    """
    Calculates an approximation of HLTV Rating 2.0.
    Formula blends KPR, DPR, ADR and Multi-kill stats.
    Returns None if essential demo stats (ADR) are missing.
    """
    if total_rounds == 0:
        return None

    kills = row.get('Kills', 0)
    deaths = row.get('Deaths', 0)
    adr = row.get('ADR', 0)

    if adr <= 0:
        return None

    kpr = kills / total_rounds
    kill_rating = kpr / 0.679

    survival_rate = (total_rounds - deaths) / total_rounds
    survival_rating = survival_rate / 0.317

    adr_rating = adr / 80.0

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

    mk_val = 0
    if mk:
        def get_cnt(d, k):
            return int(d.get(str(k), 0)) + int(d.get(int(k), 0))

        k1 = get_cnt(mk, 1)
        k2 = get_cnt(mk, 2)
        k3 = get_cnt(mk, 3)
        k4 = get_cnt(mk, 4)
        k5 = get_cnt(mk, 5)
        mk_val = (k1 + 4*k2 + 9*k3 + 16*k4 + 25*k5) / total_rounds

    mk_rating = mk_val / 1.277

    rating10 = (kill_rating + 0.7 * survival_rating + mk_rating) / 2.7
    rating = (rating10 + adr_rating) / 2.0

    return round(rating, 2)

def save_match_stats(match_id, cybershoke_id, score_str, stats_df, map_name="Unknown", score_t=0, score_ct=0, force_overwrite=False, lobby_url=None):
    """
    Saves match statistics to the database.
    If a match with the same cybershoke_id already exists, skips saving unless force_overwrite=True.
    Returns True if saved, False if skipped due to duplicate.
    """
    import json

    if not force_overwrite and cybershoke_id and cybershoke_id != 'manual':
        if is_lobby_already_analyzed(cybershoke_id):
            print(f"⚠️ Match with cybershoke_id {cybershoke_id} already analyzed. Skipping duplicate.")
            return False

    if score_t == 0 and score_ct == 0:
        try:
            if "T" in score_str and "CT" in score_str:
                parts = score_str.split("-")
                score_t = int(parts[0].replace("T", "").strip())
                score_ct = int(parts[1].replace("CT", "").strip())
        except:
            pass

    total_rounds = score_t + score_ct

    if not lobby_url and cybershoke_id and cybershoke_id != 'manual':
        lobby_url = f"https://cybershoke.net/match/{cybershoke_id}"

    steam_id_updates = []

    with sync_engine.begin() as conn:
        # Delete existing match first
        conn.execute(sa_text("DELETE FROM match_details WHERE match_id = :mid"), {"mid": match_id})

        if force_overwrite and cybershoke_id and cybershoke_id != 'manual':
            conn.execute(sa_text("DELETE FROM match_details WHERE cybershoke_id = :cid"), {"cid": str(cybershoke_id)})

        conn.execute(sa_text('''INSERT INTO match_details
                     (match_id, cybershoke_id, map, score_t, score_ct, total_rounds, lobby_url)
                     VALUES (:mid, :cid, :map, :st, :sct, :tr, :url)'''),
                  {"mid": match_id, "cid": cybershoke_id, "map": map_name,
                   "st": score_t, "sct": score_ct, "tr": total_rounds, "url": lobby_url})

        conn.execute(sa_text("DELETE FROM player_match_stats WHERE match_id = :mid"), {"mid": match_id})

        for _, row in stats_df.iterrows():
            p_team = row.get('TeamNum', 0)
            p_name = row.get('Player', '')
            p_steam = str(row.get('SteamID', ''))

            if p_name and p_steam:
                steam_id_updates.append((p_name, p_steam))

            result = 'T'
            if score_t > score_ct:
                result = 'W' if p_team == 2 else 'L'
            elif score_ct > score_t:
                result = 'W' if p_team == 3 else 'L'
            else:
                result = 'D'

            multi_kills_json = json.dumps(row.get('MultiKills', {}))
            weapon_kills_json = json.dumps(row.get('WeaponKills', {}))

            conn.execute(sa_text('''INSERT INTO player_match_stats
                          (match_id, player_name, steamid, kills, deaths, assists, score,
                           damage, adr, headshot_kills, headshot_pct, util_damage,
                           enemies_flashed, kd_ratio, player_team, match_result,
                           total_spent, entry_kills, entry_deaths, clutch_wins, rounds_last_alive, team_flashed,
                           flash_assists, bomb_plants, bomb_defuses, multi_kills, weapon_kills, rating)
                          VALUES (:mid, :pname, :steam, :kills, :deaths, :assists, :score,
                                  :damage, :adr, :hs_kills, :hs_pct, :util_dmg,
                                  :flashed, :kd, :pteam, :result,
                                  :spent, :ek, :ed, :clutch, :rla, :tf,
                                  :fa, :bp, :bd, :mk, :wk, :rating)'''),
                       {"mid": match_id, "pname": p_name, "steam": p_steam,
                        "kills": row.get('Kills', 0), "deaths": row.get('Deaths', 0),
                        "assists": row.get('Assists', 0), "score": row.get('Score', 0),
                        "damage": row.get('Damage', 0), "adr": row.get('ADR', 0.0),
                        "hs_kills": row.get('Headshots', 0), "hs_pct": row.get('HS%', 0.0),
                        "util_dmg": row.get('UtilityDamage', 0), "flashed": row.get('Flashed', 0),
                        "kd": row.get('K/D', 0.0), "pteam": p_team, "result": result,
                        "spent": row.get('TotalSpent', 0), "ek": row.get('EntryKills', 0),
                        "ed": row.get('EntryDeaths', 0), "clutch": row.get('ClutchWins', 0),
                        "rla": row.get('BaiterRating', 0), "tf": row.get('TeamFlashed', 0),
                        "fa": row.get('FlashAssists', 0), "bp": row.get('BombPlants', 0),
                        "bd": row.get('BombDefuses', 0), "mk": multi_kills_json,
                        "wk": weapon_kills_json,
                        "rating": calculate_hltv_rating(row, total_rounds)})

    # Process Steam ID updates now that lock is released
    from database import update_player_steamid
    for name, steam in steam_id_updates:
        try:
            update_player_steamid(name, steam)
        except Exception as e:
            print(f"Failed to update steamid for {name}: {e}")

    return True

def get_player_aggregate_stats(player_name, start_date=None, end_date=None):
    """
    Get aggregate statistics for a player, optionally filtered by date range (season).
    """
    with sync_engine.connect() as conn:
        # 1. Try to find SteamID for this player
        row = conn.execute(
            sa_text("SELECT steamid FROM players WHERE name = :name"),
            {"name": player_name}
        ).fetchone()
        steamid = row[0] if row else None

        if steamid:
            where_clause = "WHERE (pms.steamid = :steamid OR pms.player_name = :pname)"
            params = {"steamid": steamid, "pname": player_name}
        else:
            where_clause = "WHERE pms.player_name = :pname"
            params = {"pname": player_name}

        where_clause += " AND pms.rating IS NOT NULL"

        if start_date:
            where_clause += " AND date(md.date_analyzed) >= date(:start_date)"
            params["start_date"] = str(start_date)
        if end_date:
            where_clause += " AND date(md.date_analyzed) <= date(:end_date)"
            params["end_date"] = str(end_date)

        query = f'''
            SELECT
                COUNT(*) as matches_played,
                SUM(pms.kills) as total_kills,
                SUM(pms.deaths) as total_deaths,
                SUM(pms.assists) as total_assists,
                ROUND(AVG(NULLIF(pms.adr, 0)), 1) as avg_adr,
                ROUND(AVG(NULLIF(pms.rating, 0)), 2) as avg_rating,
                ROUND(AVG(NULLIF(pms.headshot_pct, 0)), 1) as avg_hs_pct,
                ROUND(SUM(pms.kills) * 1.0 / NULLIF(SUM(pms.deaths), 0), 2) as overall_kd,
                SUM(pms.entry_kills) as total_entry_kills,
                SUM(pms.entry_deaths) as total_entry_deaths,
                SUM(pms.util_damage) as total_util_dmg,
                SUM(pms.flash_assists) as total_flash_assists,
                SUM(pms.enemies_flashed) as total_enemies_flashed,
                SUM(pms.bomb_plants) as total_plants,
                SUM(pms.bomb_defuses) as total_defuses,
                SUM(pms.clutch_wins) as total_clutches,
                COUNT(CASE WHEN pms.match_result = 'W' THEN 1 END) as wins,
                COUNT(CASE WHEN pms.match_result = 'L' THEN 1 END) as losses,
                COUNT(CASE WHEN pms.match_result = 'D' THEN 1 END) as draws
            FROM player_match_stats pms
            JOIN match_details md ON pms.match_id = md.match_id
            {where_clause}
        '''

        df = pd.read_sql_query(query, conn, params=params)

    if not df.empty and df.iloc[0]['matches_played'] > 0:
        matches = df.iloc[0]['matches_played']
        wins = df.iloc[0]['wins']
        df['winrate_pct'] = round((wins / matches) * 100, 1)
    else:
        df['winrate_pct'] = 0.0

    return df

def get_recent_matches(limit=10):
    """
    Get recent matches with basic info.
    """
    with sync_engine.connect() as conn:
        query = '''
            SELECT match_id, cybershoke_id, map,
                   CAST(score_t AS TEXT) || '-' || CAST(score_ct AS TEXT) as score,
                   date_analyzed, lobby_url
            FROM match_details
            ORDER BY date_analyzed DESC
            LIMIT :lim
        '''
        df = pd.read_sql_query(query, conn, params={"lim": limit})
    return df

def get_season_stats_dump(start_date, end_date):
    """
    Get aggregated stats for ALL players within a date range.
    Used for Season Leaderboards.
    """
    with sync_engine.connect() as conn:
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
                COUNT(CASE WHEN pms.match_result = 'W' THEN 1 END) as wins,
                COUNT(CASE WHEN pms.match_result = 'L' THEN 1 END) as losses
            FROM player_match_stats pms
            JOIN match_details md ON pms.match_id = md.match_id
            WHERE date(md.date_analyzed) >= date(:start_date)
              AND date(md.date_analyzed) <= date(:end_date)
              AND pms.rating IS NOT NULL
            GROUP BY pms.player_name
            HAVING COUNT(*) >= 5
        '''

        df = pd.read_sql_query(query, conn, params={"start_date": start_date, "end_date": end_date})

    if not df.empty:
        df['avg_kills'] = df['total_kills'] / df['matches_played']
        df['avg_assists'] = df['total_assists'] / df['matches_played']
        df['avg_entries'] = df['total_entries'] / df['matches_played']
        df['avg_bait_rounds'] = df['total_bait_rounds'] / df['matches_played']
        df['avg_spent'] = df['total_spent_cash'] / df['matches_played']
        df['avg_flashed'] = df['total_flashed'] / df['matches_played']
        df['avg_util_dmg'] = df['total_util_dmg'] / df['matches_played']
        df['avg_flash_assists'] = df['total_flash_assists'] / df['matches_played']
        df['avg_plants'] = df['total_plants'] / df['matches_played']
        df['avg_defuses'] = df['total_defuses'] / df['matches_played']
        df['winrate'] = (df['wins'] / df['matches_played']) * 100

    return df

def add_lobby(lobby_id):
    """
    Adds a new Cybershoke lobby to the tracking table.
    """
    try:
        with sync_engine.begin() as conn:
            if _is_postgres():
                conn.execute(sa_text(
                    "INSERT INTO cybershoke_lobbies (lobby_id) VALUES (:lid) ON CONFLICT (lobby_id) DO NOTHING"
                ), {"lid": str(lobby_id)})
            else:
                conn.execute(sa_text(
                    "INSERT OR IGNORE INTO cybershoke_lobbies (lobby_id) VALUES (:lid)"
                ), {"lid": str(lobby_id)})
    except Exception as e:
        print(f"Error adding lobby: {e}")

def get_all_lobbies():
    """
    Returns all tracked lobbies ordered by creation date (newest first).
    """
    with sync_engine.connect() as conn:
        query = "SELECT * FROM cybershoke_lobbies ORDER BY created_at DESC"
        df = pd.read_sql_query(query, conn)
    return df

def update_lobby_status(lobby_id, has_demo=None, status=None):
    """
    Updates the status or demo availability of a lobby.
    """
    try:
        with sync_engine.begin() as conn:
            if has_demo is not None:
                conn.execute(sa_text(
                    "UPDATE cybershoke_lobbies SET has_demo = :hd WHERE lobby_id = :lid"
                ), {"hd": int(has_demo), "lid": str(lobby_id)})

            if status is not None:
                conn.execute(sa_text(
                    "UPDATE cybershoke_lobbies SET analysis_status = :st WHERE lobby_id = :lid"
                ), {"st": status, "lid": str(lobby_id)})
    except Exception as e:
        print(f"Error updating lobby: {e}")

def get_match_scoreboard(match_id):
    """
    Retrieves the full scoreboard (player stats) for a specific match.
    """
    with sync_engine.connect() as conn:
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
            WHERE match_id = :mid
            ORDER BY score DESC
        '''
        df = pd.read_sql_query(query, conn, params={"mid": str(match_id)})
    return df

def get_player_weapon_stats(player_name, start_date=None, end_date=None):
    """
    Get weapon-specific statistics (average kills per game) for a player.
    """
    import json

    with sync_engine.connect() as conn:
        # 1. Try to find SteamID
        row = conn.execute(
            sa_text("SELECT steamid FROM players WHERE name = :name"),
            {"name": player_name}
        ).fetchone()
        steamid = row[0] if row else None

        if steamid:
            where_clause = "WHERE (pms.steamid = :steamid OR pms.player_name = :pname)"
            params = {"steamid": steamid, "pname": player_name}
        else:
            where_clause = "WHERE pms.player_name = :pname"
            params = {"pname": player_name}

        where_clause += " AND pms.rating IS NOT NULL"

        if start_date:
            where_clause += " AND date(md.date_analyzed) >= date(:start_date)"
            params["start_date"] = str(start_date)
        if end_date:
            where_clause += " AND date(md.date_analyzed) <= date(:end_date)"
            params["end_date"] = str(end_date)

        query = f'''
            SELECT pms.weapon_kills, COUNT(*) OVER() as total_matches
            FROM player_match_stats pms
            JOIN match_details md ON pms.match_id = md.match_id
            {where_clause}
        '''

        df = pd.read_sql_query(query, conn, params=params)

    if df.empty:
        return []

    weapon_totals = {}
    total_matches = int(df.iloc[0]['total_matches']) if not df.empty else 1

    for _, row in df.iterrows():
        try:
            w = json.loads(row['weapon_kills']) if row['weapon_kills'] else {}
            if isinstance(w, dict):
                for weapon, kills in w.items():
                    weapon_totals[weapon] = weapon_totals.get(weapon, 0) + kills
        except:
            continue

    result = []
    for weapon, total in weapon_totals.items():
        result.append({
            "weapon": weapon,
            "total_kills": int(total),
            "avg_kills": float(round(total / total_matches, 2))
        })

    result.sort(key=lambda x: x['avg_kills'], reverse=True)
    return result

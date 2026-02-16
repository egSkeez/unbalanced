"""
Startup data sync: copies local SQLite data to the production database (PostgreSQL).
Only runs when the production DB is empty for a given table, to avoid duplicating data.
Called during app startup in the lifespan handler.
"""
import sqlite3
import os
from sqlalchemy import text as sa_text


def _local_sqlite_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "cs2_history.db")


def sync_local_to_production():
    """
    Syncs data from the local SQLite cs2_history.db to the production database
    (via sync_engine). Only syncs tables that are empty in the production DB.
    """
    from database import sync_engine

    is_postgres = sync_engine.name == "postgresql"
    if not is_postgres:
        # No need to sync if both local and production are the same SQLite file
        print("[SYNC] Running on SQLite — skipping production sync.")
        return

    local_db = _local_sqlite_path()
    if not os.path.exists(local_db):
        print("[SYNC] No local cs2_history.db found — skipping.")
        return

    local_conn = sqlite3.connect(local_db)
    local_conn.row_factory = sqlite3.Row

    try:
        _sync_players(sync_engine, local_conn)
        _sync_match_details(sync_engine, local_conn)
        _sync_player_match_stats(sync_engine, local_conn)
        _sync_matches(sync_engine, local_conn)
        _sync_cybershoke_lobbies(sync_engine, local_conn)
    except Exception as e:
        print(f"[SYNC] Error during production sync: {e}")
    finally:
        local_conn.close()


def _table_is_empty(engine, table_name):
    """Check if a table exists and is empty in production."""
    try:
        with engine.connect() as conn:
            count = conn.execute(sa_text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            return count == 0
    except Exception:
        return True  # Table doesn't exist yet


def _sync_players(engine, local_conn):
    """Sync players table from local SQLite to production."""
    if not _table_is_empty(engine, "players"):
        print("[SYNC] players table already has data — skipping.")
        return

    rows = local_conn.execute("SELECT name, elo, aim, util, team_play, secret_word, steamid FROM players").fetchall()
    if not rows:
        return

    print(f"[SYNC] Syncing {len(rows)} players to production...")
    with engine.begin() as conn:
        for r in rows:
            conn.execute(sa_text(
                """INSERT INTO players (name, elo, aim, util, team_play, secret_word, steamid)
                   VALUES (:name, :elo, :aim, :util, :tp, :sw, :sid)
                   ON CONFLICT (name) DO NOTHING"""
            ), {
                "name": r["name"], "elo": r["elo"], "aim": r["aim"],
                "util": r["util"], "tp": r["team_play"],
                "sw": r["secret_word"], "sid": r["steamid"]
            })
    print(f"[SYNC] ✅ Players synced.")


def _sync_match_details(engine, local_conn):
    """Sync match_details table from local SQLite to production."""
    if not _table_is_empty(engine, "match_details"):
        print("[SYNC] match_details table already has data — skipping.")
        return

    rows = local_conn.execute(
        "SELECT match_id, cybershoke_id, date_analyzed, map, score_t, score_ct, total_rounds, lobby_url FROM match_details"
    ).fetchall()
    if not rows:
        return

    print(f"[SYNC] Syncing {len(rows)} match_details to production...")
    with engine.begin() as conn:
        for r in rows:
            conn.execute(sa_text(
                """INSERT INTO match_details (match_id, cybershoke_id, date_analyzed, map, score_t, score_ct, total_rounds, lobby_url)
                   VALUES (:mid, :cid, :da, :map, :st, :sct, :tr, :url)
                   ON CONFLICT (match_id) DO NOTHING"""
            ), {
                "mid": r["match_id"], "cid": r["cybershoke_id"],
                "da": r["date_analyzed"], "map": r["map"],
                "st": r["score_t"], "sct": r["score_ct"],
                "tr": r["total_rounds"], "url": r["lobby_url"]
            })
    print(f"[SYNC] ✅ match_details synced.")


def _sync_player_match_stats(engine, local_conn):
    """Sync player_match_stats table from local SQLite to production."""
    if not _table_is_empty(engine, "player_match_stats"):
        print("[SYNC] player_match_stats table already has data — skipping.")
        return

    rows = local_conn.execute("""
        SELECT match_id, player_name, steamid, kills, deaths, assists, score,
               damage, adr, rating, headshot_kills, headshot_pct, util_damage,
               enemies_flashed, kd_ratio, player_team, match_result,
               total_spent, entry_kills, entry_deaths, clutch_wins,
               rounds_last_alive, team_flashed, flash_assists, bomb_plants,
               bomb_defuses, multi_kills, weapon_kills
        FROM player_match_stats
    """).fetchall()
    if not rows:
        return

    print(f"[SYNC] Syncing {len(rows)} player_match_stats to production...")
    with engine.begin() as conn:
        for r in rows:
            conn.execute(sa_text(
                """INSERT INTO player_match_stats
                   (match_id, player_name, steamid, kills, deaths, assists, score,
                    damage, adr, rating, headshot_kills, headshot_pct, util_damage,
                    enemies_flashed, kd_ratio, player_team, match_result,
                    total_spent, entry_kills, entry_deaths, clutch_wins,
                    rounds_last_alive, team_flashed, flash_assists, bomb_plants,
                    bomb_defuses, multi_kills, weapon_kills)
                   VALUES (:mid, :pname, :steam, :kills, :deaths, :assists, :score,
                           :damage, :adr, :rating, :hs_kills, :hs_pct, :util_dmg,
                           :flashed, :kd, :pteam, :result,
                           :spent, :ek, :ed, :clutch, :rla, :tf,
                           :fa, :bp, :bd, :mk, :wk)"""
            ), {
                "mid": r["match_id"], "pname": r["player_name"], "steam": r["steamid"],
                "kills": r["kills"], "deaths": r["deaths"], "assists": r["assists"],
                "score": r["score"], "damage": r["damage"], "adr": r["adr"],
                "rating": r["rating"], "hs_kills": r["headshot_kills"],
                "hs_pct": r["headshot_pct"], "util_dmg": r["util_damage"],
                "flashed": r["enemies_flashed"], "kd": r["kd_ratio"],
                "pteam": r["player_team"], "result": r["match_result"],
                "spent": r["total_spent"], "ek": r["entry_kills"],
                "ed": r["entry_deaths"], "clutch": r["clutch_wins"],
                "rla": r["rounds_last_alive"], "tf": r["team_flashed"],
                "fa": r["flash_assists"], "bp": r["bomb_plants"],
                "bd": r["bomb_defuses"], "mk": r["multi_kills"],
                "wk": r["weapon_kills"]
            })
    print(f"[SYNC] ✅ player_match_stats synced.")


def _sync_matches(engine, local_conn):
    """Sync matches (elo history) table from local SQLite to production."""
    if not _table_is_empty(engine, "matches"):
        print("[SYNC] matches table already has data — skipping.")
        return

    rows = local_conn.execute(
        "SELECT team1_name, team2_name, team1_players, team2_players, winner_idx, map, elo_diff, date FROM matches"
    ).fetchall()
    if not rows:
        return

    print(f"[SYNC] Syncing {len(rows)} matches to production...")
    with engine.begin() as conn:
        for r in rows:
            conn.execute(sa_text(
                """INSERT INTO matches (team1_name, team2_name, team1_players, team2_players, winner_idx, map, elo_diff, date)
                   VALUES (:t1n, :t2n, :t1p, :t2p, :widx, :map, :elo, :dt)"""
            ), {
                "t1n": r["team1_name"], "t2n": r["team2_name"],
                "t1p": r["team1_players"], "t2p": r["team2_players"],
                "widx": r["winner_idx"], "map": r["map"],
                "elo": r["elo_diff"], "dt": r["date"]
            })
    print(f"[SYNC] ✅ matches synced.")


def _sync_cybershoke_lobbies(engine, local_conn):
    """Sync cybershoke_lobbies table from local SQLite to production."""
    if not _table_is_empty(engine, "cybershoke_lobbies"):
        print("[SYNC] cybershoke_lobbies table already has data — skipping.")
        return

    rows = local_conn.execute(
        "SELECT lobby_id, created_at, has_demo, analysis_status, notes FROM cybershoke_lobbies"
    ).fetchall()
    if not rows:
        return

    print(f"[SYNC] Syncing {len(rows)} cybershoke_lobbies to production...")
    with engine.begin() as conn:
        for r in rows:
            conn.execute(sa_text(
                """INSERT INTO cybershoke_lobbies (lobby_id, created_at, has_demo, analysis_status, notes)
                   VALUES (:lid, :ca, :hd, :status, :notes)
                   ON CONFLICT (lobby_id) DO NOTHING"""
            ), {
                "lid": r["lobby_id"], "ca": r["created_at"],
                "hd": r["has_demo"], "status": r["analysis_status"],
                "notes": r["notes"]
            })
    print(f"[SYNC] ✅ cybershoke_lobbies synced.")

"""
Migration script: Copies ALL data from the committed cs2_history.db (SQLite)
into the production database (Supabase PostgreSQL via sync_engine).

Safe to run multiple times — uses upsert logic to avoid duplicates.

Usage:
    python migrate_sqlite_to_supabase.py

Set DATABASE_URL in .env or environment to point to Supabase before running.
"""

import sqlite3
import json
import sys
from sqlalchemy import text as sa_text
from dotenv import load_dotenv

load_dotenv()

from database import sync_engine

LOCAL_DB = "cs2_history.db"


def _is_postgres():
    return sync_engine.name == "postgresql"


def migrate_players(local_conn, pg_conn):
    rows = local_conn.execute(
        "SELECT name, elo, aim, util, team_play, secret_word, steamid FROM players"
    ).fetchall()
    print(f"  players: {len(rows)} rows")

    for r in rows:
        name, elo, aim, util, tp, sw, steamid = r
        if _is_postgres():
            pg_conn.execute(
                sa_text("""
                    INSERT INTO players (name, elo, aim, util, team_play, secret_word, steamid)
                    VALUES (:name, :elo, :aim, :util, :tp, :sw, :sid)
                    ON CONFLICT (name) DO UPDATE SET
                        elo = EXCLUDED.elo,
                        aim = EXCLUDED.aim,
                        util = EXCLUDED.util,
                        team_play = EXCLUDED.team_play,
                        secret_word = EXCLUDED.secret_word,
                        steamid = EXCLUDED.steamid
                """),
                {"name": name, "elo": elo, "aim": aim, "util": util,
                 "tp": tp, "sw": sw or name.lower(), "sid": steamid},
            )
        else:
            pg_conn.execute(
                sa_text("""
                    INSERT OR REPLACE INTO players (name, elo, aim, util, team_play, secret_word, steamid)
                    VALUES (:name, :elo, :aim, :util, :tp, :sw, :sid)
                """),
                {"name": name, "elo": elo, "aim": aim, "util": util,
                 "tp": tp, "sw": sw or name.lower(), "sid": steamid},
            )


def migrate_matches(local_conn, pg_conn):
    rows = local_conn.execute(
        "SELECT id, team1_name, team2_name, team1_players, team2_players, winner_idx, map, elo_diff, date FROM matches"
    ).fetchall()
    print(f"  matches: {len(rows)} rows")

    for r in rows:
        mid, t1n, t2n, t1p, t2p, widx, m, ed, dt = r
        if _is_postgres():
            pg_conn.execute(
                sa_text("""
                    INSERT INTO matches (id, team1_name, team2_name, team1_players, team2_players, winner_idx, map, elo_diff, date)
                    VALUES (:id, :t1n, :t2n, :t1p, :t2p, :widx, :map, :ed, :dt)
                    ON CONFLICT (id) DO NOTHING
                """),
                {"id": mid, "t1n": t1n, "t2n": t2n, "t1p": t1p, "t2p": t2p,
                 "widx": widx, "map": m, "ed": ed, "dt": dt},
            )
        else:
            pg_conn.execute(
                sa_text("""
                    INSERT OR IGNORE INTO matches (id, team1_name, team2_name, team1_players, team2_players, winner_idx, map, elo_diff, date)
                    VALUES (:id, :t1n, :t2n, :t1p, :t2p, :widx, :map, :ed, :dt)
                """),
                {"id": mid, "t1n": t1n, "t2n": t2n, "t1p": t1p, "t2p": t2p,
                 "widx": widx, "map": m, "ed": ed, "dt": dt},
            )

    # Reset the PG sequence to avoid id conflicts on future inserts
    if _is_postgres() and rows:
        max_id = max(r[0] for r in rows)
        pg_conn.execute(sa_text(f"SELECT setval('matches_id_seq', :val, true)"), {"val": max_id})


def migrate_match_details(local_conn, pg_conn):
    rows = local_conn.execute(
        "SELECT match_id, cybershoke_id, date_analyzed, map, score_t, score_ct, total_rounds, lobby_url FROM match_details"
    ).fetchall()
    print(f"  match_details: {len(rows)} rows")

    for r in rows:
        mid, cid, da, m, st, sct, tr, url = r
        if _is_postgres():
            pg_conn.execute(
                sa_text("""
                    INSERT INTO match_details (match_id, cybershoke_id, date_analyzed, map, score_t, score_ct, total_rounds, lobby_url)
                    VALUES (:mid, :cid, :da, :map, :st, :sct, :tr, :url)
                    ON CONFLICT (match_id) DO NOTHING
                """),
                {"mid": mid, "cid": cid, "da": da, "map": m, "st": st, "sct": sct, "tr": tr, "url": url},
            )
        else:
            pg_conn.execute(
                sa_text("""
                    INSERT OR IGNORE INTO match_details (match_id, cybershoke_id, date_analyzed, map, score_t, score_ct, total_rounds, lobby_url)
                    VALUES (:mid, :cid, :da, :map, :st, :sct, :tr, :url)
                """),
                {"mid": mid, "cid": cid, "da": da, "map": m, "st": st, "sct": sct, "tr": tr, "url": url},
            )


def migrate_player_match_stats(local_conn, pg_conn):
    """Migrate player_match_stats - the largest table."""
    # Get column names from SQLite
    cursor = local_conn.execute("SELECT * FROM player_match_stats LIMIT 1")
    cols = [d[0] for d in cursor.description]

    rows = local_conn.execute("SELECT * FROM player_match_stats").fetchall()
    print(f"  player_match_stats: {len(rows)} rows ({len(cols)} columns)")

    # Skip the 'id' column (auto-increment) — let PG assign new ids
    # Build INSERT with all columns except id
    data_cols = [c for c in cols if c != "id"]
    placeholders = ", ".join(f":{c}" for c in data_cols)
    col_list = ", ".join(data_cols)

    # For dedup: check by (match_id, player_name) composite
    # First check if data already exists
    existing = pg_conn.execute(sa_text("SELECT COUNT(*) FROM player_match_stats")).scalar()
    if existing > 0:
        print(f"    Target already has {existing} rows — checking for new data...")
        # Get existing (match_id, player_name) pairs
        existing_pairs = set()
        ex_rows = pg_conn.execute(
            sa_text("SELECT match_id, player_name FROM player_match_stats")
        ).fetchall()
        for er in ex_rows:
            existing_pairs.add((er[0], er[1]))
        rows = [r for r in rows if (r[cols.index("match_id")], r[cols.index("player_name")]) not in existing_pairs]
        print(f"    {len(rows)} new rows to insert")

    insert_sql = f"INSERT INTO player_match_stats ({col_list}) VALUES ({placeholders})"

    batch_size = 100
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        for r in batch:
            params = {}
            for j, c in enumerate(cols):
                if c == "id":
                    continue
                params[c] = r[j]
            pg_conn.execute(sa_text(insert_sql), params)

        if (i + batch_size) % 500 == 0 or i + batch_size >= len(rows):
            print(f"    ... inserted {min(i + batch_size, len(rows))}/{len(rows)}")


def migrate_cybershoke_lobbies(local_conn, pg_conn):
    rows = local_conn.execute(
        "SELECT lobby_id, created_at, has_demo, analysis_status, notes FROM cybershoke_lobbies"
    ).fetchall()
    print(f"  cybershoke_lobbies: {len(rows)} rows")

    for r in rows:
        lid, ca, hd, st, notes = r
        if _is_postgres():
            pg_conn.execute(
                sa_text("""
                    INSERT INTO cybershoke_lobbies (lobby_id, created_at, has_demo, analysis_status, notes)
                    VALUES (:lid, :ca, :hd, :st, :notes)
                    ON CONFLICT (lobby_id) DO NOTHING
                """),
                {"lid": lid, "ca": ca, "hd": hd, "st": st, "notes": notes},
            )
        else:
            pg_conn.execute(
                sa_text("""
                    INSERT OR IGNORE INTO cybershoke_lobbies (lobby_id, created_at, has_demo, analysis_status, notes)
                    VALUES (:lid, :ca, :hd, :st, :notes)
                """),
                {"lid": lid, "ca": ca, "hd": hd, "st": st, "notes": notes},
            )


def migrate_settings(local_conn, pg_conn):
    rows = local_conn.execute("SELECT key, value FROM settings").fetchall()
    print(f"  settings: {len(rows)} rows")

    for r in rows:
        k, v = r
        if _is_postgres():
            pg_conn.execute(
                sa_text("""
                    INSERT INTO settings (key, value) VALUES (:k, :v)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """),
                {"k": k, "v": v},
            )
        else:
            pg_conn.execute(
                sa_text("INSERT OR REPLACE INTO settings (key, value) VALUES (:k, :v)"),
                {"k": k, "v": v},
            )


def main():
    print(f"Source: {LOCAL_DB} (SQLite)")
    print(f"Target: {sync_engine.url} ({sync_engine.name})")
    print()

    if sync_engine.name == "sqlite":
        print("WARNING: sync_engine is SQLite (DATABASE_URL not set).")
        print("Set DATABASE_URL to your Supabase PostgreSQL connection string.")
        resp = input("Continue anyway? (y/N): ").strip().lower()
        if resp != "y":
            sys.exit(0)

    local_conn = sqlite3.connect(LOCAL_DB)

    # Ensure target tables exist
    from database import init_db
    from match_stats_db import init_match_stats_tables

    print("Ensuring target tables exist...")
    init_db()
    init_match_stats_tables()
    print()

    print("Migrating data...")
    with sync_engine.begin() as pg_conn:
        migrate_players(local_conn, pg_conn)
        migrate_matches(local_conn, pg_conn)
        migrate_match_details(local_conn, pg_conn)
        migrate_player_match_stats(local_conn, pg_conn)
        migrate_cybershoke_lobbies(local_conn, pg_conn)
        migrate_settings(local_conn, pg_conn)

    local_conn.close()

    print()
    print("Migration complete! Verifying row counts...")
    with sync_engine.connect() as conn:
        for table in ["players", "matches", "match_details", "player_match_stats", "cybershoke_lobbies", "settings"]:
            try:
                count = conn.execute(sa_text(f"SELECT COUNT(*) FROM {table}")).scalar()
                print(f"  {table}: {count} rows")
            except Exception as e:
                print(f"  {table}: ERROR - {e}")

    print()
    print("Done!")


if __name__ == "__main__":
    main()

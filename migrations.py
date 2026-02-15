
import logging
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

def run_migrations_sync(connection):
    """
    Run raw SQL migrations to ensure schema is up to date.
    Safe to run on every startup (idempotent).
    """
    try:
        # Detect dialect
        dialect_name = connection.dialect.name
        logger.info(f"Running migrations for dialect: {dialect_name}")

        # List of migrations: (Table, Column, Type, Default/Nullable)
        # Note: Type should be generic or handled per dialect if needed.
        migrations = [
            ("tournaments", "rules", "TEXT", "NULL"),
            ("tournaments", "playoffs", "BOOLEAN", "DEFAULT FALSE"),
            ("tournaments", "prize_pool", "TEXT", "NULL"),
            ("tournaments", "tournament_date", "TEXT", "NULL"),
            ("tournament_matches", "group_id", "INTEGER", "NULL"),
            ("tournament_matches", "score", "TEXT", "NULL"),
            ("tournament_matches", "cybershoke_match_id", "TEXT", "NULL"),
        ]

        for table, col, col_type, options in migrations:
            # Check if column exists
            exists = False
            if dialect_name == "sqlite":
                # SQLite check
                res = connection.execute(text(f"PRAGMA table_info({table})")).fetchall()
                # res is list of tuples (cid, name, type, notnull, dflt_value, pk)
                cols = [r[1] for r in res]
                if col in cols:
                    exists = True
            elif dialect_name == "postgresql":
                # Postgres check
                sql = text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = :t AND column_name = :c
                """)
                res = connection.execute(sql, {"t": table, "c": col}).fetchone()
                if res:
                    exists = True
            
            if not exists:
                logger.info(f"Migrating: Adding {col} to {table}")
                try:
                    # SQLite and Postgres support ALTER TABLE ADD COLUMN
                    # But syntax for 'IF NOT EXISTS' in ADD COLUMN is PG-specific (PG 9.6+). 
                    # SQLite doesn't strictly support IF NOT EXISTS in ADD COLUMN standardly in all versions/drivers?
                    # Since we checked 'exists' manually, we just run ADD COLUMN.
                    
                    alter_sql = f"ALTER TABLE {table} ADD COLUMN {col} {col_type} {options}"
                    connection.execute(text(alter_sql))
                    logger.info(f"Added {col} to {table}")
                except Exception as e:
                    logger.error(f"Failed to add {col} to {table}: {e}")
            else:
                logger.debug(f"Column {table}.{col} already exists.")

    except Exception as e:
        logger.error(f"Migration error: {e}")

async def run_async_migrations(engine: AsyncEngine):
    async with engine.begin() as conn:
        await conn.run_sync(run_migrations_sync)

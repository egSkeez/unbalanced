from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Header, Depends, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import pandas as pd
import uvicorn
import random
import json
import os
import requests
import datetime
import httpx
import uuid as uuid_mod

# Supabase Storage config (for image uploads)
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_BUCKET = "prize-images"
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB

from auth import (
    init_user_accounts, create_access_token, get_current_user, get_current_user_optional,
    get_db, hash_password, verify_password
)
from models import User, Tournament, TournamentParticipant, TournamentMatch, TournamentFormat, TournamentStatus
from schemas import UserCreate, UserLogin, UserOut, Token
from tournament_logic import (
    advance_winner, start_tournament, report_match,
    serialize_tournament, get_generator,
)

# In-memory store for player pings (username -> ms)
PLAYER_PINGS: Dict[str, float] = {}

def _is_postgres():
    return sync_engine.name == 'postgresql'

from database import (
    init_db, init_async_db, get_player_stats, save_draft_state, load_draft_state,
    clear_draft_state, get_roommates, set_roommates,
    init_veto_state, get_veto_state, update_veto_turn, update_draft_map,
    get_vote_status, set_draft_pins, submit_vote, update_elo,
    init_empty_captains, claim_captain_spot,
    get_captain_by_name, get_captain_by_pin, is_captain_banned,
    check_captain_placeholder, insert_banned_captain,
    sync_engine
)
from sqlalchemy import text as sa_text
from match_stats_db import (
    init_match_stats_tables, save_match_stats, get_player_aggregate_stats,
    get_recent_matches, get_season_stats_dump, get_match_scoreboard,
    get_all_lobbies, add_lobby, update_lobby_status, is_lobby_already_analyzed,
    get_player_weapon_stats
)
from logic import get_best_combinations, pick_captains, cycle_new_captain
from cybershoke import (
    create_cybershoke_lobby_api, set_lobby_link, get_lobby_link, clear_lobby_link,
    get_lobby_match_result,
)
from discord_bot import send_full_match_info, send_lobby_to_discord
from constants import TEAM_NAMES, MAP_POOL, MAP_LOGOS, SKEEZ_TITLES, PLAYERS_INIT
from season_logic import get_current_season_info, get_all_seasons
from migrate_ratings import check_and_migrate
from sync_to_production import sync_local_to_production

# --- Lifespan for Async Init ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db() # Legacy Sync
    init_match_stats_tables() # Legacy Sync
    check_and_migrate() # Legacy Sync
    await init_async_db() # New Async (creates all tables including tournaments)
    await init_user_accounts() # New Async
    # Migrate tournament columns for existing databases
    # IMPORTANT: Each ALTER TABLE must be in its own transaction because
    # PostgreSQL aborts the entire transaction if any statement fails
    # (e.g. "column already exists"), making subsequent statements fail too.
    try:
        from sqlalchemy import text as sa_text
        from database import sync_engine
        migration_cols = [
            ("tournaments", "tournament_date", "TEXT"),
            ("tournaments", "description", "TEXT"),
            ("tournaments", "rules", "TEXT"),
            ("tournaments", "prize_pool", "TEXT"),
            ("tournaments", "playoffs", "BOOLEAN DEFAULT FALSE"),
            ("tournaments", "format", "TEXT DEFAULT 'single_elimination'"),
            ("tournament_participants", "checked_in", "BOOLEAN DEFAULT FALSE"),
            ("tournament_matches", "group_id", "INTEGER"),
            ("tournament_matches", "score", "TEXT"),
        ]
        for table, col, col_type in migration_cols:
            try:
                with sync_engine.begin() as conn:
                    conn.execute(sa_text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                    print(f"Migration: added {table}.{col}")
            except Exception:
                pass  # column already exists
    except Exception as e:
        print(f"Migration error: {e}")
    # Sync local SQLite data to production PostgreSQL (only if production tables are empty)
    sync_local_to_production()
    yield
    # Shutdown
    pass

app = FastAPI(title="CS2 Pro Balancer API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)



# ──────────────────────────────────────────────
# PYDANTIC MODELS
# ──────────────────────────────────────────────

class DraftRequest(BaseModel):
    selected_players: List[str]
    mode: str = "balanced"  # balanced | kd_balanced | hltv_balanced | chaos

class RerollRequest(BaseModel):
    current_players: List[str]
    mode: str = "balanced"
    force_captains: Optional[List[str]] = None

class VetoActionRequest(BaseModel):
    map_name: str
    acting_team: str  # team name string

class PingRequest(BaseModel):
    ping: float

class VoteRequest(BaseModel):
    token: str
    vote: str  # "Approve" | "Reroll"

class PlayerCreateRequest(BaseModel):
    name: str
    aim: float = 5.0
    util: float = 5.0
    team_play: float = 5.0

class PlayerUpdateRequest(BaseModel):
    aim: float
    util: float
    team_play: float

class RoommatesRequest(BaseModel):
    groups: List[List[str]]

class LobbyCreateRequest(BaseModel):
    admin_name: str = "Skeez"

class BroadcastRequest(BaseModel):
    name_a: str
    team1: List[str]
    name_b: str
    team2: List[str]
    maps: str
    lobby_link: str

class EloUpdateRequest(BaseModel):
    team1: List[str]
    team2: List[str]
    name_a: str
    name_b: str
    winner_idx: int  # 1 or 2
    map_name: str

class MatchUploadData(BaseModel):
    match_id: str
    map_name: str
    score_str: str
    score_t: int
    score_ct: int
    player_stats: List[Dict[str, Any]]

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: Optional[str] = None

class GoogleLoginRequest(BaseModel):
    credential: str  # Google ID token

class TournamentCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    format: str = "single_elimination"  # single_elimination | round_robin
    prize_image_url: Optional[str] = None
    prize_name: Optional[str] = None
    prize_pool: Optional[str] = None
    max_players: int = 0  # 0 = unlimited/open registration
    playoffs: bool = False  # RR only: top-4 playoff bracket after group stage
    rules: Optional[str] = None
    tournament_date: Optional[str] = None  # e.g. "2026-03-15"

class TournamentUpdateRequest(BaseModel):
    description: Optional[str] = None
    rules: Optional[str] = None
    prize_image_url: Optional[str] = None

class AdvanceWinnerRequest(BaseModel):
    winner_id: str

class ReportMatchRequest(BaseModel):
    winner_id: str
    score: Optional[str] = None  # e.g. "16-12"

class TournamentLobbyRequest(BaseModel):
    admin_name: str = "Skeez"

class SubmitLobbyRequest(BaseModel):
    lobby_url: str  # e.g. "https://cybershoke.net/match/3387473"

# ──────────────────────────────────────────────
# PING ENDPOINT
# ──────────────────────────────────────────────

@app.post("/api/ping")
async def report_ping(req: PingRequest, current_user: User = Depends(get_current_user)):
    PLAYER_PINGS[current_user.display_name] = req.ping
    return {"status": "ok"}

# ──────────────────────────────────────────────
# AUTH ENDPOINTS
# ──────────────────────────────────────────────

@app.post("/api/auth/register", response_model=UserOut)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if len(req.password) < 4:
        raise HTTPException(400, "Password must be at least 4 characters")
    
    # Check existing username
    result = await db.execute(select(User).filter(User.username == req.username.lower()))
    if result.scalars().first():
        raise HTTPException(409, "Username already exists")
    
    # Check existing display name
    display = req.display_name or req.username
    result_display = await db.execute(select(User).filter(User.display_name == display))
    if result_display.scalars().first():
        raise HTTPException(409, f"Display name '{display}' is already taken")
    
    hashed = hash_password(req.password)
    display = req.display_name or req.username
    new_user = User(
        username=req.username.lower(),
        hashed_password=hashed,
        role="player",
        display_name=display
    )
    db.add(new_user)
    try:
        await db.commit()
        await db.refresh(new_user)
    except Exception as e:
        await db.rollback()
        raise HTTPException(500, f"Database error: {str(e)}")
    
    # Auto-create player in the players table so they're available for drafting
    try:
        with sync_engine.begin() as conn:
            if _is_postgres():
                conn.execute(sa_text(
                    "INSERT INTO players (name, elo, aim, util, team_play, secret_word) VALUES (:name, 1200, 5, 5, 5, :sw) ON CONFLICT (name) DO NOTHING"
                ), {"name": display, "sw": display.lower()})
            else:
                conn.execute(sa_text(
                    "INSERT OR IGNORE INTO players (name, elo, aim, util, team_play, secret_word) VALUES (:name, 1200, 5, 5, 5, :sw)"
                ), {"name": display, "sw": display.lower()})
    except Exception as e:
        print(f"[REGISTER] Could not auto-create player row: {e}")
        
    # Return directly matches UserOut schema
    return new_user

@app.post("/api/auth/token", response_model=Token)
async def login_for_access_token(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        # Authenticate
        result = await db.execute(select(User).filter(User.username == req.username.lower()))
        user = result.scalars().first()

        if not user or not verify_password(req.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Update last login
        user.last_login = datetime.datetime.utcnow()
        await db.commit()

        access_token = create_access_token(
            data={"sub": user.username, "role": user.role, "display_name": user.display_name}
        )
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Login error: {str(e)}")

@app.get("/api/auth/me", response_model=Dict[str, Any])
async def read_users_me(current_user: User = Depends(get_current_user)):
    # Convert to dict to append extra fields
    user_data = {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "display_name": current_user.display_name,
        "avatar_url": current_user.avatar_url,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at,
        "last_login": current_user.last_login
    }
    
    display = current_user.display_name
    
    # Check if user is captain in current draft
    cap_row = get_captain_by_name(display)
    
    user_data["is_captain"] = cap_row is not None
    user_data["captain_pin"] = cap_row[1] if cap_row else None
    user_data["captain_vote"] = cap_row[2] if cap_row else None
    
    # Check if user is in the current draft
    saved = load_draft_state()
    user_data["in_draft"] = False
    user_data["draft_team_name"] = None
    user_data["draft_role"] = None
    
    if saved:
        t1, t2, n_a, n_b, *_ = saved
        if display in t1:
            user_data["in_draft"] = True
            user_data["draft_team_name"] = n_a
        elif display in t2:
            user_data["in_draft"] = True
            user_data["draft_team_name"] = n_b
            
        if user_data["is_captain"]:
            user_data["draft_role"] = "captain"
        elif user_data["in_draft"]:
            user_data["draft_role"] = "player"
            
    return user_data

@app.get("/api/auth/me/stats")
async def my_stats(current_user: User = Depends(get_current_user), season: str = Query("Season 2 (Demos)")):
    """Get personal stats for logged-in user."""
    name = current_user.display_name
    seasons = get_all_seasons()
    if season == "All Time":
        start_date, end_date = None, None
    elif season in seasons:
        start_date, end_date = seasons[season]
    else:
        start_date, end_date = None, None

    df = get_player_aggregate_stats(name, start_date=start_date, end_date=end_date)
    records = df_to_records(df)
    stats_data = records[0] if records else None
    return {"name": name, "stats": stats_data}

@app.get("/api/auth/me/weapons")
async def my_weapon_stats(current_user: User = Depends(get_current_user), season: str = Query("Season 2 (Demos)")):
    """Get weapon kills per game for logged-in user."""
    name = current_user.display_name
    seasons = get_all_seasons()
    if season == "All Time":
        start_date, end_date = None, None
    elif season in seasons:
        start_date, end_date = seasons[season]
    else:
        start_date, end_date = None, None

    return get_player_weapon_stats(name, start_date=start_date, end_date=end_date)

@app.get("/api/players/{name}/weapons")
def player_weapon_stats(name: str, season: str = Query("Season 2 (Demos)")):
    """Get weapon stats for any player."""
    seasons = get_all_seasons()
    if season == "All Time":
        start_date, end_date = None, None
    elif season in seasons:
        start_date, end_date = seasons[season]
    else:
        start_date, end_date = None, None

    return get_player_weapon_stats(name, start_date=start_date, end_date=end_date)

@app.get("/api/auth/me/matches")
async def my_matches(current_user: User = Depends(get_current_user), season: str = Query("Season 2 (Demos)")):
    """Get personal match history for logged-in user."""
    name = current_user.display_name
    # Reuse player_matches logic
    from match_stats_db import get_season_stats_dump
    from season_logic import get_current_season_info, get_all_seasons
    all_seasons = get_all_seasons()
    s_info = all_seasons.get(season)
    if s_info and isinstance(s_info, tuple):
        start, end = s_info
    elif s_info and isinstance(s_info, dict):
        start = s_info.get("start_date", "2024-01-01")
        end = s_info.get("end_date", "2099-12-31")
    else:
        start, end = "2024-01-01", "2099-12-31"
    with sync_engine.connect() as conn:
        q = '''
            SELECT md.match_id, md.map, md.score_t || '-' || md.score_ct as score, md.date_analyzed,
                   pms.kills, pms.deaths, pms.assists, pms.adr, pms.rating
            FROM player_match_stats pms
            JOIN match_details md ON pms.match_id = md.match_id
            WHERE pms.player_name = :name
              AND date(md.date_analyzed) >= date(:start)
              AND date(md.date_analyzed) <= date(:end)
            ORDER BY md.date_analyzed DESC
        '''
        df = pd.read_sql_query(sa_text(q), conn, params={"name": name, "start": start, "end": end})
    return df_to_records(df)

# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def df_to_records(df):
    """Convert a pandas DataFrame to a list of dicts, handling NaN."""
    if df is None or df.empty:
        return []
    return json.loads(df.to_json(orient="records"))

# ──────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────

@app.get("/api/constants")
def get_constants():
    return {
        "map_pool": MAP_POOL,
        "map_logos": MAP_LOGOS,
        "team_names": TEAM_NAMES,
        "skeez_titles": SKEEZ_TITLES,
    }

# ──────────────────────────────────────────────
# SEASONS
# ──────────────────────────────────────────────

@app.get("/api/seasons")
def get_seasons():
    current = get_current_season_info()
    all_seasons = get_all_seasons()
    return {
        "current": {"name": current[0], "start": str(current[1]), "end": str(current[2])},
        "all": {k: {"start": str(v[0]) if v[0] else None, "end": str(v[1]) if v[1] else None} for k, v in all_seasons.items()}
    }

# ──────────────────────────────────────────────
# PLAYERS
# ──────────────────────────────────────────────

@app.get("/api/players")
def list_players():
    df = get_player_stats()
    records = df_to_records(df)
    # Inject pings
    for r in records:
        if r['name'] in PLAYER_PINGS:
            r['ping'] = PLAYER_PINGS[r['name']]
    return records

@app.post("/api/players")
def create_player(req: PlayerCreateRequest):
    with sync_engine.begin() as conn:
        if _is_postgres():
            conn.execute(sa_text(
                "INSERT INTO players (name, elo, aim, util, team_play, secret_word) VALUES (:name, 1200, :aim, :util, :tp, 'cs2pro') ON CONFLICT (name) DO NOTHING"
            ), {"name": req.name, "aim": req.aim, "util": req.util, "tp": req.team_play})
        else:
            conn.execute(sa_text(
                "INSERT OR IGNORE INTO players (name, elo, aim, util, team_play, secret_word) VALUES (:name, 1200, :aim, :util, :tp, 'cs2pro')"
            ), {"name": req.name, "aim": req.aim, "util": req.util, "tp": req.team_play})
    return {"status": "ok", "message": f"Added {req.name}"}

@app.put("/api/players/{name}")
def update_player(name: str, req: PlayerUpdateRequest):
    with sync_engine.begin() as conn:
        conn.execute(sa_text("UPDATE players SET aim=:aim, util=:util, team_play=:tp WHERE name=:name"),
                      {"aim": req.aim, "util": req.util, "tp": req.team_play, "name": name})
    return {"status": "ok"}

@app.delete("/api/players/{name}")
def delete_player(name: str):
    with sync_engine.begin() as conn:
        conn.execute(sa_text("DELETE FROM players WHERE name=:name"), {"name": name})
    return {"status": "ok"}

# ──────────────────────────────────────────────
# ADMIN — USER MANAGEMENT
# ──────────────────────────────────────────────

@app.get("/api/admin/users")
async def list_users(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """List all registered users (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(403, "Admin only")
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    
    # Also get player data to show which users have player entries
    with sync_engine.connect() as conn:
        player_rows = conn.execute(sa_text("SELECT name, aim, util, team_play, elo FROM players")).fetchall()
        player_map = {r[0]: {"aim": r[1], "util": r[2], "team_play": r[3], "elo": r[4]} for r in player_rows}
    
    return [
        {
            "id": u.id,
            "username": u.username,
            "display_name": u.display_name,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login": u.last_login.isoformat() if u.last_login else None,
            "has_player": u.display_name in player_map,
            "player_stats": player_map.get(u.display_name),
        }
        for u in users
    ]

@app.put("/api/admin/users/{user_id}/role")
async def update_user_role(user_id: str, role: str = Query(...), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Update a user's role (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(403, "Admin only")
    if role not in ("admin", "player"):
        raise HTTPException(400, "Role must be 'admin' or 'player'")
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(404, "User not found")
    user.role = role
    await db.commit()
    return {"status": "ok", "username": user.username, "role": role}

@app.delete("/api/admin/users/{user_id}")
async def delete_user(user_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Delete a registered user (admin only). Does NOT delete their player stats row."""
    if current_user.role != "admin":
        raise HTTPException(403, "Admin only")
    if user_id == current_user.id:
        raise HTTPException(400, "Cannot delete yourself")
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(404, "User not found")
    await db.delete(user)
    await db.commit()
    return {"status": "ok"}

@app.post("/api/admin/users/create")
async def admin_create_user(req: dict, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Admin creates a user account + player row."""
    if current_user.role != "admin":
        raise HTTPException(403, "Admin only")
    username = (req.get("username") or "").strip().lower()
    password = req.get("password", "")
    display_name = (req.get("display_name") or username).strip()
    role = req.get("role", "player")
    aim = float(req.get("aim", 5))
    util = float(req.get("util", 5))
    team_play = float(req.get("team_play", 5))

    if not username or len(username) < 2:
        raise HTTPException(400, "Username must be at least 2 characters")
    if len(password) < 4:
        raise HTTPException(400, "Password must be at least 4 characters")
    if role not in ("admin", "player"):
        raise HTTPException(400, "Role must be 'admin' or 'player'")

    # Check uniqueness
    existing = await db.execute(select(User).filter(User.username == username))
    if existing.scalars().first():
        raise HTTPException(409, "Username already exists")
    if display_name:
        existing_dn = await db.execute(select(User).filter(User.display_name == display_name))
        if existing_dn.scalars().first():
            raise HTTPException(409, f"Display name '{display_name}' is already taken")

    new_user = User(
        username=username,
        hashed_password=hash_password(password),
        role=role,
        display_name=display_name,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # Auto-create player row
    try:
        with sync_engine.begin() as conn:
            if _is_postgres():
                conn.execute(sa_text(
                    "INSERT INTO players (name, elo, aim, util, team_play, secret_word) VALUES (:name, 1200, :aim, :util, :tp, :sw) ON CONFLICT (name) DO NOTHING"
                ), {"name": display_name, "aim": aim, "util": util, "tp": team_play, "sw": display_name.lower()})
            else:
                conn.execute(sa_text(
                    "INSERT OR IGNORE INTO players (name, elo, aim, util, team_play, secret_word) VALUES (:name, 1200, :aim, :util, :tp, :sw)"
                ), {"name": display_name, "aim": aim, "util": util, "tp": team_play, "sw": display_name.lower()})
    except Exception as e:
        print(f"[ADMIN CREATE] Could not create player row: {e}")

    return {"status": "ok", "id": new_user.id, "username": new_user.username, "display_name": new_user.display_name}


@app.put("/api/admin/users/{user_id}")
async def admin_update_user(user_id: str, req: dict, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Admin updates a user's profile fields."""
    if current_user.role != "admin":
        raise HTTPException(403, "Admin only")
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(404, "User not found")

    old_display = user.display_name

    if "display_name" in req and req["display_name"]:
        new_dn = req["display_name"].strip()
        if new_dn != user.display_name:
            dup = await db.execute(select(User).filter(User.display_name == new_dn))
            if dup.scalars().first():
                raise HTTPException(409, f"Display name '{new_dn}' is already taken")
            user.display_name = new_dn
    if "role" in req and req["role"] in ("admin", "player"):
        user.role = req["role"]
    if "is_active" in req:
        user.is_active = bool(req["is_active"])
    if "avatar_url" in req:
        user.avatar_url = req["avatar_url"] or None

    await db.commit()

    # If display_name changed, rename the player row too
    if user.display_name != old_display and old_display:
        try:
            with sync_engine.begin() as conn:
                conn.execute(sa_text("UPDATE players SET name = :new_name, secret_word = :sw WHERE name = :old_name"),
                             {"new_name": user.display_name, "sw": user.display_name.lower(), "old_name": old_display})
        except Exception as e:
            print(f"[ADMIN UPDATE] Could not rename player row: {e}")

    return {"status": "ok"}


@app.put("/api/admin/users/{user_id}/password")
async def admin_reset_password(user_id: str, req: dict, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Admin resets a user's password."""
    if current_user.role != "admin":
        raise HTTPException(403, "Admin only")
    password = req.get("password", "")
    if len(password) < 4:
        raise HTTPException(400, "Password must be at least 4 characters")
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(404, "User not found")
    user.hashed_password = hash_password(password)
    await db.commit()
    return {"status": "ok"}


@app.put("/api/admin/users/{user_id}/scores")
async def admin_update_scores(user_id: str, req: dict, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Admin updates a user's player skill scores (aim, util, team_play, elo)."""
    if current_user.role != "admin":
        raise HTTPException(403, "Admin only")
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(404, "User not found")

    display = user.display_name or user.username
    with sync_engine.begin() as conn:
        # Ensure player row exists
        row = conn.execute(sa_text("SELECT 1 FROM players WHERE name = :name"), {"name": display}).fetchone()
        if not row:
            if _is_postgres():
                conn.execute(sa_text(
                    "INSERT INTO players (name, elo, aim, util, team_play, secret_word) VALUES (:name, 1200, 5, 5, 5, :sw) ON CONFLICT (name) DO NOTHING"
                ), {"name": display, "sw": display.lower()})
            else:
                conn.execute(sa_text(
                    "INSERT OR IGNORE INTO players (name, elo, aim, util, team_play, secret_word) VALUES (:name, 1200, 5, 5, 5, :sw)"
                ), {"name": display, "sw": display.lower()})

        updates = []
        params = {"name": display}
        for field in ("aim", "util", "team_play", "elo"):
            if field in req and req[field] is not None:
                updates.append(f"{field} = :{field}")
                params[field] = float(req[field])
        if updates:
            conn.execute(sa_text(f"UPDATE players SET {', '.join(updates)} WHERE name = :name"), params)

    return {"status": "ok"}


@app.post("/api/admin/sync-players")
async def sync_players(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Create player rows for any registered user who doesn't have one (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(403, "Admin only")
    result = await db.execute(select(User))
    users = result.scalars().all()
    
    synced = 0
    with sync_engine.begin() as conn:
        for u in users:
            display = u.display_name or u.username
            row = conn.execute(sa_text("SELECT 1 FROM players WHERE name = :name"), {"name": display}).fetchone()
            if not row:
                if _is_postgres():
                    conn.execute(sa_text(
                        "INSERT INTO players (name, elo, aim, util, team_play, secret_word) VALUES (:name, 1200, 5, 5, 5, :sw) ON CONFLICT (name) DO NOTHING"
                    ), {"name": display, "sw": display.lower()})
                else:
                    conn.execute(sa_text(
                        "INSERT OR IGNORE INTO players (name, elo, aim, util, team_play, secret_word) VALUES (:name, 1200, 5, 5, 5, :sw)"
                    ), {"name": display, "sw": display.lower()})
                synced += 1

    return {"status": "ok", "synced": synced}

# ──────────────────────────────────────────────
# DRAFT
# ──────────────────────────────────────────────

@app.post("/api/draft")
async def run_draft(req: DraftRequest, current_user: Optional[User] = Depends(get_current_user_optional)):
    if len(req.selected_players) != 10:
        raise HTTPException(400, "Exactly 10 players required")

    # Get creator name
    creator_name = current_user.display_name if current_user else None

    player_df = get_player_stats()

    if req.mode == "kd_balanced":
        metric = "avg_kd"
    elif req.mode == "hltv_balanced":
        metric = "hltv"
    else:
        metric = "overall"

    # Determine top 2 to force split
    col_name = "avg_rating" if metric == "hltv" else metric
    score_map = dict(zip(player_df['name'], player_df[col_name].fillna(0)))
    sorted_players = sorted(req.selected_players, key=lambda x: score_map.get(x, 0), reverse=True)
    force_split = [sorted_players[0], sorted_players[1]]

    roommates = get_roommates()
    all_combos = get_best_combinations(req.selected_players, force_split=force_split, force_together=roommates, metric=metric)

    ridx = 0 if req.mode in ["balanced", "kd_balanced", "hltv_balanced"] else random.randint(1, min(50, len(all_combos) - 1))
    t1, t2, a1, a2, gap = all_combos[ridx]
    n_a, n_b = random.sample(TEAM_NAMES, 2)

    save_draft_state(t1, t2, n_a, n_b, a1, a2, mode=req.mode, created_by=creator_name)

    # Initialize empty captain slots (First come first served)
    init_empty_captains()

    return {
        "team1": t1, "team2": t2,
        "name_a": n_a, "name_b": n_b,
        "avg1": a1, "avg2": a2, "gap": gap,
        "mode": req.mode,
        "captain1": None,
        "captain2": None,
        "created_by": creator_name,
    }

@app.get("/api/draft/state")
async def get_draft_state(current_user: Optional[User] = Depends(get_current_user_optional)):
    saved = load_draft_state()
    if not saved:
        return {"active": False}

    t1, t2, n_a, n_b, a1, a2, db_map, lobby, mid, mode, created_by = saved
    votes = get_vote_status()
    
    # Determine user role
    is_admin = False
    username = None
    if current_user:
        is_admin = current_user.role == "admin"
        username = current_user.display_name # Using display_name for comparison with captain_name

    vote_data = []
    if not votes.empty:
        records = votes.to_dict('records')
        for r in records:
            r["captain_name"] = str(r["captain_name"])
            if r.get("pin"): r["pin"] = str(r["pin"])
            if r.get("vote"): r["vote"] = str(r["vote"])
            
            name = r["captain_name"]
            
            # Infer team_idx
            team_idx = None
            if name == "__TEAM1__":
                team_idx = 1
            elif name == "__TEAM2__":
                team_idx = 2
            elif name in t1:
                team_idx = 1
            elif name in t2:
                team_idx = 2
            r["team_idx"] = team_idx

            # Masking logic
            role_to_show = r["vote"]

            if name.startswith("__TEAM"):
                # Placeholder - show as is (frontend handles it)
                pass 
            elif is_admin:
                # Admin sees all
                pass
                pass
            elif username and name == username:
                # User sees themselves
                pass
            else:
                # Mask others, but PRESERVE team_idx so frontend knows which team is filled
                r["captain_name"] = "Hidden Captain"
            
            if "pin" in r:
                if not (username and name == username):
                     r["pin"] = None 
            
            vote_data.append(r)

    lobby_link, lobby_mid = get_lobby_link()
    
    # Get ratings for sorting
    stats_df = get_player_stats()
    ratings = {name: float(rating) for name, rating in zip(stats_df['name'], stats_df['avg_rating'].fillna(0))}

    # Inject pings for all players (frontend can filter)
    pings = {name: p for name, p in PLAYER_PINGS.items()}

    return {
        "active": True,
        "team1": t1, "team2": t2,
        "name_a": n_a, "name_b": n_b,
        "avg1": a1, "avg2": a2,
        "map_pick": db_map,
        "mode": mode or "balanced",
        "votes": vote_data,
        "lobby_link": lobby_link,
        "lobby_match_id": lobby_mid,
        "ratings": ratings,
        "pings": pings,
        "created_by": created_by,
    }

@app.post("/api/draft/reroll")
async def reroll_draft(req: RerollRequest, current_user: User = Depends(get_current_user)):
    # We allow admin to reroll without ban? Or apply rules to everyone?
    # User prompt: "one of the captains decided to reroll". 
    # If admin rerolls, maybe no ban. But checking role is safer.
    is_admin = current_user.role == "admin"
    reroller_name = current_user.display_name

    # 1. Capture current captains before wipe
    votes_df = get_vote_status()
    other_captain = None
    if not votes_df.empty:
        for _, row in votes_df.iterrows():
            name = row['captain_name']
            if name != reroller_name and not name.startswith("__TEAM"):
                other_captain = name

    player_df = get_player_stats()

    if req.mode == "kd_balanced":
        metric = "avg_kd"
    elif req.mode == "hltv_balanced":
        metric = "hltv"
    else:
        metric = "overall"

    roommates = get_roommates()
    # If force_captains passed, respect it? 
    # The prompt says: keep other captain. 
    # force_split logic in get_best_combinations helps separate strong players.
    
    all_combos = get_best_combinations(req.current_players, force_split=[], force_together=roommates, metric=metric)
    ridx = random.randint(1, min(50, len(all_combos) - 1))
    t1, t2, a1, a2, gap = all_combos[ridx]

    # Preserve team names from current state
    saved = load_draft_state()
    original_creator = None
    if saved:
        n_a, n_b = saved[2], saved[3]
        if len(saved) > 10:
            original_creator = saved[10]
    else:
        n_a, n_b = random.sample(TEAM_NAMES, 2)

    save_draft_state(t1, t2, n_a, n_b, a1, a2, mode=req.mode, created_by=original_creator)
    init_empty_captains()
    
    # 2. Apply Captain Rules
    import uuid
    # Ban the reroller (unless admin? assume admin reroll is god-mode, but if acting as captain...)
    # Prompt implies "captain decided to reroll".
    if not is_admin: 
        insert_banned_captain(reroller_name)

    # Retain the other captain
    if other_captain:
        # Find their new team
        team_num = None
        if other_captain in t1:
            team_num = 1
        elif other_captain in t2:
            team_num = 2
        
        if team_num:
             claim_captain_spot(team_num, other_captain, str(uuid.uuid4()))

    return {
        "team1": t1, "team2": t2,
        "name_a": n_a, "name_b": n_b,
        "avg1": a1, "avg2": a2, "gap": gap,
        "captain1": None, "captain2": None,
        "mode": req.mode
    }

@app.post("/api/draft/step_in")
async def step_in_as_captain(current_user: User = Depends(get_current_user)):
    display = current_user.display_name
    
    saved = load_draft_state()
    if not saved:
        raise HTTPException(400, "No active draft")
    t1, t2, *_ = saved

    team_num = None
    if display in t1:
        team_num = 1
    elif display in t2:
        team_num = 2
    else:
        raise HTTPException(403, "You are not in this draft")

    if is_captain_banned(display):
        raise HTTPException(403, "You forfeited captaincy by rerolling")

    import uuid
    pin = str(uuid.uuid4())
    success = claim_captain_spot(team_num, display, pin)
    
    if not success:
        raise HTTPException(409, "Captain spot already taken or unavailable")
        
    return {"status": "ok", "role": "captain", "pin": pin}

@app.delete("/api/draft")
def clear_draft():
    clear_draft_state()
    clear_lobby_link()
    return {"status": "ok"}

@app.post("/api/draft/elo")
def update_match_elo(req: EloUpdateRequest):
    update_elo(req.team1, req.team2, req.name_a, req.name_b, req.winner_idx, req.map_name)
    return {"status": "ok"}

# ──────────────────────────────────────────────
# VETO
# ──────────────────────────────────────────────

@app.get("/api/veto/state")
def veto_state():
    rem, picked, turn_team = get_veto_state()
    if rem is None:
        return {"initialized": False}
    return {
        "initialized": True,
        "remaining": rem,
        "protected": picked,
        "picked": picked,
        "turn_team": turn_team,
        "complete": len(rem) == 0,
    }

@app.post("/api/veto/init")
def veto_init():
    """Coin flip + init veto."""
    saved = load_draft_state()
    if not saved:
        raise HTTPException(400, "No active draft")
    _, _, n_a, n_b, *_ = saved
    winner = random.choice([n_a, n_b])
    init_veto_state(MAP_POOL.copy(), winner)
    return {"winner": winner, "maps": MAP_POOL}

@app.post("/api/veto/action")
def veto_action(req: VetoActionRequest):
    rem, picked, turn_team = get_veto_state()
    if rem is None:
        raise HTTPException(400, "Veto not initialized")
    if req.map_name not in rem:
        raise HTTPException(400, f"Map {req.map_name} not in remaining pool")

    # Determine opponent team
    saved = load_draft_state()
    if not saved:
        raise HTTPException(400, "No active draft")
    _, _, n_a, n_b, *_ = saved
    opp = n_b if turn_team == n_a else n_a

    is_pick = len(picked) < 2
    if is_pick:
        picked.append(req.map_name)
    rem.remove(req.map_name)

    # Check if veto is over: 1 map remains after all bans
    if len(rem) == 1 and not is_pick:
        final_map = rem[0]
        final_three = picked + [final_map]
        update_draft_map(final_three)
        init_veto_state([], "")
        
        # AUTOMATIC LOBBY CREATION
        # Default to Skeez as admin if creator not found
        creator = "Skeez"
        if saved:
            creator = saved[10] or "Skeez"
            
        link, mid = create_cybershoke_lobby_api(admin_name=creator)
        if link:
            set_lobby_link(link, mid)
            
        return {"complete": True, "final_maps": final_three, "picked": picked, "lobby_link": link}
    else:
        update_veto_turn(rem, picked, opp)
        return {
            "complete": False,
            "remaining": rem,
            "protected": picked,
            "picked": picked,
            "next_turn": opp,
            "phase": "pick" if len(picked) < 2 else "ban"
        }

# ──────────────────────────────────────────────
# VOTING (Captains)
# ──────────────────────────────────────────────

class CaptainLoginRequest(BaseModel):
    name: str

@app.get("/api/votes")
def vote_status():
    df = get_vote_status()
    return df_to_records(df)

@app.post("/api/votes")
def submit_captain_vote(req: VoteRequest):
    submit_vote(req.token, req.vote)

    # Check consensus to auto-start veto
    votes_df = get_vote_status()
    approve_count = 0
    reroll_detected = False
    if not votes_df.empty:
        for _, r in votes_df.iterrows():
            if r['vote'] == 'Approve':
                approve_count += 1
            elif r['vote'] == 'Reroll':
                reroll_detected = True

    # Auto-reroll: if any captain voted Reroll, automatically generate new teams
    if reroll_detected:
        saved = load_draft_state()
        if saved:
            t1_old, t2_old, n_a, n_b, a1_old, a2_old, db_map, lobby, mid, mode, original_creator = saved
            all_players = t1_old + t2_old
            player_df = get_player_stats()

            if mode == "kd_balanced":
                metric = "avg_kd"
            elif mode == "hltv_balanced":
                metric = "hltv"
            else:
                metric = "overall"

            roommates = get_roommates()
            all_combos = get_best_combinations(all_players, force_split=[], force_together=roommates, metric=metric)
            ridx = random.randint(1, min(50, len(all_combos) - 1))
            t1, t2, a1, a2, gap = all_combos[ridx]

            save_draft_state(t1, t2, n_a, n_b, a1, a2, mode=mode, created_by=original_creator)
            init_empty_captains()

        return {"status": "ok", "rerolled": True}

    if approve_count >= 2:
        rem, _, _ = get_veto_state()
        if not rem:
            saved = load_draft_state()
            if saved:
                _, _, n_a, n_b, *_ = saved
                winner = random.choice([n_a, n_b])
                init_veto_state(MAP_POOL.copy(), winner)

    return {"status": "ok"}

@app.post("/api/captain/login")
def captain_login(req: CaptainLoginRequest):
    """Captain logs in by name. Returns their pin and draft info."""
    row = get_captain_by_name(req.name)

    if not row:
        raise HTTPException(401, "You are not a captain in the current draft")

    saved = load_draft_state()
    draft_data = None
    if saved:
        t1, t2, n_a, n_b, a1, a2, *_ = saved
        draft_data = {"team1": t1, "team2": t2, "name_a": n_a, "name_b": n_b, "avg1": a1, "avg2": a2}

    return {
        "captain_name": row[0],
        "pin": row[1],
        "current_vote": row[2],
        "draft": draft_data,
    }

@app.post("/api/captain/claim")
def captain_claim(req: CaptainLoginRequest):
    """Claim a captain spot by player name. Checks player is in draft, claims the spot, returns full state."""
    import uuid
    name = req.name.strip()

    saved = load_draft_state()
    if not saved:
        raise HTTPException(400, "No active draft")
    t1, t2, n_a, n_b, a1, a2, db_map, lobby, mid, mode, created_by = saved

    # Determine which team this player is on
    team_num = None
    if name in t1:
        team_num = 1
    elif name in t2:
        team_num = 2
    else:
        raise HTTPException(403, "You are not in this draft")

    # Check if banned from captaincy (rerolled)
    if is_captain_banned(name):
        raise HTTPException(403, "You forfeited captaincy by rerolling")

    # Check if already claimed (by this player)
    existing = get_captain_by_name(name)

    if existing:
        # Already a captain — just return their state
        pass
    else:
        # Check if the placeholder for this team still exists (spot not yet taken)
        if not check_captain_placeholder(team_num):
            raise HTTPException(409, "Captain for your team has already stepped in")

        # Try to claim the spot
        pin = str(uuid.uuid4())
        success = claim_captain_spot(team_num, name, pin)
        if not success:
            raise HTTPException(409, "Captain for your team has already stepped in")

    # Return full captain state (same as /api/captain/state)
    row = get_captain_by_name(name)

    if not row:
        raise HTTPException(500, "Failed to retrieve captain state after claim")

    draft_data = {
        "team1": t1, "team2": t2, "name_a": n_a, "name_b": n_b,
        "avg1": a1, "avg2": a2, "map_pick": db_map,
    }

    votes_df = get_vote_status()
    votes = df_to_records(votes_df) if not votes_df.empty else []

    rem, picked, turn_team = get_veto_state()
    veto_data = None
    if rem is not None:
        veto_data = {
            "initialized": True,
            "remaining": rem,
            "protected": picked,
            "picked": picked,
            "turn_team": turn_team,
            "complete": len(rem) == 0,
        }

    # Inject pings
    pings = {name: p for name, p in PLAYER_PINGS.items()}

    return {
        "captain_name": row[0],
        "pin": row[1],
        "current_vote": row[2],
        "draft": draft_data,
        "all_votes": votes,
        "veto": veto_data,
        "pings": pings,
    }

@app.get("/api/captain/state")
def captain_state(name: str = Query(...)):
    """Get full state for a captain: draft, vote status, veto status."""
    row = get_captain_by_name(name)

    if not row:
        raise HTTPException(401, "Not a captain in current draft")

    saved = load_draft_state()
    draft_data = None
    if saved:
        t1, t2, n_a, n_b, a1, a2, db_map, lobby, mid, mode, created_by = saved
        draft_data = {
            "team1": t1, "team2": t2, "name_a": n_a, "name_b": n_b,
            "avg1": a1, "avg2": a2, "map_pick": db_map,
        }

    # Get both votes
    votes_df = get_vote_status()
    votes = df_to_records(votes_df) if not votes_df.empty else []

    # Get veto state
    rem, picked, turn_team = get_veto_state()
    veto_data = None
    if rem is not None:
        veto_data = {
            "initialized": True,
            "remaining": rem,
            "protected": picked,
            "picked": picked,
            "turn_team": turn_team,
            "complete": len(rem) == 0,
        }

    # Inject pings
    pings = {name: p for name, p in PLAYER_PINGS.items()}

    return {
        "captain_name": row[0],
        "pin": row[1],
        "current_vote": row[2],
        "draft": draft_data,
        "all_votes": votes,
        "veto": veto_data,
        "pings": pings,
    }

@app.get("/api/votes/{token}")
def captain_info(token: str):
    """Get captain info for mobile voting page."""
    row = get_captain_by_pin(token)

    if not row:
        raise HTTPException(404, "Token expired or invalid")

    saved = load_draft_state()
    draft_data = None
    if saved:
        t1, t2, n_a, n_b, *_ = saved
        draft_data = {"team1": t1, "team2": t2, "name_a": n_a, "name_b": n_b}

    return {
        "captain_name": row[0],
        "current_vote": row[1],
        "draft": draft_data,
    }

# ──────────────────────────────────────────────
# STATS & LEADERBOARD
# ──────────────────────────────────────────────

@app.get("/api/leaderboard")
def leaderboard(season: str = Query("Season 2 (Demos)")):
    seasons = get_all_seasons()

    if season == "All Time":
        start_date, end_date = None, None
    elif season in seasons:
        start_date, end_date = seasons[season]
    else:
        start_date, end_date = None, None

    if season == "Season 1 (Manual)":
        df = get_player_stats()
        df = df[df['Matches'] > 0].sort_values("overall", ascending=False)
        return {"mode": "manual", "data": df_to_records(df)}

    # Season 2 / Demo / All Time
    date_filter = ""
    params = {}
    if start_date:
        date_filter += " AND date(md.date_analyzed) >= date(:start_date)"
        params["start_date"] = str(start_date)
    if end_date:
        date_filter += " AND date(md.date_analyzed) <= date(:end_date)"
        params["end_date"] = str(end_date)

    query = f'''
        SELECT
            pms.player_name,
            COUNT(*) as matches,
            ROUND(CAST(AVG(pms.score) AS NUMERIC), 1) as avg_score,
            ROUND(CAST(AVG(NULLIF(pms.adr, 0)) AS NUMERIC), 1) as avg_adr,
            ROUND(CAST(AVG(NULLIF(pms.rating, 0)) AS NUMERIC), 2) as rating,
            ROUND(CAST(SUM(pms.kills) * 1.0 / NULLIF(SUM(pms.deaths), 0) AS NUMERIC), 2) as kd_ratio,
            ROUND(CAST(AVG(NULLIF(pms.headshot_pct, 0)) AS NUMERIC), 1) as avg_hs_pct,
            SUM(pms.kills) as total_kills,
            COUNT(CASE WHEN pms.match_result = 'W' THEN 1 END) as wins,
            COUNT(CASE WHEN pms.match_result = 'L' THEN 1 END) as losses
        FROM player_match_stats pms
        JOIN match_details md ON pms.match_id = md.match_id
        WHERE pms.rating IS NOT NULL {date_filter}
        GROUP BY pms.player_name
        HAVING COUNT(*) >= 5
        ORDER BY rating DESC
    '''
    with sync_engine.connect() as conn:
        df = pd.read_sql_query(sa_text(query), conn, params=params)

    if not df.empty:
        df['winrate'] = 0.0
        valid = df['matches'] > 0
        df.loc[valid, 'winrate'] = (df.loc[valid, 'wins'] / df.loc[valid, 'matches'] * 100).round(1)

    return {"mode": "demo", "data": df_to_records(df)}

@app.get("/api/players/{name}/stats")
def player_stats(name: str, season: str = Query("Season 2 (Demos)")):
    seasons = get_all_seasons()
    if season == "All Time":
        start_date, end_date = None, None
    elif season in seasons:
        start_date, end_date = seasons[season]
    else:
        start_date, end_date = None, None

    df = get_player_aggregate_stats(name, start_date=start_date, end_date=end_date)
    records = df_to_records(df)
    
    if not records:
        return []

    # Inject rank
    date_filter = ""
    params = {}
    if start_date:
        date_filter += " AND date(md.date_analyzed) >= date(:start_date)"
        params["start_date"] = str(start_date)
    if end_date:
        date_filter += " AND date(md.date_analyzed) <= date(:end_date)"
        params["end_date"] = str(end_date)

    lb_query = f'''
        SELECT pms.player_name, ROUND(CAST(AVG(NULLIF(pms.rating, 0)) AS NUMERIC), 2) as rating
        FROM player_match_stats pms
        JOIN match_details md ON pms.match_id = md.match_id
        WHERE pms.rating IS NOT NULL {date_filter}
        GROUP BY pms.player_name
        ORDER BY rating DESC
    '''
    with sync_engine.connect() as conn:
        lb_df = pd.read_sql_query(sa_text(lb_query), conn, params=params)

    rank = None
    if not lb_df.empty:
        try:
            rank = int(lb_df[lb_df['player_name'] == name].index[0] + 1)
        except:
            pass
    
    records[0]['rank'] = rank
    return records

@app.get("/api/players/{name}/matches")
def player_matches(name: str, season: str = Query("Season 2 (Demos)")):
    seasons = get_all_seasons()
    if season == "All Time":
        start_date, end_date = None, None
    elif season in seasons:
        start_date, end_date = seasons[season]
    else:
        start_date, end_date = None, None

    date_filter = ""
    params = {"name": name}
    if start_date:
        date_filter += " AND date(md.date_analyzed) >= date(:start_date)"
        params["start_date"] = str(start_date)
    if end_date:
        date_filter += " AND date(md.date_analyzed) <= date(:end_date)"
        params["end_date"] = str(end_date)

    query = f'''
        SELECT
            md.map as map, md.score_t || '-' || md.score_ct as score,
            pms.match_result as result, pms.rating, pms.kills, pms.deaths,
            pms.adr, pms.kd_ratio, DATE(md.date_analyzed) as date,
            md.lobby_url as lobby
        FROM player_match_stats pms
        JOIN match_details md ON pms.match_id = md.match_id
        WHERE pms.player_name = :name {date_filter}
        ORDER BY md.date_analyzed DESC
    '''
    with sync_engine.connect() as conn:
        df = pd.read_sql_query(sa_text(query), conn, params=params)
    return df_to_records(df)

# ──────────────────────────────────────────────
# TROPHIES
# ──────────────────────────────────────────────

@app.get("/api/trophies/season")
def season_trophies():
    s_name, s_start, s_end = get_current_season_info()
    df = get_season_stats_dump(s_start, s_end)
    if df.empty:
        return {"season": s_name, "trophies": [], "rankings": []}

    trophies = []
    def add_trophy(col, title, icon, unit, grad, txt_color, reverse=False):
        if col in df.columns:
            winner = df.loc[df[col].idxmin()] if reverse else df.loc[df[col].idxmax()]
            val = winner[col]
            if val > 0 or (reverse and val >= 0):
                fmt_val = f"${val:,.0f}" if "$" in unit else f"{val:.1f}"
                trophies.append({
                    "title": title, "icon": icon, "player": winner['player_name'],
                    "value": fmt_val, "unit": unit, "gradient": grad, "color": txt_color
                })

    add_trophy('avg_rating', "Season MVP", "⭐", "rating", "linear-gradient(135deg, #FFD700, #FDB931)", "#FFD700")
    add_trophy('avg_kills', "The Terminator", "🤖", "kills/game", "linear-gradient(135deg, #2b5876, #4e4376)", "#a8c0ff")
    add_trophy('avg_assists', "Iniesta", "⚽", "ast/game", "linear-gradient(135deg, #1D976C, #93F9B9)", "#1D976C")
    add_trophy('avg_entries', "Entry King", "👑", "ent/game", "linear-gradient(135deg, #FFD700, #FDB931)", "#FFD700")
    add_trophy('avg_hs_pct', "Headshot Machine", "🤯", "%", "linear-gradient(135deg, #f12711, #f5af19)", "#f5af19")
    add_trophy('avg_flashed', "Ambouba", "🔦", "flash/game", "linear-gradient(135deg, #E0EAFC, #CFDEF3)", "#FFF")
    add_trophy('avg_util_dmg', "Utility King", "🧨", "dmg/game", "linear-gradient(135deg, #cc2b5e, #753a88)", "#cc2b5e")
    add_trophy('avg_flash_assists', "Blind Master", "🕶️", "fa/game", "linear-gradient(135deg, #42275a, #734b6d)", "#734b6d")
    add_trophy('avg_plants', "The Planter", "🌱", "plants/game", "linear-gradient(135deg, #F2994A, #F2C94C)", "#F2994A")
    add_trophy('avg_defuses', "The Ninja", "✂️", "defs/game", "linear-gradient(135deg, #11998e, #38ef7d)", "#11998e")
    add_trophy('avg_bait_rounds', "Master Baiter", "🎣", "baits/game", "linear-gradient(135deg, #00C6FF, #0072FF)", "#00C6FF")
    add_trophy('winrate', "3atba", "🧱", "% Win", "linear-gradient(135deg, #434343, #000000)", "#AAA", reverse=True)
    add_trophy('avg_rating', "Least Impact", "📉", "rating", "linear-gradient(135deg, #232526, #414345)", "#999", reverse=True)

    if 'total_clutches' in df.columns and df['total_clutches'].sum() > 0:
        clutcher = df.loc[df['total_clutches'].idxmax()]
        trophies.append({
            "title": "Clutch God", "icon": "🔥", "player": clutcher['player_name'],
            "value": str(int(clutcher['total_clutches'])), "unit": "Clutches",
            "gradient": "linear-gradient(135deg, #8E2DE2, #4A00E0)", "color": "#8E2DE2"
        })

    # Rankings table
    disp = df.copy()
    disp['kd'] = (disp['total_kills'] / disp['total_deaths'].replace(0, 1)).round(2)
    rankings = disp[['player_name', 'matches_played', 'winrate', 'avg_rating', 'kd', 'avg_adr', 'avg_hs_pct', 'avg_assists', 'avg_entries', 'total_clutches']].copy()
    rankings['avg_rating'] = rankings['avg_rating'].round(2)
    for c in rankings.columns:
        if rankings[c].dtype == 'float64' and c not in ['kd', 'avg_rating']:
            rankings[c] = rankings[c].round(1)

    return {
        "season": s_name,
        "start": str(s_start),
        "end": str(s_end),
        "trophies": trophies,
        "rankings": df_to_records(rankings.sort_values('avg_rating', ascending=False))
    }

@app.get("/api/trophies/match/{match_id}")
def match_trophies(match_id: str):
    with sync_engine.connect() as conn:
        query = "SELECT * FROM player_match_stats WHERE match_id = :mid"
        df = pd.read_sql_query(sa_text(query), conn, params={"mid": match_id})

    if df.empty:
        return {"trophies": [], "scoreboard": []}

    # Parse weapon kills
    pistols = ['glock', 'hkp2000', 'usp_silencer', 'p250', 'elite', 'fiveseven', 'tec9', 'cz75a', 'deagle', 'revolver']
    df['ak_kills'] = 0
    df['awp_kills'] = 0
    df['deagle_kills'] = 0
    df['pistol_kills'] = 0

    for idx, row in df.iterrows():
        try:
            w = row.get('weapon_kills', '{}')
            w = json.loads(w) if isinstance(w, str) else (w if isinstance(w, dict) else {})
            df.at[idx, 'ak_kills'] = w.get('ak47', 0)
            df.at[idx, 'awp_kills'] = w.get('awp', 0)
            df.at[idx, 'deagle_kills'] = w.get('deagle', 0)
            df.at[idx, 'pistol_kills'] = sum(w.get(p, 0) for p in pistols)
        except:
            pass

    trophies = []
    def add_trophy(title, icon, col, unit, grad, txt):
        if col in df.columns and df[col].sum() > 0:
            winner = df.loc[df[col].idxmax()]
            val = winner[col]
            if 'spent' in col:
                val = f"${val:,}"
            trophies.append({
                "title": title, "icon": icon, "player": winner['player_name'],
                "value": val, "unit": unit, "gradient": grad, "color": txt
            })

    add_trophy("MVP", "⭐", "rating", "Rating", "linear-gradient(135deg, #FFD700, #FDB931)", "#FFD700")
    add_trophy("Entry King", "👑", "entry_kills", "Opens", "linear-gradient(135deg, #FFD700, #FDB931)", "#FFD700")
    add_trophy("First Death", "🩸", "entry_deaths", "Deaths", "linear-gradient(135deg, #FF416C, #FF4B2B)", "#FF4B2B")
    add_trophy("Master Baiter", "🎣", "rounds_last_alive", "Rounds", "linear-gradient(135deg, #00C6FF, #0072FF)", "#00C6FF")
    add_trophy("Big Spender", "💸", "total_spent", "", "linear-gradient(135deg, #11998e, #38ef7d)", "#38ef7d")
    add_trophy("Clutch God", "🧱", "clutch_wins", "Wins", "linear-gradient(135deg, #8E2DE2, #4A00E0)", "#8E2DE2")
    add_trophy("Utility King", "🧨", "util_damage", "Dmg", "linear-gradient(135deg, #cc2b5e, #753a88)", "#cc2b5e")
    add_trophy("Blind Master", "🕶️", "flash_assists", "Assists", "linear-gradient(135deg, #42275a, #734b6d)", "#734b6d")
    add_trophy("The Planter", "🌱", "bomb_plants", "Plants", "linear-gradient(135deg, #F2994A, #F2C94C)", "#F2994A")
    add_trophy("AK-47 Master", "🔫", "ak_kills", "Kills", "linear-gradient(135deg, #b92b27, #1565C0)", "#b92b27")
    add_trophy("The Sniper", "🎯", "awp_kills", "Kills", "linear-gradient(135deg, #00b09b, #96c93d)", "#00b09b")
    add_trophy("One Deag", "🦅", "deagle_kills", "Kills", "linear-gradient(135deg, #CAC531, #F3F9A7)", "#AAA")
    add_trophy("Pistolier", "🔫", "pistol_kills", "Kills", "linear-gradient(135deg, #bdc3c7, #2c3e50)", "#bdc3c7")

    display_cols = ['player_name', 'rating', 'kills', 'deaths', 'assists', 'adr', 'entry_kills', 'rounds_last_alive', 'total_spent', 'headshot_pct']
    existing = [c for c in display_cols if c in df.columns]
    scoreboard = df[existing].sort_values('rating', ascending=False)

    return {"trophies": trophies, "scoreboard": df_to_records(scoreboard)}

# ──────────────────────────────────────────────
# MATCHES
# ──────────────────────────────────────────────

@app.get("/api/matches/recent")
def recent_matches(limit: int = 20):
    df = get_recent_matches(limit=limit)
    return df_to_records(df)

@app.get("/api/matches/{match_id}/scoreboard")
def match_scoreboard(match_id: str):
    df = get_match_scoreboard(match_id)
    return df_to_records(df)

# ──────────────────────────────────────────────
# LOBBY
# ──────────────────────────────────────────────

@app.get("/api/lobby")
def lobby_info():
    link, mid = get_lobby_link()
    return {"link": link, "match_id": mid}

@app.post("/api/lobby/create")
def create_lobby(req: LobbyCreateRequest):
    link, mid = create_cybershoke_lobby_api(admin_name=req.admin_name)
    if link:
        set_lobby_link(link, mid)
        return {"status": "ok", "link": link, "match_id": mid}
    raise HTTPException(500, "Failed to create lobby")

@app.delete("/api/lobby")
def remove_lobby():
    clear_lobby_link()
    return {"status": "ok"}

@app.post("/api/lobby/link")
def set_lobby(link: str = Query(...)):
    set_lobby_link(link)
    return {"status": "ok"}

# ──────────────────────────────────────────────
# DISCORD
# ──────────────────────────────────────────────

@app.post("/api/discord/broadcast")
def broadcast(req: BroadcastRequest, current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(403, "Only admins can broadcast to Discord")
    maps = req.maps.split(",") if isinstance(req.maps, str) else req.maps
    send_full_match_info(req.name_a, req.team1, req.name_b, req.team2, maps, req.lobby_link)
    return {"status": "ok"}

@app.post("/api/discord/lobby")
def broadcast_lobby(link: str = Query(...), current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(403, "Only admins can broadcast to Discord")
    send_lobby_to_discord(link)
    return {"status": "ok"}

# ──────────────────────────────────────────────
# ADMIN — LOBBY HISTORY
# ──────────────────────────────────────────────

@app.get("/api/lobbies")
def lobby_history():
    df = get_all_lobbies()
    return df_to_records(df)

@app.post("/api/lobbies/{lobby_id}")
def add_lobby_record(lobby_id: str):
    add_lobby(lobby_id)
    return {"status": "ok"}

@app.put("/api/lobbies/{lobby_id}/status")
def update_lobby(lobby_id: str, has_demo: Optional[int] = None, status: Optional[str] = None):
    update_lobby_status(lobby_id, has_demo=has_demo, status=status)
    return {"status": "ok"}

# ──────────────────────────────────────────────
# ADMIN — DEMO ANALYSIS
# ──────────────────────────────────────────────

@app.post("/api/admin/analyze/{lobby_id}")
def analyze_lobby(lobby_id: str):
    if is_lobby_already_analyzed(str(lobby_id)):
        raise HTTPException(409, f"Lobby {lobby_id} already analyzed")

    from demo_download import download_demo
    from demo_analysis import analyze_demo_file

    success, msg = download_demo(str(lobby_id), "Skeez")
    if not success:
        raise HTTPException(500, f"Download failed: {msg}")

    expected = f"demos/match_{lobby_id}.dem"
    if not os.path.exists(expected):
        raise HTTPException(500, "Demo file not found after download")

    try:
        score_res, stats_res, map_name, score_t, score_ct = analyze_demo_file(expected)
        if stats_res is not None:
            mid = f"match_{lobby_id}"
            saved = save_match_stats(mid, str(lobby_id), score_res, stats_res, map_name, score_t, score_ct)
            if saved:
                update_lobby_status(lobby_id, has_demo=1, status='analyzed')
                return {"status": "ok", "score": score_res, "map": map_name}
            else:
                update_lobby_status(lobby_id, has_demo=1, status='analyzed')
                return {"status": "duplicate", "message": "Already exists"}
        else:
            update_lobby_status(lobby_id, status='error')
            raise HTTPException(500, "Analysis failed")
    finally:
        if os.path.exists(expected):
            os.remove(expected)

# ──────────────────────────────────────────────
# ADMIN — ROOMMATES
# ──────────────────────────────────────────────

@app.get("/api/roommates")
def get_roommate_groups():
    raw = get_roommates()
    groups = []
    if raw:
        if isinstance(raw[0], list):
            groups = raw
        else:
            groups = [raw]
    return {"groups": groups}

@app.post("/api/roommates")
def set_roommate_groups(req: RoommatesRequest):
    set_roommates(req.groups)
    return {"status": "ok"}

# ──────────────────────────────────────────────
# MATCH UPLOAD (existing endpoint preserved)
# ──────────────────────────────────────────────

@app.post("/upload_match")
async def upload_match(data: MatchUploadData):
    try:
        if not data.player_stats:
            raise HTTPException(status_code=400, detail="No player stats provided")
        df = pd.DataFrame(data.player_stats)
        save_match_stats(
            match_id=data.match_id, cybershoke_id=data.match_id,
            score_str=data.score_str, stats_df=df,
            map_name=data.map_name, score_t=data.score_t, score_ct=data.score_ct
        )
        return {"status": "success", "message": f"Match {data.match_id} saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ──────────────────────────────────────────────
# CS2 SKIN IMAGE SEARCH (ByMykel CSGO-API)
# ──────────────────────────────────────────────

# In-memory cache for skins data (loaded once, reused)
_SKINS_CACHE: List[Dict] = []
_SKINS_CACHE_LOADED = False

@app.get("/api/skins/search")
async def search_skins(q: str = Query(..., min_length=2)):
    """Search CS2 skins by name and return matching results with images."""
    global _SKINS_CACHE, _SKINS_CACHE_LOADED

    if not _SKINS_CACHE_LOADED:
        try:
            resp = requests.get(
                "https://bymykel.github.io/CSGO-API/api/en/skins.json",
                timeout=15,
                allow_redirects=True,
            )
            if resp.status_code == 200:
                _SKINS_CACHE = resp.json()
                _SKINS_CACHE_LOADED = True
            else:
                raise HTTPException(502, "Failed to fetch skins database")
        except requests.RequestException as e:
            raise HTTPException(502, f"Failed to fetch skins database: {e}")

    query = q.lower().strip()
    results = []
    for skin in _SKINS_CACHE:
        skin_name = skin.get("name", "")
        if query in skin_name.lower():
            results.append({
                "name": skin_name,
                "image": skin.get("image", ""),
                "rarity": skin.get("rarity", {}).get("name", ""),
                "rarity_color": skin.get("rarity", {}).get("color", ""),
            })
            if len(results) >= 20:
                break

    return results


# ──────────────────────────────────────────────
# IMAGE UPLOAD (Supabase Storage)
# ──────────────────────────────────────────────

@app.post("/api/upload/image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Upload an image to Supabase Storage. Returns the public URL."""
    if current_user.role != "admin":
        raise HTTPException(403, "Only admins can upload images")

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(500, "Supabase storage not configured")

    # Validate content type
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, f"Invalid file type: {file.content_type}. Allowed: png, jpg, webp, gif")

    # Read file and validate size
    contents = await file.read()
    if len(contents) > MAX_IMAGE_SIZE:
        raise HTTPException(400, f"File too large. Maximum: 5MB")

    # Generate unique filename
    ext = file.filename.rsplit('.', 1)[-1].lower() if file.filename and '.' in file.filename else 'png'
    if ext not in ('png', 'jpg', 'jpeg', 'webp', 'gif'):
        ext = 'png'
    storage_filename = f"{uuid_mod.uuid4().hex}.{ext}"

    # Upload to Supabase Storage via REST API
    upload_url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{storage_filename}"
    headers = {
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": file.content_type or "application/octet-stream",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.put(upload_url, content=contents, headers=headers, timeout=30.0)

    if resp.status_code not in (200, 201):
        raise HTTPException(502, f"Upload failed: {resp.text}")

    # Construct public URL
    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{storage_filename}"
    return {"url": public_url, "filename": storage_filename}


# ──────────────────────────────────────────────
# TOURNAMENTS
# ──────────────────────────────────────────────

@app.get("/api/tournaments")
async def list_tournaments(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List tournaments, optionally filtered by status (open, active, completed)."""
    query = select(Tournament).order_by(Tournament.created_at.desc())
    if status:
        query = query.filter(Tournament.status == status)
    result = await db.execute(query)
    tournaments = result.scalars().all()
    return [serialize_tournament(t) for t in tournaments]


@app.post("/api/tournaments")
async def create_tournament(
    req: TournamentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only: Create a new tournament."""
    if current_user.role != "admin":
        raise HTTPException(403, "Only admins can create tournaments")
    if req.format not in (TournamentFormat.single_elimination.value, TournamentFormat.round_robin.value):
        raise HTTPException(400, "format must be 'single_elimination' or 'round_robin'")
    # Single elimination requires a fixed player count
    if req.format == TournamentFormat.single_elimination.value and req.max_players < 2:
        raise HTTPException(400, "Single elimination requires at least 2 max_players")

    tournament = Tournament(
        name=req.name,
        description=req.description,
        rules=req.rules,
        format=req.format,
        prize_image_url=req.prize_image_url,
        prize_name=req.prize_name,
        prize_pool=req.prize_pool,
        max_players=req.max_players,
        playoffs=req.playoffs if req.format == TournamentFormat.round_robin.value else False,
        tournament_date=req.tournament_date,
        created_by=current_user.id,
        status=TournamentStatus.registration.value,
    )
    db.add(tournament)
    await db.commit()
    await db.refresh(tournament)
    return serialize_tournament(tournament)


@app.get("/api/tournaments/{tournament_id}")
async def get_tournament(tournament_id: str, db: AsyncSession = Depends(get_db)):
    """Get tournament details including participant list with stats."""
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Tournament)
        .options(selectinload(Tournament.participants), selectinload(Tournament.matches))
        .filter(Tournament.id == tournament_id)
    )
    tournament = result.scalars().first()
    if not tournament:
        raise HTTPException(404, "Tournament not found")

    data = serialize_tournament(tournament)

    # Build participant list with stats
    participants = []
    for p in (tournament.participants or []):
        pdata = {
            "id": p.id,
            "user_id": p.user.id if p.user else p.user_id,
            "username": p.user.username if p.user else "Unknown",
            "display_name": p.user.display_name if p.user else "Unknown",
            "seed": p.seed,
            "stats": None,
        }
        # Fetch player stats from match_stats if available
        player_name = p.user.display_name if p.user else None
        if player_name:
            pdata["stats"] = _get_player_stats_safe(player_name)
        participants.append(pdata)

    data["participants"] = participants
    return data


@app.put("/api/tournaments/{tournament_id}")
async def update_tournament(
    tournament_id: str,
    req: TournamentUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update tournament description, rules, and prize image. Only creator or admin."""
    result = await db.execute(select(Tournament).filter(Tournament.id == tournament_id))
    tournament = result.scalars().first()
    if not tournament:
        raise HTTPException(404, "Tournament not found")
    if current_user.role != "admin" and tournament.created_by != current_user.id:
        raise HTTPException(403, "Only the creator or an admin can edit this tournament")

    if req.description is not None:
        tournament.description = req.description
    if req.rules is not None:
        tournament.rules = req.rules
    if req.prize_image_url is not None:
        tournament.prize_image_url = req.prize_image_url

    await db.commit()
    await db.refresh(tournament)
    return serialize_tournament(tournament)

def _get_player_stats_safe(player_name: str) -> dict | None:
    """Fetch player aggregate stats. Uses local SQLite (match_stats_db) where stats actually live."""
    try:
        # Use the existing function which reads from local SQLite directly
        from match_stats_db import get_player_aggregate_stats
        df = get_player_aggregate_stats(player_name)
        if df is not None and not df.empty and df.iloc[0]['matches_played'] > 0:
            row = df.iloc[0]
            return {
                "matches_played": int(row['matches_played']),
                "total_kills": int(row['total_kills']) if row['total_kills'] else 0,
                "total_deaths": int(row['total_deaths']) if row['total_deaths'] else 0,
                "total_assists": int(row['total_assists']) if row['total_assists'] else 0,
                "avg_adr": float(row['avg_adr']) if row['avg_adr'] else None,
                "avg_rating": float(row['avg_rating']) if row['avg_rating'] else None,
                "avg_hs_pct": float(row['avg_hs_pct']) if row['avg_hs_pct'] else None,
                "overall_kd": float(row['overall_kd']) if row['overall_kd'] else None,
                "wins": int(row['wins']) if 'wins' in row else 0,
                "losses": int(row['losses']) if 'losses' in row else 0,
                "winrate_pct": float(row['winrate_pct']) if 'winrate_pct' in row else 0,
            }
    except Exception as e:
        print(f"[WARN] get_player_aggregate_stats failed for {player_name}: {e}")

    # Fallback: try basic player data from sync_engine
    try:
        from database import sync_engine
        from sqlalchemy import text as sa_text
        with sync_engine.connect() as conn:
            row = conn.execute(sa_text(
                "SELECT elo, aim, util, team_play FROM players WHERE name = :name"
            ), {"name": player_name}).fetchone()
            if row:
                return {
                    "elo": round(row[0], 0) if row[0] else None,
                    "aim": round(row[1], 1) if row[1] else None,
                    "util": round(row[2], 1) if row[2] else None,
                    "team_play": round(row[3], 1) if row[3] else None,
                }
    except Exception as e:
        print(f"[WARN] Fallback stats also failed for {player_name}: {e}")
    return None


@app.post("/api/tournaments/{tournament_id}/join")
async def join_tournament(
    tournament_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Authenticated user joins an open tournament. Auto-generates bracket when full."""
    result = await db.execute(select(Tournament).filter(Tournament.id == tournament_id))
    tournament = result.scalars().first()
    if not tournament:
        raise HTTPException(404, "Tournament not found")
    if tournament.status not in ("open", TournamentStatus.registration.value):
        raise HTTPException(400, "Tournament is not open for enrollment")

    # Check if already joined
    result = await db.execute(
        select(TournamentParticipant).filter(
            TournamentParticipant.tournament_id == tournament_id,
            TournamentParticipant.user_id == current_user.id,
        )
    )
    if result.scalars().first():
        raise HTTPException(400, "Already enrolled in this tournament")

    # Check capacity (0 = unlimited)
    result = await db.execute(
        select(TournamentParticipant).filter(
            TournamentParticipant.tournament_id == tournament_id
        )
    )
    current_count = len(result.scalars().all())
    if tournament.max_players > 0 and current_count >= tournament.max_players:
        raise HTTPException(400, "Tournament is full")

    # Enroll
    participant = TournamentParticipant(
        tournament_id=tournament_id,
        user_id=current_user.id,
    )
    db.add(participant)
    await db.flush()

    new_count = current_count + 1

    # AUTO-GENERATE BRACKET when capacity reached (only for fixed-size tournaments)
    if tournament.max_players > 0 and new_count == tournament.max_players:
        await db.commit()  # commit the participant first
        tournament = await start_tournament(tournament_id, db)
        return {
            "status": "bracket_generated",
            "message": f"Tournament is full! Bracket generated with {new_count} players.",
            "participant_count": new_count,
        }

    await db.commit()
    cap_str = f"/{tournament.max_players}" if tournament.max_players > 0 else " (open)"
    return {
        "status": "joined",
        "message": f"Enrolled successfully ({new_count}{cap_str})",
        "participant_count": new_count,
    }


@app.delete("/api/tournaments/{tournament_id}/leave")
async def leave_tournament(
    tournament_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Leave an open tournament (before bracket is generated)."""
    result = await db.execute(select(Tournament).filter(Tournament.id == tournament_id))
    tournament = result.scalars().first()
    if not tournament:
        raise HTTPException(404, "Tournament not found")
    if tournament.status not in ("open", TournamentStatus.registration.value):
        raise HTTPException(400, "Cannot leave a tournament that has already started")

    result = await db.execute(
        select(TournamentParticipant).filter(
            TournamentParticipant.tournament_id == tournament_id,
            TournamentParticipant.user_id == current_user.id,
        )
    )
    participant = result.scalars().first()
    if not participant:
        raise HTTPException(400, "Not enrolled in this tournament")

    await db.delete(participant)
    await db.commit()
    return {"status": "left", "message": "Left the tournament"}


@app.get("/api/tournaments/{tournament_id}/bracket")
async def get_bracket(tournament_id: str, db: AsyncSession = Depends(get_db)):
    """Get the full bracket/standings for a tournament, enriched with player stats."""
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Tournament)
        .options(selectinload(Tournament.participants), selectinload(Tournament.matches))
        .filter(Tournament.id == tournament_id)
    )
    tournament = result.scalars().first()
    if not tournament:
        raise HTTPException(404, "Tournament not found")
    if tournament.status in ("open", TournamentStatus.registration.value):
        raise HTTPException(400, "Bracket not yet generated (tournament still in registration)")

    # Use the correct response builder based on format
    generator = get_generator(tournament)
    bracket = generator.build_response(tournament)

    # Collect all unique player display_names and fetch stats
    stats_cache: dict[str, dict | None] = {}
    for rnd in bracket.get("rounds", []):
        for match in rnd.get("matches", []):
            for key in ("player1", "player2"):
                p = match.get(key)
                if p and p.get("display_name") and p["display_name"] not in stats_cache:
                    stats_cache[p["display_name"]] = _get_player_stats_safe(p["display_name"])
            # Also add stats for winner
            w = match.get("winner")
            if w and w.get("display_name") and w["display_name"] not in stats_cache:
                stats_cache[w["display_name"]] = _get_player_stats_safe(w["display_name"])

    # Inject stats into player objects
    for rnd in bracket.get("rounds", []):
        for match in rnd.get("matches", []):
            for key in ("player1", "player2", "winner"):
                p = match.get(key)
                if p and p.get("display_name"):
                    p["stats"] = stats_cache.get(p["display_name"])

    return bracket


@app.post("/api/matches/{match_id}/create-lobby")
async def create_tournament_lobby(
    match_id: str,
    req: TournamentLobbyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only: Create a Cybershoke lobby for a tournament match."""
    if current_user.role != "admin":
        raise HTTPException(403, "Only admins can create lobbies")

    result = await db.execute(select(TournamentMatch).filter(TournamentMatch.id == match_id))
    match = result.scalars().first()
    if not match:
        raise HTTPException(404, "Match not found")
    if not match.player1_id or not match.player2_id:
        raise HTTPException(400, "Both players must be determined before creating a lobby")
    if match.winner_id:
        raise HTTPException(400, "Match already has a winner")

    # Create Cybershoke lobby
    link, lobby_id = create_cybershoke_lobby_api(admin_name=req.admin_name)
    if not link:
        raise HTTPException(500, "Failed to create Cybershoke lobby")

    match.cybershoke_lobby_url = link
    match.cybershoke_match_id = str(lobby_id) if lobby_id else None
    await db.commit()

    return {"status": "ok", "lobby_url": link, "match_id": str(lobby_id)}


@app.post("/api/matches/{match_id}/submit-lobby")
async def submit_match_lobby(
    match_id: str,
    req: SubmitLobbyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Participant submits a finished Cybershoke lobby URL.
    The backend fetches the lobby result from the Cybershoke API and auto-determines the winner.

    Only a participant in this match (or an admin) can submit.
    """
    import re as _re

    result = await db.execute(select(TournamentMatch).filter(TournamentMatch.id == match_id))
    match = result.scalars().first()
    if not match:
        raise HTTPException(404, "Match not found")
    if match.winner_id:
        raise HTTPException(400, "Match already has a result")
    if not match.player1_id or not match.player2_id:
        raise HTTPException(400, "Both players must be determined before submitting a result")

    # Auth: must be a participant in this match OR an admin
    is_participant = current_user.id in (match.player1_id, match.player2_id)
    if not is_participant and current_user.role != "admin":
        raise HTTPException(403, "Only match participants or admins can submit lobby results")

    # Extract lobby_id from URL (e.g. "https://cybershoke.net/match/3387473")
    m = _re.search(r'/match/(\d+)', req.lobby_url)
    if not m:
        raise HTTPException(400, "Invalid Cybershoke lobby URL. Expected format: https://cybershoke.net/match/<id>")
    lobby_id = m.group(1)

    # Fetch result from Cybershoke API
    lobby_result = get_lobby_match_result(lobby_id)
    if not lobby_result:
        raise HTTPException(502, "Could not fetch lobby data from Cybershoke. The lobby may not exist or has expired.")
    if not lobby_result.get("finished"):
        raise HTTPException(400, "This match hasn't finished yet. Wait for the match to end before submitting.")
    if lobby_result.get("winning_team") is None:
        raise HTTPException(400, "Match ended in a draw or has no score. An admin will need to resolve this manually.")

    # Match Cybershoke players to tournament players.
    # Strategy: each team has players. We look up display_names of player1 and player2,
    # then check which team contains a player whose Cybershoke name matches.
    # For 1v1, each team has exactly 1 player.
    result_p1 = await db.execute(select(User).filter(User.id == match.player1_id))
    result_p2 = await db.execute(select(User).filter(User.id == match.player2_id))
    user_p1 = result_p1.scalars().first()
    user_p2 = result_p2.scalars().first()

    if not user_p1 or not user_p2:
        raise HTTPException(500, "Could not load player data")

    # Build a name-to-team mapping from the lobby
    lobby_players = lobby_result.get("players", [])
    winning_team = lobby_result["winning_team"]

    # Try to match each tournament player to a lobby player by name (case-insensitive)
    def find_team_for_user(user: User) -> int | None:
        names_to_try = set()
        if user.display_name:
            names_to_try.add(user.display_name.lower())
        if user.username:
            names_to_try.add(user.username.lower())

        for lp in lobby_players:
            if lp["name"].lower() in names_to_try:
                return lp["team"]
        return None

    p1_team = find_team_for_user(user_p1)
    p2_team = find_team_for_user(user_p2)

    # Determine winner
    winner_id = None
    if p1_team == winning_team:
        winner_id = match.player1_id
    elif p2_team == winning_team:
        winner_id = match.player2_id
    elif p1_team is not None and p2_team is not None:
        # Both found but neither on winning team? Shouldn't happen, but fallback
        raise HTTPException(400, "Could not determine winner from lobby data. Player team assignments unclear.")
    else:
        # Could not match players by name — fall back to positional:
        # In a 1v1, if only 2 players in the lobby, team_2 = player slot 0, team_3 = player slot 1.
        # We assume player1 was team_2, player2 was team_3 (order they joined).
        # This is a best-effort fallback.
        if len(lobby_players) == 2:
            # Sort by team to get deterministic assignment
            sorted_lp = sorted(lobby_players, key=lambda p: p["team"])
            if winning_team == sorted_lp[0]["team"]:
                winner_id = match.player1_id
            else:
                winner_id = match.player2_id
        else:
            raise HTTPException(
                400,
                f"Could not match tournament players to Cybershoke lobby players. "
                f"Lobby players: {[p['name'] for p in lobby_players]}. "
                f"Expected: {user_p1.display_name}, {user_p2.display_name}. "
                f"An admin can report this match manually."
            )

    # Record the result
    score_str = lobby_result["score"]
    try:
        await report_match(match_id, winner_id, score_str, db)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Also save the lobby URL on the match
    result = await db.execute(select(TournamentMatch).filter(TournamentMatch.id == match_id))
    updated_match = result.scalars().first()
    if updated_match:
        updated_match.cybershoke_lobby_url = req.lobby_url
        updated_match.cybershoke_match_id = lobby_id
        await db.commit()

    winner_name = user_p1.display_name if winner_id == match.player1_id else user_p2.display_name
    return {
        "status": "ok",
        "message": f"{winner_name} wins! ({score_str})",
        "winner_id": winner_id,
        "score": score_str,
        "map": lobby_result.get("map_name"),
    }


@app.post("/api/matches/{match_id}/advance-winner")
async def advance_match_winner(
    match_id: str,
    req: AdvanceWinnerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only: Set the winner of a match and advance them in the bracket."""
    if current_user.role != "admin":
        raise HTTPException(403, "Only admins can advance winners")

    try:
        match = await advance_winner(match_id, req.winner_id, db)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {"status": "ok", "message": "Winner advanced"}


@app.post("/api/tournaments/{tournament_id}/start")
async def start_tournament_endpoint(
    tournament_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only: Lock the roster and generate bracket/schedule. Works for any format."""
    if current_user.role != "admin":
        raise HTTPException(403, "Only admins can start tournaments")
    try:
        tournament = await start_tournament(tournament_id, db)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"status": "started", "message": f"Tournament started with format '{tournament.format}'"}


@app.post("/api/matches/{match_id}/report")
async def report_match_endpoint(
    match_id: str,
    req: ReportMatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only: Report match result with score. Auto-advances winner for Single Elimination."""
    if current_user.role != "admin":
        raise HTTPException(403, "Only admins can report matches")
    try:
        match = await report_match(match_id, req.winner_id, req.score, db)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"status": "ok", "message": "Match result recorded", "score": match.score}


@app.delete("/api/tournaments/{tournament_id}")
async def delete_tournament(
    tournament_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only: Delete a tournament and all related data."""
    if current_user.role != "admin":
        raise HTTPException(403, "Only admins can delete tournaments")

    result = await db.execute(select(Tournament).filter(Tournament.id == tournament_id))
    tournament = result.scalars().first()
    if not tournament:
        raise HTTPException(404, "Tournament not found")

    # Delete matches
    result = await db.execute(
        select(TournamentMatch).filter(TournamentMatch.tournament_id == tournament_id)
    )
    for match in result.scalars().all():
        await db.delete(match)

    # Delete participants
    result = await db.execute(
        select(TournamentParticipant).filter(TournamentParticipant.tournament_id == tournament_id)
    )
    for p in result.scalars().all():
        await db.delete(p)

    await db.delete(tournament)
    await db.commit()
    return {"status": "ok", "message": "Tournament deleted"}


# ──────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

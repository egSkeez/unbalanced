from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Header, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import pandas as pd
import uvicorn
import random
import json
import sqlite3
import os
import requests
import datetime

from auth import (
    init_user_accounts, create_access_token, get_current_user, get_current_user_optional,
    get_db, hash_password, verify_password
)
from models import User, Tournament, TournamentParticipant, TournamentMatch
from schemas import UserCreate, UserLogin, UserOut, Token
from tournament_logic import (
    generate_single_elimination_bracket, advance_winner,
    build_bracket_response, serialize_tournament
)

# In-memory store for player pings (username -> ms)
PLAYER_PINGS: Dict[str, float] = {}

from database import (
    init_db, init_async_db, get_player_stats, save_draft_state, load_draft_state,
    clear_draft_state, get_roommates, set_roommates,
    init_veto_state, get_veto_state, update_veto_turn, update_draft_map,
    get_vote_status, set_draft_pins, submit_vote, update_elo,
    init_empty_captains, claim_captain_spot
)
from match_stats_db import (
    init_match_stats_tables, save_match_stats, get_player_aggregate_stats,
    get_recent_matches, get_season_stats_dump, get_match_scoreboard,
    get_all_lobbies, add_lobby, update_lobby_status, is_lobby_already_analyzed,
    get_player_weapon_stats
)
from logic import get_best_combinations, pick_captains, cycle_new_captain
from cybershoke import (
    create_cybershoke_lobby_api, set_lobby_link, get_lobby_link, clear_lobby_link
)
from discord_bot import send_full_match_info, send_lobby_to_discord
from constants import TEAM_NAMES, MAP_POOL, MAP_LOGOS, SKEEZ_TITLES, PLAYERS_INIT
from season_logic import get_current_season_info, get_all_seasons
from migrate_ratings import check_and_migrate

# --- Lifespan for Async Init ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db() # Legacy Sync
    init_match_stats_tables() # Legacy Sync
    check_and_migrate() # Legacy Sync
    await init_async_db() # New Async (creates all tables including tournaments)
    await init_user_accounts() # New Async
    # Migrate tournament_date column for existing databases
    try:
        from sqlalchemy import text as sa_text
        from database import sync_engine
        with sync_engine.begin() as conn:
            conn.execute(sa_text("ALTER TABLE tournaments ADD COLUMN tournament_date TEXT"))
    except Exception:
        pass  # column already exists or table just created with it
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
    prize_image_url: Optional[str] = None
    prize_name: Optional[str] = None
    max_players: int = 8  # 4, 8, 16, or 32
    tournament_date: Optional[str] = None  # e.g. "2026-03-15"

class AdvanceWinnerRequest(BaseModel):
    winner_id: str

class TournamentLobbyRequest(BaseModel):
    admin_name: str = "Skeez"

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
    
    # Check existing
    result = await db.execute(select(User).filter(User.username == req.username.lower()))
    if result.scalars().first():
        raise HTTPException(409, "Username already exists")
    
    hashed = hash_password(req.password)
    new_user = User(
        username=req.username.lower(),
        hashed_password=hashed,
        role="player",
        display_name=req.display_name or req.username
    )
    db.add(new_user)
    try:
        await db.commit()
        await db.refresh(new_user)
    except Exception as e:
        await db.rollback()
        raise HTTPException(500, f"Database error: {str(e)}")
        
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
    
    # Check if user is captain in current draft (Legacy SQLite mixin)
    # Ideally this should also be async or refactored, but strictly speaking we can run sync code here 
    # if it's fast, OR we use `run_sync`.
    # Since sqlite3 is blocking, we should be careful. 
    # For now, I'll keep the sync sqlite3 calls for the *game logic* parts as refactoring EVERYTHING is out of scope.
    # But I'll wrap them? No, just call them. It will block the event loop slightly but acceptable for migration MVP.
    
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("SELECT captain_name, pin, vote FROM current_draft_votes WHERE LOWER(captain_name) = LOWER(?)", (display,))
    cap_row = c.fetchone()
    conn.close()
    
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
    conn = sqlite3.connect('cs2_history.db')
    q = f'''
        SELECT md.match_id, md.map, md.score_t || '-' || md.score_ct as score, md.date_analyzed,
               pms.kills, pms.deaths, pms.assists, pms.adr, pms.rating
        FROM player_match_stats pms
        JOIN match_details md ON pms.match_id = md.match_id
        WHERE pms.player_name = ?
          AND date(md.date_analyzed) >= date(?)
          AND date(md.date_analyzed) <= date(?)
        ORDER BY md.date_analyzed DESC
    '''
    df = pd.read_sql_query(q, conn, params=[name, start, end])
    conn.close()
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
    conn = sqlite3.connect('cs2_history.db')
    try:
        conn.execute(
            "INSERT OR IGNORE INTO players (name, elo, aim, util, team_play, secret_word) VALUES (?, 1200, ?, ?, ?, ?)",
            (req.name, req.aim, req.util, req.team_play, "cs2pro")
        )
        conn.commit()
        return {"status": "ok", "message": f"Added {req.name}"}
    finally:
        conn.close()

@app.put("/api/players/{name}")
def update_player(name: str, req: PlayerUpdateRequest):
    conn = sqlite3.connect('cs2_history.db')
    try:
        conn.execute("UPDATE players SET aim=?, util=?, team_play=? WHERE name=?",
                      (req.aim, req.util, req.team_play, name))
        conn.commit()
        return {"status": "ok"}
    finally:
        conn.close()

@app.delete("/api/players/{name}")
def delete_player(name: str):
    conn = sqlite3.connect('cs2_history.db')
    try:
        conn.execute("DELETE FROM players WHERE name=?", (name,))
        conn.commit()
        return {"status": "ok"}
    finally:
        conn.close()

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
        conn = sqlite3.connect('cs2_history.db')
        conn.execute("INSERT INTO current_draft_votes (captain_name, pin, vote) VALUES (?, ?, ?)", (reroller_name, "", "BANNED"))
        conn.commit()
        conn.close()

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

    conn = sqlite3.connect('cs2_history.db')
    banned = conn.execute("SELECT 1 FROM current_draft_votes WHERE captain_name=? AND vote='BANNED'", (display,)).fetchone()
    conn.close()
    if banned:
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
        return {"complete": True, "final_maps": final_three, "picked": picked}
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
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("SELECT captain_name, pin, vote FROM current_draft_votes WHERE LOWER(captain_name) = LOWER(?)", (req.name,))
    row = c.fetchone()
    conn.close()

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
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("SELECT 1 FROM current_draft_votes WHERE captain_name=? AND vote='BANNED'", (name,))
    if c.fetchone():
        conn.close()
        raise HTTPException(403, "You forfeited captaincy by rerolling")

    # Check if already claimed (by this player)
    c.execute("SELECT captain_name, pin, vote FROM current_draft_votes WHERE LOWER(captain_name) = LOWER(?)", (name,))
    existing = c.fetchone()

    if existing:
        # Already a captain — just return their state
        conn.close()
    else:
        # Check if the placeholder for this team still exists (spot not yet taken)
        placeholder = f"__TEAM{team_num}__"
        c.execute("SELECT 1 FROM current_draft_votes WHERE captain_name = ?", (placeholder,))
        spot_available = c.fetchone()
        conn.close()

        if not spot_available:
            raise HTTPException(409, "Captain for your team has already stepped in")

        # Try to claim the spot
        pin = str(uuid.uuid4())
        success = claim_captain_spot(team_num, name, pin)
        if not success:
            raise HTTPException(409, "Captain for your team has already stepped in")

    # Return full captain state (same as /api/captain/state)
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("SELECT captain_name, pin, vote FROM current_draft_votes WHERE LOWER(captain_name) = LOWER(?)", (name,))
    row = c.fetchone()
    conn.close()

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
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("SELECT captain_name, pin, vote FROM current_draft_votes WHERE LOWER(captain_name) = LOWER(?)", (name,))
    row = c.fetchone()
    conn.close()

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
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("SELECT captain_name, vote FROM current_draft_votes WHERE pin=?", (token,))
    row = c.fetchone()
    conn.close()

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
    conn = sqlite3.connect('cs2_history.db')
    date_filter = ""
    params = []
    if start_date:
        date_filter += " AND date(md.date_analyzed) >= date(?)"
        params.append(str(start_date))
    if end_date:
        date_filter += " AND date(md.date_analyzed) <= date(?)"
        params.append(str(end_date))

    query = f'''
        SELECT
            pms.player_name,
            COUNT(*) as matches,
            ROUND(AVG(pms.score), 1) as avg_score,
            ROUND(AVG(NULLIF(pms.adr, 0)), 1) as avg_adr,
            ROUND(AVG(NULLIF(pms.rating, 0)), 2) as rating,
            ROUND(SUM(pms.kills) * 1.0 / NULLIF(SUM(pms.deaths), 0), 2) as kd_ratio,
            ROUND(AVG(NULLIF(pms.headshot_pct, 0)), 1) as avg_hs_pct,
            SUM(pms.kills) as total_kills,
            COUNT(CASE WHEN pms.match_result = 'W' THEN 1 END) as wins,
            COUNT(CASE WHEN pms.match_result = 'L' THEN 1 END) as losses
        FROM player_match_stats pms
        JOIN match_details md ON pms.match_id = md.match_id
        WHERE pms.rating IS NOT NULL {date_filter}
        GROUP BY pms.player_name
        HAVING matches >= 5
        ORDER BY rating DESC
    '''
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

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
    conn = sqlite3.connect('cs2_history.db')
    date_filter = ""
    params = []
    if start_date:
        date_filter += " AND date(md.date_analyzed) >= date(?)"
        params.append(str(start_date))
    if end_date:
        date_filter += " AND date(md.date_analyzed) <= date(?)"
        params.append(str(end_date))

    lb_query = f'''
        SELECT pms.player_name, ROUND(AVG(NULLIF(pms.rating, 0)), 2) as rating
        FROM player_match_stats pms
        JOIN match_details md ON pms.match_id = md.match_id
        WHERE pms.rating IS NOT NULL {date_filter}
        GROUP BY pms.player_name
        ORDER BY rating DESC
    '''
    lb_df = pd.read_sql_query(lb_query, conn, params=params)
    conn.close()

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

    conn = sqlite3.connect('cs2_history.db')
    date_filter = ""
    params = [name]
    if start_date:
        date_filter += " AND date(md.date_analyzed) >= date(?)"
        params.append(str(start_date))
    if end_date:
        date_filter += " AND date(md.date_analyzed) <= date(?)"
        params.append(str(end_date))

    query = f'''
        SELECT
            md.map as map, md.score_t || '-' || md.score_ct as score,
            pms.match_result as result, pms.rating, pms.kills, pms.deaths,
            pms.adr, pms.kd_ratio, DATE(md.date_analyzed) as date,
            md.lobby_url as lobby
        FROM player_match_stats pms
        JOIN match_details md ON pms.match_id = md.match_id
        WHERE pms.player_name = ? {date_filter}
        ORDER BY md.date_analyzed DESC
    '''
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
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
    conn = sqlite3.connect('cs2_history.db')
    query = "SELECT * FROM player_match_stats WHERE match_id = ?"
    df = pd.read_sql_query(query, conn, params=(match_id,))
    conn.close()

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
def broadcast(req: BroadcastRequest):
    maps = req.maps.split(",") if isinstance(req.maps, str) else req.maps
    send_full_match_info(req.name_a, req.team1, req.name_b, req.team2, maps, req.lobby_link)
    return {"status": "ok"}

@app.post("/api/discord/lobby")
def broadcast_lobby(link: str = Query(...)):
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
    if req.max_players not in (4, 8, 16, 32):
        raise HTTPException(400, "max_players must be 4, 8, 16, or 32")

    tournament = Tournament(
        name=req.name,
        prize_image_url=req.prize_image_url,
        prize_name=req.prize_name,
        max_players=req.max_players,
        tournament_date=req.tournament_date,
        created_by=current_user.id,
    )
    db.add(tournament)
    await db.commit()
    await db.refresh(tournament)
    return serialize_tournament(tournament)


@app.get("/api/tournaments/{tournament_id}")
async def get_tournament(tournament_id: str, db: AsyncSession = Depends(get_db)):
    """Get tournament details including participant list with stats."""
    result = await db.execute(select(Tournament).filter(Tournament.id == tournament_id))
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


def _get_player_stats_safe(player_name: str) -> dict | None:
    """Fetch player aggregate stats using sync_engine. Returns None if unavailable."""
    from database import sync_engine
    try:
        with sync_engine.connect() as conn:
            from sqlalchemy import text as sa_text
            # Check if player_match_stats table exists
            if sync_engine.name == 'postgresql':
                check = conn.execute(sa_text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'player_match_stats')"
                )).scalar()
            else:
                check = conn.execute(sa_text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='player_match_stats'"
                )).fetchone()

            if not check:
                # No match stats table — try basic player data
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
                return None

            # Fetch aggregate stats
            # First get steamid
            sid_row = conn.execute(sa_text(
                "SELECT steamid FROM players WHERE name = :name"
            ), {"name": player_name}).fetchone()
            steamid = sid_row[0] if sid_row else None

            if steamid:
                where = "(pms.steamid = :sid OR pms.player_name = :name)"
                params = {"sid": steamid, "name": player_name}
            else:
                where = "pms.player_name = :name"
                params = {"name": player_name}

            is_pg = sync_engine.name == 'postgresql'
            # PostgreSQL needs ::numeric cast for ROUND on floats
            cast = "::numeric" if is_pg else ""
            query = sa_text(f"""
                SELECT
                    COUNT(*) as matches_played,
                    COALESCE(SUM(pms.kills), 0) as total_kills,
                    COALESCE(SUM(pms.deaths), 0) as total_deaths,
                    COALESCE(SUM(pms.assists), 0) as total_assists,
                    ROUND(AVG(NULLIF(pms.adr, 0)){cast}, 1) as avg_adr,
                    ROUND(AVG(NULLIF(pms.rating, 0)){cast}, 2) as avg_rating,
                    ROUND(AVG(NULLIF(pms.headshot_pct, 0)){cast}, 1) as avg_hs_pct,
                    ROUND((SUM(pms.kills) * 1.0 / NULLIF(SUM(pms.deaths), 0)){cast}, 2) as overall_kd,
                    COUNT(CASE WHEN pms.match_result = 'W' THEN 1 END) as wins,
                    COUNT(CASE WHEN pms.match_result = 'L' THEN 1 END) as losses
                FROM player_match_stats pms
                JOIN match_details md ON pms.match_id = md.match_id
                WHERE {where} AND pms.rating IS NOT NULL
            """)
            row = conn.execute(query, params).fetchone()
            if row and row[0] > 0:
                matches = row[0]
                wins = row[8]
                return {
                    "matches_played": matches,
                    "total_kills": row[1],
                    "total_deaths": row[2],
                    "total_assists": row[3],
                    "avg_adr": float(row[4]) if row[4] else None,
                    "avg_rating": float(row[5]) if row[5] else None,
                    "avg_hs_pct": float(row[6]) if row[6] else None,
                    "overall_kd": float(row[7]) if row[7] else None,
                    "wins": wins,
                    "losses": row[9],
                    "winrate_pct": round((wins / matches) * 100, 1) if matches > 0 else 0,
                }

            # Fallback to basic player data
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
        print(f"[WARN] Failed to fetch stats for {player_name}: {e}")
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
    if tournament.status != "open":
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

    # Check capacity
    result = await db.execute(
        select(TournamentParticipant).filter(
            TournamentParticipant.tournament_id == tournament_id
        )
    )
    current_count = len(result.scalars().all())
    if current_count >= tournament.max_players:
        raise HTTPException(400, "Tournament is full")

    # Enroll
    participant = TournamentParticipant(
        tournament_id=tournament_id,
        user_id=current_user.id,
    )
    db.add(participant)
    await db.flush()

    new_count = current_count + 1

    # AUTO-GENERATE BRACKET when capacity reached
    if new_count == tournament.max_players:
        await db.commit()  # commit the participant first
        tournament = await generate_single_elimination_bracket(tournament_id, db)
        return {
            "status": "bracket_generated",
            "message": f"Tournament is full! Bracket generated with {new_count} players.",
            "participant_count": new_count,
        }

    await db.commit()
    return {
        "status": "joined",
        "message": f"Enrolled successfully ({new_count}/{tournament.max_players})",
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
    if tournament.status != "open":
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
    """Get the full bracket tree for a tournament, enriched with player stats."""
    result = await db.execute(select(Tournament).filter(Tournament.id == tournament_id))
    tournament = result.scalars().first()
    if not tournament:
        raise HTTPException(404, "Tournament not found")
    if tournament.status == "open":
        raise HTTPException(400, "Bracket not yet generated (tournament still open)")

    bracket = build_bracket_response(tournament)

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

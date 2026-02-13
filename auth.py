# auth.py — JWT authentication & user account management (Async/SQLAlchemy)
import os
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.future import select
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from database import async_session
from models import User
from schemas import TokenData
from constants import PLAYERS_INIT

SECRET_KEY = os.getenv("JWT_SECRET", "cs2-pro-balancer-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 72

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)

ADMIN_PLAYERS = {"Skeez", "Kim", "magon"}

# ──────────────────────────────────────────────
# SECURITY UTILS
# ──────────────────────────────────────────────

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# ──────────────────────────────────────────────
# DEPENDENCIES
# ──────────────────────────────────────────────

async def get_db():
    async with async_session() as session:
        yield session

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username, role=payload.get("role"))
    except JWTError:
        raise credentials_exception
        
    result = await db.execute(select(User).filter(User.username == username))
    user = result.scalars().first()
    
    if user is None:
        raise credentials_exception
    return user

async def get_current_user_optional(token: str | None = Depends(oauth2_scheme_optional), db: AsyncSession = Depends(get_db)) -> User | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None
        
    result = await db.execute(select(User).filter(User.username == username))
    user = result.scalars().first()
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# ──────────────────────────────────────────────
# INIT / SEEDING
# ──────────────────────────────────────────────

async def init_user_accounts():
    """Seed existing players from constants if not present."""
    async with async_session() as db:
        result = await db.execute(select(func.count(User.id)))
        count = result.scalar()
        
        if count == 0:
            print("[AUTH] Seeding player accounts...")
            default_hash = hash_password("password123")
            
            for name in PLAYERS_INIT:
                role = "admin" if name in ADMIN_PLAYERS else "player"
                # Check exist
                res = await db.execute(select(User).filter(User.username == name.lower()))
                if not res.scalars().first():
                    new_user = User(
                        username=name.lower(),
                        hashed_password=default_hash,
                        role=role,
                        display_name=name,
                        email=None
                    )
                    db.add(new_user)
            
            await db.commit()
            print(f"[AUTH] Seeded players.")

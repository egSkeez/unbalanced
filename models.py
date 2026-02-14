from sqlalchemy import Boolean, Column, String, DateTime, Integer, ForeignKey, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid
import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True) # Optional for now as legacy users might not have it
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="player") # "admin", "player"
    display_name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_login = Column(DateTime, nullable=True)


# ──────────────────────────────────────────────
# TOURNAMENT SYSTEM
# ──────────────────────────────────────────────

class Tournament(Base):
    __tablename__ = "tournaments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    prize_image_url = Column(String, nullable=True)
    prize_name = Column(String, nullable=True)
    max_players = Column(Integer, nullable=False, default=8)  # 8, 16, or 32
    status = Column(String, default="open")  # open, active, completed
    tournament_date = Column(String, nullable=True)  # e.g. "2026-03-15" — the scheduled date
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    winner_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    participants = relationship("TournamentParticipant", back_populates="tournament", lazy="selectin")
    matches = relationship("TournamentMatch", back_populates="tournament", lazy="selectin")


class TournamentParticipant(Base):
    __tablename__ = "tournament_participants"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tournament_id = Column(String, ForeignKey("tournaments.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    seed = Column(Integer, nullable=True)  # assigned after bracket generation
    joined_at = Column(DateTime, default=datetime.datetime.utcnow)

    tournament = relationship("Tournament", back_populates="participants")
    user = relationship("User", lazy="selectin")


class TournamentMatch(Base):
    __tablename__ = "tournament_matches"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tournament_id = Column(String, ForeignKey("tournaments.id"), nullable=False, index=True)
    round_number = Column(Integer, nullable=False)  # 1 = first round, 2 = quarters, etc.
    match_index = Column(Integer, nullable=False)  # position within the round (0-based)
    player1_id = Column(String, ForeignKey("users.id"), nullable=True)  # null = TBD (waiting for feeder match)
    player2_id = Column(String, ForeignKey("users.id"), nullable=True)
    winner_id = Column(String, ForeignKey("users.id"), nullable=True)
    cybershoke_lobby_url = Column(String, nullable=True)
    cybershoke_match_id = Column(String, nullable=True)
    next_match_id = Column(String, ForeignKey("tournament_matches.id"), nullable=True)  # self-ref for bracket tree

    tournament = relationship("Tournament", back_populates="matches")
    player1 = relationship("User", foreign_keys=[player1_id], lazy="selectin")
    player2 = relationship("User", foreign_keys=[player2_id], lazy="selectin")
    winner = relationship("User", foreign_keys=[winner_id], lazy="selectin")
    next_match = relationship("TournamentMatch", remote_side=[id], lazy="selectin")

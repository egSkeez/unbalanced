# tournament_logic.py — Single-elimination bracket generation & management
import random
import math
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from models import Tournament, TournamentParticipant, TournamentMatch, User


async def generate_single_elimination_bracket(tournament_id: str, db: AsyncSession):
    """
    Generates a full single-elimination bracket for a tournament.

    1. Fetches and shuffles participants
    2. Creates Round 1 matches with assigned players
    3. Creates empty placeholder matches for subsequent rounds
    4. Links all matches via next_match_id for tree traversal

    Supports 4, 8, 16, or 32 players (must be power of 2).
    """
    # Fetch tournament
    result = await db.execute(select(Tournament).filter(Tournament.id == tournament_id))
    tournament = result.scalars().first()
    if not tournament:
        raise ValueError("Tournament not found")
    if tournament.status != "open":
        raise ValueError("Tournament is not in 'open' status")

    # Fetch participants
    result = await db.execute(
        select(TournamentParticipant)
        .filter(TournamentParticipant.tournament_id == tournament_id)
    )
    participants = list(result.scalars().all())

    num_players = len(participants)
    if num_players != tournament.max_players:
        raise ValueError(f"Expected {tournament.max_players} players, got {num_players}")
    if num_players < 2 or (num_players & (num_players - 1)) != 0:
        raise ValueError(f"Player count must be a power of 2, got {num_players}")

    # Shuffle for random seeding
    random.shuffle(participants)
    for i, p in enumerate(participants):
        p.seed = i + 1

    total_rounds = int(math.log2(num_players))

    # Build all matches bottom-up: create later rounds first so we can link them.
    # Structure: rounds[round_num] = list of TournamentMatch objects
    # Round 1 has num_players/2 matches, Round 2 has num_players/4, ..., Final has 1.

    all_matches = {}  # (round_number, match_index) -> TournamentMatch

    # Create matches from the final round backward so we have IDs for next_match_id
    for round_num in range(total_rounds, 0, -1):
        matches_in_round = num_players // (2 ** round_num)
        for match_idx in range(matches_in_round):
            match_id = str(uuid.uuid4())

            # Link to next round match
            next_match_id = None
            if round_num < total_rounds:
                # This match feeds into the next round
                next_round_match_idx = match_idx // 2
                next_key = (round_num + 1, next_round_match_idx)
                if next_key in all_matches:
                    next_match_id = all_matches[next_key].id

            match = TournamentMatch(
                id=match_id,
                tournament_id=tournament_id,
                round_number=round_num,
                match_index=match_idx,
                next_match_id=next_match_id,
            )

            # Only Round 1 gets actual players
            if round_num == 1:
                p1_idx = match_idx * 2
                p2_idx = match_idx * 2 + 1
                match.player1_id = participants[p1_idx].user_id
                match.player2_id = participants[p2_idx].user_id

            all_matches[(round_num, match_idx)] = match
            db.add(match)

    # Lock tournament
    tournament.status = "active"
    await db.commit()

    return tournament


async def advance_winner(match_id: str, winner_id: str, db: AsyncSession):
    """
    Sets the winner of a match and propagates them to the next match in the bracket.
    If the next match (finals) gets its winner set, marks the tournament as completed.
    """
    result = await db.execute(select(TournamentMatch).filter(TournamentMatch.id == match_id))
    match = result.scalars().first()
    if not match:
        raise ValueError("Match not found")
    if match.winner_id:
        raise ValueError("Winner already set for this match")
    if winner_id not in (match.player1_id, match.player2_id):
        raise ValueError("Winner must be one of the two players in this match")

    match.winner_id = winner_id

    # Propagate to next match
    if match.next_match_id:
        result = await db.execute(
            select(TournamentMatch).filter(TournamentMatch.id == match.next_match_id)
        )
        next_match = result.scalars().first()
        if next_match:
            # Determine which slot (player1 or player2) to fill
            # Even match_index -> player1 slot, Odd match_index -> player2 slot
            if match.match_index % 2 == 0:
                next_match.player1_id = winner_id
            else:
                next_match.player2_id = winner_id
    else:
        # This is the final match — mark tournament as completed
        result = await db.execute(
            select(Tournament).filter(Tournament.id == match.tournament_id)
        )
        tournament = result.scalars().first()
        if tournament:
            tournament.status = "completed"
            tournament.winner_id = winner_id

    await db.commit()
    return match


def get_round_name(round_number: int, total_rounds: int) -> str:
    """Returns a human-readable name for the round."""
    rounds_from_final = total_rounds - round_number
    if rounds_from_final == 0:
        return "Finals"
    elif rounds_from_final == 1:
        return "Semi-Finals"
    elif rounds_from_final == 2:
        return "Quarter-Finals"
    else:
        return f"Round {round_number}"


def build_bracket_response(tournament: Tournament) -> dict:
    """
    Builds a structured bracket response from a tournament and its matches.
    Returns a dict suitable for the frontend bracket component.
    """
    if not tournament.matches:
        return {
            "tournament": serialize_tournament(tournament),
            "rounds": [],
            "total_rounds": 0,
        }

    total_rounds = max(m.round_number for m in tournament.matches)

    rounds = []
    for round_num in range(1, total_rounds + 1):
        round_matches = sorted(
            [m for m in tournament.matches if m.round_number == round_num],
            key=lambda m: m.match_index
        )
        rounds.append({
            "round_number": round_num,
            "name": get_round_name(round_num, total_rounds),
            "matches": [serialize_match(m) for m in round_matches],
        })

    return {
        "tournament": serialize_tournament(tournament),
        "rounds": rounds,
        "total_rounds": total_rounds,
    }


def serialize_tournament(t: Tournament) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "prize_image_url": t.prize_image_url,
        "prize_name": t.prize_name,
        "max_players": t.max_players,
        "status": t.status,
        "tournament_date": t.tournament_date,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "participant_count": len(t.participants) if t.participants else 0,
        "winner": serialize_user(t.winner_id, t) if t.winner_id else None,
    }


def serialize_user(user_id: str, tournament: Tournament) -> dict | None:
    """Look up a user from tournament participants or match relationships."""
    if not user_id:
        return None
    # Try to find from participants
    for p in (tournament.participants or []):
        if p.user and p.user.id == user_id:
            return {"id": p.user.id, "username": p.user.username, "display_name": p.user.display_name}
    return {"id": user_id, "username": "Unknown", "display_name": "Unknown"}


def serialize_match(m: TournamentMatch) -> dict:
    return {
        "id": m.id,
        "round_number": m.round_number,
        "match_index": m.match_index,
        "player1": {"id": m.player1.id, "username": m.player1.username, "display_name": m.player1.display_name} if m.player1 else None,
        "player2": {"id": m.player2.id, "username": m.player2.username, "display_name": m.player2.display_name} if m.player2 else None,
        "winner": {"id": m.winner.id, "username": m.winner.username, "display_name": m.winner.display_name} if m.winner else None,
        "cybershoke_lobby_url": m.cybershoke_lobby_url,
        "cybershoke_match_id": m.cybershoke_match_id,
        "next_match_id": m.next_match_id,
    }

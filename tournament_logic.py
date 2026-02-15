# tournament_logic.py — Tournament engine with Strategy Pattern
# Supports: Single Elimination (with byes), Round Robin
import random
import math
import uuid
from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import (
    Tournament, TournamentParticipant, TournamentMatch, User,
    TournamentFormat, TournamentStatus,
)


# ══════════════════════════════════════════════════════════════
# STRATEGY PATTERN — Abstract Base + Concrete Implementations
# ══════════════════════════════════════════════════════════════

class TournamentGenerator(ABC):
    """Abstract base for all tournament format generators."""

    @abstractmethod
    async def generate_bracket(
        self,
        tournament: Tournament,
        participants: list[TournamentParticipant],
        db: AsyncSession,
    ) -> Tournament:
        """Generate all matches for the tournament. Returns the updated tournament."""
        ...

    @abstractmethod
    def build_response(self, tournament: Tournament) -> dict:
        """Build the API response payload for this format."""
        ...


class SingleEliminationGenerator(TournamentGenerator):
    """
    Single-elimination bracket generator with BYE support.

    If player count is not a power of 2 (e.g. 14 players):
    - Rounds up to the next power of 2 (16)
    - Top-seeded players receive byes (auto-advance to Round 2)
    - Bye matches are created with only 1 player and auto-resolved
    """

    async def generate_bracket(
        self,
        tournament: Tournament,
        participants: list[TournamentParticipant],
        db: AsyncSession,
    ) -> Tournament:
        num_players = len(participants)
        if num_players < 2:
            raise ValueError("Need at least 2 participants")

        # Shuffle and assign seeds
        random.shuffle(participants)
        for i, p in enumerate(participants):
            p.seed = i + 1

        # Calculate bracket size (next power of 2)
        bracket_size = 1
        while bracket_size < num_players:
            bracket_size *= 2

        total_rounds = int(math.log2(bracket_size))
        num_byes = bracket_size - num_players

        # Standard bracket seeding: place byes so top seeds get them
        # Slot mapping: bracket_size slots, first `num_players` get real players,
        # remaining slots are BYEs
        slots: list[str | None] = []
        for i in range(bracket_size):
            if i < num_players:
                slots.append(participants[i].user_id)
            else:
                slots.append(None)  # BYE

        # Build matches from final round backward for next_match_id linking
        all_matches: dict[tuple[int, int], TournamentMatch] = {}

        for round_num in range(total_rounds, 0, -1):
            matches_in_round = bracket_size // (2 ** round_num)
            for match_idx in range(matches_in_round):
                match_id = str(uuid.uuid4())

                # Link to next round
                next_match_id = None
                if round_num < total_rounds:
                    next_key = (round_num + 1, match_idx // 2)
                    if next_key in all_matches:
                        next_match_id = all_matches[next_key].id

                match = TournamentMatch(
                    id=match_id,
                    tournament_id=tournament.id,
                    round_number=round_num,
                    match_index=match_idx,
                    next_match_id=next_match_id,
                )

                # Round 1: assign players and handle byes
                if round_num == 1:
                    p1_idx = match_idx * 2
                    p2_idx = match_idx * 2 + 1
                    p1_id = slots[p1_idx] if p1_idx < len(slots) else None
                    p2_id = slots[p2_idx] if p2_idx < len(slots) else None

                    match.player1_id = p1_id
                    match.player2_id = p2_id

                    # Auto-resolve BYE: if one player is missing, the other wins
                    if p1_id and not p2_id:
                        match.winner_id = p1_id
                    elif p2_id and not p1_id:
                        match.winner_id = p2_id

                all_matches[(round_num, match_idx)] = match
                db.add(match)

        # Propagate BYE winners to Round 2
        for (rn, mi), match in all_matches.items():
            if rn == 1 and match.winner_id and match.next_match_id:
                next_key = (2, mi // 2)
                next_match = all_matches.get(next_key)
                if next_match:
                    if mi % 2 == 0:
                        next_match.player1_id = match.winner_id
                    else:
                        next_match.player2_id = match.winner_id

        tournament.status = TournamentStatus.active.value
        await db.commit()
        return tournament

    def build_response(self, tournament: Tournament) -> dict:
        return build_bracket_response(tournament)


class RoundRobinGenerator(TournamentGenerator):
    """
    Round Robin generator — every player plays every other player once.

    Uses the "circle method" for scheduling:
    - N players require N-1 rounds (N rounds if N is odd, with a BYE each round)
    - Each round has N/2 matches
    - group_id=0 for a single-group round robin
    """

    async def generate_bracket(
        self,
        tournament: Tournament,
        participants: list[TournamentParticipant],
        db: AsyncSession,
    ) -> Tournament:
        num_players = len(participants)
        if num_players < 2:
            raise ValueError("Need at least 2 participants")

        random.shuffle(participants)
        for i, p in enumerate(participants):
            p.seed = i + 1

        player_ids = [p.user_id for p in participants]

        # Circle method: if odd number, add a phantom BYE player
        ids = list(player_ids)
        if len(ids) % 2 == 1:
            ids.append(None)  # BYE placeholder

        n = len(ids)
        num_rounds = n - 1
        match_index = 0

        for round_num in range(1, num_rounds + 1):
            for i in range(n // 2):
                p1 = ids[i]
                p2 = ids[n - 1 - i]

                # Skip matches involving the BYE placeholder
                if p1 is None or p2 is None:
                    continue

                match = TournamentMatch(
                    id=str(uuid.uuid4()),
                    tournament_id=tournament.id,
                    round_number=round_num,
                    match_index=match_index,
                    group_id=0,
                    player1_id=p1,
                    player2_id=p2,
                )
                db.add(match)
                match_index += 1

            # Rotate: fix first element, rotate the rest
            ids = [ids[0]] + [ids[-1]] + ids[1:-1]

        tournament.status = TournamentStatus.active.value
        await db.commit()
        return tournament

    def build_response(self, tournament: Tournament) -> dict:
        return build_round_robin_response(tournament)


# ══════════════════════════════════════════════════════════════
# FACTORY — Returns the correct generator for a tournament
# ══════════════════════════════════════════════════════════════

def get_generator(tournament: Tournament) -> TournamentGenerator:
    """Factory: return the correct generator based on tournament format."""
    fmt = tournament.format
    if fmt == TournamentFormat.single_elimination.value:
        return SingleEliminationGenerator()
    elif fmt == TournamentFormat.round_robin.value:
        return RoundRobinGenerator()
    else:
        raise ValueError(f"Unknown tournament format: {fmt}")


# ══════════════════════════════════════════════════════════════
# PUBLIC API — Called from endpoints
# ══════════════════════════════════════════════════════════════

async def start_tournament(tournament_id: str, db: AsyncSession) -> Tournament:
    """
    Start a tournament: lock the roster and generate all matches.
    Works for any format via the Strategy Pattern.
    """
    result = await db.execute(select(Tournament).filter(Tournament.id == tournament_id))
    tournament = result.scalars().first()
    if not tournament:
        raise ValueError("Tournament not found")
    if tournament.status not in (TournamentStatus.registration.value, "open"):
        raise ValueError(f"Tournament is not in 'registration' status (current: {tournament.status})")

    result = await db.execute(
        select(TournamentParticipant)
        .filter(TournamentParticipant.tournament_id == tournament_id)
    )
    participants = list(result.scalars().all())
    if len(participants) < 2:
        raise ValueError("Need at least 2 participants to start")

    generator = get_generator(tournament)
    return await generator.generate_bracket(tournament, participants, db)


# Legacy alias for backward compatibility with existing auto-start-on-full logic
async def generate_single_elimination_bracket(tournament_id: str, db: AsyncSession):
    """Legacy wrapper — calls start_tournament internally."""
    return await start_tournament(tournament_id, db)


async def report_match(match_id: str, winner_id: str, score: str | None, db: AsyncSession):
    """
    Report the result of a match. For Single Elimination, auto-advances the winner.
    For Round Robin, records the result and optionally generates a playoff bracket.
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
    if score:
        match.score = score

    tournament_id = match.tournament_id

    # Flush the winner change to DB before re-fetching tournament relationships.
    # This prevents selectinload from returning stale data that overwrites our change.
    await db.flush()

    # Fetch tournament to determine format
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Tournament)
        .options(selectinload(Tournament.matches), selectinload(Tournament.participants))
        .filter(Tournament.id == tournament_id)
    )
    tournament = result.scalars().first()

    if tournament and tournament.format == TournamentFormat.single_elimination.value:
        # Propagate winner to next match in bracket tree
        if match.next_match_id:
            result = await db.execute(
                select(TournamentMatch).filter(TournamentMatch.id == match.next_match_id)
            )
            next_match = result.scalars().first()
            if next_match:
                if match.match_index % 2 == 0:
                    next_match.player1_id = winner_id
                else:
                    next_match.player2_id = winner_id
        else:
            # Final match — tournament complete
            if tournament:
                tournament.status = TournamentStatus.completed.value
                tournament.winner_id = winner_id

    elif tournament and tournament.format == TournamentFormat.round_robin.value:
        is_playoff_match = match.group_id == 1  # playoff matches use group_id=1

        if is_playoff_match:
            # Handle playoff bracket just like single elimination
            if match.next_match_id:
                result = await db.execute(
                    select(TournamentMatch).filter(TournamentMatch.id == match.next_match_id)
                )
                next_match = result.scalars().first()
                if next_match:
                    if match.match_index % 2 == 0:
                        next_match.player1_id = winner_id
                    else:
                        next_match.player2_id = winner_id
            else:
                # Playoff final — tournament complete
                tournament.status = TournamentStatus.completed.value
                tournament.winner_id = winner_id
        else:
            # Group stage match — check if all group matches are complete.
            # Use the freshly loaded tournament.matches (which includes our flushed winner).
            group_matches = [m for m in tournament.matches if m.group_id == 0 or m.group_id is None]
            all_done = all(m.winner_id is not None for m in group_matches)
            if all_done:
                has_playoffs = tournament.playoffs if hasattr(tournament, 'playoffs') else False
                if has_playoffs:
                    # Generate playoff bracket for top 4
                    await _generate_playoff_bracket(tournament, group_matches, None, None, db)
                    tournament.status = TournamentStatus.playoffs.value
                else:
                    # Determine winner by most wins
                    wins: dict[str, int] = {}
                    for m in group_matches:
                        if m.winner_id:
                            wins[m.winner_id] = wins.get(m.winner_id, 0) + 1
                    if wins:
                        tournament.winner_id = max(wins, key=wins.get)
                        tournament.status = TournamentStatus.completed.value

    await db.commit()
    return match


async def _generate_playoff_bracket(
    tournament: Tournament,
    group_matches: list,
    current_match_id: str | None,
    current_winner_id: str | None,
    db: AsyncSession,
):
    """Generate a 4-player single elimination playoff bracket from top 4 in RR standings."""
    # Calculate standings - initialize with all participants to handle players with 0 wins
    standings: dict[str, int] = {p.user_id: 0 for p in (tournament.participants or [])}
    for m in group_matches:
        # All winners are already flushed to the match objects
        w = m.winner_id
        if w and w in standings:
            standings[w] = standings.get(w, 0) + 1

    # Sort by wins descending. Use seed as tie-breaker if available.
    participant_seeds = {p.user_id: p.seed or 999 for p in (tournament.participants or [])}
    sorted_players = sorted(
        standings.keys(),
        key=lambda pid: (standings[pid], -participant_seeds.get(pid, 999)),
        reverse=True
    )
    top4 = sorted_players[:4]

    if len(top4) < 4:
        # Not enough players for playoffs — determine winner by most wins and complete
        if standings:
            tournament.winner_id = max(standings, key=standings.get)
            tournament.status = TournamentStatus.completed.value
        return

    # Build a 4-player SE bracket:
    #   Semi 1: #1 vs #4 (match_index=0)
    #   Semi 2: #2 vs #3 (match_index=1)
    #   Final:            (match_index=0, round 2)

    # Create final match first
    final_id = str(uuid.uuid4())
    final_match = TournamentMatch(
        id=final_id,
        tournament_id=tournament.id,
        round_number=100,  # high number to separate from group rounds
        match_index=0,
        group_id=1,  # marks as playoff match
    )
    db.add(final_match)

    # Semi 1: #1 seed vs #4 seed
    semi1 = TournamentMatch(
        id=str(uuid.uuid4()),
        tournament_id=tournament.id,
        round_number=99,
        match_index=0,
        group_id=1,
        player1_id=top4[0],
        player2_id=top4[3],
        next_match_id=final_id,
    )
    db.add(semi1)

    # Semi 2: #2 seed vs #3 seed
    semi2 = TournamentMatch(
        id=str(uuid.uuid4()),
        tournament_id=tournament.id,
        round_number=99,
        match_index=1,
        group_id=1,
        player1_id=top4[1],
        player2_id=top4[2],
        next_match_id=final_id,
    )
    db.add(semi2)


# Legacy alias
async def advance_winner(match_id: str, winner_id: str, db: AsyncSession):
    """Legacy wrapper for backward compatibility."""
    return await report_match(match_id, winner_id, None, db)


# ══════════════════════════════════════════════════════════════
# SERIALIZATION HELPERS
# ══════════════════════════════════════════════════════════════

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
    """Build a structured bracket response for Single Elimination."""
    if not tournament.matches:
        return {
            "tournament": serialize_tournament(tournament),
            "format": "single_elimination",
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
        "format": "single_elimination",
        "rounds": rounds,
        "total_rounds": total_rounds,
    }


def build_round_robin_response(tournament: Tournament) -> dict:
    """Build a structured response for Round Robin with standings table and optional playoffs."""
    all_matches = tournament.matches or []
    participants = tournament.participants or []

    # Separate group stage from playoff matches
    group_matches = [m for m in all_matches if m.group_id == 0 or m.group_id is None]
    playoff_matches = [m for m in all_matches if m.group_id == 1]

    # Build standings from GROUP STAGE match results only
    standings: dict[str, dict] = {}
    for p in participants:
        uid = p.user_id
        standings[uid] = {
            "user_id": uid,
            "username": p.user.username if p.user else "Unknown",
            "display_name": p.user.display_name if p.user else "Unknown",
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "points": 0,
            "matches_played": 0,
        }

    for m in group_matches:
        if m.winner_id:
            loser_id = m.player2_id if m.winner_id == m.player1_id else m.player1_id
            if m.winner_id in standings:
                standings[m.winner_id]["wins"] += 1
                standings[m.winner_id]["points"] += 3
                standings[m.winner_id]["matches_played"] += 1
            if loser_id and loser_id in standings:
                standings[loser_id]["losses"] += 1
                standings[loser_id]["matches_played"] += 1

    # Sort by points desc, then wins desc
    sorted_standings = sorted(
        standings.values(),
        key=lambda s: (s["points"], s["wins"]),
        reverse=True,
    )

    # Group stage matches by round
    rounds_map: dict[int, list] = {}
    for m in group_matches:
        rounds_map.setdefault(m.round_number, []).append(serialize_match(m))

    rounds = [
        {"round_number": rn, "name": f"Round {rn}", "matches": ms}
        for rn, ms in sorted(rounds_map.items())
    ]

    response = {
        "tournament": serialize_tournament(tournament),
        "format": "round_robin",
        "rounds": rounds,
        "total_rounds": len(rounds),
        "standings": sorted_standings,
    }

    # Include playoff bracket if present
    if playoff_matches:
        playoff_rounds_map: dict[int, list] = {}
        for m in playoff_matches:
            playoff_rounds_map.setdefault(m.round_number, []).append(serialize_match(m))

        playoff_round_names = {99: "Semifinals", 100: "Final"}
        playoff_rounds = [
            {
                "round_number": rn,
                "name": playoff_round_names.get(rn, f"Playoff Round {rn}"),
                "matches": ms,
            }
            for rn, ms in sorted(playoff_rounds_map.items())
        ]
        response["playoff_rounds"] = playoff_rounds

    return response


def serialize_tournament(t: Tournament) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "rules": t.rules,
        "format": t.format,
        "prize_image_url": t.prize_image_url,
        "prize_name": t.prize_name,
        "prize_pool": t.prize_pool,
        "max_players": t.max_players,
        "playoffs": t.playoffs if hasattr(t, 'playoffs') else False,
        "status": t.status,
        "tournament_date": t.tournament_date,
        "created_by": t.created_by,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "participant_count": len(t.participants) if t.participants else 0,
        "winner": serialize_user(t.winner_id, t) if t.winner_id else None,
    }


def serialize_user(user_id: str, tournament: Tournament) -> dict | None:
    """Look up a user from tournament participants or match relationships."""
    if not user_id:
        return None
    for p in (tournament.participants or []):
        if p.user and p.user.id == user_id:
            return {"id": p.user.id, "username": p.user.username, "display_name": p.user.display_name}
    return {"id": user_id, "username": "Unknown", "display_name": "Unknown"}


def serialize_match(m: TournamentMatch) -> dict:
    return {
        "id": m.id,
        "round_number": m.round_number,
        "match_index": m.match_index,
        "group_id": m.group_id,
        "score": m.score,
        "player1": {"id": m.player1.id, "username": m.player1.username, "display_name": m.player1.display_name} if m.player1 else None,
        "player2": {"id": m.player2.id, "username": m.player2.username, "display_name": m.player2.display_name} if m.player2 else None,
        "winner": {"id": m.winner.id, "username": m.winner.username, "display_name": m.winner.display_name} if m.winner else None,
        "cybershoke_lobby_url": m.cybershoke_lobby_url,
        "cybershoke_match_id": m.cybershoke_match_id,
        "next_match_id": m.next_match_id,
    }

'use client';
import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';
import {
    getTournament, getTournamentBracket, joinTournament, leaveTournament,
    createTournamentLobby, advanceWinner,
} from '@/app/lib/api';

interface PlayerInfo {
    id: string;
    username: string;
    display_name: string;
}

interface MatchData {
    id: string;
    round_number: number;
    match_index: number;
    player1: PlayerInfo | null;
    player2: PlayerInfo | null;
    winner: PlayerInfo | null;
    cybershoke_lobby_url: string | null;
    cybershoke_match_id: string | null;
    next_match_id: string | null;
}

interface RoundData {
    round_number: number;
    name: string;
    matches: MatchData[];
}

interface BracketData {
    tournament: TournamentInfo;
    rounds: RoundData[];
    total_rounds: number;
}

interface TournamentInfo {
    id: string;
    name: string;
    prize_image_url: string | null;
    prize_name: string | null;
    max_players: number;
    status: string;
    tournament_date: string | null;
    created_at: string;
    participant_count: number;
    winner: PlayerInfo | null;
}

interface ParticipantData {
    id: string;
    user_id: string;
    username: string;
    display_name: string;
    seed: number | null;
}

export default function TournamentDetailPage() {
    const params = useParams();
    const tournamentId = params.id as string;
    const { user, token } = useAuth();

    const [tournament, setTournament] = useState<TournamentInfo | null>(null);
    const [participants, setParticipants] = useState<ParticipantData[]>([]);
    const [bracket, setBracket] = useState<BracketData | null>(null);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState<string | null>(null);
    const [error, setError] = useState('');

    const isAdmin = user?.role === 'admin';

    const loadData = useCallback(async () => {
        try {
            const tData = await getTournament(tournamentId);
            setTournament(tData);
            setParticipants(tData.participants || []);

            if (tData.status === 'active' || tData.status === 'completed') {
                const bData = await getTournamentBracket(tournamentId);
                setBracket(bData);
            }
        } catch (e) {
            console.error('Failed to load tournament', e);
        } finally {
            setLoading(false);
        }
    }, [tournamentId]);

    useEffect(() => { loadData(); }, [loadData]);

    const handleJoin = async () => {
        if (!token) return;
        setError('');
        try {
            await joinTournament(tournamentId, token);
            await loadData();
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to join');
        }
    };

    const handleLeave = async () => {
        if (!token) return;
        setError('');
        try {
            await leaveTournament(tournamentId, token);
            await loadData();
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to leave');
        }
    };

    const handleCreateLobby = async (matchId: string) => {
        if (!token) return;
        setActionLoading(matchId);
        setError('');
        try {
            await createTournamentLobby(matchId, user?.display_name || 'Skeez', token);
            await loadData();
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to create lobby');
        } finally {
            setActionLoading(null);
        }
    };

    const handleAdvanceWinner = async (matchId: string, winnerId: string) => {
        if (!token) return;
        setActionLoading(matchId);
        setError('');
        try {
            await advanceWinner(matchId, winnerId, token);
            await loadData();
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to advance winner');
        } finally {
            setActionLoading(null);
        }
    };

    if (loading) {
        return (
            <div className="page-container">
                <div className="loading-spinner"><div className="spinner" /></div>
            </div>
        );
    }

    if (!tournament) {
        return (
            <div className="page-container">
                <div className="card" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                    Tournament not found
                </div>
            </div>
        );
    }

    const statusColors: Record<string, string> = {
        open: 'var(--neon-green)',
        active: 'var(--orange)',
        completed: 'var(--text-muted)',
    };

    return (
        <div className="page-container" style={{ maxWidth: 1400 }}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <Link href="/tournaments" style={{ color: 'var(--text-secondary)', textDecoration: 'none', fontSize: 14 }}>
                    Tournaments
                </Link>
                <span style={{ color: 'var(--text-muted)' }}>/</span>
            </div>

            <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <h1 className="page-title">{tournament.name}</h1>
                        <span style={{
                            fontSize: 12, fontWeight: 700, textTransform: 'uppercase',
                            padding: '3px 10px', borderRadius: 4,
                            background: `${statusColors[tournament.status]}22`,
                            color: statusColors[tournament.status],
                            border: `1px solid ${statusColors[tournament.status]}44`,
                        }}>
                            {tournament.status}
                        </span>
                    </div>
                    <p className="page-subtitle">
                        {tournament.max_players}-player single elimination
                        {tournament.prize_name && <span style={{ color: 'var(--gold)', marginLeft: 8 }}>Prize: {tournament.prize_name}</span>}
                        {tournament.tournament_date && (
                            <span style={{ marginLeft: 12, color: 'var(--text-muted)' }}>
                                {new Date(tournament.tournament_date + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })}
                            </span>
                        )}
                    </p>
                </div>
                {/* Prize display with actual skin image */}
                {tournament.prize_image_url && (
                    <div style={{
                        width: 120, height: 90, borderRadius: 12,
                        background: '#111',
                        border: '2px solid rgba(255,215,0,0.3)',
                        flexShrink: 0,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        overflow: 'hidden',
                    }}>
                        <img
                            src={tournament.prize_image_url}
                            alt={tournament.prize_name || 'Prize'}
                            style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain', padding: 6 }}
                        />
                    </div>
                )}
            </div>

            {error && (
                <div style={{ padding: '12px 16px', background: 'rgba(255,51,51,0.15)', border: '1px solid rgba(255,51,51,0.3)', borderRadius: 8, marginBottom: 16, color: 'var(--red)' }}>
                    {error}
                </div>
            )}

            {/* Winner Banner */}
            {tournament.status === 'completed' && tournament.winner && (
                <div style={{
                    padding: '20px 24px', marginBottom: 24, borderRadius: 12,
                    background: 'linear-gradient(135deg, rgba(255,215,0,0.15), rgba(255,140,0,0.1))',
                    border: '1px solid rgba(255,215,0,0.3)',
                    textAlign: 'center',
                }}>
                    <div style={{ fontSize: 32, marginBottom: 4 }}>🏆</div>
                    <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--gold)' }}>
                        {tournament.winner.display_name} wins!
                    </div>
                </div>
            )}

            {/* Open: Enrollment UI */}
            {tournament.status === 'open' && (
                <div className="card" style={{ marginBottom: 24 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                        <h3 style={{ fontWeight: 700, margin: 0 }}>
                            Enrollment ({tournament.participant_count}/{tournament.max_players})
                        </h3>
                        {user && (
                            <div style={{ display: 'flex', gap: 8 }}>
                                <button className="btn btn-primary btn-sm" onClick={handleJoin}>
                                    Join Tournament
                                </button>
                                <button className="btn btn-sm" onClick={handleLeave} style={{ color: 'var(--red)' }}>
                                    Leave
                                </button>
                            </div>
                        )}
                    </div>
                    {/* Progress */}
                    <div style={{ background: '#222', borderRadius: 6, height: 8, overflow: 'hidden', marginBottom: 16 }}>
                        <div style={{
                            width: `${(tournament.participant_count / tournament.max_players) * 100}%`,
                            height: '100%',
                            background: 'var(--neon-green)',
                            borderRadius: 6,
                            transition: 'width 0.3s',
                        }} />
                    </div>
                    {/* Participant list */}
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                        {participants.map(p => (
                            <div key={p.id} className="player-chip" style={{ padding: '6px 14px', borderRadius: 20, fontSize: 13 }}>
                                {p.display_name}
                            </div>
                        ))}
                        {Array.from({ length: tournament.max_players - tournament.participant_count }).map((_, i) => (
                            <div key={`empty-${i}`} style={{
                                padding: '6px 14px', borderRadius: 20, fontSize: 13,
                                border: '1px dashed var(--border)', color: 'var(--text-muted)',
                            }}>
                                Open Slot
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Bracket View */}
            {bracket && bracket.rounds.length > 0 && (
                <BracketView
                    bracket={bracket}
                    isAdmin={isAdmin}
                    actionLoading={actionLoading}
                    onCreateLobby={handleCreateLobby}
                    onAdvanceWinner={handleAdvanceWinner}
                />
            )}
        </div>
    );
}


// ──────────────────────────────────────────────
// BRACKET VIEW COMPONENT
// ──────────────────────────────────────────────

function BracketView({
    bracket,
    isAdmin,
    actionLoading,
    onCreateLobby,
    onAdvanceWinner,
}: {
    bracket: BracketData;
    isAdmin: boolean;
    actionLoading: string | null;
    onCreateLobby: (matchId: string) => void;
    onAdvanceWinner: (matchId: string, winnerId: string) => void;
}) {
    const totalRounds = bracket.total_rounds;

    return (
        <div>
            <h2 style={{ fontWeight: 700, marginBottom: 16, fontSize: 20 }}>Bracket</h2>
            <div style={{
                display: 'flex',
                gap: 0,
                overflowX: 'auto',
                paddingBottom: 16,
            }}>
                {bracket.rounds.map((round) => (
                    <BracketRound
                        key={round.round_number}
                        round={round}
                        totalRounds={totalRounds}
                        isAdmin={isAdmin}
                        actionLoading={actionLoading}
                        onCreateLobby={onCreateLobby}
                        onAdvanceWinner={onAdvanceWinner}
                    />
                ))}
            </div>
        </div>
    );
}

function BracketRound({
    round,
    totalRounds,
    isAdmin,
    actionLoading,
    onCreateLobby,
    onAdvanceWinner,
}: {
    round: RoundData;
    totalRounds: number;
    isAdmin: boolean;
    actionLoading: string | null;
    onCreateLobby: (matchId: string) => void;
    onAdvanceWinner: (matchId: string, winnerId: string) => void;
}) {
    // Calculate spacing: each subsequent round needs more vertical space to center-align
    // with the previous round's match pairs
    const matchHeight = 140; // approximate height of a match card + margin
    const roundSpacing = Math.pow(2, round.round_number - 1);
    const topPadding = (roundSpacing - 1) * (matchHeight / 2);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', minWidth: 260 }}>
            {/* Round Header */}
            <div style={{
                textAlign: 'center', padding: '8px 16px', marginBottom: 12,
                fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)',
                textTransform: 'uppercase', letterSpacing: '0.05em',
            }}>
                {round.name}
            </div>

            {/* Matches */}
            <div style={{
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-around',
                flex: 1,
                paddingTop: topPadding,
                gap: (roundSpacing - 1) * matchHeight,
            }}>
                {round.matches.map((match) => (
                    <MatchCard
                        key={match.id}
                        match={match}
                        isAdmin={isAdmin}
                        actionLoading={actionLoading}
                        onCreateLobby={onCreateLobby}
                        onAdvanceWinner={onAdvanceWinner}
                        isFinal={round.round_number === totalRounds}
                    />
                ))}
            </div>
        </div>
    );
}


function MatchCard({
    match,
    isAdmin,
    actionLoading,
    onCreateLobby,
    onAdvanceWinner,
    isFinal,
}: {
    match: MatchData;
    isAdmin: boolean;
    actionLoading: string | null;
    onCreateLobby: (matchId: string) => void;
    onAdvanceWinner: (matchId: string, winnerId: string) => void;
    isFinal: boolean;
}) {
    const isActive = match.player1 && match.player2 && !match.winner;
    const isLoading = actionLoading === match.id;

    const borderColor = match.winner
        ? 'rgba(57,255,20,0.3)'
        : isActive
            ? 'rgba(255,140,0,0.4)'
            : 'var(--border)';

    return (
        <div style={{
            background: 'var(--card-bg)',
            border: `1px solid ${borderColor}`,
            borderRadius: 10,
            padding: 12,
            margin: '0 8px',
            minWidth: 240,
            position: 'relative',
        }}>
            {isFinal && (
                <div style={{ textAlign: 'center', fontSize: 20, marginBottom: 4 }}>🏆</div>
            )}

            {/* Player Slots */}
            <PlayerSlot
                player={match.player1}
                isWinner={match.winner?.id === match.player1?.id}
                isActive={!!(isActive && !match.winner)}
                isAdmin={isAdmin}
                onSelect={() => match.player1 && onAdvanceWinner(match.id, match.player1.id)}
            />

            <div style={{
                textAlign: 'center', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)',
                margin: '4px 0', letterSpacing: '0.1em',
            }}>
                VS
            </div>

            <PlayerSlot
                player={match.player2}
                isWinner={match.winner?.id === match.player2?.id}
                isActive={!!(isActive && !match.winner)}
                isAdmin={isAdmin}
                onSelect={() => match.player2 && onAdvanceWinner(match.id, match.player2.id)}
            />

            {/* Lobby URL Display */}
            {match.cybershoke_lobby_url && (
                <a
                    href={match.cybershoke_lobby_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                        display: 'block', marginTop: 8, padding: '6px 10px',
                        background: 'rgba(0,160,255,0.1)', border: '1px solid rgba(0,160,255,0.3)',
                        borderRadius: 6, color: 'var(--blue)', fontSize: 11,
                        textDecoration: 'none', textAlign: 'center',
                        wordBreak: 'break-all',
                    }}
                >
                    Join Lobby
                </a>
            )}

            {/* Admin Controls */}
            {isAdmin && isActive && !isLoading && (
                <div style={{ marginTop: 8, display: 'flex', gap: 6 }}>
                    {!match.cybershoke_lobby_url && (
                        <button
                            className="btn btn-sm"
                            onClick={() => onCreateLobby(match.id)}
                            style={{
                                flex: 1, fontSize: 11, padding: '5px 8px',
                                background: 'rgba(0,160,255,0.15)', color: 'var(--blue)',
                                border: '1px solid rgba(0,160,255,0.3)',
                            }}
                        >
                            Create Cybershoke Server
                        </button>
                    )}
                </div>
            )}

            {isLoading && (
                <div style={{ textAlign: 'center', marginTop: 8, fontSize: 12, color: 'var(--text-muted)' }}>
                    Loading...
                </div>
            )}
        </div>
    );
}


function PlayerSlot({
    player,
    isWinner,
    isActive,
    isAdmin,
    onSelect,
}: {
    player: PlayerInfo | null;
    isWinner: boolean;
    isActive: boolean;
    isAdmin: boolean;
    onSelect: () => void;
}) {
    if (!player) {
        return (
            <div style={{
                padding: '8px 12px', borderRadius: 6,
                background: '#111', border: '1px dashed var(--border)',
                color: 'var(--text-muted)', fontSize: 13,
                textAlign: 'center',
            }}>
                TBD
            </div>
        );
    }

    return (
        <div
            onClick={isAdmin && isActive ? onSelect : undefined}
            style={{
                padding: '8px 12px', borderRadius: 6,
                background: isWinner ? 'rgba(57,255,20,0.12)' : '#111',
                border: `1px solid ${isWinner ? 'rgba(57,255,20,0.4)' : 'transparent'}`,
                display: 'flex', alignItems: 'center', gap: 8,
                cursor: isAdmin && isActive ? 'pointer' : 'default',
                transition: 'all 0.15s',
            }}
            onMouseEnter={e => {
                if (isAdmin && isActive) {
                    (e.currentTarget as HTMLDivElement).style.background = 'rgba(57,255,20,0.08)';
                    (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(57,255,20,0.3)';
                }
            }}
            onMouseLeave={e => {
                if (isAdmin && isActive && !isWinner) {
                    (e.currentTarget as HTMLDivElement).style.background = '#111';
                    (e.currentTarget as HTMLDivElement).style.borderColor = 'transparent';
                }
            }}
        >
            {/* Avatar */}
            <div style={{
                width: 24, height: 24, borderRadius: '50%', flexShrink: 0,
                background: isWinner ? 'var(--neon-green)' : 'var(--card-hover)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 10, fontWeight: 800, color: isWinner ? '#000' : 'var(--text-secondary)',
            }}>
                {isWinner ? '✓' : player.display_name[0]?.toUpperCase()}
            </div>

            <span style={{
                fontSize: 13, fontWeight: isWinner ? 700 : 500,
                color: isWinner ? 'var(--neon-green)' : 'var(--text-primary)',
                flex: 1,
            }}>
                {player.display_name}
            </span>

            {isAdmin && isActive && (
                <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>click to win</span>
            )}
        </div>
    );
}

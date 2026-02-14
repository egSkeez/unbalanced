'use client';
import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';
import {
    getTournament, getTournamentBracket, joinTournament, leaveTournament,
    createTournamentLobby, advanceWinner, searchSkins,
} from '@/app/lib/api';

interface PlayerStats {
    matches_played?: number;
    avg_rating?: number | null;
    overall_kd?: number | null;
    avg_adr?: number | null;
    avg_hs_pct?: number | null;
    winrate_pct?: number | null;
    wins?: number;
    losses?: number;
    elo?: number | null;
    aim?: number | null;
    util?: number | null;
    team_play?: number | null;
}

interface PlayerInfo {
    id: string;
    username: string;
    display_name: string;
    stats?: PlayerStats | null;
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
    stats?: PlayerStats | null;
}

// ──────────────────────────────────────────────
// HELPERS
// ──────────────────────────────────────────────

function getStatLine(stats: PlayerStats | null | undefined): string {
    if (!stats) return '';
    if (stats.avg_rating != null) {
        const parts = [`${stats.avg_rating.toFixed(2)} Rating`];
        if (stats.overall_kd != null) parts.push(`${stats.overall_kd.toFixed(2)} K/D`);
        if (stats.avg_adr != null) parts.push(`${stats.avg_adr.toFixed(0)} ADR`);
        return parts.join(' · ');
    }
    if (stats.elo != null) {
        const parts = [`${Math.round(stats.elo)} ELO`];
        if (stats.aim != null) parts.push(`${stats.aim.toFixed(1)} Aim`);
        if (stats.util != null) parts.push(`${stats.util.toFixed(1)} Util`);
        if (stats.team_play != null) parts.push(`${stats.team_play.toFixed(1)} Team`);
        return parts.join(' · ');
    }
    return '';
}

function getEloColor(elo: number): string {
    if (elo >= 1700) return '#39ff14';
    if (elo >= 1500) return '#4da6ff';
    if (elo >= 1300) return 'var(--text-primary)';
    if (elo >= 1100) return 'var(--orange)';
    return 'var(--red)';
}

function getRatingColor(rating: number): string {
    if (rating >= 1.3) return '#39ff14';
    if (rating >= 1.1) return '#4da6ff';
    if (rating >= 0.9) return 'var(--text-primary)';
    if (rating >= 0.7) return 'var(--orange)';
    return 'var(--red)';
}

function getMainStatDisplay(stats: PlayerStats | null | undefined): { value: string; color: string } | null {
    if (!stats) return null;
    if (stats.avg_rating != null) return { value: stats.avg_rating.toFixed(2), color: getRatingColor(stats.avg_rating) };
    if (stats.elo != null) return { value: String(Math.round(stats.elo)), color: getEloColor(stats.elo) };
    return null;
}

// ──────────────────────────────────────────────
// MAIN PAGE
// ──────────────────────────────────────────────

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
    const [prizeImage, setPrizeImage] = useState<string | null>(null);

    const isAdmin = user?.role === 'admin';

    const loadData = useCallback(async () => {
        try {
            const tData = await getTournament(tournamentId);
            setTournament(tData);
            setParticipants(tData.participants || []);

            // Auto-fetch prize image if missing but prize_name exists
            if (!tData.prize_image_url && tData.prize_name) {
                try {
                    const skins = await searchSkins(tData.prize_name);
                    if (skins.length > 0) setPrizeImage(skins[0].image);
                } catch { /* ignore */ }
            } else if (tData.prize_image_url) {
                setPrizeImage(tData.prize_image_url);
            }

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
            {/* Breadcrumb */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <Link href="/tournaments" style={{ color: 'var(--text-secondary)', textDecoration: 'none', fontSize: 14 }}>
                    Tournaments
                </Link>
                <span style={{ color: 'var(--text-muted)' }}>/</span>
            </div>

            {/* Header */}
            <div style={{ marginBottom: 24 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                    <h1 className="page-title" style={{ margin: 0 }}>{tournament.name}</h1>
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
                <p style={{ color: 'var(--text-secondary)', margin: '4px 0', fontSize: 14 }}>
                    {tournament.max_players}-player single elimination
                    {tournament.tournament_date && (
                        <span style={{ marginLeft: 12, color: 'var(--text-muted)' }}>
                            {new Date(tournament.tournament_date + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })}
                        </span>
                    )}
                </p>
            </div>

            {/* Prize Banner — always visible if prize exists */}
            {(prizeImage || tournament.prize_name) && (
                <div style={{
                    display: 'flex', alignItems: 'center', gap: 20,
                    padding: '16px 24px', borderRadius: 12, marginBottom: 24,
                    background: 'linear-gradient(135deg, rgba(255,215,0,0.1), rgba(255,140,0,0.05))',
                    border: '1px solid rgba(255,215,0,0.3)',
                }}>
                    {prizeImage ? (
                        <div style={{
                            width: 120, height: 90, flexShrink: 0,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                        }}>
                            <img
                                src={prizeImage}
                                alt={tournament.prize_name || 'Prize'}
                                style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                            />
                        </div>
                    ) : (
                        <div style={{
                            width: 80, height: 80, flexShrink: 0, borderRadius: 12,
                            background: 'linear-gradient(135deg, var(--gold), var(--orange))',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: 36,
                        }}>
                            🏆
                        </div>
                    )}
                    <div>
                        <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--gold)', letterSpacing: '0.1em', marginBottom: 4 }}>
                            Prize
                        </div>
                        <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>
                            {tournament.prize_name || 'TBA'}
                        </div>
                    </div>
                </div>
            )}

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
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16,
                }}>
                    {prizeImage && (
                        <img src={prizeImage} alt="" style={{ width: 48, height: 48, objectFit: 'contain' }} />
                    )}
                    <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: 28, marginBottom: 2 }}>🏆</div>
                        <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--gold)' }}>
                            {tournament.winner.display_name} wins!
                        </div>
                    </div>
                </div>
            )}

            {/* Enrollment Actions (open only) */}
            {tournament.status === 'open' && user && (
                <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                    <button className="btn btn-primary btn-sm" onClick={handleJoin}>
                        Join Tournament
                    </button>
                    <button className="btn btn-sm" onClick={handleLeave} style={{ color: 'var(--red)' }}>
                        Leave
                    </button>
                </div>
            )}

            {/* Progress bar (open only) */}
            {tournament.status === 'open' && (
                <div style={{ background: '#222', borderRadius: 6, height: 8, overflow: 'hidden', marginBottom: 20 }}>
                    <div style={{
                        width: `${(tournament.participant_count / tournament.max_players) * 100}%`,
                        height: '100%',
                        background: 'var(--neon-green)',
                        borderRadius: 6,
                        transition: 'width 0.3s',
                    }} />
                </div>
            )}

            {/* Players Section — ALWAYS visible */}
            {participants.length > 0 && (
                <div className="card" style={{ marginBottom: 24 }}>
                    <h3 style={{ fontWeight: 700, margin: '0 0 16px 0', fontSize: 16 }}>
                        Players ({participants.length}/{tournament.max_players})
                    </h3>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 10 }}>
                        {participants.map(p => {
                            const stat = getMainStatDisplay(p.stats);
                            const line = getStatLine(p.stats);
                            return (
                                <div key={p.id} style={{
                                    padding: '12px 16px', borderRadius: 10,
                                    background: '#111',
                                    border: '1px solid var(--border)',
                                    display: 'flex', alignItems: 'center', gap: 12,
                                }}>
                                    {/* Avatar with main stat */}
                                    <div style={{
                                        width: 40, height: 40, borderRadius: '50%', flexShrink: 0,
                                        background: stat ? `${stat.color}18` : 'var(--card-hover)',
                                        border: stat ? `2px solid ${stat.color}55` : '2px solid var(--border)',
                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                        fontSize: stat ? 12 : 15, fontWeight: 800,
                                        color: stat ? stat.color : 'var(--text-secondary)',
                                    }}>
                                        {stat ? stat.value : p.display_name[0]?.toUpperCase()}
                                    </div>
                                    {/* Name + stat line */}
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
                                            {p.display_name}
                                        </div>
                                        {line && (
                                            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                                                {line}
                                            </div>
                                        )}
                                    </div>
                                    {p.seed && tournament.status !== 'open' && (
                                        <div style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 600 }}>
                                            #{p.seed}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                        {tournament.status === 'open' && Array.from({ length: tournament.max_players - tournament.participant_count }).map((_, i) => (
                            <div key={`empty-${i}`} style={{
                                padding: '14px 16px', borderRadius: 10,
                                border: '1px dashed var(--border)', color: 'var(--text-muted)',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                minHeight: 56, fontSize: 13,
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
// BRACKET VIEW
// ──────────────────────────────────────────────

function BracketView({
    bracket, isAdmin, actionLoading, onCreateLobby, onAdvanceWinner,
}: {
    bracket: BracketData; isAdmin: boolean; actionLoading: string | null;
    onCreateLobby: (id: string) => void; onAdvanceWinner: (id: string, wid: string) => void;
}) {
    return (
        <div>
            <h2 style={{ fontWeight: 700, marginBottom: 16, fontSize: 20 }}>Bracket</h2>
            <div style={{ display: 'flex', gap: 0, overflowX: 'auto', paddingBottom: 16 }}>
                {bracket.rounds.map((round) => (
                    <BracketRound key={round.round_number} round={round} totalRounds={bracket.total_rounds}
                        isAdmin={isAdmin} actionLoading={actionLoading}
                        onCreateLobby={onCreateLobby} onAdvanceWinner={onAdvanceWinner}
                    />
                ))}
            </div>
        </div>
    );
}

function BracketRound({
    round, totalRounds, isAdmin, actionLoading, onCreateLobby, onAdvanceWinner,
}: {
    round: RoundData; totalRounds: number; isAdmin: boolean; actionLoading: string | null;
    onCreateLobby: (id: string) => void; onAdvanceWinner: (id: string, wid: string) => void;
}) {
    const matchHeight = 200;
    const roundSpacing = Math.pow(2, round.round_number - 1);
    const topPadding = (roundSpacing - 1) * (matchHeight / 2);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', minWidth: 300 }}>
            <div style={{
                textAlign: 'center', padding: '8px 16px', marginBottom: 12,
                fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)',
                textTransform: 'uppercase', letterSpacing: '0.05em',
            }}>
                {round.name}
            </div>
            <div style={{
                display: 'flex', flexDirection: 'column', justifyContent: 'space-around',
                flex: 1, paddingTop: topPadding, gap: (roundSpacing - 1) * matchHeight,
            }}>
                {round.matches.map((match) => (
                    <MatchCard key={match.id} match={match} isAdmin={isAdmin}
                        actionLoading={actionLoading} onCreateLobby={onCreateLobby}
                        onAdvanceWinner={onAdvanceWinner} isFinal={round.round_number === totalRounds}
                    />
                ))}
            </div>
        </div>
    );
}


function MatchCard({
    match, isAdmin, actionLoading, onCreateLobby, onAdvanceWinner, isFinal,
}: {
    match: MatchData; isAdmin: boolean; actionLoading: string | null;
    onCreateLobby: (id: string) => void; onAdvanceWinner: (id: string, wid: string) => void;
    isFinal: boolean;
}) {
    const isActive = match.player1 && match.player2 && !match.winner;
    const isLoading = actionLoading === match.id;
    const borderColor = match.winner ? 'rgba(57,255,20,0.3)' : isActive ? 'rgba(255,140,0,0.4)' : 'var(--border)';

    return (
        <div style={{
            background: 'var(--card-bg)', border: `1px solid ${borderColor}`,
            borderRadius: 10, padding: 12, margin: '0 8px', minWidth: 280,
        }}>
            {isFinal && <div style={{ textAlign: 'center', fontSize: 20, marginBottom: 4 }}>🏆</div>}

            <PlayerSlot player={match.player1} isWinner={match.winner?.id === match.player1?.id}
                isActive={!!(isActive && !match.winner)} isAdmin={isAdmin}
                onSelect={() => match.player1 && onAdvanceWinner(match.id, match.player1.id)} />

            <div style={{ textAlign: 'center', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', margin: '4px 0', letterSpacing: '0.1em' }}>VS</div>

            <PlayerSlot player={match.player2} isWinner={match.winner?.id === match.player2?.id}
                isActive={!!(isActive && !match.winner)} isAdmin={isAdmin}
                onSelect={() => match.player2 && onAdvanceWinner(match.id, match.player2.id)} />

            {match.cybershoke_lobby_url && (
                <a href={match.cybershoke_lobby_url} target="_blank" rel="noopener noreferrer" style={{
                    display: 'block', marginTop: 8, padding: '6px 10px',
                    background: 'rgba(0,160,255,0.1)', border: '1px solid rgba(0,160,255,0.3)',
                    borderRadius: 6, color: 'var(--blue)', fontSize: 11,
                    textDecoration: 'none', textAlign: 'center',
                }}>
                    Join Lobby
                </a>
            )}

            {isAdmin && isActive && !isLoading && !match.cybershoke_lobby_url && (
                <button className="btn btn-sm" onClick={() => onCreateLobby(match.id)} style={{
                    width: '100%', marginTop: 8, fontSize: 11, padding: '5px 8px',
                    background: 'rgba(0,160,255,0.15)', color: 'var(--blue)',
                    border: '1px solid rgba(0,160,255,0.3)',
                }}>
                    Create Cybershoke Server
                </button>
            )}

            {isLoading && <div style={{ textAlign: 'center', marginTop: 8, fontSize: 12, color: 'var(--text-muted)' }}>Loading...</div>}
        </div>
    );
}


function PlayerSlot({
    player, isWinner, isActive, isAdmin, onSelect,
}: {
    player: PlayerInfo | null; isWinner: boolean; isActive: boolean;
    isAdmin: boolean; onSelect: () => void;
}) {
    if (!player) {
        return (
            <div style={{
                padding: '10px 12px', borderRadius: 6,
                background: '#111', border: '1px dashed var(--border)',
                color: 'var(--text-muted)', fontSize: 13, textAlign: 'center',
            }}>TBD</div>
        );
    }

    const stat = getMainStatDisplay(player.stats);
    const line = getStatLine(player.stats);

    return (
        <div
            onClick={isAdmin && isActive ? onSelect : undefined}
            style={{
                padding: '8px 12px', borderRadius: 6,
                background: isWinner ? 'rgba(57,255,20,0.12)' : '#111',
                border: `1px solid ${isWinner ? 'rgba(57,255,20,0.4)' : 'transparent'}`,
                cursor: isAdmin && isActive ? 'pointer' : 'default',
                transition: 'all 0.15s',
            }}
            onMouseEnter={e => { if (isAdmin && isActive) { e.currentTarget.style.background = 'rgba(57,255,20,0.08)'; e.currentTarget.style.borderColor = 'rgba(57,255,20,0.3)'; } }}
            onMouseLeave={e => { if (isAdmin && isActive && !isWinner) { e.currentTarget.style.background = '#111'; e.currentTarget.style.borderColor = 'transparent'; } }}
        >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {/* Avatar */}
                <div style={{
                    width: 26, height: 26, borderRadius: '50%', flexShrink: 0,
                    background: isWinner ? 'var(--neon-green)' : 'var(--card-hover)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 10, fontWeight: 800, color: isWinner ? '#000' : 'var(--text-secondary)',
                }}>
                    {isWinner ? '✓' : player.display_name[0]?.toUpperCase()}
                </div>

                {/* Name */}
                <span style={{
                    fontSize: 13, fontWeight: isWinner ? 700 : 500,
                    color: isWinner ? 'var(--neon-green)' : 'var(--text-primary)',
                    flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                    {player.display_name}
                </span>

                {/* Main stat badge */}
                {stat && (
                    <span style={{
                        fontSize: 12, fontWeight: 800, color: stat.color, flexShrink: 0,
                        background: `${stat.color}15`, padding: '2px 6px', borderRadius: 4,
                    }}>
                        {stat.value}
                    </span>
                )}

                {isAdmin && isActive && (
                    <span style={{ fontSize: 9, color: 'var(--text-muted)', flexShrink: 0 }}>click</span>
                )}
            </div>

            {/* Stat detail line */}
            {line && (
                <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3, marginLeft: 34 }}>
                    {line}
                </div>
            )}
        </div>
    );
}

'use client';
import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';
import {
    getTournament, getTournamentBracket, joinTournament, leaveTournament,
    createTournamentLobby, reportMatch, startTournament, searchSkins,
    updateTournament, submitMatchLobby,
} from '@/app/lib/api';

// ──────────────────────────────────────────────
// TYPES
// ──────────────────────────────────────────────

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
    group_id: number | null;
    score: string | null;
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

interface StandingData {
    user_id: string;
    username: string;
    display_name: string;
    wins: number;
    losses: number;
    draws: number;
    points: number;
    matches_played: number;
}

interface BracketData {
    tournament: TournamentInfo;
    format: string;
    rounds: RoundData[];
    playoff_rounds?: RoundData[];
    total_rounds: number;
    standings?: StandingData[];
}

interface TournamentInfo {
    id: string;
    name: string;
    description: string | null;
    rules: string | null;
    format: string;
    prize_image_url: string | null;
    prize_name: string | null;
    prize_pool: string | null;
    max_players: number;
    playoffs: boolean;
    status: string;
    tournament_date: string | null;
    created_by: string | null;
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
    checked_in?: boolean;
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

function formatLabel(f: string): string {
    return f.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// ──────────────────────────────────────────────
// MAIN PAGE
// ──────────────────────────────────────────────

type TabKey = 'overview' | 'description' | 'participants' | 'bracket';

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
    const [activeTab, setActiveTab] = useState<TabKey>('overview');

    // Description editing state
    const [editingDesc, setEditingDesc] = useState(false);
    const [descDraft, setDescDraft] = useState('');
    const [rulesDraft, setRulesDraft] = useState('');
    const [prizeImgDraft, setPrizeImgDraft] = useState('');
    const [savingDesc, setSavingDesc] = useState(false);

    // Score dialog state (admin fallback)
    const [scoreDialog, setScoreDialog] = useState<{ matchId: string; player1: PlayerInfo; player2: PlayerInfo } | null>(null);
    const [scoreInput, setScoreInput] = useState('');
    const [scoreWinner, setScoreWinner] = useState('');

    // Lobby submission dialog state (participants)
    const [lobbyDialog, setLobbyDialog] = useState<{ matchId: string } | null>(null);
    const [lobbyUrlInput, setLobbyUrlInput] = useState('');
    const [lobbySubmitting, setLobbySubmitting] = useState(false);

    const isAdmin = user?.role === 'admin';
    const isCreator = !!(user && tournament?.created_by && user.id === tournament.created_by);
    const canEdit = isAdmin || isCreator;
    const isRegistration = tournament?.status === 'registration' || tournament?.status === 'open';
    const isRoundRobin = tournament?.format === 'round_robin';
    const isParticipant = participants.some(p => p.user_id === user?.id);

    const loadData = useCallback(async () => {
        try {
            const tData = await getTournament(tournamentId);
            setTournament(tData);
            setParticipants(tData.participants || []);

            if (!tData.prize_image_url && tData.prize_name) {
                try {
                    const skins = await searchSkins(tData.prize_name);
                    if (skins.length > 0) setPrizeImage(skins[0].image);
                } catch { /* ignore */ }
            } else if (tData.prize_image_url) {
                setPrizeImage(tData.prize_image_url);
            }

            if (tData.status === 'active' || tData.status === 'completed' || tData.status === 'playoffs') {
                const bData = await getTournamentBracket(tournamentId);
                setBracket(bData);
                setActiveTab('bracket');
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

    const handleStart = async () => {
        if (!token) return;
        setError('');
        setActionLoading('start');
        try {
            await startTournament(tournamentId, token);
            await loadData();
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to start');
        } finally {
            setActionLoading(null);
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

    const openScoreDialog = (match: MatchData) => {
        if (!match.player1 || !match.player2) return;
        setScoreDialog({ matchId: match.id, player1: match.player1, player2: match.player2 });
        setScoreInput('');
        setScoreWinner('');
    };

    const handleReportScore = async () => {
        if (!token || !scoreDialog || !scoreWinner) return;
        setActionLoading(scoreDialog.matchId);
        setError('');
        try {
            await reportMatch(scoreDialog.matchId, scoreWinner, scoreInput || null, token);
            setScoreDialog(null);
            await loadData();
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to report match');
        } finally {
            setActionLoading(null);
        }
    };

    const openLobbyDialog = (match: MatchData) => {
        setLobbyDialog({ matchId: match.id });
        setLobbyUrlInput('');
        setError('');
    };

    const handleSubmitLobby = async () => {
        if (!token || !lobbyDialog || !lobbyUrlInput.trim()) return;
        setLobbySubmitting(true);
        setError('');
        try {
            await submitMatchLobby(lobbyDialog.matchId, lobbyUrlInput.trim(), token);
            setLobbyDialog(null);
            await loadData();
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to submit lobby result');
        } finally {
            setLobbySubmitting(false);
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
        registration: 'var(--neon-green)',
        active: 'var(--orange)',
        playoffs: 'var(--gold)',
        completed: 'var(--text-muted)',
    };

    const tabs: { key: TabKey; label: string }[] = [
        { key: 'overview', label: 'Overview' },
        { key: 'description', label: 'Description & Rules' },
        { key: 'participants', label: `Participants (${participants.length})` },
        { key: 'bracket', label: isRoundRobin ? 'Standings' : 'Bracket' },
    ];

    const startEditing = () => {
        setDescDraft(tournament?.description || '');
        setRulesDraft(tournament?.rules || '');
        setPrizeImgDraft(tournament?.prize_image_url || '');
        setEditingDesc(true);
    };

    const handleSaveDesc = async () => {
        if (!token || !tournament) return;
        setSavingDesc(true);
        setError('');
        try {
            await updateTournament(tournament.id, {
                description: descDraft,
                rules: rulesDraft,
                prize_image_url: prizeImgDraft || undefined,
            }, token);
            setEditingDesc(false);
            await loadData();
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to save');
        } finally {
            setSavingDesc(false);
        }
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

            {/* ═══════ HERO SECTION ═══════ */}
            <div style={{
                padding: '28px 32px', borderRadius: 16, marginBottom: 24,
                background: 'linear-gradient(135deg, rgba(15,15,25,0.95), rgba(20,20,35,0.9))',
                border: '1px solid var(--border)',
                position: 'relative', overflow: 'hidden',
            }}>
                {/* Subtle accent glow */}
                <div style={{
                    position: 'absolute', top: -40, right: -40, width: 200, height: 200,
                    borderRadius: '50%', opacity: 0.08,
                    background: tournament.status === 'completed' ? 'var(--gold)' : 'var(--neon-green)',
                    filter: 'blur(60px)', pointerEvents: 'none',
                }} />

                <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start', position: 'relative' }}>
                    {/* Prize image */}
                    {(prizeImage || tournament.prize_name) && (
                        <div style={{
                            width: 120, height: 100, flexShrink: 0, borderRadius: 12,
                            background: prizeImage ? 'transparent' : 'linear-gradient(135deg, var(--gold), var(--orange))',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            border: '1px solid rgba(255,215,0,0.25)',
                        }}>
                            {prizeImage ? (
                                <img src={prizeImage} alt={tournament.prize_name || 'Prize'} style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} />
                            ) : (
                                <span style={{ fontSize: 40 }}>🏆</span>
                            )}
                        </div>
                    )}

                    {/* Info */}
                    <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
                            <h1 style={{ margin: 0, fontSize: 26, fontWeight: 800 }}>{tournament.name}</h1>
                            <span style={{
                                fontSize: 11, fontWeight: 700, textTransform: 'uppercase',
                                padding: '3px 10px', borderRadius: 4,
                                background: `${statusColors[tournament.status] || 'var(--text-muted)'}22`,
                                color: statusColors[tournament.status] || 'var(--text-muted)',
                                border: `1px solid ${statusColors[tournament.status] || 'var(--text-muted)'}44`,
                            }}>
                                {tournament.status}
                            </span>
                        </div>

                        {tournament.description && (
                            <p style={{ color: 'var(--text-secondary)', margin: '4px 0 8px', fontSize: 14 }}>
                                {tournament.description}
                            </p>
                        )}

                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 20, fontSize: 13, color: 'var(--text-secondary)' }}>
                            <span>{formatLabel(tournament.format)}{tournament.playoffs ? ' + Playoffs' : ''}</span>
                            <span>{tournament.max_players > 0 ? `${tournament.max_players} Players` : 'Unlimited Players'}</span>
                            {tournament.tournament_date && (
                                <span>
                                    {new Date(tournament.tournament_date + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })}
                                </span>
                            )}
                            {(tournament.prize_pool || tournament.prize_name) && (
                                <span style={{ color: 'var(--gold)', fontWeight: 700 }}>
                                    Prize: {tournament.prize_pool || tournament.prize_name}
                                </span>
                            )}
                        </div>

                        {/* Action buttons */}
                        <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
                            {isRegistration && user && (
                                <>
                                    {!isParticipant ? (
                                        <button className="btn btn-primary btn-sm" onClick={handleJoin}>
                                            Join Tournament
                                        </button>
                                    ) : (
                                        <button className="btn btn-sm" onClick={handleLeave} style={{ color: 'var(--red)' }}>
                                            Leave
                                        </button>
                                    )}
                                </>
                            )}
                            {isAdmin && isRegistration && participants.length >= 2 && (
                                <button
                                    className="btn btn-sm"
                                    onClick={handleStart}
                                    disabled={actionLoading === 'start'}
                                    style={{ background: 'rgba(255,140,0,0.15)', color: 'var(--orange)', border: '1px solid rgba(255,140,0,0.3)' }}
                                >
                                    {actionLoading === 'start' ? 'Starting...' : 'Start Tournament'}
                                </button>
                            )}
                        </div>
                    </div>
                </div>

                {/* Progress bar (registration only) */}
                {(isRegistration || tournament.status === 'open') && (
                    <div style={{ marginTop: 16 }}>
                        {tournament.max_players > 0 ? (
                            <>
                                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>
                                    <span>{participants.length} / {tournament.max_players} enrolled</span>
                                    <span>{Math.round((participants.length / tournament.max_players) * 100)}%</span>
                                </div>
                                <div style={{ background: '#222', borderRadius: 6, height: 6, overflow: 'hidden' }}>
                                    <div style={{
                                        width: `${Math.min((participants.length / tournament.max_players) * 100, 100)}%`,
                                        height: '100%', background: 'var(--neon-green)', borderRadius: 6, transition: 'width 0.3s',
                                    }} />
                                </div>
                            </>
                        ) : (
                            <div style={{ fontSize: 11, color: 'var(--neon-green)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                Open Registration • {participants.length} Enrolled
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Winner Banner */}
            {tournament.status === 'completed' && tournament.winner && (
                <div style={{
                    padding: '20px 24px', marginBottom: 24, borderRadius: 12,
                    background: 'linear-gradient(135deg, rgba(255,215,0,0.15), rgba(255,140,0,0.1))',
                    border: '1px solid rgba(255,215,0,0.3)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16,
                }}>
                    {prizeImage && <img src={prizeImage} alt="" style={{ width: 48, height: 48, objectFit: 'contain' }} />}
                    <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: 28, marginBottom: 2 }}>🏆</div>
                        <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--gold)' }}>
                            {tournament.winner.display_name} wins!
                        </div>
                    </div>
                </div>
            )}

            {error && (
                <div style={{ padding: '12px 16px', background: 'rgba(255,51,51,0.15)', border: '1px solid rgba(255,51,51,0.3)', borderRadius: 8, marginBottom: 16, color: 'var(--red)' }}>
                    {error}
                </div>
            )}

            {/* ═══════ TABS ═══════ */}
            <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--border)', marginBottom: 24 }}>
                {tabs.map(tab => (
                    <button
                        key={tab.key}
                        onClick={() => setActiveTab(tab.key)}
                        style={{
                            padding: '10px 20px', fontSize: 14, fontWeight: 600,
                            background: 'none', border: 'none', cursor: 'pointer',
                            color: activeTab === tab.key ? 'var(--text-primary)' : 'var(--text-muted)',
                            borderBottom: activeTab === tab.key ? '2px solid var(--neon-green)' : '2px solid transparent',
                            transition: 'all 0.15s',
                        }}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* ═══════ TAB CONTENT ═══════ */}

            {/* Overview Tab */}
            {activeTab === 'overview' && (
                <div style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))' }}>
                    <InfoCard label="Format" value={`${formatLabel(tournament.format)}${tournament.playoffs ? ' + Playoffs' : ''}`} />
                    <InfoCard label="Players" value={tournament.max_players > 0 ? `${participants.length} / ${tournament.max_players}` : `${participants.length} (Unlimited)`} />
                    <InfoCard label="Status" value={tournament.status.charAt(0).toUpperCase() + tournament.status.slice(1)} color={statusColors[tournament.status]} />
                    {tournament.tournament_date && (
                        <InfoCard label="Date" value={new Date(tournament.tournament_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })} />
                    )}
                    {(tournament.prize_pool || tournament.prize_name) && (
                        <InfoCard label="Prize" value={tournament.prize_pool || tournament.prize_name || 'TBA'} color="var(--gold)" />
                    )}
                    {bracket && (
                        <InfoCard label="Total Rounds" value={String(bracket.total_rounds)} />
                    )}
                </div>
            )}

            {/* Description & Rules Tab */}
            {activeTab === 'description' && (
                <div style={{ maxWidth: 800 }}>
                    {/* Edit / View toggle */}
                    {canEdit && !editingDesc && (
                        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
                            <button className="btn btn-sm" onClick={startEditing} style={{
                                fontSize: 12, padding: '6px 14px', background: 'rgba(57,255,20,0.1)',
                                color: 'var(--neon-green)', border: '1px solid rgba(57,255,20,0.3)',
                            }}>
                                ✏️ Edit
                            </button>
                        </div>
                    )}

                    {editingDesc ? (
                        /* ─── EDITING MODE ─── */
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                            {/* Description */}
                            <div>
                                <label style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: 6 }}>Description</label>
                                <textarea
                                    value={descDraft}
                                    onChange={e => setDescDraft(e.target.value)}
                                    placeholder="Describe the tournament..."
                                    rows={4}
                                    style={{
                                        width: '100%', background: '#111', border: '1px solid var(--border)', borderRadius: 10,
                                        padding: '12px 14px', color: '#fff', fontSize: 14, resize: 'vertical', lineHeight: 1.6,
                                    }}
                                />
                            </div>

                            {/* Rules */}
                            <div>
                                <label style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: 6 }}>Rules</label>
                                <textarea
                                    value={rulesDraft}
                                    onChange={e => setRulesDraft(e.target.value)}
                                    placeholder={"1. Best of 1\n2. No timeouts\n3. Must check in 10 minutes before start\n..."}
                                    rows={8}
                                    style={{
                                        width: '100%', background: '#111', border: '1px solid var(--border)', borderRadius: 10,
                                        padding: '12px 14px', color: '#fff', fontSize: 14, resize: 'vertical', lineHeight: 1.6,
                                        fontFamily: 'inherit',
                                    }}
                                />
                            </div>

                            {/* Prize Image URL */}
                            <div>
                                <label style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: 6 }}>Prize Image URL</label>
                                <input
                                    value={prizeImgDraft}
                                    onChange={e => setPrizeImgDraft(e.target.value)}
                                    placeholder="https://example.com/prize.png"
                                    style={{
                                        width: '100%', background: '#111', border: '1px solid var(--border)', borderRadius: 10,
                                        padding: '10px 14px', color: '#fff', fontSize: 14,
                                    }}
                                />
                                {prizeImgDraft && (
                                    <div style={{ marginTop: 10, padding: 12, background: '#0a0a0a', borderRadius: 10, border: '1px solid var(--border)', textAlign: 'center' }}>
                                        <img src={prizeImgDraft} alt="Prize preview" style={{ maxWidth: '100%', maxHeight: 200, objectFit: 'contain', borderRadius: 6 }} />
                                    </div>
                                )}
                            </div>

                            {/* Action Buttons */}
                            <div style={{ display: 'flex', gap: 8 }}>
                                <button className="btn btn-primary btn-sm" onClick={handleSaveDesc} disabled={savingDesc} style={{ padding: '8px 20px' }}>
                                    {savingDesc ? 'Saving...' : 'Save Changes'}
                                </button>
                                <button className="btn btn-sm" onClick={() => setEditingDesc(false)} style={{ padding: '8px 16px' }}>Cancel</button>
                            </div>
                        </div>
                    ) : (
                        /* ─── VIEW MODE ─── */
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
                            {/* Prize Image */}
                            {(prizeImage || tournament.prize_image_url) && (
                                <div style={{
                                    padding: 20, borderRadius: 14,
                                    background: 'linear-gradient(135deg, rgba(255,215,0,0.08), rgba(255,140,0,0.05))',
                                    border: '1px solid rgba(255,215,0,0.2)',
                                    textAlign: 'center',
                                }}>
                                    <img
                                        src={prizeImage || tournament.prize_image_url || ''}
                                        alt={tournament.prize_name || 'Prize'}
                                        style={{ maxWidth: '100%', maxHeight: 240, objectFit: 'contain', borderRadius: 8 }}
                                    />
                                    {tournament.prize_name && (
                                        <div style={{ marginTop: 10, fontSize: 16, fontWeight: 700, color: 'var(--gold)' }}>
                                            🏆 {tournament.prize_name}
                                        </div>
                                    )}
                                    {tournament.prize_pool && (
                                        <div style={{ marginTop: 4, fontSize: 14, color: 'var(--text-secondary)' }}>
                                            {tournament.prize_pool}
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* Description */}
                            <div style={{
                                padding: '20px 24px', borderRadius: 14,
                                background: 'var(--card-bg)', border: '1px solid var(--border)',
                            }}>
                                <h3 style={{ margin: '0 0 12px', fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>
                                    📋 Description
                                </h3>
                                {tournament.description ? (
                                    <p style={{ margin: 0, fontSize: 14, lineHeight: 1.7, color: 'var(--text-secondary)', whiteSpace: 'pre-wrap' }}>
                                        {tournament.description}
                                    </p>
                                ) : (
                                    <p style={{ margin: 0, fontSize: 14, color: 'var(--text-muted)', fontStyle: 'italic' }}>
                                        No description provided yet.{canEdit ? ' Click Edit to add one.' : ''}
                                    </p>
                                )}
                            </div>

                            {/* Rules */}
                            <div style={{
                                padding: '20px 24px', borderRadius: 14,
                                background: 'var(--card-bg)', border: '1px solid var(--border)',
                            }}>
                                <h3 style={{ margin: '0 0 12px', fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>
                                    📜 Rules
                                </h3>
                                {tournament.rules ? (
                                    <div style={{ fontSize: 14, lineHeight: 1.8, color: 'var(--text-secondary)', whiteSpace: 'pre-wrap' }}>
                                        {tournament.rules}
                                    </div>
                                ) : (
                                    <p style={{ margin: 0, fontSize: 14, color: 'var(--text-muted)', fontStyle: 'italic' }}>
                                        No rules set yet.{canEdit ? ' Click Edit to add rules.' : ''}
                                    </p>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Participants Tab */}
            {activeTab === 'participants' && (
                <div>
                    {participants.length === 0 ? (
                        <div className="card" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                            No participants yet. Be the first to join!
                        </div>
                    ) : (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 10 }}>
                            {participants.map(p => {
                                const s = p.stats;
                                const rating = s?.avg_rating;
                                const ratingColor = rating != null ? getRatingColor(rating) : 'var(--text-muted)';
                                return (
                                    <div key={p.id} style={{
                                        padding: '14px 16px', borderRadius: 12, background: '#111',
                                        border: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 14,
                                    }}>
                                        {/* HLTV Rating Badge */}
                                        <div style={{
                                            width: 46, height: 46, borderRadius: '50%', flexShrink: 0,
                                            background: `${ratingColor}15`,
                                            border: `2px solid ${ratingColor}55`,
                                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                                            flexDirection: 'column',
                                        }}>
                                            <div style={{ fontSize: 13, fontWeight: 800, color: ratingColor, lineHeight: 1.1 }}>
                                                {rating != null ? rating.toFixed(2) : '—'}
                                            </div>
                                            <div style={{ fontSize: 7, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                                HLTV
                                            </div>
                                        </div>

                                        {/* Name + Stats */}
                                        <div style={{ flex: 1, minWidth: 0 }}>
                                            <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 3 }}>
                                                {p.display_name}
                                            </div>
                                            {s && (s.overall_kd != null || s.avg_adr != null || s.avg_hs_pct != null) ? (
                                                <div style={{ display: 'flex', gap: 10, fontSize: 12, color: 'var(--text-secondary)', flexWrap: 'wrap' }}>
                                                    {s.overall_kd != null && (
                                                        <span><strong style={{ color: s.overall_kd >= 1.0 ? '#4da6ff' : 'var(--red)' }}>{s.overall_kd.toFixed(2)}</strong> K/D</span>
                                                    )}
                                                    {s.avg_adr != null && (
                                                        <span><strong style={{ color: s.avg_adr >= 80 ? '#4da6ff' : 'var(--text-secondary)' }}>{s.avg_adr.toFixed(0)}</strong> ADR</span>
                                                    )}
                                                    {s.avg_hs_pct != null && (
                                                        <span><strong>{s.avg_hs_pct.toFixed(0)}%</strong> HS</span>
                                                    )}
                                                    {(s.wins != null || s.losses != null) && (
                                                        <span style={{ color: 'var(--text-muted)' }}>
                                                            <span style={{ color: 'var(--neon-green)' }}>{s.wins ?? 0}W</span>
                                                            {' - '}
                                                            <span style={{ color: 'var(--red)' }}>{s.losses ?? 0}L</span>
                                                        </span>
                                                    )}
                                                </div>
                                            ) : (
                                                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No match data</div>
                                            )}
                                        </div>

                                        {/* Seed badge */}
                                        {p.seed && !isRegistration && (
                                            <div style={{
                                                fontSize: 10, color: 'var(--text-muted)', fontWeight: 700,
                                                background: 'rgba(255,255,255,0.05)', padding: '2px 8px', borderRadius: 4,
                                            }}>#{p.seed}</div>
                                        )}
                                    </div>
                                );
                            })}
                            {isRegistration && tournament.max_players > 0 && Array.from({ length: Math.max(0, tournament.max_players - participants.length) }).map((_, i) => (
                                <div key={`empty-${i}`} style={{
                                    padding: '14px 16px', borderRadius: 12, border: '1px dashed var(--border)',
                                    color: 'var(--text-muted)', display: 'flex', alignItems: 'center',
                                    justifyContent: 'center', minHeight: 64, fontSize: 13,
                                }}>
                                    Open Slot
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Bracket / Standings Tab */}
            {activeTab === 'bracket' && (
                <>
                    {!bracket || bracket.rounds.length === 0 ? (
                        <div className="card" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                            {isRegistration ? 'Tournament hasn\'t started yet.' : 'No matches found.'}
                        </div>
                    ) : isRoundRobin ? (
                        <RoundRobinView
                            bracket={bracket}
                            isAdmin={isAdmin}
                            canEdit={canEdit}
                            currentUserId={user?.id}
                            actionLoading={actionLoading}
                            onEditMatch={openScoreDialog}
                            onCreateLobby={handleCreateLobby}
                            onSubmitLobby={openLobbyDialog}
                        />
                    ) : (
                        <BracketView
                            bracket={bracket}
                            isAdmin={isAdmin}
                            canEdit={canEdit}
                            currentUserId={user?.id}
                            actionLoading={actionLoading}
                            onCreateLobby={handleCreateLobby}
                            onEditMatch={openScoreDialog}
                            onSubmitLobby={openLobbyDialog}
                        />
                    )}
                </>
            )}

            {/* ═══════ SCORE DIALOG ═══════ */}
            {scoreDialog && (
                <div style={{
                    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 1000,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                }} onClick={() => setScoreDialog(null)}>
                    <div
                        style={{
                            background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: 16,
                            padding: 28, width: 400, maxWidth: '90vw',
                        }}
                        onClick={e => e.stopPropagation()}
                    >
                        <h3 style={{ margin: '0 0 20px', fontWeight: 700 }}>Report Match Result</h3>

                        <div style={{ marginBottom: 16 }}>
                            <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>Winner</label>
                            {[scoreDialog.player1, scoreDialog.player2].map(p => (
                                <button
                                    key={p.id}
                                    onClick={() => setScoreWinner(p.id)}
                                    style={{
                                        display: 'block', width: '100%', padding: '10px 14px', marginBottom: 6,
                                        borderRadius: 8, border: `2px solid ${scoreWinner === p.id ? 'var(--neon-green)' : 'var(--border)'}`,
                                        background: scoreWinner === p.id ? 'rgba(57,255,20,0.1)' : '#111',
                                        color: scoreWinner === p.id ? 'var(--neon-green)' : 'var(--text-primary)',
                                        cursor: 'pointer', textAlign: 'left', fontSize: 14, fontWeight: 600,
                                        transition: 'all 0.15s',
                                    }}
                                >
                                    {p.display_name}
                                </button>
                            ))}
                        </div>

                        <div style={{ marginBottom: 20 }}>
                            <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                                Score <span style={{ color: 'var(--text-muted)' }}>(optional, e.g. 16-12)</span>
                            </label>
                            <input
                                value={scoreInput}
                                onChange={e => setScoreInput(e.target.value)}
                                placeholder="16-12"
                                style={{
                                    background: '#111', border: '1px solid var(--border)', borderRadius: 8,
                                    padding: '10px 14px', color: '#fff', width: '100%',
                                }}
                            />
                        </div>

                        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                            <button className="btn btn-sm" onClick={() => setScoreDialog(null)}>Cancel</button>
                            <button
                                className="btn btn-primary btn-sm"
                                onClick={handleReportScore}
                                disabled={!scoreWinner || actionLoading === scoreDialog.matchId}
                            >
                                {actionLoading === scoreDialog.matchId ? 'Saving...' : 'Submit Result'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* ═══════ LOBBY SUBMISSION DIALOG ═══════ */}
            {lobbyDialog && (
                <div style={{
                    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 1000,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                }} onClick={() => setLobbyDialog(null)}>
                    <div
                        style={{
                            background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: 16,
                            padding: 28, width: 440, maxWidth: '90vw',
                        }}
                        onClick={e => e.stopPropagation()}
                    >
                        <h3 style={{ margin: '0 0 8px', fontWeight: 700 }}>Submit Match Result</h3>
                        <p style={{ margin: '0 0 20px', fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                            Paste the Cybershoke lobby URL from your finished match. The score and winner will be extracted automatically.
                        </p>

                        <div style={{ marginBottom: 20 }}>
                            <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                                Lobby URL
                            </label>
                            <input
                                value={lobbyUrlInput}
                                onChange={e => setLobbyUrlInput(e.target.value)}
                                placeholder="https://cybershoke.net/match/12345"
                                style={{
                                    background: '#111', border: '1px solid var(--border)', borderRadius: 8,
                                    padding: '10px 14px', color: '#fff', width: '100%', fontSize: 14,
                                }}
                                autoFocus
                            />
                        </div>

                        {error && (
                            <div style={{
                                padding: '10px 14px', marginBottom: 16, borderRadius: 8,
                                background: 'rgba(255,51,51,0.15)', border: '1px solid rgba(255,51,51,0.3)',
                                color: 'var(--red)', fontSize: 13,
                            }}>
                                {error}
                            </div>
                        )}

                        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                            <button className="btn btn-sm" onClick={() => setLobbyDialog(null)}>Cancel</button>
                            <button
                                className="btn btn-primary btn-sm"
                                onClick={handleSubmitLobby}
                                disabled={!lobbyUrlInput.trim() || lobbySubmitting}
                            >
                                {lobbySubmitting ? 'Submitting...' : 'Submit'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}


// ──────────────────────────────────────────────
// INFO CARD
// ──────────────────────────────────────────────

function InfoCard({ label, value, color }: { label: string; value: string; color?: string }) {
    return (
        <div className="card" style={{ padding: '16px 20px' }}>
            <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.08em', marginBottom: 4 }}>
                {label}
            </div>
            <div style={{ fontSize: 18, fontWeight: 700, color: color || 'var(--text-primary)' }}>
                {value}
            </div>
        </div>
    );
}


// ──────────────────────────────────────────────
// ROUND ROBIN VIEW — Standings Table + Match List
// ──────────────────────────────────────────────

function RoundRobinView({
    bracket, isAdmin, canEdit, currentUserId, actionLoading, onEditMatch, onCreateLobby, onSubmitLobby,
}: {
    bracket: BracketData; isAdmin: boolean; canEdit: boolean; currentUserId?: string; actionLoading: string | null;
    onEditMatch: (match: MatchData) => void;
    onCreateLobby?: (id: string) => void;
    onSubmitLobby: (match: MatchData) => void;
}) {
    const standings = bracket.standings || [];
    const playoffRounds = bracket.playoff_rounds || [];

    // Construct a pseudo-bracket object for the BracketView if playoffs exist
    const playoffBracket: BracketData | null = playoffRounds.length > 0 ? {
        ...bracket,
        rounds: playoffRounds,
        total_rounds: playoffRounds.length,
    } : null;

    return (
        <div>
            {/* Standings Table */}
            <h3 style={{ fontWeight: 700, marginBottom: 12, fontSize: 18 }}>Standings</h3>
            <div style={{ overflowX: 'auto', marginBottom: 32 }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
                    <thead>
                        <tr style={{ borderBottom: '2px solid var(--border)' }}>
                            <th style={thStyle}>#</th>
                            <th style={{ ...thStyle, textAlign: 'left' }}>Player</th>
                            <th style={thStyle}>W</th>
                            <th style={thStyle}>L</th>
                            <th style={thStyle}>Pts</th>
                            <th style={thStyle}>Played</th>
                        </tr>
                    </thead>
                    <tbody>
                        {standings.map((s, i) => (
                            <tr key={s.user_id} style={{
                                borderBottom: '1px solid var(--border)',
                                background: i === 0 ? 'rgba(255,215,0,0.06)' : 'transparent',
                            }}>
                                <td style={tdStyle}>
                                    <span style={{
                                        fontWeight: 800, fontSize: 13,
                                        color: i === 0 ? 'var(--gold)' : i < 3 ? 'var(--neon-green)' : 'var(--text-muted)',
                                    }}>
                                        {i + 1}
                                    </span>
                                </td>
                                <td style={{ ...tdStyle, textAlign: 'left', fontWeight: 600, color: i === 0 ? 'var(--gold)' : 'var(--text-primary)' }}>
                                    {s.display_name}
                                </td>
                                <td style={{ ...tdStyle, color: 'var(--neon-green)' }}>{s.wins}</td>
                                <td style={{ ...tdStyle, color: 'var(--red)' }}>{s.losses}</td>
                                <td style={{ ...tdStyle, fontWeight: 700 }}>{s.points}</td>
                                <td style={tdStyle}>{s.matches_played}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Playoff Bracket (if active) */}
            {playoffBracket && (
                <div style={{ marginBottom: 40, padding: '24px', background: 'rgba(255,215,0,0.03)', borderRadius: 16, border: '1px solid rgba(255,215,0,0.1)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                        <h3 style={{ fontWeight: 800, fontSize: 22, color: 'var(--gold)', margin: 0 }}>Playoffs</h3>
                        <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--gold)', padding: '2px 8px', border: '1px solid var(--gold)', borderRadius: 4 }}>
                            Top 4
                        </span>
                    </div>
                    <BracketView
                        bracket={playoffBracket}
                        isAdmin={isAdmin}
                        canEdit={canEdit}
                        currentUserId={currentUserId}
                        actionLoading={actionLoading}
                        onCreateLobby={onCreateLobby || (() => { })}
                        onEditMatch={onEditMatch}
                        onSubmitLobby={onSubmitLobby}
                    />
                </div>
            )}

            {/* Group Stage Matches */}
            <h3 style={{ fontWeight: 700, marginBottom: 12, fontSize: 18 }}>Group Stage Matches</h3>
            {bracket.rounds.map(round => (
                <div key={round.round_number} style={{ marginBottom: 20 }}>
                    <h4 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 8 }}>{round.name}</h4>
                    <div style={{ display: 'grid', gap: 8, gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))' }}>
                        {round.matches.map(match => (
                            <RoundRobinMatchCard key={match.id} match={match} isAdmin={isAdmin} canEdit={canEdit} currentUserId={currentUserId} actionLoading={actionLoading} onEditMatch={onEditMatch} onCreateLobby={onCreateLobby} onSubmitLobby={onSubmitLobby} />
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
}

const thStyle: React.CSSProperties = { padding: '10px 12px', textAlign: 'center', fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' };
const tdStyle: React.CSSProperties = { padding: '10px 12px', textAlign: 'center' };

function RoundRobinMatchCard({
    match, canEdit, currentUserId, actionLoading, onEditMatch, onCreateLobby, onSubmitLobby,
}: {
    match: MatchData; isAdmin?: boolean; canEdit: boolean; currentUserId?: string; actionLoading: string | null;
    onEditMatch: (match: MatchData) => void;
    onCreateLobby?: (id: string) => void;
    onSubmitLobby: (match: MatchData) => void;
}) {
    const isActive = match.player1 && match.player2 && !match.winner;
    const isMatchParticipant = currentUserId && (match.player1?.id === currentUserId || match.player2?.id === currentUserId);
    const borderColor = match.winner ? 'rgba(57,255,20,0.3)' : isActive ? 'rgba(255,140,0,0.4)' : 'var(--border)';

    return (
        <div style={{
            background: 'var(--card-bg)', border: `1px solid ${borderColor}`,
            borderRadius: 10, padding: 12, display: 'flex', alignItems: 'center', gap: 12,
        }}>
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{
                    fontWeight: 600, fontSize: 13,
                    color: match.winner?.id === match.player1?.id ? 'var(--neon-green)' : 'var(--text-primary)',
                }}>
                    {match.player1?.display_name || 'TBD'}
                </span>
                <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 700 }}>vs</span>
                <span style={{
                    fontWeight: 600, fontSize: 13,
                    color: match.winner?.id === match.player2?.id ? 'var(--neon-green)' : 'var(--text-primary)',
                }}>
                    {match.player2?.display_name || 'TBD'}
                </span>
            </div>

            {match.score && (
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)' }}>{match.score}</span>
            )}

            {match.winner && !match.score && (
                <span style={{ fontSize: 11, color: 'var(--neon-green)', fontWeight: 600 }}>
                    {match.winner.display_name} W
                </span>
            )}

            {/* Lobby Link */}
            {match.cybershoke_lobby_url && !match.winner && (
                <a
                    href={match.cybershoke_lobby_url} target="_blank" rel="noopener noreferrer"
                    className="btn btn-sm"
                    style={{
                        fontSize: 10, padding: '4px 8px',
                        background: 'rgba(0,160,255,0.1)', color: '#00a0ff', border: '1px solid rgba(0,160,255,0.3)',
                        textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4
                    }}
                >
                    <span style={{ fontSize: 12 }}>🌐</span> Connect
                </a>
            )}

            {/* Participant: Submit Result */}
            {isMatchParticipant && isActive && (
                <button
                    className="btn btn-sm"
                    onClick={() => onSubmitLobby(match)}
                    style={{
                        fontSize: 10, padding: '4px 10px', flexShrink: 0,
                        background: 'rgba(57,255,20,0.1)', color: 'var(--neon-green)', border: '1px solid rgba(57,255,20,0.3)',
                    }}
                >
                    Submit Result
                </button>
            )}

            {/* Admin Actions */}
            {canEdit && isActive && !isMatchParticipant && (
                <div style={{ display: 'flex', gap: 6, marginLeft: 4 }}>
                    {onCreateLobby && !match.cybershoke_lobby_url && !match.winner && (
                        <button
                            className="btn btn-sm"
                            onClick={() => onCreateLobby(match.id)}
                            disabled={!!actionLoading}
                            style={{
                                fontSize: 10, padding: '4px 8px', flexShrink: 0,
                                background: 'rgba(255,140,0,0.1)', color: 'var(--orange)', border: '1px solid rgba(255,140,0,0.3)',
                                opacity: actionLoading ? 0.6 : 1, cursor: actionLoading ? 'not-allowed' : 'pointer',
                            }}
                        >
                            {actionLoading === match.id ? '...' : '+ Server'}
                        </button>
                    )}
                    {actionLoading !== match.id && (
                        <button
                            className="btn btn-sm"
                            onClick={() => onEditMatch(match)}
                            style={{ fontSize: 11, padding: '4px 10px', flexShrink: 0, opacity: 0.7 }}
                            title="Admin override"
                        >
                            Edit
                        </button>
                    )}
                </div>
            )}
        </div>
    );
}


// ──────────────────────────────────────────────
// BRACKET VIEW — Single Elimination Tree
// ──────────────────────────────────────────────

function BracketView({
    bracket, isAdmin, canEdit, currentUserId, actionLoading, onCreateLobby, onEditMatch, onSubmitLobby,
}: {
    bracket: BracketData; isAdmin: boolean; canEdit: boolean; currentUserId?: string; actionLoading: string | null;
    onCreateLobby: (id: string) => void; onEditMatch: (match: MatchData) => void; onSubmitLobby: (match: MatchData) => void;
}) {
    return (
        <div>
            <h2 style={{ fontWeight: 700, marginBottom: 16, fontSize: 20 }}>Bracket</h2>
            <div style={{ display: 'flex', gap: 0, overflowX: 'auto', paddingBottom: 16 }}>
                {bracket.rounds.map((round) => (
                    <BracketRound key={round.round_number} round={round} totalRounds={bracket.total_rounds}
                        isAdmin={isAdmin} canEdit={canEdit} currentUserId={currentUserId} actionLoading={actionLoading}
                        onCreateLobby={onCreateLobby} onEditMatch={onEditMatch} onSubmitLobby={onSubmitLobby}
                    />
                ))}
            </div>
        </div>
    );
}

function BracketRound({
    round, totalRounds, isAdmin, canEdit, currentUserId, actionLoading, onCreateLobby, onEditMatch, onSubmitLobby,
}: {
    round: RoundData; totalRounds: number; isAdmin: boolean; canEdit: boolean; currentUserId?: string; actionLoading: string | null;
    onCreateLobby: (id: string) => void; onEditMatch: (match: MatchData) => void; onSubmitLobby: (match: MatchData) => void;
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
                    <MatchCard key={match.id} match={match} isAdmin={isAdmin} canEdit={canEdit}
                        currentUserId={currentUserId} actionLoading={actionLoading} onCreateLobby={onCreateLobby}
                        onEditMatch={onEditMatch} onSubmitLobby={onSubmitLobby} isFinal={round.round_number === totalRounds}
                    />
                ))}
            </div>
        </div>
    );
}


function MatchCard({
    match, canEdit, currentUserId, actionLoading, onCreateLobby, onEditMatch, onSubmitLobby, isFinal,
}: {
    match: MatchData; isAdmin?: boolean; canEdit: boolean; currentUserId?: string; actionLoading: string | null;
    onCreateLobby: (id: string) => void; onEditMatch: (match: MatchData) => void; onSubmitLobby: (match: MatchData) => void;
    isFinal: boolean;
}) {
    const isActive = match.player1 && match.player2 && !match.winner;
    const isMatchParticipant = currentUserId && (match.player1?.id === currentUserId || match.player2?.id === currentUserId);
    const isBye = (match.player1 && !match.player2) || (!match.player1 && match.player2);
    const isLoading = actionLoading === match.id;
    const borderColor = match.winner ? 'rgba(57,255,20,0.3)' : isActive ? 'rgba(255,140,0,0.4)' : 'var(--border)';

    return (
        <div style={{
            background: 'var(--card-bg)', border: `1px solid ${borderColor}`,
            borderRadius: 10, padding: 12, margin: '0 8px', minWidth: 280,
            opacity: isBye && match.winner ? 0.6 : 1,
        }}>
            {isFinal && <div style={{ textAlign: 'center', fontSize: 20, marginBottom: 4 }}>🏆</div>}

            <PlayerSlot player={match.player1} isWinner={match.winner?.id === match.player1?.id} />

            <div style={{ textAlign: 'center', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', margin: '4px 0', letterSpacing: '0.1em' }}>
                {match.score ? match.score : 'VS'}
            </div>

            <PlayerSlot player={match.player2} isWinner={match.winner?.id === match.player2?.id} />

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

            {/* Participant: Submit Result */}
            {isMatchParticipant && isActive && !isLoading && (
                <button className="btn btn-sm" onClick={() => onSubmitLobby(match)} style={{
                    width: '100%', marginTop: 8, fontSize: 11, padding: '6px 8px',
                    background: 'rgba(57,255,20,0.1)', color: 'var(--neon-green)',
                    border: '1px solid rgba(57,255,20,0.3)',
                }}>
                    Submit Result
                </button>
            )}

            {/* Admin: fallback controls */}
            {canEdit && isActive && !isMatchParticipant && !isLoading && (
                <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                    {!match.cybershoke_lobby_url && (
                        <button className="btn btn-sm" onClick={() => onCreateLobby(match.id)} style={{
                            flex: 1, fontSize: 11, padding: '5px 8px',
                            background: 'rgba(0,160,255,0.15)', color: 'var(--blue)',
                            border: '1px solid rgba(0,160,255,0.3)',
                        }}>
                            Create Server
                        </button>
                    )}
                    <button className="btn btn-sm" onClick={() => onEditMatch(match)} style={{
                        flex: 1, fontSize: 11, padding: '5px 8px', opacity: 0.7,
                        background: 'rgba(255,140,0,0.15)', color: 'var(--orange)',
                        border: '1px solid rgba(255,140,0,0.3)',
                    }}
                        title="Admin override"
                    >
                        Edit Match
                    </button>
                </div>
            )}

            {isLoading && <div style={{ textAlign: 'center', marginTop: 8, fontSize: 12, color: 'var(--text-muted)' }}>Loading...</div>}
        </div>
    );
}


function PlayerSlot({ player, isWinner }: { player: PlayerInfo | null; isWinner: boolean }) {
    if (!player) {
        return (
            <div style={{
                padding: '10px 12px', borderRadius: 6,
                background: '#111', border: '1px dashed var(--border)',
                color: 'var(--text-muted)', fontSize: 13, textAlign: 'center',
            }}>BYE</div>
        );
    }

    const stat = getMainStatDisplay(player.stats);
    const line = getStatLine(player.stats);

    return (
        <div style={{
            padding: '8px 12px', borderRadius: 6,
            background: isWinner ? 'rgba(57,255,20,0.12)' : '#111',
            border: `1px solid ${isWinner ? 'rgba(57,255,20,0.4)' : 'transparent'}`,
        }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{
                    width: 26, height: 26, borderRadius: '50%', flexShrink: 0,
                    background: isWinner ? 'var(--neon-green)' : 'var(--card-hover)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 10, fontWeight: 800, color: isWinner ? '#000' : 'var(--text-secondary)',
                }}>
                    {isWinner ? '✓' : player.display_name[0]?.toUpperCase()}
                </div>
                <span style={{
                    fontSize: 13, fontWeight: isWinner ? 700 : 500,
                    color: isWinner ? 'var(--neon-green)' : 'var(--text-primary)',
                    flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                    {player.display_name}
                </span>
                {stat && (
                    <span style={{
                        fontSize: 12, fontWeight: 800, color: stat.color, flexShrink: 0,
                        background: `${stat.color}15`, padding: '2px 6px', borderRadius: 4,
                    }}>
                        {stat.value}
                    </span>
                )}
            </div>
            {line && (
                <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3, marginLeft: 34 }}>
                    {line}
                </div>
            )}
        </div>
    );
}

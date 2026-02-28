'use client';
import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '@/context/AuthContext';
import { getPingColor } from '@/lib/utils';
import {
    getDraftState, getConstants, captainClaim,
    getCaptainState, submitVote, vetoAction, broadcastToDiscord
} from '../lib/api';

interface DraftInfo {
    team1: string[];
    team2: string[];
    name_a: string;
    name_b: string;
    avg1: number;
    avg2: number;
    map_pick?: string;
    lobby_link?: string;
    mode?: string;
    ratings?: Record<string, number>;
    pings?: Record<string, number>;
    rerolls_remaining?: number;
}

interface VetoInfo {
    initialized: boolean;
    remaining: string[];
    protected: string[];
    picked: string[];
    turn_team: string;
    complete: boolean;
}

interface CaptainSession {
    captain_name: string;
    pin: string;
    current_vote: string;
    draft: DraftInfo | null;
    all_votes: Array<{ captain_name: string; vote: string; pin: string }>;
    veto: VetoInfo | null;
    pings?: Record<string, number>;
}

export default function CaptainPage() {
    const { user, token, loading: authLoading } = useAuth();

    // Draft preview state (shown to everyone immediately)
    const [draftState, setDraftState] = useState<any>(null);
    const [draftLoading, setDraftLoading] = useState(true);
    const [constants, setConstants] = useState<{ map_pool: string[]; map_logos: Record<string, string> }>({ map_pool: [], map_logos: {} });
    const [lobbyLink, setLobbyLink] = useState('');

    // Captain session state (only after stepping in)
    const [session, setSession] = useState<CaptainSession | null>(null);
    const [steppingIn, setSteppingIn] = useState(false);
    const [error, setError] = useState('');
    const [actionLoading, setActionLoading] = useState(false);
    const [broadcasting, setBroadcasting] = useState(false);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    // ─── LOAD DRAFT STATE + CONSTANTS ON MOUNT ───────────
    useEffect(() => {
        const loadDraft = async () => {
            try {
                const [draft, consts] = await Promise.all([
                    getDraftState(token || undefined),
                    getConstants()
                ]);
                if (draft.active) {
                    setDraftState(draft);
                    if (draft.lobby_link) setLobbyLink(draft.lobby_link);
                }
                setConstants(consts);
            } catch {
                // No active draft
            }
            setDraftLoading(false);
        };
        loadDraft();
    }, [token]);

    // ─── AUTO-RECOVER: If user is already a captain, restore their session ───
    useEffect(() => {
        if (authLoading || !user) return;
        // Always verify captain state — even if session exists — to detect draft changes
        getCaptainState(user.display_name)
            .then(state => {
                if (state?.pin && state?.draft) {
                    const isInDraft = state.draft.team1?.includes(user.display_name) ||
                        state.draft.team2?.includes(user.display_name);
                    if (isInDraft) {
                        setSession(state);
                    } else {
                        setSession(null);
                    }
                } else {
                    // Captain state returned but no valid draft — clear session
                    setSession(null);
                }
            })
            .catch(() => {
                // Not a captain (401) — clear any stale session
                setSession(null);
            });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [user, authLoading]);

    // ─── POLL FOR STATE UPDATES ──────────────────────────
    const pollState = useCallback(async () => {
        if (!session) return;
        try {
            // Also check if the draft itself has changed
            const currentDraft = await getDraftState(token || undefined);
            if (!currentDraft.active) {
                // Draft was cleared — reset everything
                setSession(null);
                setDraftState(null);
                setError('');
                return;
            }

            // Check if this is a different draft (teams changed)
            const sessionDraft = session.draft;
            if (sessionDraft) {
                const teamsChanged =
                    JSON.stringify(currentDraft.team1?.sort()) !== JSON.stringify(sessionDraft.team1?.slice().sort()) ||
                    JSON.stringify(currentDraft.team2?.sort()) !== JSON.stringify(sessionDraft.team2?.slice().sort());
                if (teamsChanged) {
                    // New draft detected — clear captain session and refresh draft state
                    setSession(null);
                    setDraftState(currentDraft);
                    setError('');
                    return;
                }
            }

            // Update the preview draft state
            setDraftState(currentDraft);
            if (currentDraft.lobby_link) setLobbyLink(currentDraft.lobby_link);

            const state = await getCaptainState(session.captain_name);
            const anyReroll = state.all_votes?.some((v: { vote: string }) => v.vote === 'Reroll');
            if (anyReroll) {
                setTimeout(async () => {
                    setSession(null);
                    setError('');
                    try {
                        const draft = await getDraftState(token || undefined);
                        if (draft.active) setDraftState(draft);
                    } catch { /* ignore */ }
                }, 1500);
                return;
            }
            setSession(prev => prev ? { ...prev, ...state } : null);
        } catch {
            setSession(null);
            setError('');
            try {
                const draft = await getDraftState(token || undefined);
                if (draft.active) setDraftState(draft);
                else setDraftState(null);
            } catch { /* ignore */ }
        }
    }, [session, token]);

    useEffect(() => {
        if (!session) return;
        pollRef.current = setInterval(pollState, 2000);
        return () => { if (pollRef.current) clearInterval(pollRef.current); };
    }, [session, pollState]);

    // Also poll draft state while viewing (before stepping in) so it stays fresh
    useEffect(() => {
        if (session || draftLoading) return;
        const interval = setInterval(async () => {
            try {
                const draft = await getDraftState(token || undefined);
                if (draft.active) {
                    setDraftState(draft);
                    if (draft.lobby_link) setLobbyLink(draft.lobby_link);
                } else {
                    setDraftState(null);
                    setSession(null);
                }
            } catch { /* ignore */ }
        }, 3000);
        return () => clearInterval(interval);
    }, [session, draftLoading, token]);

    // ─── STEP IN AS CAPTAIN ──────────────────────────────
    const handleStepIn = async () => {
        if (!user) return;
        setSteppingIn(true);
        setError('');
        try {
            const state = await captainClaim(user.display_name);
            setSession(state);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Could not step in as captain');
        }
        setSteppingIn(false);
    };

    // ─── VOTE (Approve / Reroll) ─────────────────────────
    const handleVote = async (vote: string) => {
        if (!session) return;
        setActionLoading(true);
        setError('');
        try {
            await submitVote({ token: session.pin, vote });
            if (vote === 'Reroll') {
                setTimeout(async () => {
                    setSession(null);
                    try {
                        const draft = await getDraftState(token || undefined);
                        if (draft.active) setDraftState(draft);
                    } catch { /* ignore */ }
                    setActionLoading(false);
                }, 1000);
                return;
            }
            const state = await getCaptainState(session.captain_name);
            setSession(state);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Vote failed');
        }
        setActionLoading(false);
    };

    // ─── VETO (Map Pick/Ban) ─────────────────────────────
    const handleVetoPick = async (mapName: string) => {
        if (!session || !session.veto) return;
        setActionLoading(true);
        setError('');
        try {
            await vetoAction({ map_name: mapName, acting_team: session.veto.turn_team });
            const state = await getCaptainState(session.captain_name);
            setSession(state);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Veto action failed');
        }
        setActionLoading(false);
    };

    // ─── BROADCAST TO DISCORD ────────────────────────────
    const handleBroadcast = async () => {
        if (!session?.draft) return;
        setBroadcasting(true);
        setError('');
        try {
            const draft = session.draft;
            const maps = draft.map_pick || session.veto?.picked?.join(',') || '';
            const link = lobbyLink || draft.lobby_link || '';
            await broadcastToDiscord({
                name_a: draft.name_a,
                team1: draft.team1,
                name_b: draft.name_b,
                team2: draft.team2,
                maps,
                lobby_link: link,
            }, token || undefined);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to send to Discord');
        }
        setBroadcasting(false);
    };

    // ─── LOADING ─────────────────────────────────────────
    if (authLoading || draftLoading) {
        return (
            <div className="page-container">
                <div className="loading-spinner"><div className="spinner" /></div>
            </div>
        );
    }

    // ─── NO ACTIVE DRAFT ─────────────────────────────────
    if (!draftState) {
        return (
            <div className="page-container">
                <div style={{ textAlign: 'center', padding: 60 }}>
                    <div style={{ fontSize: 48, marginBottom: 16 }}>⏳</div>
                    <h2 className="font-orbitron" style={{ marginBottom: 8 }}>No Active Draft</h2>
                    <p style={{ color: 'var(--text-secondary)' }}>There&apos;s no draft running right now. Check back when the host starts one.</p>
                </div>
            </div>
        );
    }

    // ─── CAPTAIN DASHBOARD (after stepping in) ───────────
    if (session && session.draft) {
        const draft = session.draft;
        const myTeamName = draft.team1.includes(session.captain_name) ? draft.name_a : draft.name_b;
        const myTeam = draft.team1.includes(session.captain_name) ? draft.team1 : draft.team2;
        const oppTeam = draft.team1.includes(session.captain_name) ? draft.team2 : draft.team1;
        const oppTeamName = myTeamName === draft.name_a ? draft.name_b : draft.name_a;
        const myColor = myTeamName === draft.name_a ? 'var(--blue)' : 'var(--orange)';
        const oppColor = myTeamName === draft.name_a ? 'var(--orange)' : 'var(--blue)';
        const total = draft.avg1 + draft.avg2;
        const pct1 = total > 0 ? (draft.avg1 / total) * 100 : 50;

        const allVotes = session.all_votes || [];
        const bothApproved = allVotes.length === 2 && allVotes.every(v => v.vote === 'Approve');
        const anyReroll = allVotes.some(v => v.vote === 'Reroll');
        const otherCaptain = allVotes.find(v => v.captain_name !== session.captain_name);
        const isMyTurn = session.veto && session.veto.turn_team === myTeamName;
        const pickedMaps = session.veto?.picked || session.veto?.protected || [];
        const isPickPhase = pickedMaps.length < 2;
        const isAdmin = user?.role === 'admin';
        const vetoComplete = session.veto?.complete || !!draft.map_pick;

        // Parse final maps in play order
        const finalMaps: string[] = [];
        if (draft.map_pick) {
            finalMaps.push(...draft.map_pick.split(',').map((m: string) => m.trim()));
        } else if (session.veto?.complete && pickedMaps.length > 0) {
            finalMaps.push(...pickedMaps);
        }

        return (
            <div className="page-container">
                {/* Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
                    <div>
                        <h1 className="page-title">👑 {session.captain_name}</h1>
                        <p className="page-subtitle">Captain of <span style={{ color: myColor, fontWeight: 700 }}>{myTeamName}</span></p>
                    </div>
                    <button className="btn btn-sm" onClick={() => setSession(null)}>← Leave</button>
                </div>

                {error && <div className="error-message">{error}</div>}

                {/* Team comparison bar */}
                <div style={{ marginBottom: 24 }}>
                    <div className="comparison-labels">
                        <span className="text-blue">{draft.name_a} — {draft.avg1.toFixed(1)}</span>
                        <span className="text-orange">{draft.name_b} — {draft.avg2.toFixed(1)}</span>
                    </div>
                    <div className="comparison-bar">
                        <div className="comparison-bar-fill-blue" style={{ width: `${pct1}%` }} />
                        <div className="comparison-bar-fill-orange" style={{ width: `${100 - pct1}%` }} />
                    </div>
                </div>

                {/* Teams side by side */}
                <div className="grid-2" style={{ marginBottom: 32 }}>
                    <div className="card" style={{ border: `2px solid ${myColor}` }}>
                        <div className="team-header" style={{ color: myColor, borderColor: myColor }}>
                            👑 {myTeamName} (YOUR TEAM)
                        </div>
                        {myTeam.map(p => (
                            <div key={p} className={`player-chip ${p === session.captain_name ? 'selected' : ''}`}>
                                {p === session.captain_name && <span className="player-chip-crown">👑</span>}
                                <span style={{ fontWeight: p === session.captain_name ? 700 : 500 }}>{p}</span>
                                {session.pings?.[p] != null && (
                                    <span style={{ fontSize: 10, color: getPingColor(session.pings[p]), marginLeft: 'auto' }}>
                                        {session.pings[p]}ms
                                    </span>
                                )}
                            </div>
                        ))}
                    </div>
                    <div className="card">
                        <div className="team-header" style={{ color: oppColor, borderColor: oppColor }}>
                            {oppTeamName}
                        </div>
                        {oppTeam.map(p => (
                            <div key={p} className="player-chip">
                                <span>{p}</span>
                                {session.pings?.[p] != null && (
                                    <span style={{ fontSize: 10, color: getPingColor(session.pings[p]), marginLeft: 'auto' }}>
                                        {session.pings[p]}ms
                                    </span>
                                )}
                            </div>
                        ))}
                    </div>
                </div>

                {/* ─── PHASE 1: VOTING (Approve/Reroll) ─── */}
                {session.current_vote === 'Waiting' && !anyReroll && (
                    <div className="card" style={{ textAlign: 'center', padding: 32, marginBottom: 32, border: '2px solid var(--gold)' }}>
                        <h2 className="font-orbitron" style={{ fontSize: 20, color: 'var(--gold)', marginBottom: 8 }}>⚖️ APPROVE THESE TEAMS?</h2>
                        <p style={{ color: 'var(--text-secondary)', marginBottom: 20 }}>Both captains must approve to proceed to map picks</p>

                        {otherCaptain && (
                            <div style={{ marginBottom: 20, padding: '8px 16px', background: 'var(--bg-glass)', borderRadius: 'var(--radius-md)', display: 'inline-block' }}>
                                {otherCaptain.vote === 'Waiting' ? (
                                    <span style={{ color: 'var(--text-muted)' }}>⏳ {otherCaptain.captain_name} hasn&apos;t voted yet</span>
                                ) : otherCaptain.vote === 'Approve' ? (
                                    <span className="text-neon">✅ {otherCaptain.captain_name} approved</span>
                                ) : (
                                    <span style={{ color: 'var(--red)' }}>❌ A reroll has been requested</span>
                                )}
                            </div>
                        )}

                        <div className="grid-2">
                            <button className="btn btn-primary btn-block" onClick={() => handleVote('Approve')} disabled={actionLoading} style={{ minHeight: 56, fontSize: 16 }}>
                                ✅ APPROVE
                            </button>
                            {(draft.rerolls_remaining ?? 3) > 0 ? (
                                <button className="btn btn-danger btn-block" onClick={() => handleVote('Reroll')} disabled={actionLoading} style={{ minHeight: 56, fontSize: 16 }}>
                                    ❌ REROLL ({draft.rerolls_remaining ?? 3} LEFT)
                                </button>
                            ) : (
                                <button className="btn btn-danger btn-block" disabled={true} style={{ minHeight: 56, fontSize: 16, opacity: 0.5 }}>
                                    ❌ 0 REROLLS LEFT
                                </button>
                            )}
                        </div>
                    </div>
                )}

                {/* Waiting for other captain to vote */}
                {session.current_vote === 'Approve' && !bothApproved && !anyReroll && (
                    <div className="card" style={{ textAlign: 'center', padding: 32, marginBottom: 32 }}>
                        <div style={{ fontSize: 40, marginBottom: 12 }}>✅</div>
                        <h3 className="font-orbitron text-neon" style={{ marginBottom: 8 }}>YOU APPROVED</h3>
                        <p style={{ color: 'var(--text-secondary)' }}>
                            ⏳ Waiting for <strong>{otherCaptain?.captain_name}</strong> to approve...
                        </p>
                        <div className="spinner" style={{ margin: '16px auto' }} />
                    </div>
                )}

                {/* Reroll requested */}
                {anyReroll && (
                    <div className="card" style={{ textAlign: 'center', padding: 32, marginBottom: 32, border: '2px solid var(--red)' }}>
                        <div style={{ fontSize: 40, marginBottom: 12 }}>🔄</div>
                        <h3 className="font-orbitron" style={{ color: 'var(--red)', marginBottom: 8 }}>REROLLING...</h3>
                        <p style={{ color: 'var(--text-secondary)' }}>New teams are being generated. You&apos;ll need to step in again.</p>
                        <p style={{ margin: '8px 0 0 0', fontWeight: 700, color: 'var(--gold)' }}>
                            {draft.rerolls_remaining ?? 3} Reroll{((draft.rerolls_remaining ?? 3) === 1) ? '' : 's'} Remaining
                        </p>
                        <div className="spinner" style={{ margin: '16px auto' }} />
                    </div>
                )}

                {/* ─── PHASE 2: VETO (Map Pick/Ban) ─── */}
                {bothApproved && !session.veto && !draft.map_pick && (
                    <div className="card" style={{ textAlign: 'center', padding: 32, marginBottom: 32 }}>
                        <div style={{ fontSize: 40, marginBottom: 12 }}>🪙</div>
                        <h3 className="font-orbitron text-gold" style={{ marginBottom: 8 }}>BOTH APPROVED!</h3>
                        <p style={{ color: 'var(--text-secondary)' }}>Coin flip in progress... Map picks starting soon.</p>
                        <div className="spinner" style={{ margin: '16px auto' }} />
                    </div>
                )}

                {/* Active Veto */}
                {session.veto && !session.veto.complete && session.veto.remaining.length > 0 && (
                    <div className="card" style={{ marginBottom: 32, border: isMyTurn ? '2px solid var(--neon-green)' : '1px solid var(--border)' }}>
                        <div className={`veto-turn-indicator ${isMyTurn
                            ? (isPickPhase ? 'veto-turn-protect' : 'veto-turn-ban')
                            : 'veto-turn-waiting'
                            }`}>
                            {isMyTurn ? (
                                isPickPhase
                                    ? `🗺️ YOUR TURN — PICK MAP ${pickedMaps.length + 1} TO PLAY`
                                    : '❌ YOUR TURN — BAN A MAP'
                            ) : (
                                `⏳ ${session.veto.turn_team} is choosing...`
                            )}
                        </div>

                        {/* Show picked maps */}
                        {pickedMaps.length > 0 && (
                            <div style={{ display: 'flex', gap: 12, marginBottom: 16, justifyContent: 'center' }}>
                                {pickedMaps.map((m, i) => (
                                    <div key={m} style={{
                                        display: 'flex', alignItems: 'center', gap: 8,
                                        padding: '8px 16px', background: 'var(--bg-glass)',
                                        borderRadius: 'var(--radius-md)', border: '1px solid var(--neon-green)',
                                    }}>
                                        <span style={{ color: 'var(--neon-green)', fontWeight: 700, fontSize: 12 }}>MAP {i + 1}</span>
                                        <img src={constants.map_logos[m]} alt={m} style={{ width: 32, height: 20, borderRadius: 4, objectFit: 'cover' }} />
                                        <span style={{ fontWeight: 600 }}>{m}</span>
                                    </div>
                                ))}
                            </div>
                        )}

                        {/* Map grid */}
                        <div className="grid-7">
                            {constants.map_pool.map(m => {
                                const isRemaining = session.veto!.remaining.includes(m);
                                const isPicked = pickedMaps.includes(m);
                                const isBanned = !isRemaining && !isPicked;
                                const canClick = isMyTurn && isRemaining && !isPicked;

                                return (
                                    <div
                                        key={m}
                                        className={`map-card ${isBanned ? 'banned' : ''} ${isPicked ? 'protected' : ''}`}
                                        onClick={() => canClick ? handleVetoPick(m) : null}
                                        style={{ cursor: canClick ? 'pointer' : 'default', opacity: actionLoading && canClick ? 0.5 : undefined }}
                                    >
                                        <img src={constants.map_logos[m]} alt={m} />
                                        <div className="map-card-name">{m}</div>
                                        {isBanned && <div className="banned-overlay">BANNED</div>}
                                        {isPicked && <div style={{ position: 'absolute', top: 4, right: 4, fontSize: 14, fontWeight: 700, color: 'var(--neon-green)' }}>MAP {pickedMaps.indexOf(m) + 1}</div>}
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}

                {/* ─── PHASE 3: VETO COMPLETE / MAPS SELECTED ─── */}
                {vetoComplete && (
                    <>
                        <div className="lobby-box" style={{ marginBottom: 24 }}>
                            <div className="lobby-box-title">🗺️ MAPS SELECTED</div>
                            <div style={{ display: 'flex', justifyContent: 'center', gap: 16, flexWrap: 'wrap', marginBottom: 16 }}>
                                {finalMaps.map((m, i) => (
                                    <div key={m} style={{ textAlign: 'center' }}>
                                        <div style={{ fontSize: 12, fontWeight: 700, color: i < 2 ? 'var(--neon-green)' : 'var(--gold)', marginBottom: 4 }}>
                                            {i < 2 ? `MAP ${i + 1}` : 'DECIDER'}
                                        </div>
                                        <img src={constants.map_logos[m]} alt={m} style={{ width: 140, borderRadius: 8 }} />
                                        <div className="font-orbitron" style={{ fontSize: 14, fontWeight: 700, marginTop: 4 }}>{m}</div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Lobby link — shown once available */}
                        {lobbyLink ? (
                            <div className="lobby-box" style={{ marginBottom: 24 }}>
                                <div className="lobby-box-title">🚀 LOBBY READY</div>
                                <p style={{ textAlign: 'center', color: 'var(--text-primary)', marginBottom: 16, fontSize: 18, fontWeight: 600 }}>
                                    ⚠️ EVERYONE JOIN THE SERVER NOW ⚠️
                                </p>
                                <div className="lobby-box-link">
                                    <a href={lobbyLink} target="_blank" rel="noopener noreferrer">{lobbyLink}</a>
                                </div>
                                <div className="lobby-box-password">🔑 Password: kimkim</div>
                                <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
                                    <a href={lobbyLink} target="_blank" rel="noopener noreferrer" className="btn btn-primary">JOIN SERVER</a>
                                    {isAdmin && (
                                        <button className="btn btn-primary" onClick={handleBroadcast} disabled={broadcasting}>
                                            {broadcasting ? '⏳ Sending...' : '📢 Send to Discord'}
                                        </button>
                                    )}
                                </div>
                            </div>
                        ) : (
                            <div style={{ textAlign: 'center', marginBottom: 24 }}>
                                <div className="spinner" style={{ margin: '0 auto 12px' }} />
                                <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>⏳ Creating lobby...</p>
                                {isAdmin && (
                                    <button className="btn btn-primary" onClick={handleBroadcast} disabled={broadcasting} style={{ marginTop: 16 }}>
                                        {broadcasting ? '⏳ Sending...' : '📢 Send to Discord'}
                                    </button>
                                )}
                            </div>
                        )}
                    </>
                )}
            </div>
        );
    }

    // ─── DRAFT PREVIEW (before stepping in as captain) ───
    const draft = draftState;
    const userTeam = user ? (
        draft.team1?.includes(user.display_name) ? draft.name_a :
            draft.team2?.includes(user.display_name) ? draft.name_b : null
    ) : null;
    const total = (draft.avg1 || 0) + (draft.avg2 || 0);
    const pct1 = total > 0 ? ((draft.avg1 || 0) / total) * 100 : 50;

    return (
        <div className="page-container">
            <div className="page-header">
                <h1 className="page-title">⚔️ Live Draft</h1>
                <p className="page-subtitle">
                    {userTeam
                        ? <>You&apos;re on <span style={{ fontWeight: 700, color: userTeam === draft.name_a ? 'var(--blue)' : 'var(--orange)' }}>{userTeam}</span></>
                        : 'View the current draft teams'
                    }
                </p>
            </div>

            {error && <div className="error-message" style={{ marginBottom: 16 }}>{error}</div>}

            {/* Comparison bar */}
            <div style={{ marginBottom: 24 }}>
                <div className="comparison-labels">
                    <span className="text-blue">{draft.name_a} — {Number(draft.avg1).toFixed(1)}</span>
                    <span className="text-orange">{draft.name_b} — {Number(draft.avg2).toFixed(1)}</span>
                </div>
                <div className="comparison-bar">
                    <div className="comparison-bar-fill-blue" style={{ width: `${pct1}%` }} />
                    <div className="comparison-bar-fill-orange" style={{ width: `${pct1 < 100 ? 100 - pct1 : 50}%` }} />
                </div>
            </div>

            {/* Team cards */}
            <div className="grid-2" style={{ marginBottom: 32 }}>
                {([
                    { raw: draft.team1, name: draft.name_a, colorClass: 'team-blue', icon: '🔵', borderColor: 'var(--blue)' },
                    { raw: draft.team2, name: draft.name_b, colorClass: 'team-orange', icon: '🔴', borderColor: 'var(--orange)' },
                ] as const).map(({ raw, name, colorClass, icon, borderColor }) => {
                    const sorted = raw ? [...raw].sort((a, b) => (draft.ratings?.[b] ?? 0) - (draft.ratings?.[a] ?? 0)) : [];
                    const isMyTeam = userTeam === name;
                    return (
                        <div key={name} className="card" style={isMyTeam ? { border: `2px solid ${borderColor}` } : {}}>
                            <div className={`team-header ${colorClass}`}>{icon} {name}</div>
                            {sorted.map((p: string) => (
                                <div key={p} className={`player-chip ${user?.display_name === p ? 'selected' : ''}`} style={{ justifyContent: 'space-between' }}>
                                    <span style={{ fontWeight: user?.display_name === p ? 700 : 500 }}>
                                        {user?.display_name === p ? '👤 ' : ''}{p}
                                    </span>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                        {draft.pings?.[p] != null && (
                                            <span style={{ fontSize: 10, color: getPingColor(draft.pings[p]) }}>
                                                {draft.pings[p]}ms
                                            </span>
                                        )}
                                        {draft.ratings?.[p] != null && (
                                            <span className="font-orbitron" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                                                {(draft.ratings[p] as number).toFixed(2)}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    );
                })}
            </div>

            {/* Step In as Captain button */}
            {user && userTeam && (
                <div className="card" style={{ maxWidth: 480, margin: '0 auto', textAlign: 'center', padding: 32 }}>
                    <div style={{ fontSize: 48, marginBottom: 12 }}>👑</div>
                    <h2 className="font-orbitron" style={{ fontSize: 18, marginBottom: 8 }}>Become Captain</h2>
                    <p style={{ color: 'var(--text-secondary)', marginBottom: 24, fontSize: '0.9rem' }}>
                        Step in as captain for <strong style={{ color: userTeam === draft.name_a ? 'var(--blue)' : 'var(--orange)' }}>{userTeam}</strong> to approve teams and pick maps
                    </p>

                    {user.captain_cooldown && user.captain_cooldown > 0 ? (
                        <>
                            <button
                                className="btn btn-primary btn-block"
                                disabled={true}
                                style={{ fontSize: 16, padding: '14px 0', opacity: 0.5, cursor: 'not-allowed' }}
                            >
                                ⏳ COOLDOWN ({user.captain_cooldown} DRAFTS)
                            </button>
                            <p style={{ color: 'var(--red)', marginTop: 12, fontSize: 13, fontWeight: 500 }}>
                                You are banned from captaincy for {user.captain_cooldown} more draft{user.captain_cooldown > 1 ? 's' : ''}.
                            </p>
                        </>
                    ) : (
                        <button
                            className="btn btn-primary btn-block"
                            onClick={handleStepIn}
                            disabled={steppingIn}
                            style={{ fontSize: 16, padding: '14px 0' }}
                        >
                            {steppingIn ? '⏳ Stepping in...' : '👑 STEP IN AS CAPTAIN'}
                        </button>
                    )}
                </div>
            )}

            {/* Not in this draft */}
            {user && !userTeam && (
                <div className="card" style={{ maxWidth: 480, margin: '0 auto', textAlign: 'center', padding: 32, opacity: 0.7 }}>
                    <div style={{ fontSize: 36, marginBottom: 8 }}>👁️</div>
                    <p style={{ color: 'var(--text-secondary)' }}>
                        You&apos;re not in this draft — viewing as spectator
                    </p>
                </div>
            )}

            {/* Not logged in */}
            {!user && (
                <div className="card" style={{ maxWidth: 480, margin: '0 auto', textAlign: 'center', padding: 32, opacity: 0.7 }}>
                    <div style={{ fontSize: 36, marginBottom: 8 }}>🔑</div>
                    <p style={{ color: 'var(--text-secondary)' }}>
                        Sign in to step in as captain
                    </p>
                </div>
            )}
        </div>
    );
}

'use client';
import { useState, useEffect, useRef, useCallback } from 'react';
import { captainLogin, getCaptainState, submitVote, vetoAction, getConstants } from '../lib/api';

interface DraftInfo {
    team1: string[];
    team2: string[];
    name_a: string;
    name_b: string;
    avg1: number;
    avg2: number;
    map_pick?: string;
}

interface VetoInfo {
    initialized: boolean;
    remaining: string[];
    protected: string[];
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
}

export default function CaptainPage() {
    const [name, setName] = useState('');
    const [session, setSession] = useState<CaptainSession | null>(null);
    const [constants, setConstants] = useState<{ map_pool: string[]; map_logos: Record<string, string> }>({ map_pool: [], map_logos: {} });
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const [loginLoading, setLoginLoading] = useState(false);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    // Load constants once
    useEffect(() => {
        getConstants().then(setConstants).catch(() => { });
    }, []);

    // Poll for state updates when logged in
    const pollState = useCallback(async () => {
        if (!session) return;
        try {
            const state = await getCaptainState(session.captain_name);
            setSession(prev => prev ? { ...prev, ...state } : null);
        } catch { /* captain removed from draft */ }
    }, [session]);

    useEffect(() => {
        if (!session) return;
        pollRef.current = setInterval(pollState, 2000);
        return () => { if (pollRef.current) clearInterval(pollRef.current); };
    }, [session, pollState]);

    const handleLogin = async () => {
        if (!name.trim()) return;
        setLoginLoading(true);
        setError('');
        try {
            const res = await captainLogin(name.trim());
            // Now get full state
            const state = await getCaptainState(res.captain_name);
            setSession(state);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Login failed');
        }
        setLoginLoading(false);
    };

    const handleVote = async (vote: string) => {
        if (!session) return;
        setLoading(true);
        try {
            await submitVote({ token: session.pin, vote });
            const state = await getCaptainState(session.captain_name);
            setSession(state);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Vote failed');
        }
        setLoading(false);
    };

    const handleVetoPick = async (mapName: string) => {
        if (!session || !session.veto) return;
        setLoading(true);
        try {
            await vetoAction({ map_name: mapName, acting_team: session.veto.turn_team });
            const state = await getCaptainState(session.captain_name);
            setSession(state);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Veto action failed');
        }
        setLoading(false);
    };

    // ─── LOGIN SCREEN ────────────────────────
    if (!session) {
        return (
            <div className="page-container">
                <div style={{ maxWidth: 440, margin: '80px auto', textAlign: 'center' }}>
                    <div style={{ fontSize: 64, marginBottom: 16 }}>👑</div>
                    <h1 className="page-title" style={{ marginBottom: 8 }}>Captain Login</h1>
                    <p className="page-subtitle" style={{ marginBottom: 32 }}>Enter your player name to join the draft</p>

                    <input
                        className="input"
                        type="text"
                        placeholder="Your name (e.g. Skeez)"
                        value={name}
                        onChange={e => setName(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && handleLogin()}
                        style={{ marginBottom: 16, fontSize: 16, textAlign: 'center' }}
                        autoFocus
                    />
                    <button
                        className="btn btn-primary btn-block"
                        onClick={handleLogin}
                        disabled={loginLoading || !name.trim()}
                        style={{ fontSize: 16, padding: '14px 0' }}
                    >
                        {loginLoading ? '⏳ Logging in...' : '⚡ JOIN AS CAPTAIN'}
                    </button>
                    {error && (
                        <div style={{ marginTop: 16, padding: '12px 16px', background: 'rgba(255,68,68,0.1)', border: '1px solid rgba(255,68,68,0.3)', borderRadius: 'var(--radius-md)', color: 'var(--red)' }}>
                            {error}
                        </div>
                    )}
                </div>
            </div>
        );
    }

    // ─── CAPTAIN DASHBOARD ───────────────────
    const draft = session.draft;
    if (!draft) {
        return (
            <div className="page-container">
                <div style={{ textAlign: 'center', padding: 60 }}>
                    <div style={{ fontSize: 48, marginBottom: 16 }}>⏳</div>
                    <h2 style={{ fontFamily: 'Orbitron', marginBottom: 8 }}>Waiting for Draft</h2>
                    <p style={{ color: 'var(--text-secondary)' }}>No active draft found. The host needs to start it first.</p>
                    <button className="btn" onClick={() => setSession(null)} style={{ marginTop: 24 }}>← Back to Login</button>
                </div>
            </div>
        );
    }

    const myTeamName = draft.team1.includes(session.captain_name) ? draft.name_a : draft.name_b;
    const myTeam = draft.team1.includes(session.captain_name) ? draft.team1 : draft.team2;
    const oppTeam = draft.team1.includes(session.captain_name) ? draft.team2 : draft.team1;
    const oppTeamName = myTeamName === draft.name_a ? draft.name_b : draft.name_a;
    const myColor = myTeamName === draft.name_a ? 'var(--blue)' : 'var(--orange)';
    const oppColor = myTeamName === draft.name_a ? 'var(--orange)' : 'var(--blue)';
    const total = draft.avg1 + draft.avg2;
    const pct1 = total > 0 ? (draft.avg1 / total) * 100 : 50;

    // Check all votes status
    const allVotes = session.all_votes || [];
    const bothApproved = allVotes.length === 2 && allVotes.every(v => v.vote === 'Approve');
    const anyReroll = allVotes.some(v => v.vote === 'Reroll');
    const otherCaptain = allVotes.find(v => v.captain_name !== session.captain_name);
    const isMyTurn = session.veto && session.veto.turn_team === myTeamName;

    return (
        <div className="page-container">
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
                <div>
                    <h1 className="page-title">👑 {session.captain_name}</h1>
                    <p className="page-subtitle">Captain of <span style={{ color: myColor, fontWeight: 700 }}>{myTeamName}</span></p>
                </div>
                <button className="btn btn-sm" onClick={() => setSession(null)}>← Logout</button>
            </div>

            {error && <div style={{ padding: '12px 16px', background: 'rgba(255,68,68,0.1)', border: '1px solid rgba(255,68,68,0.3)', borderRadius: 'var(--radius-md)', color: 'var(--red)', marginBottom: 16 }}>{error}</div>}

            {/* Team comparison bar */}
            <div style={{ marginBottom: 24 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: 13, color: 'var(--text-secondary)' }}>
                    <span style={{ color: 'var(--blue)' }}>{draft.name_a} — {draft.avg1.toFixed(1)}</span>
                    <span style={{ color: 'var(--orange)' }}>{draft.name_b} — {draft.avg2.toFixed(1)}</span>
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
                        <div key={p} className="player-chip" style={{ background: p === session.captain_name ? 'rgba(0,229,0,0.08)' : undefined }}>
                            {p === session.captain_name && <span style={{ fontSize: 16 }}>👑</span>}
                            <span style={{ fontWeight: p === session.captain_name ? 700 : 500 }}>{p}</span>
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
                        </div>
                    ))}
                </div>
            </div>

            {/* ─── PHASE 1: VOTING (Approve/Reroll) ─── */}
            {session.current_vote === 'Waiting' && !anyReroll && (
                <div className="card" style={{ textAlign: 'center', padding: 32, marginBottom: 32, border: '2px solid var(--gold)' }}>
                    <h2 style={{ fontFamily: 'Orbitron', fontSize: 20, color: 'var(--gold)', marginBottom: 8 }}>⚖️ APPROVE THESE TEAMS?</h2>
                    <p style={{ color: 'var(--text-secondary)', marginBottom: 20 }}>Both captains must approve to proceed to map veto</p>

                    {otherCaptain && (
                        <div style={{ marginBottom: 20, padding: '8px 16px', background: 'var(--bg-glass)', borderRadius: 'var(--radius-md)', display: 'inline-block' }}>
                            {otherCaptain.vote === 'Waiting' ? (
                                <span style={{ color: 'var(--text-muted)' }}>⏳ {otherCaptain.captain_name} hasn&apos;t voted yet</span>
                            ) : otherCaptain.vote === 'Approve' ? (
                                <span style={{ color: 'var(--neon-green)' }}>✅ {otherCaptain.captain_name} approved</span>
                            ) : (
                                <span style={{ color: 'var(--red)' }}>❌ {otherCaptain.captain_name} wants a reroll</span>
                            )}
                        </div>
                    )}

                    <div className="grid-2">
                        <button className="btn btn-primary btn-block" onClick={() => handleVote('Approve')} disabled={loading} style={{ minHeight: 56, fontSize: 16 }}>
                            ✅ APPROVE
                        </button>
                        <button className="btn btn-danger btn-block" onClick={() => handleVote('Reroll')} disabled={loading} style={{ minHeight: 56, fontSize: 16 }}>
                            ❌ REROLL
                        </button>
                    </div>
                </div>
            )}

            {/* Waiting for other captain to vote */}
            {session.current_vote === 'Approve' && !bothApproved && !anyReroll && (
                <div className="card" style={{ textAlign: 'center', padding: 32, marginBottom: 32 }}>
                    <div style={{ fontSize: 40, marginBottom: 12 }}>✅</div>
                    <h3 style={{ fontFamily: 'Orbitron', color: 'var(--neon-green)', marginBottom: 8 }}>YOU APPROVED</h3>
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
                    <h3 style={{ fontFamily: 'Orbitron', color: 'var(--red)', marginBottom: 8 }}>REROLL REQUESTED</h3>
                    <p style={{ color: 'var(--text-secondary)' }}>The host is generating new teams. Please wait...</p>
                    <div className="spinner" style={{ margin: '16px auto' }} />
                </div>
            )}

            {/* ─── PHASE 2: VETO (Map Pick/Ban) ─── */}
            {bothApproved && !session.veto && !draft.map_pick && (
                <div className="card" style={{ textAlign: 'center', padding: 32, marginBottom: 32 }}>
                    <div style={{ fontSize: 40, marginBottom: 12 }}>🪙</div>
                    <h3 style={{ fontFamily: 'Orbitron', color: 'var(--gold)', marginBottom: 8 }}>BOTH APPROVED!</h3>
                    <p style={{ color: 'var(--text-secondary)' }}>Waiting for the host to start the coin flip &amp; veto...</p>
                    <div className="spinner" style={{ margin: '16px auto' }} />
                </div>
            )}

            {/* Active Veto */}
            {session.veto && !session.veto.complete && session.veto.remaining.length > 0 && (
                <div className="card" style={{ marginBottom: 32, border: isMyTurn ? '2px solid var(--neon-green)' : '1px solid var(--border)' }}>
                    <div style={{
                        padding: '12px 20px',
                        borderRadius: 'var(--radius-sm)',
                        marginBottom: 20,
                        textAlign: 'center',
                        fontSize: 18,
                        fontFamily: 'Orbitron',
                        fontWeight: 700,
                        background: isMyTurn
                            ? ((session.veto.protected?.length || 0) < 2 ? 'rgba(0,229,0,0.15)' : 'rgba(255,68,68,0.15)')
                            : 'var(--bg-glass)',
                        color: isMyTurn
                            ? ((session.veto.protected?.length || 0) < 2 ? 'var(--neon-green)' : 'var(--red)')
                            : 'var(--text-muted)',
                    }}>
                        {isMyTurn ? (
                            (session.veto.protected?.length || 0) < 2
                                ? '🛡️ YOUR TURN — PROTECT A MAP'
                                : '❌ YOUR TURN — BAN A MAP'
                        ) : (
                            `⏳ ${session.veto.turn_team} is choosing...`
                        )}
                    </div>

                    {/* Show protected maps */}
                    {session.veto.protected && session.veto.protected.length > 0 && (
                        <div style={{ display: 'flex', gap: 8, marginBottom: 16, justifyContent: 'center' }}>
                            {session.veto.protected.map(m => (
                                <div key={m} style={{ padding: '6px 14px', background: 'rgba(0,229,0,0.1)', border: '1px solid rgba(0,229,0,0.3)', borderRadius: 'var(--radius-sm)', color: 'var(--neon-green)', fontSize: 13, fontWeight: 600 }}>
                                    🛡️ {m}
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Map grid */}
                    <div className="grid-7">
                        {constants.map_pool.map(m => {
                            const isRemaining = session.veto!.remaining.includes(m);
                            const isProtected = session.veto!.protected?.includes(m);
                            const isBanned = !isRemaining && !isProtected;
                            const canClick = isMyTurn && isRemaining && !isProtected;

                            return (
                                <div
                                    key={m}
                                    className={`map-card ${isBanned ? 'banned' : ''} ${isProtected ? 'protected' : ''}`}
                                    onClick={() => canClick ? handleVetoPick(m) : null}
                                    style={{ cursor: canClick ? 'pointer' : 'default', opacity: loading && canClick ? 0.5 : undefined }}
                                >
                                    <img src={constants.map_logos[m]} alt={m} />
                                    <div className="map-card-name">{m}</div>
                                    {isBanned && <div className="banned-overlay">BANNED</div>}
                                    {isProtected && <div style={{ position: 'absolute', top: 4, right: 4, fontSize: 18 }}>🛡️</div>}
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* ─── PHASE 3: VETO COMPLETE / MAP SELECTED ─── */}
            {(session.veto?.complete || draft.map_pick) && (
                <div className="lobby-box" style={{ marginBottom: 32 }}>
                    <div className="lobby-box-title">🗺️ MAP SELECTED</div>
                    <div style={{ fontSize: 28, fontWeight: 800, fontFamily: 'Orbitron', color: 'var(--gold)', marginBottom: 16 }}>
                        {draft.map_pick || session.veto?.protected?.join(', ')}
                    </div>
                    {(draft.map_pick || '').split(',').map(m => (
                        <img key={m.trim()} src={constants.map_logos[m.trim()]} alt={m.trim()} style={{ width: '100%', maxWidth: 300, borderRadius: 8, marginTop: 8 }} />
                    ))}
                    <p style={{ color: 'var(--text-secondary)', marginTop: 16 }}>🎮 Get ready to play!</p>
                </div>
            )}
        </div>
    );
}

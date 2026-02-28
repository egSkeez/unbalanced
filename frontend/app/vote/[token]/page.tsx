'use client';
import { useState, useEffect, use } from 'react';
import { getCaptainInfo, submitVote, getVetoState, vetoAction, getDraftState, getConstants } from '../../lib/api';
import PlayerStatsModal from '@/components/PlayerStatsModal';

export default function VotePage({ params }: { params: Promise<{ token: string }> }) {
    const resolvedParams = use(params);
    const token = resolvedParams.token;
    const [captainName, setCaptainName] = useState('');
    const [currentVote, setCurrentVote] = useState('');
    const [draft, setDraft] = useState<{ team1: string[]; team2: string[]; name_a: string; name_b: string; ratings?: Record<string, number>; votes?: Array<{ vote: string }>; rerolls_remaining?: number } | null>(null);
    const [veto, setVeto] = useState<{ initialized: boolean; remaining?: string[]; protected?: string[]; turn_team?: string; complete?: boolean }>({ initialized: false });
    const [mapLogos, setMapLogos] = useState<Record<string, string>>({});
    const [mapPick, setMapPick] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(true);
    const [submitted, setSubmitted] = useState(false);
    const [viewingPlayer, setViewingPlayer] = useState<string | null>(null);

    useEffect(() => {
        const load = async () => {
            try {
                const [info, constants] = await Promise.all([getCaptainInfo(token), getConstants()]);
                setCaptainName(info.captain_name);
                setCurrentVote(info.current_vote);
                setDraft(info.draft);
                setMapLogos(constants.map_logos || {});
            } catch (e: unknown) {
                setError(e instanceof Error ? e.message : 'Token expired or invalid');
            }
            setLoading(false);
        };
        load();
    }, [token]);

    // Poll veto state
    useEffect(() => {
        if (!captainName || currentVote === 'Waiting') return;
        const poll = setInterval(async () => {
            try {
                const v = await getVetoState();
                setVeto(v);
                if (v.complete) {
                    const d = await getDraftState();
                    if (d.map_pick) setMapPick(d.map_pick);
                }
                const info = await getCaptainInfo(token);
                setDraft(info.draft);
            } catch { /* ignore */ }
        }, 2000);
        return () => clearInterval(poll);
    }, [captainName, currentVote, token]);

    const handleVote = async (vote: string) => {
        await submitVote({ token, vote });
        setCurrentVote(vote);
        if (vote === 'Reroll') setSubmitted(true);
    };

    const handleVetoPick = async (mapName: string) => {
        try {
            const result = await vetoAction({ map_name: mapName, acting_team: veto.turn_team || '' });
            if (result.complete) {
                setVeto({ initialized: true, remaining: [], protected: result.final_maps, complete: true });
                setMapPick(result.final_maps.join(','));
            } else {
                setVeto({
                    initialized: true,
                    remaining: result.remaining,
                    protected: result.protected,
                    turn_team: result.next_turn,
                    complete: false,
                });
            }
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Veto failed');
        }
    };

    if (loading) return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}><div className="spinner" /></div>;

    if (error) {
        return (
            <div style={{ padding: 32, textAlign: 'center', maxWidth: 400, margin: '0 auto' }}>
                <h2 style={{ color: 'var(--red)', marginBottom: 12 }}>❌ Token Expired</h2>
                <p style={{ color: 'var(--text-secondary)' }}>Please scan the new QR code on the host screen.</p>
            </div>
        );
    }

    if (submitted) {
        return (
            <div style={{ padding: 32, textAlign: 'center', maxWidth: 400, margin: '0 auto' }}>
                <h2 style={{ color: 'var(--neon-green)', marginBottom: 12 }}>✅ Reroll Requested</h2>
                <p style={{ color: 'var(--text-secondary)' }}>The draft is being reset. Scan the NEW QR code.</p>
            </div>
        );
    }

    const myTeamName = draft ? (draft.team1.includes(captainName) ? draft.name_a : draft.name_b) : '';

    return (
        <div style={{ padding: 20, maxWidth: 480, margin: '0 auto' }}>
            <h2 style={{ textAlign: 'center', color: 'var(--gold)', fontFamily: 'Orbitron', marginBottom: 20 }}>
                👑 {captainName}
            </h2>

            {/* Reroll Notification */}
            {draft?.votes?.some(v => v.vote === 'Reroll' || v.vote === 'BANNED') && (
                <div className="reroll-banner" style={{ marginBottom: 20 }}>
                    <span style={{ fontSize: 18 }}>🎲</span>
                    <div style={{ fontSize: 13 }}>
                        <strong>REROLL IN PROGRESS</strong>
                        <p style={{ margin: '4px 0 0 0', fontWeight: 700, color: 'var(--gold)' }}>
                            {draft?.rerolls_remaining ?? 3} Reroll{((draft?.rerolls_remaining ?? 3) === 1) ? '' : 's'} Remaining
                        </p>
                    </div>
                </div>
            )}

            {/* Teams */}
            {draft && (
                <div className="grid-2" style={{ marginBottom: 20 }}>
                    {[1, 2].map(teamNum => {
                        const isTeam1 = teamNum === 1;
                        const name = isTeam1 ? draft.name_a : draft.name_b;
                        const rawPlayers = isTeam1 ? draft.team1 : draft.team2;
                        const players = [...rawPlayers].sort((a, b) => (draft.ratings?.[b] || 0) - (draft.ratings?.[a] || 0));
                        const color = isTeam1 ? 'var(--blue)' : 'var(--orange)';

                        return (
                            <div key={teamNum} className="card" style={{ padding: 12, border: `1px solid ${color}` }}>
                                <div style={{ fontWeight: 700, color: color, marginBottom: 8, fontSize: 14 }}>{isTeam1 ? '🔵' : '🔴'} {name}</div>
                                {players.map((p, idx) => (
                                    <div
                                        key={p}
                                        className="stagger-in"
                                        style={{
                                            fontSize: 12,
                                            padding: '6px 0',
                                            display: 'flex',
                                            justifyContent: 'space-between',
                                            animationDelay: `${idx * 0.1}s`,
                                            cursor: 'pointer',
                                            borderBottom: idx === players.length - 1 ? 'none' : '1px solid rgba(255,255,255,0.03)'
                                        }}
                                        onClick={() => setViewingPlayer(p)}
                                    >
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                            <span>{p}</span>
                                            <span style={{ fontSize: 10, opacity: 0.4 }}>📊</span>
                                        </div>
                                        <span style={{ opacity: 0.6, fontSize: 10 }}>{(draft.ratings?.[p] || 0).toFixed(2)}</span>
                                    </div>
                                ))}
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Voting buttons */}
            {currentVote === 'Waiting' && (
                <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
                    <button className="btn btn-primary" onClick={() => handleVote('Approve')} style={{ flex: 1, padding: 16 }}>✅ Approve</button>
                    {(draft?.rerolls_remaining ?? 3) > 0 ? (
                        <button className="btn btn-secondary" onClick={() => handleVote('Reroll')} style={{ flex: 1, padding: 16, background: 'rgba(255,68,68,0.1)', color: 'var(--red)', borderColor: 'var(--red)' }}>🎲 Reroll ({(draft?.rerolls_remaining ?? 3)} LEFT)</button>
                    ) : (
                        <button className="btn btn-secondary" disabled={true} style={{ flex: 1, padding: 16, background: 'rgba(255,68,68,0.1)', color: 'var(--red)', borderColor: 'var(--red)', opacity: 0.5 }}>❌ 0 REROLLS LEFT</button>
                    )}
                </div>
            )}

            {/* Veto Section */}
            {currentVote === 'Approve' && (
                <div className="card" style={{ padding: 20 }}>
                    <h3 style={{ marginBottom: 16, textAlign: 'center', fontSize: 16, color: 'var(--blue)' }}>🗺️ Map Veto</h3>

                    {!veto.initialized ? (
                        <div style={{ textAlign: 'center', padding: 20 }}>
                            <div className="spinner" style={{ margin: '0 auto 12px' }} />
                            <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>Waiting for other captain...</p>
                        </div>
                    ) : veto.complete ? (
                        <div style={{ textAlign: 'center' }}>
                            <div style={{ padding: 12, background: 'rgba(0,229,0,0.1)', borderRadius: 8, marginBottom: 16 }}>
                                <div style={{ fontSize: 12, textTransform: 'uppercase', marginBottom: 4 }}>Map Selected</div>
                                <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--neon-green)', fontFamily: 'Orbitron' }}>{mapPick}</div>
                            </div>
                            <img src={mapLogos[mapPick] || `/maps/${mapPick?.toLowerCase()}.jpg`} style={{ width: '100%', borderRadius: 8, border: '1px solid var(--border)' }} />
                        </div>
                    ) : (
                        <div>
                            <div style={{ marginBottom: 16, textAlign: 'center' }}>
                                <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4 }}>Turn</div>
                                <div style={{ fontSize: 16, fontWeight: 700, color: veto.turn_team === myTeamName ? 'var(--neon-green)' : 'var(--text-muted)' }}>
                                    {veto.turn_team === myTeamName ? '👉 YOUR TURN' : '⌛ Waiting for Enemy...'}
                                </div>
                            </div>

                            <div className="grid-2" style={{ gap: 12 }}>
                                {veto.remaining?.map(m => (
                                    <button
                                        key={m}
                                        className="btn btn-sm"
                                        disabled={veto.turn_team !== myTeamName}
                                        onClick={() => handleVetoPick(m)}
                                        style={{ height: 40, fontSize: 12 }}
                                    >
                                        BANNED {m}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Veto complete */}
            {(veto.complete || mapPick) && (
                <div className="lobby-box" style={{ marginTop: 20 }}>
                    <div className="lobby-box-title">✅ VETO COMPLETE</div>
                    <div style={{ fontFamily: 'Orbitron', fontSize: 24, color: 'var(--gold)', fontWeight: 800, marginBottom: 12 }}>
                        {mapPick || veto.protected?.join(', ')}
                    </div>
                    {(mapPick || '').split(',').map(m => (
                        <img key={m.trim()} src={mapLogos[m.trim()] || ''} alt={m.trim()} style={{ width: '100%', borderRadius: 8, marginTop: 8 }} />
                    ))}
                </div>
            )}
        </div>
    );
}

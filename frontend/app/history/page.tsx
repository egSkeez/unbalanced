'use client';
import { useState, useEffect } from 'react';
import { getRecentMatches, getMatchScoreboard } from '../lib/api';

export default function HistoryPage() {
    const [matches, setMatches] = useState<Array<Record<string, string | number>>>([]);
    const [expandedMatch, setExpandedMatch] = useState('');
    const [scoreboard, setScoreboard] = useState<Array<Record<string, string | number>>>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        getRecentMatches(30).then(m => { setMatches(m); setLoading(false); }).catch(() => setLoading(false));
    }, []);

    const toggleMatch = async (matchId: string) => {
        if (expandedMatch === matchId) {
            setExpandedMatch('');
            return;
        }
        setExpandedMatch(matchId);
        const sb = await getMatchScoreboard(matchId);
        setScoreboard(sb);
    };

    if (loading) return <div className="page-container"><div className="loading-spinner"><div className="spinner" /></div></div>;

    return (
        <div className="page-container">
            <div className="page-header">
                <h1 className="page-title">📜 Match History</h1>
                <p className="page-subtitle">{matches.length} matches recorded</p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {matches.map(m => {
                    const isExpanded = expandedMatch === String(m.match_id);
                    const team2 = scoreboard.filter(p => Number(p.player_team) === 2);
                    const team3 = scoreboard.filter(p => Number(p.player_team) === 3);

                    return (
                        <div key={String(m.match_id)} className="card" style={{ cursor: 'pointer' }}>
                            <div onClick={() => toggleMatch(String(m.match_id))} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                                    <span style={{ fontSize: 24 }}>🗺️</span>
                                    <div>
                                        <div style={{ fontWeight: 700, fontSize: 16 }}>{String(m.map)}</div>
                                        <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>{String(m.date_analyzed || '').split('T')[0]}</div>
                                    </div>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                                    <div style={{ fontFamily: 'Orbitron', fontSize: 20, fontWeight: 700 }}>{String(m.score)}</div>
                                    {m.lobby_url && (
                                        <a href={String(m.lobby_url)} target="_blank" rel="noopener noreferrer" className="btn btn-sm" onClick={e => e.stopPropagation()}>
                                            🔗 Lobby
                                        </a>
                                    )}
                                    <span style={{ color: 'var(--text-muted)' }}>{isExpanded ? '▲' : '▼'}</span>
                                </div>
                            </div>

                            {isExpanded && scoreboard.length > 0 && (
                                <div style={{ marginTop: 20 }}>
                                    <div className="divider" />
                                    <div className="grid-2">
                                        {/* Team 2 (T) */}
                                        <div>
                                            <div className="team-header team-blue">🔵 Team 1 (T-Side)</div>
                                            <table className="data-table">
                                                <thead>
                                                    <tr><th>Player</th><th>K</th><th>D</th><th>A</th><th>ADR</th><th>Rating</th></tr>
                                                </thead>
                                                <tbody>
                                                    {team2.map((p, i) => (
                                                        <tr key={i}>
                                                            <td style={{ fontWeight: 600 }}>{String(p.player_name)}</td>
                                                            <td>{String(p.kills)}</td>
                                                            <td>{String(p.deaths)}</td>
                                                            <td>{String(p.assists)}</td>
                                                            <td>{Number(p.adr || 0).toFixed(1)}</td>
                                                            <td style={{ color: 'var(--neon-green)', fontWeight: 700 }}>{Number(p.rating || 0).toFixed(2)}</td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>

                                        {/* Team 3 (CT) */}
                                        <div>
                                            <div className="team-header team-orange">🔴 Team 2 (CT-Side)</div>
                                            <table className="data-table">
                                                <thead>
                                                    <tr><th>Player</th><th>K</th><th>D</th><th>A</th><th>ADR</th><th>Rating</th></tr>
                                                </thead>
                                                <tbody>
                                                    {team3.map((p, i) => (
                                                        <tr key={i}>
                                                            <td style={{ fontWeight: 600 }}>{String(p.player_name)}</td>
                                                            <td>{String(p.kills)}</td>
                                                            <td>{String(p.deaths)}</td>
                                                            <td>{String(p.assists)}</td>
                                                            <td>{Number(p.adr || 0).toFixed(1)}</td>
                                                            <td style={{ color: 'var(--neon-green)', fontWeight: 700 }}>{Number(p.rating || 0).toFixed(2)}</td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

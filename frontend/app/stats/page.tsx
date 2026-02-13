'use client';
import { useState, useEffect } from 'react';
import { getLeaderboard, getPlayerStats, getPlayerMatches, getSeasons } from '../lib/api';

export default function StatsPage() {
    const [seasons, setSeasons] = useState<Record<string, { start: string | null; end: string | null }>>({});
    const [season, setSeason] = useState('Season 2 (Demos)');
    const [leaderboard, setLeaderboard] = useState<{ mode: string; data: Array<Record<string, number | string>> }>({ mode: '', data: [] });
    const [selectedPlayer, setSelectedPlayer] = useState('');
    const [playerStats, setPlayerStats] = useState<Record<string, number | string>[]>([]);
    const [playerMatches, setPlayerMatches] = useState<Array<Record<string, string | number>>>([]);
    const [tab, setTab] = useState<'leaderboard' | 'player' | 'matches'>('leaderboard');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        getSeasons().then(s => {
            setSeasons({ ...s.all, 'All Time': { start: null, end: null } });
        });
    }, []);

    useEffect(() => {
        setLoading(true);
        getLeaderboard(season).then(d => { setLeaderboard(d); setLoading(false); }).catch(() => setLoading(false));
    }, [season]);

    const loadPlayer = async (name: string) => {
        setSelectedPlayer(name);
        setTab('player');
        const [stats, matches] = await Promise.all([
            getPlayerStats(name, season),
            getPlayerMatches(name, season),
        ]);
        setPlayerStats(stats);
        setPlayerMatches(matches);
    };

    const podiumColors = ['linear-gradient(135deg, #FFD700 0%, #B8860B 100%)', 'linear-gradient(135deg, #C0C0C0 0%, #808080 100%)', 'linear-gradient(135deg, #CD7F32 0%, #8B4513 100%)'];
    const podiumIcons = ['👑', '🥈', '🥉'];

    return (
        <div className="page-container">
            <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                    <h1 className="page-title">📊 Stats</h1>
                    <p className="page-subtitle">Player performance & leaderboards</p>
                </div>
                <select className="select" style={{ width: 220 }} value={season} onChange={e => setSeason(e.target.value)}>
                    {Object.keys(seasons).map(s => <option key={s} value={s}>{s}</option>)}
                </select>
            </div>

            {/* Tabs */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
                {(['leaderboard', 'player', 'matches'] as const).map(t => (
                    <button key={t} className={`btn btn-sm ${tab === t ? 'btn-primary' : ''}`} onClick={() => setTab(t)}>
                        {t === 'leaderboard' ? '🏆 Leaderboard' : t === 'player' ? '👤 Player Stats' : '📋 Matches'}
                    </button>
                ))}
            </div>

            {loading && <div className="loading-spinner"><div className="spinner" /></div>}

            {/* LEADERBOARD TAB */}
            {!loading && tab === 'leaderboard' && (
                <>
                    {/* Top 3 Podium */}
                    {leaderboard.data.slice(0, 3).map((p, i) => (
                        <div key={String(p.player_name)} className="podium-card" style={{ background: podiumColors[i], cursor: 'pointer' }} onClick={() => loadPlayer(String(p.player_name))}>
                            <h2>{podiumIcons[i]} #{i + 1} — {String(p.player_name)}</h2>
                            <div className="podium-metrics">
                                <div className="stat-card">
                                    <div className="stat-card-label">Rating</div>
                                    <div className="stat-card-value">{Number(p.rating || p.overall || 0).toFixed(2)}</div>
                                </div>
                                <div className="stat-card">
                                    <div className="stat-card-label">K/D</div>
                                    <div className="stat-card-value">{Number(p.kd_ratio || 0).toFixed(2)}</div>
                                </div>
                                <div className="stat-card">
                                    <div className="stat-card-label">ADR</div>
                                    <div className="stat-card-value">{Number(p.avg_adr || 0).toFixed(1)}</div>
                                </div>
                                <div className="stat-card">
                                    <div className="stat-card-label">Win%</div>
                                    <div className="stat-card-value">{Number(p.winrate || 0).toFixed(0)}%</div>
                                </div>
                            </div>
                        </div>
                    ))}

                    {/* Full table */}
                    <div className="card" style={{ marginTop: 24 }}>
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>Player</th>
                                    <th>Rating</th>
                                    <th>K/D</th>
                                    <th>ADR</th>
                                    <th>HS%</th>
                                    <th>Matches</th>
                                    <th>Win%</th>
                                </tr>
                            </thead>
                            <tbody>
                                {leaderboard.data.map((p, i) => (
                                    <tr key={String(p.player_name)} style={{ cursor: 'pointer' }} onClick={() => loadPlayer(String(p.player_name))}>
                                        <td style={{ fontWeight: 700, color: i < 3 ? 'var(--gold)' : 'var(--text-secondary)' }}>{i + 1}</td>
                                        <td style={{ fontWeight: 600 }}>{String(p.player_name)}</td>
                                        <td style={{ color: 'var(--neon-green)', fontWeight: 700 }}>{Number(p.rating || p.overall || 0).toFixed(2)}</td>
                                        <td>{Number(p.kd_ratio || 0).toFixed(2)}</td>
                                        <td>{Number(p.avg_adr || 0).toFixed(1)}</td>
                                        <td>{Number(p.avg_hs_pct || 0).toFixed(0)}%</td>
                                        <td>{String(p.matches || p.Matches || 0)}</td>
                                        <td>{Number(p.winrate || 0).toFixed(0)}%</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </>
            )}

            {/* PLAYER STATS TAB */}
            {!loading && tab === 'player' && selectedPlayer && playerStats.length > 0 && (
                <div>
                    <h2 style={{ fontFamily: 'Orbitron', fontSize: 22, marginBottom: 24 }}>👤 {selectedPlayer}</h2>
                    {playerStats.map((s, idx) => {
                        const matches = Number(s.matches_played || 0);
                        const wins = Number(s.wins || 0);
                        const losses = Number(s.losses || 0);
                        const winrate = Number(s.winrate_pct || 0);
                        return (
                            <div key={idx}>
                                <div className="grid-4" style={{ marginBottom: 24 }}>
                                    <div className="stat-card"><div className="stat-card-icon">⭐</div><div className="stat-card-label">Rating</div><div className="stat-card-value">{Number(s.avg_rating || 0).toFixed(2)}</div></div>
                                    <div className="stat-card"><div className="stat-card-icon">🎯</div><div className="stat-card-label">K/D</div><div className="stat-card-value">{Number(s.overall_kd || 0).toFixed(2)}</div></div>
                                    <div className="stat-card"><div className="stat-card-icon">💥</div><div className="stat-card-label">ADR</div><div className="stat-card-value">{Number(s.avg_adr || 0).toFixed(1)}</div></div>
                                    <div className="stat-card"><div className="stat-card-icon">🎯</div><div className="stat-card-label">HS%</div><div className="stat-card-value">{Number(s.avg_hs_pct || 0).toFixed(0)}%</div></div>
                                </div>
                                <div className="grid-4" style={{ marginBottom: 24 }}>
                                    <div className="stat-card"><div className="stat-card-icon">🎮</div><div className="stat-card-label">Matches</div><div className="stat-card-value">{matches}</div></div>
                                    <div className="stat-card"><div className="stat-card-icon">🏆</div><div className="stat-card-label">Wins</div><div className="stat-card-value" style={{ color: '#2ecc71' }}>{wins}</div></div>
                                    <div className="stat-card"><div className="stat-card-icon">💀</div><div className="stat-card-label">Losses</div><div className="stat-card-value" style={{ color: '#e74c3c' }}>{losses}</div></div>
                                    <div className="stat-card"><div className="stat-card-icon">📈</div><div className="stat-card-label">Win Rate</div><div className="stat-card-value">{winrate.toFixed(0)}%</div></div>
                                </div>
                                <div className="grid-4" style={{ marginBottom: 24 }}>
                                    <div className="stat-card"><div className="stat-card-icon">⚔️</div><div className="stat-card-label">Total Kills</div><div className="stat-card-value">{String(s.total_kills || 0)}</div></div>
                                    <div className="stat-card"><div className="stat-card-icon">👑</div><div className="stat-card-label">Entry Kills</div><div className="stat-card-value">{String(s.total_entry_kills || 0)}</div></div>
                                    <div className="stat-card"><div className="stat-card-icon">🔥</div><div className="stat-card-label">Clutches</div><div className="stat-card-value">{String(s.total_clutches || 0)}</div></div>
                                    <div className="stat-card"><div className="stat-card-icon">🔦</div><div className="stat-card-label">Flashes</div><div className="stat-card-value">{String(s.total_enemies_flashed || 0)}</div></div>
                                </div>
                            </div>
                        );
                    })}

                    {/* Match history */}
                    <h3 style={{ fontFamily: 'Orbitron', fontSize: 16, marginBottom: 16 }}>Recent Matches</h3>
                    <div className="card">
                        <table className="data-table">
                            <thead>
                                <tr><th>Map</th><th>Score</th><th>Result</th><th>Rating</th><th>K</th><th>D</th><th>ADR</th><th>Date</th></tr>
                            </thead>
                            <tbody>
                                {playerMatches.map((m, i) => (
                                    <tr key={i}>
                                        <td>{String(m.map)}</td>
                                        <td>{String(m.score)}</td>
                                        <td><span className={`badge badge-${m.result === 'W' ? 'win' : m.result === 'L' ? 'loss' : 'draw'}`}>{String(m.result)}</span></td>
                                        <td style={{ color: 'var(--neon-green)', fontWeight: 700 }}>{Number(m.rating || 0).toFixed(2)}</td>
                                        <td>{String(m.kills)}</td>
                                        <td>{String(m.deaths)}</td>
                                        <td>{Number(m.adr || 0).toFixed(1)}</td>
                                        <td style={{ color: 'var(--text-muted)' }}>{String(m.date)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {!loading && tab === 'player' && !selectedPlayer && (
                <div className="card" style={{ textAlign: 'center', padding: 48, color: 'var(--text-secondary)' }}>
                    Click a player from the leaderboard to view their stats
                </div>
            )}

            {/* RECENT MATCHES TAB */}
            {!loading && tab === 'matches' && (
                <div className="card">
                    <table className="data-table">
                        <thead>
                            <tr><th>Map</th><th>Score</th><th>Result</th><th>Rating</th><th>K</th><th>D</th><th>ADR</th><th>Date</th></tr>
                        </thead>
                        <tbody>
                            {playerMatches.map((m, i) => (
                                <tr key={i}>
                                    <td>{String(m.map)}</td>
                                    <td>{String(m.score)}</td>
                                    <td><span className={`badge badge-${m.result === 'W' ? 'win' : m.result === 'L' ? 'loss' : 'draw'}`}>{String(m.result)}</span></td>
                                    <td style={{ color: 'var(--neon-green)', fontWeight: 700 }}>{Number(m.rating || 0).toFixed(2)}</td>
                                    <td>{String(m.kills)}</td>
                                    <td>{String(m.deaths)}</td>
                                    <td>{Number(m.adr || 0).toFixed(1)}</td>
                                    <td style={{ color: 'var(--text-muted)' }}>{String(m.date)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}

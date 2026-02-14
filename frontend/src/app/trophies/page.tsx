'use client';
import { useState, useEffect } from 'react';
import { getSeasonTrophies, getRecentMatches, getMatchTrophies } from '../lib/api';

interface Trophy {
    title: string;
    icon: string;
    player: string;
    value: string | number;
    unit: string;
    gradient: string;
    color: string;
}

export default function TrophiesPage() {
    const [tab, setTab] = useState<'season' | 'match'>('season');
    const [seasonData, setSeasonData] = useState<{
        season: string; trophies: Trophy[]; rankings: Array<Record<string, number | string>>;
    }>({ season: '', trophies: [], rankings: [] });
    const [matches, setMatches] = useState<Array<Record<string, string>>>([]);
    const [selectedMatch, setSelectedMatch] = useState('');
    const [matchData, setMatchData] = useState<{ trophies: Trophy[]; scoreboard: Array<Record<string, string | number>> }>({ trophies: [], scoreboard: [] });
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        getSeasonTrophies().then(d => { setSeasonData(d); setLoading(false); }).catch(() => setLoading(false));
        getRecentMatches(30).then(setMatches).catch(() => { });
    }, []);

    const loadMatch = async (matchId: string) => {
        setSelectedMatch(matchId);
        setLoading(true);
        const data = await getMatchTrophies(matchId);
        setMatchData(data);
        setLoading(false);
    };

    return (
        <div className="page-container">
            <div className="page-header">
                <h1 className="page-title">🏆 Hall of Fame</h1>
                <p className="page-subtitle">{seasonData.season || 'Season awards & match trophies'}</p>
            </div>

            <div style={{ display: 'flex', gap: 8, marginBottom: 32 }}>
                <button className={`btn btn-sm ${tab === 'season' ? 'btn-primary' : ''}`} onClick={() => setTab('season')}>
                    🏅 Season Trophies
                </button>
                <button className={`btn btn-sm ${tab === 'match' ? 'btn-primary' : ''}`} onClick={() => setTab('match')}>
                    🎮 Match Analysis
                </button>
            </div>

            {loading && <div className="loading-spinner"><div className="spinner" /></div>}

            {/* SEASON TROPHIES */}
            {!loading && tab === 'season' && (
                <>
                    <div className="grid-4" style={{ marginBottom: 40 }}>
                        {seasonData.trophies.map((t, i) => (
                            <div key={i} className="trophy-card">
                                <div className="trophy-card-bar" style={{ background: t.gradient }} />
                                <div className="trophy-card-icon">{t.icon}</div>
                                <div className="trophy-card-title">{t.title}</div>
                                <div className="trophy-card-player">{t.player}</div>
                                <div className="trophy-card-value" style={{ color: t.color }}>
                                    {t.value} {t.unit}
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Season rankings table */}
                    {seasonData.rankings.length > 0 && (
                        <div className="card">
                            <div className="card-header">📊 Season Rankings</div>
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>#</th><th>Player</th><th>Rating</th><th>K/D</th><th>ADR</th>
                                        <th>HS%</th><th>Entries</th><th>Clutches</th><th>Win%</th><th>Matches</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {seasonData.rankings.map((p, i) => (
                                        <tr key={String(p.player_name)}>
                                            <td style={{ fontWeight: 700, color: i < 3 ? 'var(--gold)' : 'var(--text-secondary)' }}>{i + 1}</td>
                                            <td style={{ fontWeight: 600 }}>{String(p.player_name)}</td>
                                            <td style={{ color: 'var(--neon-green)', fontWeight: 700 }}>{Number(p.avg_rating || 0).toFixed(2)}</td>
                                            <td>{Number(p.kd || 0).toFixed(2)}</td>
                                            <td>{Number(p.avg_adr || 0).toFixed(1)}</td>
                                            <td>{Number(p.avg_hs_pct || 0).toFixed(0)}%</td>
                                            <td>{Number(p.avg_entries || 0).toFixed(1)}</td>
                                            <td>{String(p.total_clutches || 0)}</td>
                                            <td>{Number(p.winrate || 0).toFixed(0)}%</td>
                                            <td>{String(p.matches_played || 0)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </>
            )}

            {/* MATCH ANALYSIS */}
            {!loading && tab === 'match' && (
                <div className="grid-2" style={{ alignItems: 'start' }}>
                    {/* Match selector */}
                    <div className="card" style={{ maxHeight: 500, overflowY: 'auto' }}>
                        <div className="card-header">Select a Match</div>
                        {matches.map((m) => (
                            <div
                                key={m.match_id}
                                className={`player-chip ${selectedMatch === m.match_id ? 'selected' : ''}`}
                                style={{ marginBottom: 8 }}
                                onClick={() => loadMatch(m.match_id)}
                            >
                                <div>
                                    <div style={{ fontWeight: 600 }}>{m.map} — {m.score}</div>
                                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{m.date_analyzed?.split('T')[0] || ''}</div>
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Match trophies */}
                    <div>
                        {selectedMatch && matchData.trophies.length > 0 && (
                            <>
                                <div className="grid-3" style={{ marginBottom: 24 }}>
                                    {matchData.trophies.map((t, i) => (
                                        <div key={i} className="trophy-card">
                                            <div className="trophy-card-bar" style={{ background: t.gradient }} />
                                            <div className="trophy-card-icon">{t.icon}</div>
                                            <div className="trophy-card-title">{t.title}</div>
                                            <div className="trophy-card-player">{t.player}</div>
                                            <div className="trophy-card-value" style={{ color: t.color }}>
                                                {t.value} {t.unit}
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                <div className="card">
                                    <div className="card-header">Scoreboard</div>
                                    <table className="data-table">
                                        <thead>
                                            <tr>
                                                <th>Player</th><th>Rating</th><th>K</th><th>D</th><th>A</th><th>ADR</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {matchData.scoreboard.map((p, i) => (
                                                <tr key={i}>
                                                    <td style={{ fontWeight: 600 }}>{String(p.player_name)}</td>
                                                    <td style={{ color: 'var(--neon-green)', fontWeight: 700 }}>{Number(p.rating || 0).toFixed(2)}</td>
                                                    <td>{String(p.kills)}</td>
                                                    <td>{String(p.deaths)}</td>
                                                    <td>{String(p.assists)}</td>
                                                    <td>{Number(p.adr || 0).toFixed(1)}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </>
                        )}

                        {selectedMatch && matchData.trophies.length === 0 && !loading && (
                            <div className="card" style={{ textAlign: 'center', padding: 48, color: 'var(--text-secondary)' }}>
                                No trophy data available for this match
                            </div>
                        )}

                        {!selectedMatch && (
                            <div className="card" style={{ textAlign: 'center', padding: 48, color: 'var(--text-secondary)' }}>
                                Select a match to view its trophies
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

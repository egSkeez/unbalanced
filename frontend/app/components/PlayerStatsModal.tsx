'use client';
import { useState, useEffect } from 'react';
import { getPlayerStats } from '../lib/api';

interface PlayerStatsModalProps {
    playerName: string;
    onClose: () => void;
}

export default function PlayerStatsModal({ playerName, onClose }: PlayerStatsModalProps) {
    const [stats, setStats] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        getPlayerStats(playerName)
            .then(res => {
                setStats(res[0] || null);
                setLoading(false);
            })
            .catch(() => setLoading(false));
    }, [playerName]);

    // Close on backdrop click
    const handleBackdropClick = (e: React.MouseEvent) => {
        if (e.target === e.currentTarget) onClose();
    };

    return (
        <div className="modal-backdrop" onClick={handleBackdropClick}>
            <div className="modal-content player-modal stagger-in">
                <button className="modal-close" onClick={onClose}>&times;</button>

                <div className="modal-header">
                    <div className="player-avatar-container">
                        <div className="player-avatar-large">
                            {playerName[0].toUpperCase()}
                        </div>
                        {stats?.rank && (
                            <div className="rank-badge">#{stats.rank}</div>
                        )}
                    </div>
                    <h2 className="modal-title">{playerName}</h2>
                    <p className="modal-subtitle">
                        {stats?.rank ? `${stats.rank}${getOrdinal(stats.rank)} Ranked` : 'Season 2 Performance'}
                    </p>
                </div>


                {loading ? (
                    <div className="loading-spinner"><div className="spinner" /></div>
                ) : stats ? (
                    <div className="modal-body">
                        <div className="stats-grid-compact">
                            {[
                                { label: 'Rating', value: stats.avg_rating, icon: '⭐', color: 'var(--gold)' },
                                { label: 'K/D Ratio', value: stats.overall_kd, icon: '🎯', color: 'var(--neon-green)' },
                                { label: 'ADR', value: stats.avg_adr, icon: '💥', color: 'var(--blue)' },
                                { label: 'Win Rate', value: stats.winrate_pct + '%', icon: '🏆', color: 'var(--purple)' },
                                { label: 'Matches', value: stats.matches_played, icon: '🎮', color: 'var(--text-secondary)' },
                                { label: 'HS %', value: stats.avg_hs_pct + '%', icon: '🤯', color: 'var(--orange)' },
                            ].map(s => (
                                <div key={s.label} className="stat-card-mini">
                                    <span className="stat-icon">{s.icon}</span>
                                    <div className="stat-info">
                                        <div className="stat-value" style={{ color: s.color }}>
                                            {typeof s.value === 'number' ? s.value.toFixed(2) : s.value}
                                        </div>
                                        <div className="stat-label">{s.label}</div>
                                    </div>
                                </div>
                            ))}
                        </div>

                        <div className="divider" style={{ margin: '16px 0' }} />

                        <div className="extended-stats">
                            <div className="stat-row">
                                <span>Entry Kills</span>
                                <span className="val">{stats.total_entry_kills}</span>
                            </div>
                            <div className="stat-row">
                                <span>Utility Damage</span>
                                <span className="val">{Math.round(stats.total_util_dmg)}</span>
                            </div>
                            <div className="stat-row">
                                <span>Clutches Won</span>
                                <span className="val">{stats.total_clutches}</span>
                            </div>
                            <div className="stat-row">
                                <span>Enemies Flashed</span>
                                <span className="val">{stats.total_enemies_flashed}</span>
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="modal-body" style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)' }}>
                        No stats found for this player.
                    </div>
                )}
            </div>
        </div>
    );
}

function getOrdinal(n: number) {
    const s = ["th", "st", "nd", "rd"],
        v = n % 100;
    return s[(v - 20) % 10] || s[v] || s[0];
}

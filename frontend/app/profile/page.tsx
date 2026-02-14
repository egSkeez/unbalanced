"use client";

import { useAuth } from "@/context/AuthContext";
import { useEffect, useState } from "react";
import axios from "axios";
import { useRouter } from "next/navigation";
import { getPingColor } from "@/lib/utils";

export default function ProfilePage() {
    const { user, logout, loading, refreshUser } = useAuth();
    const router = useRouter();
    const [stats, setStats] = useState<any>(null);

    useEffect(() => {
        if (!loading && !user) {
            router.push("/login");
        }
    }, [user, loading, router]);

    useEffect(() => {
        if (user) {
            const fetchStats = async () => {
                try {
                    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
                    const { data } = await axios.get(`${apiBase}/api/auth/me/stats`);
                    setStats(data);
                } catch (e) {
                    console.error("Failed to fetch stats", e);
                }
            };
            fetchStats();
        }
    }, [user]);

    if (loading || !user) {
        return (
            <div className="page-container">
                <div className="loading-spinner"><div className="spinner" /></div>
            </div>
        );
    }

    return (
        <div className="page-container">
            {/* Header */}
            <div className="profile-header">
                <div>
                    <div className="profile-name">
                        {user.display_name}
                        {user.ping && (
                            <span
                                className="badge"
                                style={{
                                    color: getPingColor(user.ping),
                                    borderColor: getPingColor(user.ping),
                                    backgroundColor: `${getPingColor(user.ping)}10`,
                                    marginLeft: 12,
                                    fontSize: '0.75rem',
                                    fontFamily: "'Orbitron', sans-serif",
                                    verticalAlign: 'middle',
                                }}
                            >
                                {user.ping}ms
                            </span>
                        )}
                    </div>
                    <p className="profile-username">@{user.username}</p>
                </div>
                <button onClick={logout} className="btn btn-danger">Sign out</button>
            </div>

            {/* Info Grid */}
            <div className="grid-2" style={{ marginBottom: '2rem' }}>
                <div className="profile-card">
                    <h2 className="profile-card-title">Account Details</h2>
                    <div className="profile-detail-row">
                        <span className="profile-detail-label">Role</span>
                        <span style={{ textTransform: 'capitalize' }}>{user.role}</span>
                    </div>
                    <div className="profile-detail-row">
                        <span className="profile-detail-label">Status</span>
                        <span className={user.is_active ? "text-neon" : ""} style={{ color: user.is_active ? undefined : 'var(--red)' }}>
                            {user.is_active ? "Active" : "Inactive"}
                        </span>
                    </div>
                    <div className="profile-detail-row">
                        <span className="profile-detail-label">Member Since</span>
                        <span>{new Date(user.created_at).toLocaleDateString()}</span>
                    </div>
                </div>

                <div className="profile-card">
                    <h2 className="profile-card-title">Draft Status</h2>
                    {user.in_draft ? (
                        <>
                            <div className="profile-detail-row">
                                <span className="profile-detail-label">Team</span>
                                <span className="text-blue" style={{ fontWeight: 700 }}>{user.draft_team_name || "Assigned"}</span>
                            </div>
                            <div className="profile-detail-row">
                                <span className="profile-detail-label">Role</span>
                                <span style={{ textTransform: 'capitalize' }}>{user.is_captain ? "Captain 👑" : "Player"}</span>
                            </div>
                        </>
                    ) : (
                        <p style={{ color: 'var(--text-muted)' }}>Not currently in a draft.</p>
                    )}
                </div>
            </div>

            {/* Stats */}
            <div className="profile-card">
                <h2 className="profile-card-title">Season Stats</h2>
                {stats && stats.stats ? (
                    <div className="profile-stats-grid">
                        <div className="profile-stat-card">
                            <div className="profile-stat-value text-gold">{stats.stats.matches_played || 0}</div>
                            <div className="profile-stat-label">Matches</div>
                        </div>
                        <div className="profile-stat-card">
                            <div className="profile-stat-value text-neon">{Number(stats.stats.avg_rating || 0).toFixed(2)}</div>
                            <div className="profile-stat-label">Rating</div>
                        </div>
                        <div className="profile-stat-card">
                            <div className="profile-stat-value text-blue">{Number(stats.stats.avg_adr || 0).toFixed(1)}</div>
                            <div className="profile-stat-label">ADR</div>
                        </div>
                        <div className="profile-stat-card">
                            <div className="profile-stat-value" style={{ color: 'var(--purple)' }}>{Number(stats.stats.overall_kd || 0).toFixed(2)}</div>
                            <div className="profile-stat-label">K/D</div>
                        </div>
                    </div>
                ) : (
                    <p style={{ color: 'var(--text-muted)' }}>No stats available for this season.</p>
                )}
            </div>
        </div>
    );
}

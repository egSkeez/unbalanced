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
            <div className="flex min-h-screen items-center justify-center bg-gray-900 text-white">
                <p>Loading...</p>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-900 text-white p-8">
            <div className="max-w-4xl mx-auto space-y-8">
                {/* Header */}
                <div className="flex items-center justify-between border-b border-gray-700 pb-6">
                    <div>
                        <div className="flex items-center gap-3">
                            <h1 className="text-3xl font-bold">{user.display_name}</h1>
                            {user.ping && (
                                <span
                                    className="px-2 py-0.5 rounded text-sm font-mono border"
                                    style={{
                                        color: getPingColor(user.ping),
                                        borderColor: getPingColor(user.ping),
                                        backgroundColor: `${getPingColor(user.ping)}10`
                                    }}
                                >
                                    {user.ping}ms
                                </span>
                            )}
                        </div>
                        <p className="text-gray-400">@{user.username}</p>
                    </div>
                    <button
                        onClick={logout}
                        className="rounded-md bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-500"
                    >
                        Sign out
                    </button>
                </div>

                {/* User Info Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="bg-gray-800 p-6 rounded-lg shadow-lg">
                        <h2 className="text-xl font-semibold mb-4">Account Details</h2>
                        <div className="space-y-3">
                            <div className="flex justify-between">
                                <span className="text-gray-400">Role</span>
                                <span className="capitalize">{user.role}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-gray-400">Status</span>
                                <span className={user.is_active ? "text-green-400" : "text-red-400"}>
                                    {user.is_active ? "Active" : "Inactive"}
                                </span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-gray-400">Member Since</span>
                                <span>{new Date(user.created_at).toLocaleDateString()}</span>
                            </div>
                        </div>
                    </div>

                    {/* Current Draft Status */}
                    <div className="bg-gray-800 p-6 rounded-lg shadow-lg">
                        <h2 className="text-xl font-semibold mb-4">Draft Status</h2>
                        {user.in_draft ? (
                            <div className="space-y-3">
                                <div className="flex justify-between">
                                    <span className="text-gray-400">Team</span>
                                    <span className="font-bold text-indigo-400">{user.draft_team_name || "Assigned"}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-gray-400">Role</span>
                                    <span className="capitalize">{user.is_captain ? "Captain 👑" : "Player"}</span>
                                </div>
                            </div>
                        ) : (
                            <p className="text-gray-400">Not currently in a draft.</p>
                        )}
                    </div>
                </div>

                {/* Stats Section */}
                <div className="bg-gray-800 p-6 rounded-lg shadow-lg">
                    <h2 className="text-xl font-semibold mb-6">Season Stats</h2>
                    {stats && stats.stats ? (
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div className="bg-gray-700 p-4 rounded text-center">
                                <div className="text-2xl font-bold text-yellow-400">{stats.stats.matches_played || 0}</div>
                                <div className="text-xs text-gray-400 uppercase tracking-widest mt-1">Matches</div>
                            </div>
                            <div className="bg-gray-700 p-4 rounded text-center">
                                <div className="text-2xl font-bold text-green-400">{Number(stats.stats.avg_rating || 0).toFixed(2)}</div>
                                <div className="text-xs text-gray-400 uppercase tracking-widest mt-1">Rating</div>
                            </div>
                            <div className="bg-gray-700 p-4 rounded text-center">
                                <div className="text-2xl font-bold text-blue-400">{Number(stats.stats.avg_adr || 0).toFixed(1)}</div>
                                <div className="text-xs text-gray-400 uppercase tracking-widest mt-1">ADR</div>
                            </div>
                            <div className="bg-gray-700 p-4 rounded text-center">
                                <div className="text-2xl font-bold text-purple-400">{Number(stats.stats.overall_kd || 0).toFixed(2)}</div>
                                <div className="text-xs text-gray-400 uppercase tracking-widest mt-1">K/D</div>
                            </div>
                        </div>
                    ) : (
                        <p className="text-gray-400">No stats available for this season.</p>
                    )}
                </div>
            </div>
        </div>
    );
}

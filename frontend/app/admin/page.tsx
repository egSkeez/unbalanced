'use client';
import { useState, useEffect, useMemo, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import {
    getPlayers, createPlayer, updatePlayer, deletePlayer,
    getLobbyHistory, analyzeLobby, getRoommates, setRoommates, clearDraft,
    getUsers, updateUserRole, deleteUser, syncPlayers,
    adminCreateUser, adminUpdateUser, adminResetPassword, adminUpdateScores,
} from '../lib/api';

interface Player {
    name: string;
    aim: number;
    util: number;
    team_play: number;
    elo: number;
    overall: number;
    avg_kd: number;
    avg_rating: number;
}

interface RegisteredUser {
    id: string;
    username: string;
    display_name: string;
    role: string;
    is_active: boolean;
    created_at: string | null;
    last_login: string | null;
    has_player: boolean;
    player_stats: { aim: number; util: number; team_play: number; elo: number } | null;
}

export default function AdminPage() {
    const { user, token, loading: authLoading } = useAuth();
    const router = useRouter();

    const [tab, setTab] = useState<'players' | 'users' | 'lobbies' | 'roommates' | 'danger'>('players');
    const [players, setPlayers] = useState<Player[]>([]);
    const [registeredUsers, setRegisteredUsers] = useState<RegisteredUser[]>([]);
    const [lobbies, setLobbies] = useState<Array<Record<string, string | number>>>([]);
    const [roommates, setRoommateGroups] = useState<string[][]>([]);
    const [editing, setEditing] = useState<string | null>(null);
    const [editForm, setEditForm] = useState({ aim: 5, util: 5, team_play: 5 });
    const [newPlayer, setNewPlayer] = useState({ name: '', aim: 5, util: 5, team_play: 5 });
    const [newRoommate, setNewRoommate] = useState('');
    const [status, setStatus] = useState('');
    const [analyzing, setAnalyzing] = useState<string | null>(null);
    const [loadingData, setLoadingData] = useState(false);
    const [playerSearch, setPlayerSearch] = useState('');
    const [userSearch, setUserSearch] = useState('');
    const [playerSortBy, setPlayerSortBy] = useState<'name' | 'aim' | 'util' | 'team_play' | 'overall' | 'avg_rating'>('avg_rating');
    const [playerSortDir, setPlayerSortDir] = useState<'asc' | 'desc'>('desc');
    const [showAddPlayer, setShowAddPlayer] = useState(false);

    // User management state
    const [showCreateUser, setShowCreateUser] = useState(false);
    const [newUser, setNewUser] = useState({ username: '', password: '', display_name: '', role: 'player', aim: 5, util: 5, team_play: 5 });
    const [editingUser, setEditingUser] = useState<string | null>(null);
    const [userEditForm, setUserEditForm] = useState({ display_name: '', role: 'player', is_active: true, aim: 5, util: 5, team_play: 5, elo: 1200 });
    const [passwordDialog, setPasswordDialog] = useState<{ userId: string; displayName: string } | null>(null);
    const [newPassword, setNewPassword] = useState('');

    const didLoad = useRef(false);

    useEffect(() => {
        if (authLoading) return;
        if (!user || user.role !== 'admin') {
            router.push('/');
            return;
        }
        if (didLoad.current) return;
        didLoad.current = true;

        setLoadingData(true);
        const promises: Promise<any>[] = [getPlayers(), getLobbyHistory(), getRoommates()];
        if (token) promises.push(getUsers(token));

        Promise.all(promises)
            .then(([p, l, r, u]) => {
                setPlayers(p);
                setLobbies(l);
                setRoommateGroups(r.groups || []);
                if (u) setRegisteredUsers(u);
            })
            .catch(() => { setStatus('Failed to load admin data'); })
            .finally(() => setLoadingData(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [authLoading]);

    // Auto-dismiss status messages
    useEffect(() => {
        if (status) {
            const timer = setTimeout(() => setStatus(''), 5000);
            return () => clearTimeout(timer);
        }
    }, [status]);

    const handleAnalyze = async (lobbyId: string) => {
        setAnalyzing(lobbyId);
        setStatus('');
        try {
            const res = await analyzeLobby(lobbyId);
            setStatus(`✅ Analyzed: ${res.map} — ${res.score}`);
            const updated = await getLobbyHistory();
            setLobbies(updated);
        } catch (e: unknown) {
            setStatus(`❌ ${e instanceof Error ? e.message : 'Analysis failed'}`);
        }
        setAnalyzing(null);
    };

    const handleSavePlayer = async (name: string) => {
        try {
            await updatePlayer(name, editForm);
            setEditing(null);
            const updated = await getPlayers();
            setPlayers(updated);
            setStatus(`✅ Updated ${name}'s scores`);
        } catch {
            setStatus(`❌ Failed to update ${name}`);
        }
    };

    const handleDeletePlayer = async (name: string) => {
        if (!confirm(`Delete ${name}? This removes them from the drafting pool.`)) return;
        try {
            await deletePlayer(name);
            const updated = await getPlayers();
            setPlayers(updated);
            setStatus(`✅ Deleted ${name}`);
        } catch {
            setStatus(`❌ Failed to delete ${name}`);
        }
    };

    const handleAddPlayer = async () => {
        if (!newPlayer.name.trim()) return;
        try {
            await createPlayer(newPlayer);
            const updated = await getPlayers();
            setPlayers(updated);
            setNewPlayer({ name: '', aim: 5, util: 5, team_play: 5 });
            setShowAddPlayer(false);
            setStatus(`✅ Added ${newPlayer.name}`);
        } catch {
            setStatus(`❌ Failed to add player`);
        }
    };

    const handleToggleRole = async (userId: string, currentRole: string) => {
        if (!token) return;
        const newRole = currentRole === 'admin' ? 'player' : 'admin';
        if (!confirm(`Change role to ${newRole}?`)) return;
        try {
            await updateUserRole(userId, newRole, token);
            const updated = await getUsers(token);
            setRegisteredUsers(updated);
            setStatus(`✅ Role updated to ${newRole}`);
        } catch {
            setStatus(`❌ Failed to update role`);
        }
    };

    const handleDeleteUser = async (userId: string, displayName: string) => {
        if (!token) return;
        if (!confirm(`Delete user account "${displayName}"? Their player stats will remain.`)) return;
        try {
            await deleteUser(userId, token);
            const updated = await getUsers(token);
            setRegisteredUsers(updated);
            setStatus(`✅ Deleted user ${displayName}`);
        } catch (e: unknown) {
            setStatus(`❌ ${e instanceof Error ? e.message : 'Failed to delete user'}`);
        }
    };

    const handleSyncPlayers = async () => {
        if (!token) return;
        try {
            const res = await syncPlayers(token);
            setStatus(`✅ Synced ${res.synced} users to player pool`);
            const [p, u] = await Promise.all([getPlayers(), getUsers(token)]);
            setPlayers(p);
            setRegisteredUsers(u);
        } catch {
            setStatus('❌ Sync failed');
        }
    };

    const handleCreateUser = async () => {
        if (!token || !newUser.username.trim() || !newUser.password) return;
        try {
            await adminCreateUser({
                username: newUser.username,
                password: newUser.password,
                display_name: newUser.display_name || newUser.username,
                role: newUser.role,
                aim: newUser.aim,
                util: newUser.util,
                team_play: newUser.team_play,
            }, token);
            setNewUser({ username: '', password: '', display_name: '', role: 'player', aim: 5, util: 5, team_play: 5 });
            setShowCreateUser(false);
            const [p, u] = await Promise.all([getPlayers(), getUsers(token)]);
            setPlayers(p);
            setRegisteredUsers(u);
            setStatus(`✅ Created account "${newUser.display_name || newUser.username}"`);
        } catch (e: unknown) {
            setStatus(`❌ ${e instanceof Error ? e.message : 'Failed to create user'}`);
        }
    };

    const startEditingUser = (u: RegisteredUser) => {
        setEditingUser(u.id);
        setUserEditForm({
            display_name: u.display_name || u.username,
            role: u.role,
            is_active: u.is_active,
            aim: u.player_stats?.aim ?? 5,
            util: u.player_stats?.util ?? 5,
            team_play: u.player_stats?.team_play ?? 5,
            elo: u.player_stats?.elo ?? 1200,
        });
    };

    const handleSaveUser = async (userId: string) => {
        if (!token) return;
        try {
            await adminUpdateUser(userId, {
                display_name: userEditForm.display_name,
                role: userEditForm.role,
                is_active: userEditForm.is_active,
            }, token);
            await adminUpdateScores(userId, {
                aim: userEditForm.aim,
                util: userEditForm.util,
                team_play: userEditForm.team_play,
                elo: userEditForm.elo,
            }, token);
            setEditingUser(null);
            const [p, u] = await Promise.all([getPlayers(), getUsers(token)]);
            setPlayers(p);
            setRegisteredUsers(u);
            setStatus(`✅ Updated user`);
        } catch (e: unknown) {
            setStatus(`❌ ${e instanceof Error ? e.message : 'Failed to update user'}`);
        }
    };

    const handleResetPassword = async () => {
        if (!token || !passwordDialog || newPassword.length < 4) return;
        try {
            await adminResetPassword(passwordDialog.userId, newPassword, token);
            setPasswordDialog(null);
            setNewPassword('');
            setStatus(`✅ Password reset for ${passwordDialog.displayName}`);
        } catch (e: unknown) {
            setStatus(`❌ ${e instanceof Error ? e.message : 'Failed to reset password'}`);
        }
    };

    const addRoommateGroup = () => {
        if (newRoommate.trim()) {
            const names = newRoommate.split(',').map(n => n.trim()).filter(Boolean);
            if (names.length >= 2) {
                const updated = [...roommates, names];
                setRoommateGroups(updated);
                setRoommates(updated);
                setNewRoommate('');
                setStatus('✅ Roommate group added');
            }
        }
    };

    const removeRoommateGroup = (idx: number) => {
        const updated = roommates.filter((_, i) => i !== idx);
        setRoommateGroups(updated);
        setRoommates(updated);
        setStatus('✅ Roommate group removed');
    };

    const handleFullReset = async () => {
        if (!confirm('⚠️ This will clear the current draft. Continue?')) return;
        await clearDraft();
        setStatus('✅ Draft cleared');
    };

    // Filtered and sorted players
    const filteredPlayers = useMemo(() => {
        let result = [...players];
        if (playerSearch.trim()) {
            const q = playerSearch.toLowerCase();
            result = result.filter(p => p.name.toLowerCase().includes(q));
        }
        result.sort((a, b) => {
            const aVal = a[playerSortBy] ?? 0;
            const bVal = b[playerSortBy] ?? 0;
            if (typeof aVal === 'string' && typeof bVal === 'string') {
                return playerSortDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
            }
            return playerSortDir === 'asc' ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
        });
        return result;
    }, [players, playerSearch, playerSortBy, playerSortDir]);

    // Filtered users
    const filteredUsers = useMemo(() => {
        if (!userSearch.trim()) return registeredUsers;
        const q = userSearch.toLowerCase();
        return registeredUsers.filter(u =>
            u.display_name?.toLowerCase().includes(q) ||
            u.username.toLowerCase().includes(q)
        );
    }, [registeredUsers, userSearch]);

    const handleSortToggle = (col: typeof playerSortBy) => {
        if (playerSortBy === col) {
            setPlayerSortDir(d => d === 'asc' ? 'desc' : 'asc');
        } else {
            setPlayerSortBy(col);
            setPlayerSortDir(col === 'name' ? 'asc' : 'desc');
        }
    };

    const SortArrow = ({ col }: { col: typeof playerSortBy }) => {
        if (playerSortBy !== col) return <span style={{ opacity: 0.2 }}>↕</span>;
        return <span style={{ color: 'var(--neon-green)' }}>{playerSortDir === 'asc' ? '↑' : '↓'}</span>;
    };

    if (authLoading || (user?.role === 'admin' && loadingData)) {
        return (
            <div className="page-container">
                <div className="loading-spinner"><div className="spinner" /></div>
            </div>
        );
    }

    if (!user || user.role !== 'admin') {
        return null;
    }

    const tabItems = [
        { key: 'players' as const, icon: '👥', label: 'Players', count: players.length },
        { key: 'users' as const, icon: '🔑', label: 'Accounts', count: registeredUsers.length },
        { key: 'lobbies' as const, icon: '🏢', label: 'Lobbies', count: lobbies.length },
        { key: 'roommates' as const, icon: '🏠', label: 'Roommates', count: roommates.length },
        { key: 'danger' as const, icon: '⚠️', label: 'Danger Zone' },
    ];

    return (
        <div className="page-container">
            <div className="page-header">
                <h1 className="page-title">⚙️ Admin Panel</h1>
                <p className="page-subtitle">Manage players, accounts, lobbies, and settings</p>
            </div>

            {status && (
                <div className="status-message" style={{
                    animation: 'fadeIn 0.3s var(--ease-out)',
                    background: status.startsWith('✅')
                        ? 'rgba(0,230,118,0.06)'
                        : status.startsWith('❌')
                            ? 'rgba(255,71,87,0.06)'
                            : 'var(--bg-elevated)',
                    borderColor: status.startsWith('✅')
                        ? 'rgba(0,230,118,0.15)'
                        : status.startsWith('❌')
                            ? 'rgba(255,71,87,0.15)'
                            : 'var(--border)',
                }}>
                    {status}
                </div>
            )}

            {/* Tab Navigation */}
            <div style={{ display: 'flex', gap: 6, marginBottom: 24, overflowX: 'auto', paddingBottom: 4 }}>
                {tabItems.map(t => (
                    <button
                        key={t.key}
                        className={`btn btn-sm ${tab === t.key ? (t.key === 'danger' ? 'btn-danger' : 'btn-primary') : ''}`}
                        onClick={() => setTab(t.key)}
                        style={{
                            display: 'flex', alignItems: 'center', gap: 6,
                            transition: 'all 0.2s var(--ease-out)',
                        }}
                    >
                        <span>{t.icon}</span>
                        <span>{t.label}</span>
                        {t.count !== undefined && (
                            <span style={{
                                background: tab === t.key ? 'rgba(0,0,0,0.15)' : 'rgba(255,255,255,0.06)',
                                padding: '1px 7px', borderRadius: 99, fontSize: '0.7rem',
                                fontFamily: "'Orbitron', sans-serif", fontWeight: 700,
                            }}>
                                {t.count}
                            </span>
                        )}
                    </button>
                ))}
            </div>

            {/* ══════════════ PLAYERS TAB ══════════════ */}
            {tab === 'players' && (
                <div>
                    {/* Search + Quick Actions Bar */}
                    <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
                        <div style={{ position: 'relative', flex: '1 1 250px', maxWidth: 400 }}>
                            <input
                                className="input"
                                placeholder="🔍 Search players..."
                                value={playerSearch}
                                onChange={e => setPlayerSearch(e.target.value)}
                                style={{ paddingLeft: 16 }}
                            />
                        </div>
                        <button
                            className={`btn btn-sm ${showAddPlayer ? 'btn-danger' : 'btn-primary'}`}
                            onClick={() => setShowAddPlayer(!showAddPlayer)}
                        >
                            {showAddPlayer ? '✕ Cancel' : '+ Add Player'}
                        </button>
                        <button className="btn btn-sm" onClick={handleSyncPlayers} title="Create player entries for all registered users who don't have one">
                            🔄 Sync Accounts → Players
                        </button>
                    </div>

                    {/* Add Player Form (collapsible) */}
                    {showAddPlayer && (
                        <div className="card" style={{
                            marginBottom: 20,
                            background: 'linear-gradient(135deg, rgba(0,230,118,0.03), rgba(77,166,255,0.03))',
                            border: '1px solid rgba(0,230,118,0.12)',
                            animation: 'fadeIn 0.3s var(--ease-out)',
                        }}>
                            <div className="card-header" style={{ color: 'var(--neon-green)' }}>✨ Add New Player</div>
                            <div style={{ display: 'flex', gap: 16, alignItems: 'end', flexWrap: 'wrap' }}>
                                <div style={{ flex: '1 1 160px' }}>
                                    <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Player Name</label>
                                    <input className="input" value={newPlayer.name} onChange={e => setNewPlayer({ ...newPlayer, name: e.target.value })}
                                        placeholder="Enter name..." onKeyDown={e => e.key === 'Enter' && handleAddPlayer()} />
                                </div>
                                {(['aim', 'util', 'team_play'] as const).map(f => (
                                    <div key={f} style={{ flex: '0 0 auto' }}>
                                        <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                            {f === 'team_play' ? 'Team Play' : f.charAt(0).toUpperCase() + f.slice(1)}
                                        </label>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                            <input
                                                type="range" min={1} max={10} step={0.1}
                                                value={newPlayer[f]}
                                                onChange={e => setNewPlayer({ ...newPlayer, [f]: Number(e.target.value) })}
                                                style={{ width: 100, accentColor: 'var(--neon-green)' }}
                                            />
                                            <span className="font-orbitron" style={{ color: 'var(--neon-green)', fontWeight: 700, fontSize: '0.9rem', minWidth: 30, textAlign: 'center' }}>
                                                {newPlayer[f]}
                                            </span>
                                        </div>
                                    </div>
                                ))}
                                <button className="btn btn-primary btn-sm" onClick={handleAddPlayer}
                                    disabled={!newPlayer.name.trim()}>
                                    ✅ Add Player
                                </button>
                            </div>
                        </div>
                    )}

                    {/* Player Table */}
                    <div className="card">
                        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span>Player Pool ({filteredPlayers.length}{playerSearch ? ` of ${players.length}` : ''})</span>
                        </div>
                        <div style={{ overflowX: 'auto' }}>
                            <table className="data-table" style={{ width: '100%' }}>
                                <thead>
                                    <tr>
                                        <th onClick={() => handleSortToggle('name')} style={{ cursor: 'pointer', userSelect: 'none' }}>
                                            Name <SortArrow col="name" />
                                        </th>
                                        <th onClick={() => handleSortToggle('aim')} style={{ cursor: 'pointer', userSelect: 'none', textAlign: 'center' }}>
                                            Aim <SortArrow col="aim" />
                                        </th>
                                        <th onClick={() => handleSortToggle('util')} style={{ cursor: 'pointer', userSelect: 'none', textAlign: 'center' }}>
                                            Util <SortArrow col="util" />
                                        </th>
                                        <th onClick={() => handleSortToggle('team_play')} style={{ cursor: 'pointer', userSelect: 'none', textAlign: 'center' }}>
                                            Team <SortArrow col="team_play" />
                                        </th>
                                        <th onClick={() => handleSortToggle('overall')} style={{ cursor: 'pointer', userSelect: 'none', textAlign: 'center' }}>
                                            OVR <SortArrow col="overall" />
                                        </th>
                                        <th onClick={() => handleSortToggle('avg_rating')} style={{ cursor: 'pointer', userSelect: 'none', textAlign: 'center' }}>
                                            HLTV <SortArrow col="avg_rating" />
                                        </th>
                                        <th style={{ textAlign: 'center' }}>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {filteredPlayers.map(p => (
                                        <tr key={p.name} style={{
                                            animation: 'fadeIn 0.3s var(--ease-out)',
                                            background: editing === p.name ? 'rgba(0,230,118,0.03)' : undefined,
                                        }}>
                                            <td style={{ fontWeight: 600 }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                                    <div style={{
                                                        width: 26, height: 26, borderRadius: '50%',
                                                        background: `linear-gradient(135deg, hsl(${(p.overall || 5) * 12}, 70%, 50%), hsl(${(p.overall || 5) * 12 + 40}, 70%, 40%))`,
                                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                                        fontSize: '0.65rem', fontWeight: 800, color: '#000', flexShrink: 0,
                                                    }}>
                                                        {p.name.charAt(0).toUpperCase()}
                                                    </div>
                                                    {p.name}
                                                </div>
                                            </td>
                                            <td style={{ textAlign: 'center' }}>
                                                {editing === p.name ? (
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'center' }}>
                                                        <input type="range" min={1} max={10} step={0.1}
                                                            value={editForm.aim}
                                                            onChange={e => setEditForm({ ...editForm, aim: Number(e.target.value) })}
                                                            style={{ width: 60, accentColor: 'var(--neon-green)' }} />
                                                        <span className="font-orbitron" style={{ color: 'var(--neon-green)', fontWeight: 700, fontSize: '0.8rem', minWidth: 24 }}>{editForm.aim}</span>
                                                    </div>
                                                ) : (
                                                    <ScoreBadge value={p.aim} />
                                                )}
                                            </td>
                                            <td style={{ textAlign: 'center' }}>
                                                {editing === p.name ? (
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'center' }}>
                                                        <input type="range" min={1} max={10} step={0.1}
                                                            value={editForm.util}
                                                            onChange={e => setEditForm({ ...editForm, util: Number(e.target.value) })}
                                                            style={{ width: 60, accentColor: 'var(--blue)' }} />
                                                        <span className="font-orbitron" style={{ color: 'var(--blue)', fontWeight: 700, fontSize: '0.8rem', minWidth: 24 }}>{editForm.util}</span>
                                                    </div>
                                                ) : (
                                                    <ScoreBadge value={p.util} color="blue" />
                                                )}
                                            </td>
                                            <td style={{ textAlign: 'center' }}>
                                                {editing === p.name ? (
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'center' }}>
                                                        <input type="range" min={1} max={10} step={0.1}
                                                            value={editForm.team_play}
                                                            onChange={e => setEditForm({ ...editForm, team_play: Number(e.target.value) })}
                                                            style={{ width: 60, accentColor: 'var(--purple)' }} />
                                                        <span className="font-orbitron" style={{ color: 'var(--purple)', fontWeight: 700, fontSize: '0.8rem', minWidth: 24 }}>{editForm.team_play}</span>
                                                    </div>
                                                ) : (
                                                    <ScoreBadge value={p.team_play} color="purple" />
                                                )}
                                            </td>
                                            <td style={{ textAlign: 'center' }}>
                                                <span className="font-orbitron text-neon" style={{ fontWeight: 700, fontSize: '0.85rem' }}>
                                                    {p.overall?.toFixed(1)}
                                                </span>
                                            </td>
                                            <td style={{ textAlign: 'center' }}>
                                                <span className="font-orbitron" style={{ fontWeight: 700, fontSize: '0.85rem', color: 'var(--gold)' }}>
                                                    {p.avg_rating?.toFixed(2)}
                                                </span>
                                            </td>
                                            <td style={{ textAlign: 'center' }}>
                                                {editing === p.name ? (
                                                    <div style={{ display: 'flex', gap: 6, justifyContent: 'center' }}>
                                                        <button className="btn btn-sm btn-primary" onClick={() => handleSavePlayer(p.name)}>💾 Save</button>
                                                        <button className="btn btn-sm" onClick={() => setEditing(null)}>Cancel</button>
                                                    </div>
                                                ) : (
                                                    <div style={{ display: 'flex', gap: 6, justifyContent: 'center' }}>
                                                        <button className="btn btn-sm" onClick={() => { setEditing(p.name); setEditForm({ aim: p.aim, util: p.util, team_play: p.team_play }); }}
                                                            title="Edit scores">✏️</button>
                                                        <button className="btn btn-sm btn-danger" onClick={() => handleDeletePlayer(p.name)}
                                                            title="Remove from player pool">🗑️</button>
                                                    </div>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                    {filteredPlayers.length === 0 && (
                                        <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem' }}>
                                            {playerSearch ? `No players matching "${playerSearch}"` : 'No players found'}
                                        </td></tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            )}

            {/* ══════════════ REGISTERED USERS TAB ══════════════ */}
            {tab === 'users' && (
                <div>
                    {/* Summary Cards */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: 20 }}>
                        <div className="stat-card">
                            <div className="stat-card-icon">👥</div>
                            <div className="stat-card-value text-neon">{registeredUsers.length}</div>
                            <div className="stat-card-label">Total Accounts</div>
                        </div>
                        <div className="stat-card">
                            <div className="stat-card-icon">🛡️</div>
                            <div className="stat-card-value text-gold">{registeredUsers.filter(u => u.role === 'admin').length}</div>
                            <div className="stat-card-label">Admins</div>
                        </div>
                        <div className="stat-card">
                            <div className="stat-card-icon">🎮</div>
                            <div className="stat-card-value text-blue">{registeredUsers.filter(u => u.has_player).length}</div>
                            <div className="stat-card-label">In Player Pool</div>
                        </div>
                        <div className="stat-card">
                            <div className="stat-card-icon">⚡</div>
                            <div className="stat-card-value" style={{ color: 'var(--orange)' }}>
                                {registeredUsers.filter(u => !u.has_player).length}
                            </div>
                            <div className="stat-card-label">Not In Pool</div>
                        </div>
                    </div>

                    {/* Search + Actions */}
                    <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
                        <div style={{ flex: '1 1 250px', maxWidth: 400 }}>
                            <input
                                className="input"
                                placeholder="🔍 Search accounts..."
                                value={userSearch}
                                onChange={e => setUserSearch(e.target.value)}
                            />
                        </div>
                        <button
                            className={`btn btn-sm ${showCreateUser ? 'btn-danger' : 'btn-primary'}`}
                            onClick={() => setShowCreateUser(!showCreateUser)}
                        >
                            {showCreateUser ? '✕ Cancel' : '+ Create Account'}
                        </button>
                        <button className="btn btn-sm" onClick={handleSyncPlayers}>
                            🔄 Sync All → Player Pool
                        </button>
                    </div>

                    {/* Create Account Form (collapsible) */}
                    {showCreateUser && (
                        <div className="card" style={{
                            marginBottom: 20,
                            background: 'linear-gradient(135deg, rgba(77,166,255,0.03), rgba(0,230,118,0.03))',
                            border: '1px solid rgba(77,166,255,0.12)',
                            animation: 'fadeIn 0.3s var(--ease-out)',
                        }}>
                            <div className="card-header" style={{ color: 'var(--blue)' }}>🔑 Create New Account</div>
                            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'end' }}>
                                <div style={{ flex: '1 1 140px' }}>
                                    <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Username</label>
                                    <input className="input" value={newUser.username} onChange={e => setNewUser({ ...newUser, username: e.target.value })}
                                        placeholder="username" />
                                </div>
                                <div style={{ flex: '1 1 140px' }}>
                                    <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Display Name</label>
                                    <input className="input" value={newUser.display_name} onChange={e => setNewUser({ ...newUser, display_name: e.target.value })}
                                        placeholder="Display Name" />
                                </div>
                                <div style={{ flex: '1 1 140px' }}>
                                    <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Password</label>
                                    <input className="input" type="password" value={newUser.password} onChange={e => setNewUser({ ...newUser, password: e.target.value })}
                                        placeholder="Min 4 chars" />
                                </div>
                                <div style={{ flex: '0 0 auto' }}>
                                    <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Role</label>
                                    <select className="input" value={newUser.role} onChange={e => setNewUser({ ...newUser, role: e.target.value })}
                                        style={{ padding: '8px 12px', minWidth: 100 }}>
                                        <option value="player">Player</option>
                                        <option value="admin">Admin</option>
                                    </select>
                                </div>
                            </div>
                            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'end', marginTop: 12 }}>
                                {(['aim', 'util', 'team_play'] as const).map(f => (
                                    <div key={f} style={{ flex: '0 0 auto' }}>
                                        <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                            {f === 'team_play' ? 'Team Play' : f.charAt(0).toUpperCase() + f.slice(1)}
                                        </label>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                            <input type="range" min={1} max={10} step={0.1}
                                                value={newUser[f]}
                                                onChange={e => setNewUser({ ...newUser, [f]: Number(e.target.value) })}
                                                style={{ width: 80, accentColor: f === 'aim' ? 'var(--neon-green)' : f === 'util' ? 'var(--blue)' : 'var(--purple)' }}
                                            />
                                            <span className="font-orbitron" style={{ fontWeight: 700, fontSize: '0.8rem', minWidth: 24, color: f === 'aim' ? 'var(--neon-green)' : f === 'util' ? 'var(--blue)' : 'var(--purple)' }}>
                                                {newUser[f]}
                                            </span>
                                        </div>
                                    </div>
                                ))}
                                <button className="btn btn-primary btn-sm" onClick={handleCreateUser}
                                    disabled={!newUser.username.trim() || newUser.password.length < 4}
                                    style={{ marginLeft: 'auto' }}>
                                    ✅ Create Account
                                </button>
                            </div>
                        </div>
                    )}

                    {/* Users List */}
                    <div className="card">
                        <div className="card-header">Registered Accounts ({filteredUsers.length})</div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                            {filteredUsers.map(u => {
                                const isEditing = editingUser === u.id;
                                return (
                                    <div key={u.id} style={{
                                        borderBottom: '1px solid var(--border)',
                                        animation: 'fadeIn 0.3s var(--ease-out)',
                                        background: isEditing ? 'rgba(0,230,118,0.03)' : undefined,
                                    }}>
                                        {/* Main row */}
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', flexWrap: 'wrap' }}>
                                            {/* Avatar + Name */}
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: '1 1 180px', minWidth: 0 }}>
                                                <div className={`user-avatar ${u.role === 'admin' ? 'user-avatar-admin' : 'user-avatar-user'}`}>
                                                    {(u.display_name || u.username).charAt(0).toUpperCase()}
                                                </div>
                                                <div style={{ minWidth: 0 }}>
                                                    <div style={{ fontWeight: 600, fontSize: '0.9rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                                        {u.display_name || u.username}
                                                    </div>
                                                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>@{u.username}</div>
                                                </div>
                                            </div>

                                            {/* Role badge */}
                                            <span className={`badge ${u.role === 'admin' ? 'badge-win' : 'badge-draw'}`}
                                                style={{ cursor: 'pointer', flexShrink: 0 }}
                                                onClick={() => handleToggleRole(u.id, u.role)}
                                                title="Click to toggle role">
                                                {u.role === 'admin' ? '👑 Admin' : '🎮 Player'}
                                            </span>

                                            {/* Scores */}
                                            <div style={{ display: 'flex', gap: 6, flexShrink: 0, fontSize: '0.75rem' }}>
                                                {u.player_stats ? (
                                                    <>
                                                        <ScoreBadge value={u.player_stats.aim} />
                                                        <ScoreBadge value={u.player_stats.util} color="blue" />
                                                        <ScoreBadge value={u.player_stats.team_play} color="purple" />
                                                    </>
                                                ) : (
                                                    <span className="badge badge-loss" style={{ fontSize: '0.7rem' }}>No Player Row</span>
                                                )}
                                            </div>

                                            {/* Status + dates */}
                                            <div style={{ display: 'flex', gap: 12, flexShrink: 0, fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                                                {!u.is_active && <span style={{ color: 'var(--red)', fontWeight: 700 }}>INACTIVE</span>}
                                                <span title="Last login">{u.last_login ? new Date(u.last_login).toLocaleDateString() : 'Never'}</span>
                                            </div>

                                            {/* Action buttons */}
                                            <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                                                {isEditing ? (
                                                    <>
                                                        <button className="btn btn-sm btn-primary" onClick={() => handleSaveUser(u.id)}>💾 Save</button>
                                                        <button className="btn btn-sm" onClick={() => setEditingUser(null)}>Cancel</button>
                                                    </>
                                                ) : (
                                                    <>
                                                        <button className="btn btn-sm" onClick={() => startEditingUser(u)} title="Edit user">✏️</button>
                                                        <button className="btn btn-sm" onClick={() => { setPasswordDialog({ userId: u.id, displayName: u.display_name || u.username }); setNewPassword(''); }}
                                                            title="Reset password">🔑</button>
                                                        <button className="btn btn-sm btn-danger" onClick={() => handleDeleteUser(u.id, u.display_name || u.username)}
                                                            title="Delete account">🗑️</button>
                                                    </>
                                                )}
                                            </div>
                                        </div>

                                        {/* Edit panel (expanded) */}
                                        {isEditing && (
                                            <div style={{
                                                padding: '12px 16px 16px', borderTop: '1px solid var(--border)',
                                                background: 'rgba(0,230,118,0.02)',
                                                animation: 'fadeIn 0.2s var(--ease-out)',
                                            }}>
                                                <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'end' }}>
                                                    <div style={{ flex: '1 1 160px' }}>
                                                        <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Display Name</label>
                                                        <input className="input" value={userEditForm.display_name}
                                                            onChange={e => setUserEditForm({ ...userEditForm, display_name: e.target.value })} />
                                                    </div>
                                                    <div style={{ flex: '0 0 auto' }}>
                                                        <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Role</label>
                                                        <select className="input" value={userEditForm.role}
                                                            onChange={e => setUserEditForm({ ...userEditForm, role: e.target.value })}
                                                            style={{ padding: '8px 12px', minWidth: 100 }}>
                                                            <option value="player">Player</option>
                                                            <option value="admin">Admin</option>
                                                        </select>
                                                    </div>
                                                    <div style={{ flex: '0 0 auto', display: 'flex', alignItems: 'center', gap: 8 }}>
                                                        <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Active</label>
                                                        <input type="checkbox" checked={userEditForm.is_active}
                                                            onChange={e => setUserEditForm({ ...userEditForm, is_active: e.target.checked })}
                                                            style={{ width: 18, height: 18, accentColor: 'var(--neon-green)' }} />
                                                    </div>
                                                </div>
                                                <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'end', marginTop: 12 }}>
                                                    {(['aim', 'util', 'team_play'] as const).map(f => (
                                                        <div key={f} style={{ flex: '0 0 auto' }}>
                                                            <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                                                {f === 'team_play' ? 'Team Play' : f.charAt(0).toUpperCase() + f.slice(1)}
                                                            </label>
                                                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                                                <input type="range" min={1} max={10} step={0.1}
                                                                    value={userEditForm[f]}
                                                                    onChange={e => setUserEditForm({ ...userEditForm, [f]: Number(e.target.value) })}
                                                                    style={{ width: 80, accentColor: f === 'aim' ? 'var(--neon-green)' : f === 'util' ? 'var(--blue)' : 'var(--purple)' }} />
                                                                <span className="font-orbitron" style={{ fontWeight: 700, fontSize: '0.8rem', minWidth: 24, color: f === 'aim' ? 'var(--neon-green)' : f === 'util' ? 'var(--blue)' : 'var(--purple)' }}>
                                                                    {userEditForm[f]}
                                                                </span>
                                                            </div>
                                                        </div>
                                                    ))}
                                                    <div style={{ flex: '0 0 auto' }}>
                                                        <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>ELO</label>
                                                        <input type="number" className="input" value={userEditForm.elo}
                                                            onChange={e => setUserEditForm({ ...userEditForm, elo: Number(e.target.value) })}
                                                            style={{ width: 90, padding: '6px 10px', textAlign: 'center' }} />
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                            {filteredUsers.length === 0 && (
                                <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem' }}>
                                    {userSearch ? `No accounts matching "${userSearch}"` : 'No registered accounts'}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* ═══════ PASSWORD RESET DIALOG ═══════ */}
            {passwordDialog && (
                <div style={{
                    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 1000,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                }} onClick={() => setPasswordDialog(null)}>
                    <div style={{
                        background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: 16,
                        padding: 28, width: 380, maxWidth: '90vw',
                    }} onClick={e => e.stopPropagation()}>
                        <h3 style={{ margin: '0 0 8px', fontWeight: 700 }}>Reset Password</h3>
                        <p style={{ margin: '0 0 20px', fontSize: 13, color: 'var(--text-secondary)' }}>
                            Set a new password for <strong>{passwordDialog.displayName}</strong>
                        </p>
                        <div style={{ marginBottom: 20 }}>
                            <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>New Password</label>
                            <input
                                type="password"
                                value={newPassword}
                                onChange={e => setNewPassword(e.target.value)}
                                placeholder="Min 4 characters"
                                autoFocus
                                onKeyDown={e => e.key === 'Enter' && handleResetPassword()}
                                style={{
                                    background: '#111', border: '1px solid var(--border)', borderRadius: 8,
                                    padding: '10px 14px', color: '#fff', width: '100%', fontSize: 14,
                                }}
                            />
                        </div>
                        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                            <button className="btn btn-sm" onClick={() => setPasswordDialog(null)}>Cancel</button>
                            <button className="btn btn-primary btn-sm" onClick={handleResetPassword}
                                disabled={newPassword.length < 4}>
                                Reset Password
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* ══════════════ LOBBIES TAB ══════════════ */}
            {tab === 'lobbies' && (
                <div className="card">
                    <div className="card-header">Lobby History</div>
                    <div style={{ overflowX: 'auto' }}>
                        <table className="data-table" style={{ width: '100%' }}>
                            <thead>
                                <tr><th>Lobby ID</th><th>Created</th><th>Status</th><th>Demo</th><th>Action</th></tr>
                            </thead>
                            <tbody>
                                {lobbies.map(l => (
                                    <tr key={String(l.lobby_id)}>
                                        <td className="font-orbitron" style={{ fontSize: '0.8rem' }}>{String(l.lobby_id)}</td>
                                        <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{String(l.created_at || '').split('.')[0]}</td>
                                        <td>
                                            <span className={`badge ${l.analysis_status === 'analyzed' ? 'badge-win' : 'badge-draw'}`}>
                                                {String(l.analysis_status || 'pending')}
                                            </span>
                                        </td>
                                        <td>{Number(l.has_demo) === 1 ? '✅' : Number(l.has_demo) === -1 ? '❌' : '⏳'}</td>
                                        <td>
                                            {l.analysis_status !== 'analyzed' && (
                                                <button
                                                    className="btn btn-sm"
                                                    onClick={() => handleAnalyze(String(l.lobby_id))}
                                                    disabled={analyzing === String(l.lobby_id)}
                                                >
                                                    {analyzing === String(l.lobby_id) ? '⏳' : '📊 Analyze'}
                                                </button>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                                {lobbies.length === 0 && (
                                    <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem' }}>No lobbies tracked</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* ══════════════ ROOMMATES TAB ══════════════ */}
            {tab === 'roommates' && (
                <div className="card">
                    <div className="card-header">Roommate Groups (Force Same Team)</div>
                    <div style={{ marginBottom: 24, display: 'flex', flexDirection: 'column', gap: 8 }}>
                        {roommates.map((group, i) => (
                            <div key={i} className="player-chip" style={{ justifyContent: 'space-between' }}>
                                <span>🏠 {group.join(' + ')}</span>
                                <button className="btn btn-sm btn-danger" onClick={() => removeRoommateGroup(i)}>✕</button>
                            </div>
                        ))}
                        {roommates.length === 0 && <p style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>No roommate groups configured</p>}
                    </div>
                    <div style={{ display: 'flex', gap: 8 }}>
                        <input className="input" style={{ flex: 1 }} value={newRoommate} onChange={e => setNewRoommate(e.target.value)} placeholder="Player1, Player2 (comma separated)"
                            onKeyDown={e => e.key === 'Enter' && addRoommateGroup()} />
                        <button className="btn btn-sm btn-primary" onClick={addRoommateGroup}>Add Group</button>
                    </div>
                </div>
            )}

            {/* ══════════════ DANGER ZONE ══════════════ */}
            {tab === 'danger' && (
                <div className="card" style={{ border: '2px solid rgba(255,71,87,0.3)' }}>
                    <div className="card-header" style={{ color: 'var(--red)' }}>⚠️ Danger Zone</div>
                    <p style={{ color: 'var(--text-muted)', marginBottom: 24 }}>These actions cannot be undone and affect live drafts immediately.</p>
                    <div style={{ display: 'flex', gap: 16 }}>
                        <button className="btn btn-danger" onClick={handleFullReset}>🗑️ Clear Current Draft</button>
                    </div>
                </div>
            )}
        </div>
    );
}

/* ── Helper Components ── */

function ScoreBadge({ value, color = 'green' }: { value: number; color?: 'green' | 'blue' | 'purple' }) {
    const colorMap = {
        green: { bg: 'rgba(0,230,118,0.08)', text: 'var(--neon-green)', border: 'rgba(0,230,118,0.15)' },
        blue: { bg: 'rgba(77,166,255,0.08)', text: 'var(--blue)', border: 'rgba(77,166,255,0.15)' },
        purple: { bg: 'rgba(180,124,255,0.08)', text: 'var(--purple)', border: 'rgba(180,124,255,0.15)' },
    };
    const c = colorMap[color];
    // Color intensity based on score
    const intensity = Math.min(1, value / 10);

    return (
        <span className="font-orbitron" style={{
            display: 'inline-block',
            padding: '3px 10px',
            borderRadius: 6,
            background: c.bg,
            border: `1px solid ${c.border}`,
            color: c.text,
            fontWeight: 700,
            fontSize: '0.8rem',
            opacity: 0.5 + intensity * 0.5,
            minWidth: 42,
            textAlign: 'center',
        }}>
            {value}
        </span>
    );
}

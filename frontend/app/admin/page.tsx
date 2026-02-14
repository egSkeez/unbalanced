'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import {
    getPlayers, createPlayer, updatePlayer, deletePlayer,
    getLobbyHistory, analyzeLobby, getRoommates, setRoommates, clearDraft,
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

export default function AdminPage() {
    const { user, loading: authLoading } = useAuth();
    const router = useRouter();

    const [tab, setTab] = useState<'lobbies' | 'players' | 'roommates' | 'danger'>('lobbies');
    const [players, setPlayers] = useState<Player[]>([]);
    const [lobbies, setLobbies] = useState<Array<Record<string, string | number>>>([]);
    const [roommates, setRoommateGroups] = useState<string[][]>([]);
    const [editing, setEditing] = useState<string | null>(null);
    const [editForm, setEditForm] = useState({ aim: 5, util: 5, team_play: 5 });
    const [newPlayer, setNewPlayer] = useState({ name: '', aim: 5, util: 5, team_play: 5 });
    const [newRoommate, setNewRoommate] = useState('');
    const [status, setStatus] = useState('');
    const [analyzing, setAnalyzing] = useState<string | null>(null);
    const [loadingData, setLoadingData] = useState(false);

    useEffect(() => {
        if (authLoading) return;
        if (!user || user.role !== 'admin') {
            router.push('/');
            return;
        }

        setLoadingData(true);
        Promise.all([getPlayers(), getLobbyHistory(), getRoommates()])
            .then(([p, l, r]) => {
                setPlayers(p);
                setLobbies(l);
                setRoommateGroups(r.groups || []);
            })
            .catch(() => { setStatus('Failed to load admin data'); })
            .finally(() => setLoadingData(false));
    }, [user, authLoading, router]);

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
        await updatePlayer(name, editForm);
        setEditing(null);
        const updated = await getPlayers();
        setPlayers(updated);
        setStatus(`✅ Updated ${name}`);
    };

    const handleDeletePlayer = async (name: string) => {
        if (!confirm(`Delete ${name}?`)) return;
        await deletePlayer(name);
        const updated = await getPlayers();
        setPlayers(updated);
        setStatus(`✅ Deleted ${name}`);
    };

    const handleAddPlayer = async () => {
        if (!newPlayer.name.trim()) return;
        await createPlayer(newPlayer);
        const updated = await getPlayers();
        setPlayers(updated);
        setNewPlayer({ name: '', aim: 5, util: 5, team_play: 5 });
        setStatus(`✅ Added ${newPlayer.name}`);
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

    return (
        <div className="page-container">
            <div className="page-header">
                <h1 className="page-title">⚙️ Admin Panel</h1>
                <p className="page-subtitle">Manage lobbies, players, and settings</p>
            </div>

            {status && <div className="status-message">{status}</div>}

            {/* Tabs */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 24, overflowX: 'auto' }}>
                {(['lobbies', 'players', 'roommates', 'danger'] as const).map(t => (
                    <button
                        key={t}
                        className={`btn btn-sm ${tab === t ? (t === 'danger' ? 'btn-danger' : 'btn-primary') : ''}`}
                        onClick={() => setTab(t)}
                    >
                        {t === 'lobbies' ? '🏢 Lobbies' : t === 'players' ? '👥 Players' : t === 'roommates' ? '🏠 Roommates' : '⚠️ Danger Zone'}
                    </button>
                ))}
            </div>

            {/* LOBBIES TAB */}
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

            {/* PLAYERS TAB */}
            {tab === 'players' && (
                <div>
                    {/* Add player */}
                    <div className="card" style={{ marginBottom: 24 }}>
                        <div className="card-header">Add Player</div>
                        <div style={{ display: 'flex', gap: 16, alignItems: 'end', flexWrap: 'wrap' }}>
                            <div>
                                <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Name</label>
                                <input className="input" style={{ width: 160 }} value={newPlayer.name} onChange={e => setNewPlayer({ ...newPlayer, name: e.target.value })} />
                            </div>
                            {(['aim', 'util', 'team_play'] as const).map(f => (
                                <div key={f}>
                                    <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{f}</label>
                                    <input className="input" style={{ width: 80 }} type="number" min={1} max={10} value={newPlayer[f]} onChange={e => setNewPlayer({ ...newPlayer, [f]: Number(e.target.value) })} />
                                </div>
                            ))}
                            <button className="btn btn-primary btn-sm" onClick={handleAddPlayer}>+ Add</button>
                        </div>
                    </div>

                    {/* Player list */}
                    <div className="card">
                        <div className="card-header">All Players ({players.length})</div>
                        <div style={{ overflowX: 'auto' }}>
                            <table className="data-table" style={{ width: '100%' }}>
                                <thead>
                                    <tr><th>Name</th><th>Aim</th><th>Util</th><th>Team</th><th>ELO</th><th>OVR</th><th>Actions</th></tr>
                                </thead>
                                <tbody>
                                    {players.map(p => (
                                        <tr key={p.name}>
                                            <td style={{ fontWeight: 600 }}>{p.name}</td>
                                            <td>{editing === p.name ? <input className="input" style={{ width: 64, padding: 4, textAlign: 'center' }} type="number" value={editForm.aim} onChange={e => setEditForm({ ...editForm, aim: Number(e.target.value) })} /> : p.aim}</td>
                                            <td>{editing === p.name ? <input className="input" style={{ width: 64, padding: 4, textAlign: 'center' }} type="number" value={editForm.util} onChange={e => setEditForm({ ...editForm, util: Number(e.target.value) })} /> : p.util}</td>
                                            <td>{editing === p.name ? <input className="input" style={{ width: 64, padding: 4, textAlign: 'center' }} type="number" value={editForm.team_play} onChange={e => setEditForm({ ...editForm, team_play: Number(e.target.value) })} /> : p.team_play}</td>
                                            <td>{p.elo}</td>
                                            <td className="text-neon" style={{ fontWeight: 700 }}>{p.overall?.toFixed(1)}</td>
                                            <td>
                                                {editing === p.name ? (
                                                    <div style={{ display: 'flex', gap: 8 }}>
                                                        <button className="btn btn-sm btn-primary" onClick={() => handleSavePlayer(p.name)}>Save</button>
                                                        <button className="btn btn-sm" onClick={() => setEditing(null)}>Cancel</button>
                                                    </div>
                                                ) : (
                                                    <div style={{ display: 'flex', gap: 8 }}>
                                                        <button className="btn btn-sm" onClick={() => { setEditing(p.name); setEditForm({ aim: p.aim, util: p.util, team_play: p.team_play }); }}>✏️</button>
                                                        <button className="btn btn-sm btn-danger" onClick={() => handleDeletePlayer(p.name)}>🗑️</button>
                                                    </div>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            )}

            {/* ROOMMATES TAB */}
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
                        <input className="input" style={{ flex: 1 }} value={newRoommate} onChange={e => setNewRoommate(e.target.value)} placeholder="Player1, Player2 (comma separated)" />
                        <button className="btn btn-sm btn-primary" onClick={addRoommateGroup}>Add Group</button>
                    </div>
                </div>
            )}

            {/* DANGER ZONE */}
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

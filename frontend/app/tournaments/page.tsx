'use client';
import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';
import { getTournaments, joinTournament, leaveTournament, createTournament, deleteTournament, searchSkins } from '@/app/lib/api';

interface TournamentData {
    id: string;
    name: string;
    format: string;
    prize_image_url: string | null;
    prize_name: string | null;
    max_players: number;
    playoffs: boolean;
    status: string;
    tournament_date: string | null;
    created_at: string;
    participant_count: number;
    winner: { id: string; username: string; display_name: string } | null;
}

interface SkinResult {
    name: string;
    image: string;
    rarity: string;
    rarity_color: string;
}

export default function TournamentsPage() {
    const { user, token } = useAuth();
    const [tournaments, setTournaments] = useState<TournamentData[]>([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState<string>('');
    const [joining, setJoining] = useState<string | null>(null);
    const [showCreate, setShowCreate] = useState(false);
    const [createForm, setCreateForm] = useState({ name: '', format: 'single_elimination', prize_image_url: '', prize_name: '', prize_pool: '', max_players: 8, playoffs: false, unlimited: false, tournament_date: '' });
    const [error, setError] = useState('');

    // Skin search state
    const [skinQuery, setSkinQuery] = useState('');
    const [skinResults, setSkinResults] = useState<SkinResult[]>([]);
    const [skinSearching, setSkinSearching] = useState(false);
    const [showSkinDropdown, setShowSkinDropdown] = useState(false);
    const skinTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const dropdownRef = useRef<HTMLDivElement>(null);

    const loadTournaments = async () => {
        try {
            const data = await getTournaments(filter || undefined);
            setTournaments(data);
        } catch (e) {
            console.error('Failed to load tournaments', e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { loadTournaments(); }, [filter]);

    // Close skin dropdown on outside click
    useEffect(() => {
        const handler = (e: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
                setShowSkinDropdown(false);
            }
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);

    // Debounced skin search
    const handleSkinQueryChange = (val: string) => {
        setSkinQuery(val);
        setCreateForm(f => ({ ...f, prize_name: val, prize_image_url: '' }));

        if (skinTimerRef.current) clearTimeout(skinTimerRef.current);

        if (val.trim().length < 2) {
            setSkinResults([]);
            setShowSkinDropdown(false);
            return;
        }

        skinTimerRef.current = setTimeout(async () => {
            setSkinSearching(true);
            try {
                const results = await searchSkins(val.trim());
                setSkinResults(results);
                setShowSkinDropdown(results.length > 0);
            } catch {
                setSkinResults([]);
            } finally {
                setSkinSearching(false);
            }
        }, 350);
    };

    const selectSkin = (skin: SkinResult) => {
        setSkinQuery(skin.name);
        setCreateForm(f => ({ ...f, prize_name: skin.name, prize_image_url: skin.image }));
        setShowSkinDropdown(false);
    };

    const handleJoin = async (id: string) => {
        if (!token) return;
        setJoining(id);
        setError('');
        try {
            await joinTournament(id, token);
            await loadTournaments();
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to join');
        } finally {
            setJoining(null);
        }
    };

    const handleLeave = async (id: string) => {
        if (!token) return;
        setError('');
        try {
            await leaveTournament(id, token);
            await loadTournaments();
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to leave');
        }
    };

    const handleCreate = async () => {
        if (!token) return;
        setError('');
        try {
            await createTournament({
                name: createForm.name,
                format: createForm.format,
                prize_image_url: createForm.prize_image_url || undefined,
                prize_name: createForm.prize_name || undefined,
                prize_pool: createForm.prize_pool || undefined,
                max_players: createForm.unlimited ? 0 : createForm.max_players,
                playoffs: createForm.format === 'round_robin' ? createForm.playoffs : undefined,
                tournament_date: createForm.tournament_date || undefined,
            }, token);
            setShowCreate(false);
            setCreateForm({ name: '', format: 'single_elimination', prize_image_url: '', prize_name: '', prize_pool: '', max_players: 8, playoffs: false, unlimited: false, tournament_date: '' });
            setSkinQuery('');
            await loadTournaments();
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to create');
        }
    };

    const handleDelete = async (id: string) => {
        if (!token) return;
        try {
            await deleteTournament(id, token);
            await loadTournaments();
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to delete');
        }
    };

    const formatDate = (dateStr: string | null) => {
        if (!dateStr) return null;
        try {
            return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
        } catch { return dateStr; }
    };

    const statusColors: Record<string, string> = {
        open: 'var(--neon-green)',
        registration: 'var(--neon-green)',
        active: 'var(--orange)',
        playoffs: 'var(--gold)',
        completed: 'var(--text-muted)',
    };

    const inputStyle = { background: '#111', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 14px', color: '#fff', width: '100%' };

    return (
        <div className="page-container">
            <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                    <h1 className="page-title">1v1 Tournaments</h1>
                    <p className="page-subtitle">Compete in CS2 tournaments for prizes</p>
                </div>
                {user?.role === 'admin' && (
                    <button className="btn btn-primary" onClick={() => setShowCreate(!showCreate)}>
                        + New Tournament
                    </button>
                )}
            </div>

            {error && (
                <div style={{ padding: '12px 16px', background: 'rgba(255,51,51,0.15)', border: '1px solid rgba(255,51,51,0.3)', borderRadius: 8, marginBottom: 16, color: 'var(--red)' }}>
                    {error}
                </div>
            )}

            {/* Admin: Create Tournament Form */}
            {showCreate && (
                <div className="card" style={{ marginBottom: 24 }}>
                    <h3 style={{ marginBottom: 16, fontWeight: 700 }}>Create Tournament</h3>
                    <div style={{ display: 'grid', gap: 14, maxWidth: 520 }}>
                        <div>
                            <label style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4, display: 'block' }}>Tournament Name</label>
                            <input
                                placeholder="e.g. Friday Night 1v1"
                                value={createForm.name}
                                onChange={e => setCreateForm(f => ({ ...f, name: e.target.value }))}
                                style={inputStyle}
                            />
                        </div>

                        <div>
                            <label style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4, display: 'block' }}>Format</label>
                            <select
                                value={createForm.format}
                                onChange={e => setCreateForm(f => ({ ...f, format: e.target.value }))}
                                style={inputStyle}
                            >
                                <option value="single_elimination">Single Elimination</option>
                                <option value="round_robin">Round Robin</option>
                            </select>
                        </div>

                        <div>
                            <label style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4, display: 'block' }}>Tournament Date</label>
                            <input
                                type="date"
                                value={createForm.tournament_date}
                                onChange={e => setCreateForm(f => ({ ...f, tournament_date: e.target.value }))}
                                style={{ ...inputStyle, colorScheme: 'dark' }}
                            />
                        </div>

                        {/* Skin search with autocomplete */}
                        <div ref={dropdownRef} style={{ position: 'relative' }}>
                            <label style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4, display: 'block' }}>
                                Prize Skin Name <span style={{ color: 'var(--text-muted)' }}>(type to search CS2 skins)</span>
                            </label>
                            <input
                                placeholder="e.g. AWP | Dragon Lore"
                                value={skinQuery}
                                onChange={e => handleSkinQueryChange(e.target.value)}
                                onFocus={() => { if (skinResults.length > 0) setShowSkinDropdown(true); }}
                                style={inputStyle}
                            />
                            {skinSearching && (
                                <div style={{ position: 'absolute', right: 12, top: 34, color: 'var(--text-muted)', fontSize: 12 }}>
                                    Searching...
                                </div>
                            )}

                            {/* Dropdown */}
                            {showSkinDropdown && skinResults.length > 0 && (
                                <div style={{
                                    position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 50,
                                    background: '#1a1a1a', border: '1px solid var(--border)', borderRadius: 8,
                                    maxHeight: 300, overflowY: 'auto', marginTop: 4,
                                    boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
                                }}>
                                    {skinResults.map((skin, i) => (
                                        <div
                                            key={i}
                                            onClick={() => selectSkin(skin)}
                                            style={{
                                                display: 'flex', alignItems: 'center', gap: 12, padding: '8px 12px',
                                                cursor: 'pointer', borderBottom: '1px solid #222',
                                                transition: 'background 0.1s',
                                            }}
                                            onMouseEnter={e => (e.currentTarget.style.background = '#252525')}
                                            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                                        >
                                            {skin.image && (
                                                <img
                                                    src={skin.image}
                                                    alt={skin.name}
                                                    style={{ width: 48, height: 36, objectFit: 'contain', flexShrink: 0 }}
                                                />
                                            )}
                                            <div style={{ flex: 1, minWidth: 0 }}>
                                                <div style={{ fontSize: 13, fontWeight: 600, color: '#fff', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                                    {skin.name}
                                                </div>
                                                {skin.rarity && (
                                                    <div style={{ fontSize: 11, color: skin.rarity_color || 'var(--text-muted)' }}>
                                                        {skin.rarity}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Selected skin preview */}
                        {createForm.prize_image_url && (
                            <div style={{
                                display: 'flex', alignItems: 'center', gap: 12, padding: 12,
                                background: 'rgba(255,215,0,0.05)', border: '1px solid rgba(255,215,0,0.2)',
                                borderRadius: 8,
                            }}>
                                <img src={createForm.prize_image_url} alt="Prize" style={{ width: 80, height: 60, objectFit: 'contain' }} />
                                <div>
                                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--gold)' }}>{createForm.prize_name}</div>
                                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Prize skin selected</div>
                                </div>
                            </div>
                        )}

                        <div>
                            <label style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4, display: 'block' }}>Max Players</label>
                            {createForm.format === 'round_robin' ? (
                                <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                                    <input
                                        type="number"
                                        min={2}
                                        max={64}
                                        placeholder="e.g. 10"
                                        value={createForm.unlimited ? '' : createForm.max_players}
                                        onChange={e => setCreateForm(f => ({ ...f, max_players: parseInt(e.target.value) || 2, unlimited: false }))}
                                        disabled={createForm.unlimited}
                                        style={{ ...inputStyle, flex: 1, opacity: createForm.unlimited ? 0.4 : 1 }}
                                    />
                                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text-secondary)', cursor: 'pointer', whiteSpace: 'nowrap' }}>
                                        <input
                                            type="checkbox"
                                            checked={createForm.unlimited}
                                            onChange={e => setCreateForm(f => ({ ...f, unlimited: e.target.checked }))}
                                            style={{ accentColor: 'var(--neon-green)' }}
                                        />
                                        No limit (open)
                                    </label>
                                </div>
                            ) : (
                                <select
                                    value={createForm.max_players}
                                    onChange={e => setCreateForm(f => ({ ...f, max_players: parseInt(e.target.value) }))}
                                    style={inputStyle}
                                >
                                    <option value={4}>4 Players</option>
                                    <option value={8}>8 Players</option>
                                    <option value={16}>16 Players</option>
                                    <option value={32}>32 Players</option>
                                </select>
                            )}
                        </div>

                        {createForm.format === 'round_robin' && (
                            <div>
                                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--text-secondary)', cursor: 'pointer' }}>
                                    <input
                                        type="checkbox"
                                        checked={createForm.playoffs}
                                        onChange={e => setCreateForm(f => ({ ...f, playoffs: e.target.checked }))}
                                        style={{ accentColor: 'var(--gold)', width: 16, height: 16 }}
                                    />
                                    <span>Enable Playoffs <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>(Top 4 advance to SE bracket after group stage)</span></span>
                                </label>
                            </div>
                        )}

                        <button className="btn btn-primary" onClick={handleCreate} disabled={!createForm.name.trim()}>
                            Create Tournament
                        </button>
                    </div>
                </div>
            )}

            {/* Filters */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
                {['', 'registration', 'open', 'active', 'playoffs', 'completed'].map(f => (
                    <button
                        key={f}
                        className={`btn btn-sm ${filter === f ? 'btn-primary' : ''}`}
                        onClick={() => setFilter(f)}
                    >
                        {f === '' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1)}
                    </button>
                ))}
            </div>

            {loading && <div className="loading-spinner"><div className="spinner" /></div>}

            {/* Tournament List */}
            {!loading && tournaments.length === 0 && (
                <div className="card" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                    No tournaments found. {user?.role === 'admin' && 'Create one to get started!'}
                </div>
            )}

            <div style={{ display: 'grid', gap: 16 }}>
                {tournaments.map(t => (
                    <div key={t.id} className="card" style={{ display: 'flex', gap: 20, alignItems: 'center' }}>
                        {/* Prize Image */}
                        <div style={{
                            width: 80, height: 80, borderRadius: 12, flexShrink: 0,
                            background: t.prize_image_url ? '#111' : 'linear-gradient(135deg, var(--gold), var(--orange))',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: t.prize_image_url ? 0 : 36,
                            border: '2px solid rgba(255,215,0,0.3)',
                            overflow: 'hidden',
                        }}>
                            {t.prize_image_url ? (
                                <img src={t.prize_image_url} alt={t.prize_name || 'Prize'} style={{ width: '100%', height: '100%', objectFit: 'contain', padding: 4 }} />
                            ) : '🏆'}
                        </div>

                        {/* Info */}
                        <div style={{ flex: 1 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                                <h3 style={{ fontWeight: 700, fontSize: 18, margin: 0 }}>{t.name}</h3>
                                <span style={{
                                    fontSize: 11, fontWeight: 700, textTransform: 'uppercase',
                                    padding: '2px 8px', borderRadius: 4,
                                    background: `${statusColors[t.status]}22`,
                                    color: statusColors[t.status],
                                    border: `1px solid ${statusColors[t.status]}44`,
                                }}>
                                    {t.status}
                                </span>
                            </div>
                            {t.prize_name && (
                                <div style={{ color: 'var(--gold)', fontSize: 13, marginBottom: 2 }}>
                                    Prize: {t.prize_name}
                                </div>
                            )}
                            <div style={{ color: 'var(--text-secondary)', fontSize: 13, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                                <span>
                                    {t.max_players > 0 ? `${t.participant_count}/${t.max_players}` : `${t.participant_count}`} players enrolled
                                    {t.max_players === 0 && <span style={{ color: 'var(--text-muted)' }}> (open)</span>}
                                </span>
                                {t.format === 'round_robin' && (
                                    <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 3, background: 'rgba(100,149,237,0.15)', color: '#6495ed', border: '1px solid rgba(100,149,237,0.3)' }}>RR</span>
                                )}
                                {t.playoffs && (
                                    <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 3, background: 'rgba(255,215,0,0.12)', color: 'var(--gold)', border: '1px solid rgba(255,215,0,0.3)' }}>+ Playoffs</span>
                                )}
                                {t.tournament_date && (
                                    <span style={{ color: 'var(--text-muted)' }}>
                                        {formatDate(t.tournament_date)}
                                    </span>
                                )}
                                {t.winner && (
                                    <span style={{ color: 'var(--gold)' }}>
                                        Winner: {t.winner.display_name}
                                    </span>
                                )}
                            </div>

                            {/* Progress bar */}
                            {(t.status === 'open' || t.status === 'registration') && t.max_players > 0 && (
                                <div style={{ marginTop: 8, background: '#222', borderRadius: 4, height: 6, overflow: 'hidden' }}>
                                    <div style={{
                                        width: `${(t.participant_count / t.max_players) * 100}%`,
                                        height: '100%',
                                        background: 'var(--neon-green)',
                                        borderRadius: 4,
                                        transition: 'width 0.3s',
                                    }} />
                                </div>
                            )}
                        </div>

                        {/* Actions */}
                        <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                            {(t.status === 'open' || t.status === 'registration') && user && (
                                <button
                                    className="btn btn-primary btn-sm"
                                    onClick={() => handleJoin(t.id)}
                                    disabled={joining === t.id}
                                >
                                    {joining === t.id ? 'Joining...' : 'Join'}
                                </button>
                            )}
                            {(t.status === 'open' || t.status === 'registration') && user && (
                                <button
                                    className="btn btn-sm"
                                    onClick={() => handleLeave(t.id)}
                                    style={{ color: 'var(--red)' }}
                                >
                                    Leave
                                </button>
                            )}
                            {(t.status === 'active' || t.status === 'completed' || t.status === 'playoffs') && (
                                <Link href={`/tournaments/${t.id}`} className="btn btn-sm btn-primary">
                                    View Bracket
                                </Link>
                            )}
                            <Link href={`/tournaments/${t.id}`} className="btn btn-sm">
                                Details
                            </Link>
                            {user?.role === 'admin' && (
                                <button
                                    className="btn btn-sm"
                                    onClick={() => handleDelete(t.id)}
                                    style={{ color: 'var(--red)', fontSize: 12 }}
                                >
                                    Delete
                                </button>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

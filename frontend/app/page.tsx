'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Cookies from 'js-cookie';
import { useAuth } from '@/context/AuthContext';
import { getPlayers, runDraft, getDraftState, rerollDraft, clearDraft, getConstants, initVeto, getVetoState, vetoAction, getLobby, createLobby, broadcastToDiscord } from './lib/api';
import PlayerStatsModal from '@/components/PlayerStatsModal';
import { getPingColor } from '@/lib/utils';

interface Player {
  name: string;
  overall: number;
  aim: number;
  util: number;
  team_play: number;
  elo: number;
  avg_kd: number;
  avg_rating: number;
  ping?: number;
}

interface DraftState {
  active: boolean;
  team1: string[];
  team2: string[];
  name_a: string;
  name_b: string;
  avg1: number;
  avg2: number;
  map_pick?: string;
  mode: string;
  votes?: Array<{ captain_name: string; vote: string; pin: string }>;
  lobby_link?: string;
  created_by?: string;
  ratings?: Record<string, number>;
  pings?: Record<string, number>;
}

interface VetoState {
  initialized: boolean;
  remaining?: string[];
  protected?: string[];
  turn_team?: string;
  complete?: boolean;
}

export default function MixerPage() {
  const [players, setPlayers] = useState<Player[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [mode, setMode] = useState('balanced');
  const [draft, setDraft] = useState<DraftState | null>(null);
  const [veto, setVeto] = useState<VetoState | null>(null);
  const [constants, setConstants] = useState<{ map_pool: string[]; map_logos: Record<string, string>; skeez_titles: string[] }>({ map_pool: [], map_logos: {}, skeez_titles: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [lobbyLink, setLobbyLink] = useState('');
  const [bannedMaps, setBannedMaps] = useState<string[]>([]);
  const [skeezTitle, setSkeezTitle] = useState('');
  const [viewingPlayer, setViewingPlayer] = useState<string | null>(null);

  const { user, token, loading: authLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.push('/login');
      return;
    }
    if (draft?.active) {
      const isCreator = draft.created_by && user.display_name === draft.created_by;
      const isAdmin = user.role === 'admin';
      if (!isCreator && !isAdmin) {
        router.push('/captain');
      }
    }
  }, [user, draft, authLoading, router]);

  useEffect(() => {
    Promise.all([getPlayers(), getDraftState(), getConstants()])
      .then(([p, d, c]) => {
        setPlayers(p);
        if (d.active) {
          setDraft(d);
          setSelected([...d.team1, ...d.team2]);
          if (d.lobby_link) setLobbyLink(d.lobby_link);
        }
        setConstants(c);
        if (c.skeez_titles?.length) {
          setSkeezTitle(c.skeez_titles[Math.floor(Math.random() * c.skeez_titles.length)]);
        }
        setLoading(false);
      })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

  useEffect(() => {
    const poll = setInterval(async () => {
      try {
        if (draft?.active) {
          const v = await getVetoState();
          setVeto(v);
          const d = await getDraftState();
          if (d.active) {
            setDraft(d);
            if (d.lobby_link) setLobbyLink(d.lobby_link);
          } else {
            setDraft(null);
          }
        } else {
          const p = await getPlayers();
          setPlayers(p);
          const d = await getDraftState();
          if (d.active) {
            setDraft(d);
            setConstants(await getConstants());
          }
        }
      } catch { /* ignore */ }
    }, 3000);
    return () => clearInterval(poll);
  }, [draft?.active]);

  const togglePlayer = (name: string) => {
    setSelected(prev =>
      prev.includes(name) ? prev.filter(p => p !== name) : prev.length < 10 ? [...prev, name] : prev
    );
  };

  const handleDraft = async () => {
    if (selected.length !== 10) return;
    setLoading(true);
    try {
      const activeToken = token || Cookies.get('token');
      const result = await runDraft({ selected_players: selected, mode }, activeToken);
      setDraft({ active: true, ...result });
      setError('');
    } catch (e: unknown) {
      console.error("Draft Error:", e);
      setError(e instanceof Error ? e.message : 'Draft failed');
    }
    setLoading(false);
  };

  const handleReroll = async () => {
    if (!draft) return;
    setLoading(true);
    try {
      const activeToken = token || Cookies.get('token');
      const result = await rerollDraft({
        current_players: [...draft.team1, ...draft.team2],
        mode: draft.mode,
      }, activeToken);
      setDraft({ active: true, ...result });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Reroll failed');
    }
    setLoading(false);
  };

  const handleClear = async () => {
    const activeToken = token || Cookies.get('token');
    if (activeToken) await clearDraft(activeToken);
    setDraft(null);
    setVeto(null);
    setSelected([]);
    setLobbyLink('');
    setBannedMaps([]);
  };

  const handleInitVeto = async () => {
    try {
      const v = await initVeto();
      setVeto({ initialized: true, remaining: v.maps, protected: [], turn_team: v.winner });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Veto init failed');
    }
  };

  const handleVetoPick = async (mapName: string) => {
    if (!veto || !draft) return;
    try {
      const result = await vetoAction({ map_name: mapName, acting_team: veto.turn_team || '' });
      if (result.complete) {
        setVeto({ initialized: true, remaining: [], protected: result.final_maps, complete: true });
        setBannedMaps([]);
        const d = await getDraftState();
        if (d.active) setDraft(d);
      } else {
        setBannedMaps(prev => {
          if (result.remaining && constants.map_pool) {
            return constants.map_pool.filter(m => !result.remaining.includes(m) && !result.protected?.includes(m));
          }
          return prev;
        });
        setVeto({
          initialized: true,
          remaining: result.remaining,
          protected: result.protected,
          turn_team: result.next_turn,
          complete: false,
        });
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Veto action failed');
    }
  };

  const handleCreateLobby = async () => {
    try {
      const res = await createLobby();
      setLobbyLink(res.link);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Lobby creation failed');
    }
  };

  const handleBroadcast = async () => {
    if (!draft || !lobbyLink) return;
    try {
      await broadcastToDiscord({
        name_a: draft.name_a,
        team1: draft.team1,
        name_b: draft.name_b,
        team2: draft.team2,
        maps: draft.map_pick || '',
        lobby_link: lobbyLink,
      }, token || undefined);
    } catch { /* ignore */ }
  };

  if (loading || authLoading) {
    return (
      <div className="page-container">
        <div className="loading-spinner"><div className="spinner" /></div>
      </div>
    );
  }

  // ─── DRAFT ACTIVE ────────────────────────
  if (draft?.active) {
    const total = draft.avg1 + draft.avg2;
    const pct1 = total > 0 ? (draft.avg1 / total) * 100 : 50;

    return (
      <div className="page-container">
        <div className="page-header">
          <h1 className="page-title">⚔️ Teams Drafted</h1>
          <p className="page-subtitle">Mode: {(draft.mode || 'balanced').replace('_', ' ').toUpperCase()}</p>
        </div>

        {error && <div className="error-message">{error}</div>}

        {/* Team comparison bar */}
        <div style={{ marginBottom: 24 }}>
          <div className="comparison-labels">
            <span className="text-blue">{draft.name_a} — {draft.avg1.toFixed(1)}</span>
            <span className="text-orange">{draft.name_b} — {draft.avg2.toFixed(1)}</span>
          </div>
          <div className="comparison-bar">
            <div className="comparison-bar-fill-blue" style={{ width: `${pct1}%` }} />
            <div className="comparison-bar-fill-orange" style={{ width: `${100 - pct1}%` }} />
          </div>
        </div>

        {/* Reroll Notification */}
        {draft.votes?.some(v => v.vote === 'Reroll' || v.vote === 'BANNED') && (
          <div className="reroll-banner" style={{ maxWidth: 800, margin: '0 auto 24px' }}>
            <span style={{ fontSize: 20 }}>🎲</span>
            <div>
              <strong>REROLL IN PROGRESS</strong>
              <p style={{ margin: 0, fontSize: 12, opacity: 0.8 }}>A captain has requested a reroll. Approvals are reset.</p>
            </div>
          </div>
        )}

        {/* Teams */}
        <div className="grid-2" style={{ marginBottom: 32 }}>
          {[1, 2].map(teamNum => {
            const isTeam1 = teamNum === 1;
            const teamName = isTeam1 ? draft.name_a : draft.name_b;
            const rawPlayers = isTeam1 ? draft.team1 : draft.team2;
            const teamPlayers = rawPlayers ? [...rawPlayers].sort((a, b) => (draft.ratings?.[b] || 0) - (draft.ratings?.[a] || 0)) : [];
            const colorClass = isTeam1 ? 'team-blue' : 'team-orange';

            return (
              <div key={teamNum} className="card">
                <div className={`team-header ${colorClass}`}>{isTeam1 ? '🔵' : '🔴'} {teamName}</div>
                {teamPlayers.map((p, idx) => {
                  const rating = draft.ratings?.[p] || 0;
                  return (
                    <div
                      key={`${draft.active}-${p}`}
                      className="player-chip stagger-in"
                      style={{ animationDelay: `${idx * 0.1}s`, justifyContent: 'space-between', cursor: 'pointer' }}
                      onClick={() => setViewingPlayer(p)}
                      title="Click for stats"
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        {draft.votes?.find(v => v.captain_name === p) && <span className="player-chip-crown">👑</span>}
                        <span>{p === 'Skeez' && skeezTitle ? `${skeezTitle} (${p})` : p}</span>
                        {draft.pings?.[p] && (
                          <span style={{ fontSize: 10, color: getPingColor(draft.pings[p]), marginLeft: 4 }}>
                            {draft.pings[p]}ms
                          </span>
                        )}
                        <span style={{ fontSize: 10, opacity: 0.5 }}>📊</span>
                      </div>
                      <span className="font-orbitron" style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                        {rating.toFixed(2)}
                      </span>
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>

        {/* Modal */}
        {viewingPlayer && (
          <PlayerStatsModal
            playerName={viewingPlayer}
            onClose={() => setViewingPlayer(null)}
          />
        )}

        {/* Veto Section */}
        {!veto?.initialized && !draft.map_pick && (
          <div style={{ textAlign: 'center', marginBottom: 32 }}>
            <button className="btn btn-primary" onClick={handleInitVeto}>🪙 Start Coin Flip & Veto</button>
          </div>
        )}

        {veto?.initialized && !veto.complete && veto.remaining && veto.remaining.length > 0 && (
          <div className="card" style={{ marginBottom: 32 }}>
            <div className="card-header">
              {(veto.protected?.length || 0) < 2 ? '🗺️ PICK PHASE' : '❌ BAN PHASE'} — {veto.turn_team}&apos;s Turn
            </div>
            <div className="grid-7">
              {constants.map_pool.map(m => {
                const isRemaining = veto.remaining!.includes(m);
                const isProtected = veto.protected?.includes(m);
                const isBanned = bannedMaps.includes(m);

                return (
                  <div
                    key={m}
                    className={`map-card ${isBanned ? 'banned' : ''} ${isProtected ? 'protected' : ''}`}
                    onClick={() => isRemaining && !isProtected ? handleVetoPick(m) : null}
                  >
                    <img src={constants.map_logos[m]} alt={m} />
                    <div className="map-card-name">{m}</div>
                    {isBanned && <div className="banned-overlay">BANNED</div>}
                    {isProtected && <div style={{ position: 'absolute', top: 4, right: 4, fontSize: 14, fontWeight: 700, color: 'var(--neon-green)' }}>MAP {(veto.protected?.indexOf(m) ?? 0) + 1}</div>}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {(veto?.complete || draft.map_pick) && (
          <div className="lobby-box" style={{ marginBottom: 32 }}>
            <div className="lobby-box-title">🗺️ MAP SELECTED</div>
            <div className="font-orbitron text-gold" style={{ fontSize: 24, fontWeight: 800, marginBottom: 16 }}>
              {draft.map_pick || veto?.protected?.join(', ')}
            </div>
            {draft.map_pick && (
              <div style={{ display: 'flex', justifyContent: 'center', gap: 12, flexWrap: 'wrap' }}>
                {String(draft.map_pick).split(',').map(m => (
                  <img key={m.trim()} src={constants.map_logos[m.trim()]} alt={m.trim()} style={{ width: 160, borderRadius: 8 }} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Lobby */}
        {lobbyLink ? (
          <div className="lobby-box" style={{ marginBottom: 24 }}>
            <div className="lobby-box-title">🚀 LOBBY READY</div>
            <p style={{ textAlign: 'center', color: 'var(--text-primary)', marginBottom: 16, fontSize: 18, fontWeight: 600 }}>
              ⚠️ EVERYONE JOIN THE SERVER NOW ⚠️
            </p>
            <div className="lobby-box-link">
              <a href={lobbyLink} target="_blank" rel="noopener noreferrer">{lobbyLink}</a>
            </div>
            <div className="lobby-box-password">🔑 Password: kimkim</div>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
              <a href={lobbyLink} target="_blank" rel="noopener noreferrer" className="btn btn-primary">JOIN SERVER</a>
            </div>
          </div>
        ) : (
          (user?.role === 'admin' || (draft.created_by && user?.display_name === draft.created_by)) && (
            <div style={{ textAlign: 'center', marginBottom: 24 }}>
              <button className="btn" onClick={handleCreateLobby}>🔧 Create Cybershoke Lobby</button>
            </div>
          )
        )}

        {/* Admin controls */}
        <div className="divider" />
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
          <button className="btn" onClick={handleReroll}>🔀 Reroll Teams</button>
          <button className="btn btn-danger" onClick={handleClear}>🗑️ Clear Draft</button>

          {(user?.role === 'admin' || (draft.created_by && user?.display_name === draft.created_by)) && lobbyLink && (
            <button className="btn btn-primary" onClick={handleBroadcast}>
              📢 Send to Discord
            </button>
          )}
        </div>
      </div>
    );
  }

  // ─── PLAYER SELECTION ────────────────────
  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">🎮 Mixer & Draft</h1>
        <p className="page-subtitle">Select 10 players and choose a balancing mode</p>
      </div>

      {error && <div className="error-message">{error}</div>}

      {/* Draft mode selector */}
      <div className="card" style={{ marginBottom: 24, display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ fontWeight: 600, color: 'var(--text-secondary)', fontSize: 13 }}>BALANCE MODE:</span>
        {[
          { key: 'balanced', label: '⚖️ Balanced', desc: 'Rating-based' },
          { key: 'kd_balanced', label: '🎯 K/D', desc: 'Kill/Death ratio' },
          { key: 'hltv_balanced', label: '📈 HLTV', desc: 'HLTV Rating' },
          { key: 'chaos', label: '🎲 Chaos', desc: 'Random!' },
        ].map(m => (
          <button
            key={m.key}
            className={`btn btn-sm ${mode === m.key ? 'btn-primary' : ''}`}
            onClick={() => setMode(m.key)}
            title={m.desc}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* Player grid */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
          <strong style={{ color: selected.length === 10 ? 'var(--neon-green)' : 'var(--text-primary)' }}>{selected.length}</strong>/10 selected
        </span>
        {selected.length > 0 && (
          <button className="btn btn-sm" onClick={() => setSelected([])}>Clear</button>
        )}
      </div>

      <div className="grid-5" style={{ marginBottom: 32 }}>
        {players.map(p => (
          <div
            key={p.name}
            className={`player-chip ${selected.includes(p.name) ? 'selected' : ''}`}
            onClick={() => togglePlayer(p.name)}
            style={{ justifyContent: 'space-between' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 18 }}>{selected.includes(p.name) ? '✅' : '⬜'}</span>
              <div>
                <div style={{ fontWeight: 600 }}>
                  {p.name}
                  {p.ping && (
                    <span style={{ fontSize: 11, color: getPingColor(p.ping), marginLeft: 6, fontWeight: 400 }}>
                      {p.ping}ms
                    </span>
                  )}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  OVR: {p.overall?.toFixed(1)} | ELO: {p.elo}
                </div>
              </div>
            </div>
            <button
              className="btn-info-small"
              onClick={(e) => { e.stopPropagation(); setViewingPlayer(p.name); }}
              title="View Statistics"
            >
              📊
            </button>
          </div>
        ))}
      </div>

      {/* Draft button */}
      <div style={{ textAlign: 'center' }}>
        <button
          className="btn btn-primary"
          disabled={selected.length !== 10}
          onClick={handleDraft}
          style={{ fontSize: 18, padding: '16px 48px' }}
        >
          ⚡ DRAFT TEAMS
        </button>
      </div>

      {/* Selection Modal */}
      {viewingPlayer && !draft?.active && (
        <PlayerStatsModal playerName={viewingPlayer} onClose={() => setViewingPlayer(null)} />
      )}
    </div>
  );
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function fetchApi(path: string, options?: RequestInit) {
    const res = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers: { 'Content-Type': 'application/json', ...options?.headers },
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || res.statusText);
    }
    return res.json();
}

export const sendPing = (ping: number) => fetchApi('/api/ping', { method: 'POST', body: JSON.stringify({ ping }) });

// Constants
export const getConstants = () => fetchApi('/api/constants');
export const getSeasons = () => fetchApi('/api/seasons');

// Players
export const getPlayers = () => fetchApi('/api/players');
export const createPlayer = (data: { name: string; aim: number; util: number; team_play: number }) =>
    fetchApi('/api/players', { method: 'POST', body: JSON.stringify(data) });
export const updatePlayer = (name: string, data: { aim: number; util: number; team_play: number }) =>
    fetchApi(`/api/players/${encodeURIComponent(name)}`, { method: 'PUT', body: JSON.stringify(data) });
export const deletePlayer = (name: string) =>
    fetchApi(`/api/players/${encodeURIComponent(name)}`, { method: 'DELETE' });

// Draft
export const runDraft = (data: { selected_players: string[]; mode: string }, token?: string) =>
    fetchApi('/api/draft', {
        method: 'POST',
        body: JSON.stringify(data),
        headers: token ? { 'Authorization': `Bearer ${token}` } : undefined
    });
export const getDraftState = (token?: string) =>
    fetchApi('/api/draft/state', token ? { headers: { 'Authorization': `Bearer ${token}` } } : undefined);
export const stepInAsCaptain = (token: string) =>
    fetchApi('/api/draft/step_in', { method: 'POST', headers: { 'Authorization': `Bearer ${token}` } });
export const rerollDraft = (data: { current_players: string[]; mode: string; force_captains?: string[]; keep_map?: boolean }, token?: string) =>
    fetchApi('/api/draft/reroll', {
        method: 'POST',
        body: JSON.stringify(data),
        headers: token ? { 'Authorization': `Bearer ${token}` } : undefined
    });
export const clearDraft = (token?: string) =>
    fetchApi('/api/draft', {
        method: 'DELETE',
        headers: token ? { 'Authorization': `Bearer ${token}` } : undefined
    });
export const updateElo = (data: { team1: string[]; team2: string[]; name_a: string; name_b: string; winner_idx: number; map_name: string }) =>
    fetchApi('/api/draft/elo', { method: 'POST', body: JSON.stringify(data) });

// Veto
export const getVetoState = () => fetchApi('/api/veto/state');
export const initVeto = () => fetchApi('/api/veto/init', { method: 'POST' });
export const resetVeto = (token?: string) =>
    fetchApi('/api/veto/reset', { method: 'POST', headers: token ? { 'Authorization': `Bearer ${token}` } : undefined });
export const vetoAction = (data: { map_name: string; acting_team: string }) =>
    fetchApi('/api/veto/action', { method: 'POST', body: JSON.stringify(data) });

// Votes
export const getVotes = () => fetchApi('/api/votes');
export const submitVote = (data: { token: string; vote: string }) =>
    fetchApi('/api/votes', { method: 'POST', body: JSON.stringify(data) });
export const getCaptainInfo = (token: string) => fetchApi(`/api/votes/${token}`);

// Captain Auth
export const captainLogin = (name: string) =>
    fetchApi('/api/captain/login', { method: 'POST', body: JSON.stringify({ name }) });
export const captainClaim = (name: string) =>
    fetchApi('/api/captain/claim', { method: 'POST', body: JSON.stringify({ name }) });
export const getCaptainState = (name: string) =>
    fetchApi(`/api/captain/state?name=${encodeURIComponent(name)}`);

// Leaderboard & Stats
export const getLeaderboard = (season: string = 'Season 2 (Demos)') =>
    fetchApi(`/api/leaderboard?season=${encodeURIComponent(season)}`);
export const getPlayerStats = (name: string, season: string = 'Season 2 (Demos)') =>
    fetchApi(`/api/players/${encodeURIComponent(name)}/stats?season=${encodeURIComponent(season)}`);
export const getPlayerMatches = (name: string, season: string = 'Season 2 (Demos)') =>
    fetchApi(`/api/players/${encodeURIComponent(name)}/matches?season=${encodeURIComponent(season)}`);
export const getPlayerWeapons = (name: string, season: string = 'Season 2 (Demos)') =>
    fetchApi(`/api/players/${encodeURIComponent(name)}/weapons?season=${encodeURIComponent(season)}`);

// Trophies
export const getSeasonTrophies = () => fetchApi('/api/trophies/season');
export const getMatchTrophies = (matchId: string) => fetchApi(`/api/trophies/match/${encodeURIComponent(matchId)}`);

// Matches
export const getRecentMatches = (limit: number = 20) => fetchApi(`/api/matches/recent?limit=${limit}`);
export const getMatchScoreboard = (matchId: string) => fetchApi(`/api/matches/${encodeURIComponent(matchId)}/scoreboard`);

// Lobby
export const getLobby = () => fetchApi('/api/lobby');
export const createLobby = (adminName: string) =>
    fetchApi('/api/lobby/create', { method: 'POST', body: JSON.stringify({ admin_name: adminName }) });
export const deleteLobby = () => fetchApi('/api/lobby', { method: 'DELETE' });

// Discord
export const broadcastToDiscord = (data: { name_a: string; team1: string[]; name_b: string; team2: string[]; maps: string; lobby_link: string }, token?: string) =>
    fetchApi('/api/discord/broadcast', {
        method: 'POST',
        body: JSON.stringify(data),
        headers: token ? { 'Authorization': `Bearer ${token}` } : undefined
    });
export const broadcastLobbyToDiscord = (link: string, token?: string) =>
    fetchApi(`/api/discord/lobby?link=${encodeURIComponent(link)}`, {
        method: 'POST',
        headers: token ? { 'Authorization': `Bearer ${token}` } : undefined
    });

// Admin - Lobbies
export const getLobbyHistory = () => fetchApi('/api/lobbies');
export const addLobbyRecord = (id: string) => fetchApi(`/api/lobbies/${id}`, { method: 'POST' });
export const updateLobbyStatus = (id: string, has_demo?: number, status?: string) => {
    const params = new URLSearchParams();
    if (has_demo !== undefined) params.set('has_demo', String(has_demo));
    if (status) params.set('status', status);
    return fetchApi(`/api/lobbies/${id}/status?${params}`, { method: 'PUT' });
};
export const analyzeLobby = (id: string) => fetchApi(`/api/admin/analyze/${id}`, { method: 'POST' });

/** Fetch live match data from Cybershoke API (no demo download, instant). */
export const lobbyQuickCheck = (lobbyId: string, token: string) =>
    fetchApi(`/api/admin/lobby-check/${encodeURIComponent(lobbyId)}`, {
        headers: { 'Authorization': `Bearer ${token}` },
    });

/** Full pipeline: download demo → analyse → reconcile web stats → save to DB. */
export const importLobbyFull = (data: { lobby_id: string; admin_name?: string }, token: string) =>
    fetchApi('/api/admin/import-lobby', {
        method: 'POST',
        body: JSON.stringify(data),
        headers: { 'Authorization': `Bearer ${token}` },
    });

// Roommates
export const getRoommates = () => fetchApi('/api/roommates');
export const setRoommates = (groups: string[][]) =>
    fetchApi('/api/roommates', { method: 'POST', body: JSON.stringify({ groups }) });

// Admin - Users
export const getUsers = (token: string) =>
    fetchApi('/api/admin/users', { headers: { 'Authorization': `Bearer ${token}` } });
export const updateUserRole = (userId: string, role: string, token: string) =>
    fetchApi(`/api/admin/users/${userId}/role?role=${encodeURIComponent(role)}`, { method: 'PUT', headers: { 'Authorization': `Bearer ${token}` } });
export const deleteUser = (userId: string, token: string) =>
    fetchApi(`/api/admin/users/${userId}`, { method: 'DELETE', headers: { 'Authorization': `Bearer ${token}` } });
export const syncPlayers = (token: string) =>
    fetchApi('/api/admin/sync-players', { method: 'POST', headers: { 'Authorization': `Bearer ${token}` } });

export const adminCreateUser = (data: {
    username: string; password: string; display_name?: string; role?: string;
    aim?: number; util?: number; team_play?: number;
}, token: string) =>
    fetchApi('/api/admin/users/create', { method: 'POST', body: JSON.stringify(data), headers: { 'Authorization': `Bearer ${token}` } });

export const adminUpdateUser = (userId: string, data: {
    display_name?: string; role?: string; is_active?: boolean; avatar_url?: string;
}, token: string) =>
    fetchApi(`/api/admin/users/${userId}`, { method: 'PUT', body: JSON.stringify(data), headers: { 'Authorization': `Bearer ${token}` } });

export const adminResetPassword = (userId: string, password: string, token: string) =>
    fetchApi(`/api/admin/users/${userId}/password`, { method: 'PUT', body: JSON.stringify({ password }), headers: { 'Authorization': `Bearer ${token}` } });

export const adminUpdateScores = (userId: string, data: {
    aim?: number; util?: number; team_play?: number; elo?: number;
}, token: string) =>
    fetchApi(`/api/admin/users/${userId}/scores`, { method: 'PUT', body: JSON.stringify(data), headers: { 'Authorization': `Bearer ${token}` } });

// Tournaments
export const getTournaments = (status?: string) =>
    fetchApi(`/api/tournaments${status ? `?status=${status}` : ''}`);
export const createTournament = (data: {
    name: string; description?: string; format?: string;
    prize_image_url?: string; prize_name?: string; prize_pool?: string;
    max_players?: number; playoffs?: boolean; tournament_date?: string;
}, token: string) =>
    fetchApi('/api/tournaments', { method: 'POST', body: JSON.stringify(data), headers: { 'Authorization': `Bearer ${token}` } });
export const getTournament = (id: string) =>
    fetchApi(`/api/tournaments/${id}`);
export const updateTournament = (id: string, data: {
    description?: string; rules?: string; prize_image_url?: string;
}, token: string) =>
    fetchApi(`/api/tournaments/${id}`, { method: 'PUT', body: JSON.stringify(data), headers: { 'Authorization': `Bearer ${token}` } });
export const joinTournament = (id: string, token: string) =>
    fetchApi(`/api/tournaments/${id}/join`, { method: 'POST', headers: { 'Authorization': `Bearer ${token}` } });
export const leaveTournament = (id: string, token: string) =>
    fetchApi(`/api/tournaments/${id}/leave`, { method: 'DELETE', headers: { 'Authorization': `Bearer ${token}` } });
export const startTournament = (id: string, token: string) =>
    fetchApi(`/api/tournaments/${id}/start`, { method: 'POST', headers: { 'Authorization': `Bearer ${token}` } });
export const getTournamentBracket = (id: string) =>
    fetchApi(`/api/tournaments/${id}/bracket`);
export const createTournamentLobby = (matchId: string, adminName: string, token: string) =>
    fetchApi(`/api/matches/${matchId}/create-lobby`, { method: 'POST', body: JSON.stringify({ admin_name: adminName }), headers: { 'Authorization': `Bearer ${token}` } });
export const advanceWinner = (matchId: string, winnerId: string, token: string) =>
    fetchApi(`/api/matches/${matchId}/advance-winner`, { method: 'POST', body: JSON.stringify({ winner_id: winnerId }), headers: { 'Authorization': `Bearer ${token}` } });
export const reportMatch = (matchId: string, winnerId: string, score: string | null, token: string) =>
    fetchApi(`/api/matches/${matchId}/report`, { method: 'POST', body: JSON.stringify({ winner_id: winnerId, score }), headers: { 'Authorization': `Bearer ${token}` } });
export const submitMatchLobby = (matchId: string, lobbyUrl: string, token: string) =>
    fetchApi(`/api/matches/${matchId}/submit-lobby`, { method: 'POST', body: JSON.stringify({ lobby_url: lobbyUrl }), headers: { 'Authorization': `Bearer ${token}` } });
export const deleteTournament = (id: string, token: string) =>
    fetchApi(`/api/tournaments/${id}`, { method: 'DELETE', headers: { 'Authorization': `Bearer ${token}` } });

// CS2 Skin Search
export const searchSkins = (query: string) =>
    fetchApi(`/api/skins/search?q=${encodeURIComponent(query)}`);

// Image Upload (Supabase Storage)
export const uploadImage = async (file: File, token: string): Promise<{ url: string; filename: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/api/upload/image`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || res.statusText);
    }
    return res.json();
};

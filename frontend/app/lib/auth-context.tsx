'use client';
import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface User {
    username: string;
    role: string;
    display_name: string;
    avatar_url?: string;
    is_captain?: boolean;
    captain_pin?: string;
    captain_vote?: string;
    in_draft?: boolean;
    draft_role?: string;
}

interface AuthContextType {
    user: User | null;
    token: string | null;
    loading: boolean;
    login: (username: string, password: string) => Promise<void>;
    register: (username: string, password: string, displayName?: string) => Promise<void>;
    googleLogin: (credential: string) => Promise<void>;
    logout: () => void;
    refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
    user: null, token: null, loading: true,
    login: async () => { }, register: async () => { }, googleLogin: async () => { },
    logout: () => { }, refreshUser: async () => { },
});

export function useAuth() { return useContext(AuthContext); }

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [token, setToken] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    const fetchMe = useCallback(async (t: string) => {
        try {
            const res = await fetch(`${API_BASE}/api/auth/me`, {
                headers: { 'Authorization': `Bearer ${t}` },
            });
            if (res.ok) {
                const data = await res.json();
                setUser(data);
                return true;
            }
        } catch { /* ignore */ }
        return false;
    }, []);

    // Load token from localStorage on mount
    useEffect(() => {
        const stored = localStorage.getItem('cs2_token');
        if (stored) {
            setToken(stored);
            fetchMe(stored).then(ok => {
                if (!ok) {
                    localStorage.removeItem('cs2_token');
                    setToken(null);
                }
                setLoading(false);
            });
        } else {
            setLoading(false);
        }
    }, [fetchMe]);

    const login = async (username: string, password: string) => {
        const res = await fetch(`${API_BASE}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: 'Login failed' }));
            throw new Error(err.detail || 'Login failed');
        }
        const data = await res.json();
        localStorage.setItem('cs2_token', data.token);
        setToken(data.token);
        setUser({ username: data.username, role: data.role, display_name: data.display_name });
    };

    const register = async (username: string, password: string, displayName?: string) => {
        const res = await fetch(`${API_BASE}/api/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, display_name: displayName || username }),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: 'Registration failed' }));
            throw new Error(err.detail || 'Registration failed');
        }
        const data = await res.json();
        localStorage.setItem('cs2_token', data.token);
        setToken(data.token);
        setUser({ username: data.username, role: data.role, display_name: data.display_name });
    };

    const googleLogin = async (credential: string) => {
        const res = await fetch(`${API_BASE}/api/auth/google`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ credential }),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: 'Google login failed' }));
            throw new Error(err.detail || 'Google login failed');
        }
        const data = await res.json();
        localStorage.setItem('cs2_token', data.token);
        setToken(data.token);
        setUser({ username: data.username, role: data.role, display_name: data.display_name });
    };

    const logout = () => {
        localStorage.removeItem('cs2_token');
        setToken(null);
        setUser(null);
    };

    const refreshUser = async () => {
        if (token) await fetchMe(token);
    };

    return (
        <AuthContext.Provider value={{ user, token, loading, login, register, googleLogin, logout, refreshUser }}>
            {children}
        </AuthContext.Provider>
    );
}

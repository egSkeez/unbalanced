"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import axios from "axios";
import Cookies from "js-cookie";
import { useRouter } from "next/navigation";

// Define the User type matching backend
export interface User {
    id: string;
    username: string;
    display_name: string;
    role: string;
    is_active: boolean;
    created_at: string;
    avatar_url?: string;
    is_captain?: boolean;
    in_draft?: boolean;
    draft_team_name?: string;
    ping?: number;
    captain_cooldown?: number;
}

interface AuthContextType {
    user: User | null;
    token: string | null;
    loading: boolean;
    login: (token: string, user: User) => void;
    logout: () => void;
    refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
    const [user, setUser] = useState<User | null>(null);
    const [token, setToken] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const router = useRouter();

    // Initialize Auth State from Token
    useEffect(() => {
        const initAuth = async () => {
            const storedToken = Cookies.get("token");
            if (storedToken) {
                setToken(storedToken);
                try {
                    // Validate token & get user data
                    // We set the default header for axios here
                    axios.defaults.headers.common["Authorization"] = `Bearer ${storedToken}`;
                    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
                    const { data } = await axios.get(`${apiBase}/api/auth/me`);
                    setUser(data);
                } catch (error) {
                    console.error("Auth initialization failed:", error);
                    logout();
                }
            }
            setLoading(false);
        };

        initAuth();
    }, []);

    // Ping Tracker
    useEffect(() => {
        if (!user || !token) return;

        const measurePing = async () => {
            const start = performance.now();
            try {
                // Fetch a small resource from Google (DNS API)
                // Mode 'no-cors' might reduce overhead/errors but returns opaque response.
                // However, we need to wait for it.
                // 'cors' is better if supported. dns.google supports CORS.
                await fetch('https://dns.google/resolve?name=google.com');
                const end = performance.now();
                const ping = Math.round(end - start);

                // Update local state (optimistic)
                setUser(prev => prev ? { ...prev, ping } : null);

                // Send to backend
                const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
                await axios.post(`${apiBase}/api/ping`, { ping });
            } catch (e) {
                console.error("Ping failed", e);
            }
        };

        measurePing();
        const interval = setInterval(measurePing, 3000); // 3 seconds
        return () => clearInterval(interval);
    }, [user?.username, token]); // Re-run if user changes or token refreshes 

    // Periodic user refresh (keeps sidebar "Live Draft" indicator current)
    useEffect(() => {
        if (!token) return;

        const refreshInterval = setInterval(async () => {
            const storedToken = Cookies.get("token");
            if (!storedToken) return;
            const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            try {
                const { data } = await axios.get(`${apiBase}/api/auth/me`, {
                    headers: { Authorization: `Bearer ${storedToken}` },
                });
                setUser(prev => prev ? {
                    ...prev,
                    in_draft: data.in_draft,
                    is_captain: data.is_captain,
                    draft_team_name: data.draft_team_name,
                    draft_role: data.draft_role,
                } : null);
            } catch {
                // Ignore refresh errors
            }
        }, 3000); // 3 seconds — fast enough for draft indicator

        return () => clearInterval(refreshInterval);
    }, [token]);


    const login = (newToken: string, userData: User) => {
        Cookies.set("token", newToken, { expires: 90 }); // 90 days
        setToken(newToken);
        axios.defaults.headers.common["Authorization"] = `Bearer ${newToken}`;
        setUser(userData);
        router.push("/");
    };

    const logout = () => {
        Cookies.remove("token");
        setToken(null);
        delete axios.defaults.headers.common["Authorization"];
        setUser(null);
        router.push("/login");
    };

    const refreshUser = async () => {
        const storedToken = Cookies.get("token");
        if (!storedToken) return;
        const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        try {
            const { data } = await axios.get(`${apiBase}/api/auth/me`);
            setUser(data);
        } catch (e) {
            console.error("Failed to refresh user", e);
        }
    }

    return (
        <AuthContext.Provider value={{ user, token, loading, login, logout, refreshUser }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error("useAuth must be used within an AuthProvider");
    }
    return context;
};

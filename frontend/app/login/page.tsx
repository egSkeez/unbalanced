"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import axios from "axios";
import { useAuth } from "@/context/AuthContext";
import { useState } from "react";
import Link from "next/link";

const loginSchema = z.object({
    username: z.string().min(1, "Username is required"),
    password: z.string().min(1, "Password is required"),
});

type FormData = z.infer<typeof loginSchema>;

export default function LoginPage() {
    const { login } = useAuth();
    const [error, setError] = useState("");
    const {
        register,
        handleSubmit,
        formState: { errors, isSubmitting },
    } = useForm<FormData>({
        resolver: zodResolver(loginSchema),
    });

    const onSubmit = async (data: FormData) => {
        setError("");
        try {
            const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            const res = await axios.post(`${apiBase}/api/auth/token`, data);
            const token = res.data.access_token;

            axios.defaults.headers.common["Authorization"] = `Bearer ${token}`;
            const meRes = await axios.get(`${apiBase}/api/auth/me`);

            login(token, meRes.data);
        } catch (err: any) {
            console.error(err);
            if (err.response) {
                setError(err.response.data.detail || "Login failed");
            } else {
                setError("Network error");
            }
        }
    };

    return (
        <div className="auth-page">
            <div className="auth-card">
                <h2 className="auth-title">Sign In</h2>
                <p className="auth-subtitle">Welcome back to Unbalanced</p>

                <form onSubmit={handleSubmit(onSubmit)}>
                    <div>
                        <input
                            id="username"
                            type="text"
                            autoComplete="username"
                            className="auth-input"
                            placeholder="Username"
                            {...register("username")}
                        />
                        {errors.username && (
                            <p className="auth-error">{errors.username.message}</p>
                        )}
                        <input
                            id="password"
                            type="password"
                            autoComplete="current-password"
                            className="auth-input"
                            placeholder="Password"
                            {...register("password")}
                        />
                        {errors.password && (
                            <p className="auth-error">{errors.password.message}</p>
                        )}
                    </div>

                    {error && <div className="auth-error">{error}</div>}

                    <button type="submit" disabled={isSubmitting} className="auth-btn">
                        {isSubmitting ? "Signing in..." : "⚡ Sign in"}
                    </button>

                    <div className="auth-link">
                        Don&apos;t have an account?{" "}
                        <Link href="/register">Register</Link>
                    </div>
                </form>
            </div>
        </div>
    );
}

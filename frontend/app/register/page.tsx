"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import axios from "axios";
import { useAuth } from "@/context/AuthContext";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const registerSchema = z.object({
    username: z.string().min(1, "Username is required"),
    password: z.string().min(4, "Password must be at least 4 characters"),
    display_name: z.string().optional(),
});

type FormData = z.infer<typeof registerSchema>;

export default function RegisterPage() {
    const { login } = useAuth();
    const router = useRouter();
    const [error, setError] = useState("");
    const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({
        resolver: zodResolver(registerSchema),
    });

    const onSubmit = async (data: FormData) => {
        setError("");
        try {
            const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            const { data: regData } = await axios.post(`${apiBase}/api/auth/register`, data);

            const loginRes = await axios.post(`${apiBase}/api/auth/token`, {
                username: data.username,
                password: data.password
            });

            login(loginRes.data.access_token, regData);
        } catch (err: any) {
            if (err.response) {
                setError(err.response.data.detail || "Registration failed");
            } else {
                setError("Network error");
            }
        }
    };

    return (
        <div className="auth-page">
            <div className="auth-card">
                <h2 className="auth-title">Create Account</h2>
                <p className="auth-subtitle">Join the Unbalanced community</p>

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
                        {errors.username && <p className="auth-error">{errors.username.message}</p>}
                        <input
                            id="display_name"
                            type="text"
                            autoComplete="nickname"
                            className="auth-input"
                            placeholder="Display Name (Optional)"
                            {...register("display_name")}
                        />
                        <input
                            id="password"
                            type="password"
                            autoComplete="new-password"
                            className="auth-input"
                            placeholder="Password"
                            {...register("password")}
                        />
                        {errors.password && <p className="auth-error">{errors.password.message}</p>}
                    </div>

                    {error && <div className="auth-error">{error}</div>}

                    <button type="submit" disabled={isSubmitting} className="auth-btn">
                        {isSubmitting ? "Registering..." : "⚡ Sign up"}
                    </button>

                    <div className="auth-link">
                        Already have an account?{" "}
                        <Link href="/login">Login</Link>
                    </div>
                </form>
            </div>
        </div>
    );
}

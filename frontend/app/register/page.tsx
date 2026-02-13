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
    const { login } = useAuth(); // Ideally we auto login
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

            // 2. Auto-login to get token
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
        <div className="flex min-h-screen items-center justify-center bg-gray-900 text-white">
            <div className="w-full max-w-md space-y-8 rounded-lg bg-gray-800 p-8 shadow-lg">
                <div>
                    <h2 className="mt-6 text-center text-3xl font-bold tracking-tight">
                        Create Account
                    </h2>
                </div>
                <form className="mt-8 space-y-6" onSubmit={handleSubmit(onSubmit)}>
                    <div className="-space-y-px rounded-md shadow-sm">
                        <div>
                            <label htmlFor="username" className="sr-only">
                                Username
                            </label>
                            <input
                                id="username"
                                type="text"
                                autoComplete="username"
                                className="relative block w-full rounded-t-md border-0 bg-gray-700 py-1.5 text-white ring-1 ring-inset ring-gray-600 placeholder:text-gray-400 focus:z-10 focus:ring-2 focus:ring-indigo-500 sm:text-sm sm:leading-6 px-3"
                                placeholder="Username"
                                {...register("username")}
                            />
                            {errors.username && <p className="text-red-500 text-xs mt-1">{errors.username.message}</p>}
                        </div>
                        <div>
                            <label htmlFor="display_name" className="sr-only">
                                Display Name (Optional)
                            </label>
                            <input
                                id="display_name"
                                type="text"
                                autoComplete="nickname"
                                className="relative block w-full border-0 bg-gray-700 py-1.5 text-white ring-1 ring-inset ring-gray-600 placeholder:text-gray-400 focus:z-10 focus:ring-2 focus:ring-indigo-500 sm:text-sm sm:leading-6 px-3"
                                placeholder="Display Name (Optional)"
                                {...register("display_name")}
                            />
                        </div>
                        <div>
                            <label htmlFor="password" className="sr-only">
                                Password
                            </label>
                            <input
                                id="password"
                                type="password"
                                autoComplete="new-password"
                                className="relative block w-full rounded-b-md border-0 bg-gray-700 py-1.5 text-white ring-1 ring-inset ring-gray-600 placeholder:text-gray-400 focus:z-10 focus:ring-2 focus:ring-indigo-500 sm:text-sm sm:leading-6 px-3"
                                placeholder="Password"
                                {...register("password")}
                            />
                            {errors.password && <p className="text-red-500 text-xs mt-1">{errors.password.message}</p>}
                        </div>
                    </div>

                    {error && <div className="text-red-500 text-sm">{error}</div>}

                    <div>
                        <button
                            type="submit"
                            disabled={isSubmitting}
                            className="group relative flex w-full justify-center rounded-md bg-green-600 px-3 py-2 text-sm font-semibold text-white hover:bg-green-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-600 disabled:opacity-50"
                        >
                            {isSubmitting ? "Registering..." : "Sign up"}
                        </button>
                    </div>
                    <div className="text-center text-sm">
                        <span className="text-gray-400">Already have an account? </span>
                        <Link href="/login" className="font-medium text-indigo-400 hover:text-indigo-300">
                            Login
                        </Link>
                    </div>
                </form>
            </div>
        </div>
    );
}

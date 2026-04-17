"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { authLogin, getErrorMessage, setToken } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [registered, setRegistered] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setError(null);
  }, [email, password]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    setRegistered(params.get("registered") === "1");
  }, []);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result = await authLogin(email, password);
      setToken(result.access_token);
      router.push("/");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Failed to sign in"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center p-4">
      <div className="w-full max-w-md rounded-xl border border-gray-800 bg-gray-900 p-6">
        <h1 className="mb-2 text-2xl font-bold">Sign in</h1>
        <p className="mb-6 text-sm text-gray-400">Access your trading dashboard</p>

        {registered && (
          <div className="mb-4 rounded border border-green-700 bg-green-900/30 px-3 py-2 text-sm text-green-300">
            Account created — sign in below
          </div>
        )}

        {error && (
          <div className="mb-4 rounded border border-red-700 bg-red-900/30 px-3 py-2 text-sm text-red-300">
            {error}
          </div>
        )}

        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm text-gray-300">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded border border-gray-800 bg-gray-950 px-3 py-2 text-white focus:border-green-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-gray-300">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded border border-gray-800 bg-gray-950 px-3 py-2 text-white focus:border-green-500 focus:outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded bg-green-600 px-3 py-2 text-sm font-semibold text-white hover:bg-green-500 disabled:opacity-60"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p className="mt-4 text-sm text-gray-400">
          New here?{" "}
          <Link href="/register" className="text-green-400 hover:text-green-300">
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
}

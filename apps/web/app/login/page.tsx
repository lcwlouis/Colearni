"use client";

import { useState, useCallback, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api/client";
import { useAuth } from "@/lib/auth";

type LoginStep = "email" | "verify";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();

  const [step, setStep] = useState<LoginStep>("email");
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [debugToken, setDebugToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleRequestLink = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      setError(null);
      setBusy(true);
      try {
        const res = await apiClient.requestMagicLink(email);
        if (res.debug_token) {
          setDebugToken(res.debug_token);
          setToken(res.debug_token);
        }
        setStep("verify");
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to send magic link.");
      } finally {
        setBusy(false);
      }
    },
    [email],
  );

  const handleVerify = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      setError(null);
      setBusy(true);
      try {
        const res = await apiClient.verifyMagicLink(token);
        login(res.session_token, res.user);
        router.push("/tutor");
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Invalid or expired token.");
      } finally {
        setBusy(false);
      }
    },
    [token, login, router],
  );

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-gray-900 px-4">
      <div className="w-full max-w-sm rounded-2xl bg-white dark:bg-gray-800 p-8 shadow-lg">
        <h1 className="text-2xl font-bold text-center mb-6 text-gray-900 dark:text-white">
          Welcome to Colearni
        </h1>

        {step === "email" && (
          <form onSubmit={handleRequestLink} className="space-y-4">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
              Email address
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-gray-300 dark:border-gray-600 px-4 py-2
                         bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2
                         focus:ring-blue-500 focus:border-transparent"
              placeholder="you@example.com"
            />
            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-lg bg-blue-600 px-4 py-2 text-white font-medium
                         hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {busy ? "Sending…" : "Send magic link"}
            </button>
          </form>
        )}

        {step === "verify" && (
          <form onSubmit={handleVerify} className="space-y-4">
            <p className="text-sm text-gray-600 dark:text-gray-400">
              We sent a magic link to <strong>{email}</strong>.
              {debugToken && (
                <span className="block text-xs text-green-600 dark:text-green-400 mt-1">
                  Dev mode: token auto-filled.
                </span>
              )}
            </p>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
              Verification token
            </label>
            <input
              type="text"
              required
              value={token}
              onChange={(e) => setToken(e.target.value)}
              className="w-full rounded-lg border border-gray-300 dark:border-gray-600 px-4 py-2
                         bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2
                         focus:ring-blue-500 focus:border-transparent font-mono text-sm"
              placeholder="Paste token here"
            />
            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-lg bg-blue-600 px-4 py-2 text-white font-medium
                         hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {busy ? "Verifying…" : "Sign in"}
            </button>
            <button
              type="button"
              onClick={() => { setStep("email"); setError(null); }}
              className="w-full text-sm text-gray-500 dark:text-gray-400 hover:underline"
            >
              Use a different email
            </button>
          </form>
        )}

        {error && (
          <p className="mt-4 text-sm text-red-600 dark:text-red-400 text-center">{error}</p>
        )}
      </div>
    </div>
  );
}

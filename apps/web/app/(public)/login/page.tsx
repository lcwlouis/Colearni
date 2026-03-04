"use client";

import { useState, useCallback, useEffect, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api/client";
import { useAuth } from "@/lib/auth";
import { AuthShell } from "@/components/public/auth-shell";
import { LoginCard, type LoginStep } from "@/components/public/login-card";

export default function LoginPage() {
  const router = useRouter();
  const { user, isLoading, login } = useAuth();

  const [step, setStep] = useState<LoginStep>("email");
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [debugToken, setDebugToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Redirect already-authenticated visitors
  useEffect(() => {
    if (!isLoading && user) {
      router.replace("/tutor");
    }
  }, [user, isLoading, router]);

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

  if (isLoading || user) return null;

  return (
    <AuthShell>
      <LoginCard
        step={step}
        email={email}
        token={token}
        debugToken={debugToken}
        error={error}
        busy={busy}
        onEmailChange={setEmail}
        onTokenChange={setToken}
        onRequestLink={handleRequestLink}
        onVerify={handleVerify}
        onBackToEmail={() => { setStep("email"); setError(null); }}
      />
    </AuthShell>
  );
}

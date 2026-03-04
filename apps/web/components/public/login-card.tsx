import type { FormEvent } from "react";

export type LoginStep = "email" | "verify";

export interface LoginCardProps {
  step: LoginStep;
  email: string;
  token: string;
  debugToken: string | null;
  error: string | null;
  busy: boolean;
  onEmailChange: (value: string) => void;
  onTokenChange: (value: string) => void;
  onRequestLink: (e: FormEvent) => void;
  onVerify: (e: FormEvent) => void;
  onBackToEmail: () => void;
}

export function LoginCard({
  step,
  email,
  token,
  debugToken,
  error,
  busy,
  onEmailChange,
  onTokenChange,
  onRequestLink,
  onVerify,
  onBackToEmail,
}: LoginCardProps) {
  return (
    <div className="login-card">
      <h1 className="login-card-title">Welcome to CoLearni</h1>
      <p className="login-card-subtitle">
        {step === "email"
          ? "Enter your email to receive a magic link."
          : "Check your inbox for a verification token."}
      </p>

      {step === "email" && (
        <form onSubmit={onRequestLink} className="login-card-form">
          <label className="login-card-label" htmlFor="login-email">
            Email address
          </label>
          <input
            id="login-email"
            type="email"
            required
            value={email}
            onChange={(e) => onEmailChange(e.target.value)}
            placeholder="you@example.com"
          />
          <button type="submit" disabled={busy}>
            {busy ? "Sending…" : "Send magic link"}
          </button>
        </form>
      )}

      {step === "verify" && (
        <form onSubmit={onVerify} className="login-card-form">
          <p className="login-card-sent-to">
            We sent a magic link to <strong>{email}</strong>.
          </p>
          {debugToken && (
            <p className="login-card-dev-notice" data-testid="dev-token-notice">
              Dev mode — token auto-filled.
            </p>
          )}
          <label className="login-card-label" htmlFor="login-token">
            Verification token
          </label>
          <input
            id="login-token"
            type="text"
            required
            value={token}
            onChange={(e) => onTokenChange(e.target.value)}
            placeholder="Paste token here"
            style={{ fontFamily: "monospace", fontSize: "0.9rem" }}
          />
          <button type="submit" disabled={busy}>
            {busy ? "Verifying…" : "Sign in"}
          </button>
          <button type="button" className="secondary login-card-back" onClick={onBackToEmail}>
            Use a different email
          </button>
        </form>
      )}

      {error && (
        <p className="login-card-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";

import { getHealth, getWorkspace } from "@/lib/api";
import type { HealthResponse } from "@/lib/api";
import type { Workspace } from "@/lib/types";
import { ensureWorkspaceId } from "@/lib/workspace";

const THEME_KEY = "colearni.theme";

export default function SettingsPage() {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [reasoningView, setReasoningView] = useState<"summary" | "full">("summary");
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem(THEME_KEY);
    const initial = stored === "dark" ? "dark" : "light";
    setTheme(initial);
    if (initial === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, []);

  useEffect(() => {
    const stored = localStorage.getItem("colearni.reasoningView");
    if (stored === "full") setReasoningView("full");
    else setReasoningView("summary");
  }, []);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const id = await ensureWorkspaceId();
        const ws = await getWorkspace(id);
        if (cancelled) return;
        setWorkspace(ws);
        setLoading(false);
      } catch (exc) {
        if (cancelled) return;
        setError(
          exc instanceof Error ? exc.message : "Could not load workspace",
        );
        setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  function toggleTheme() {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    localStorage.setItem(THEME_KEY, next);
    if (next === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }

  function handleReasoningViewChange(value: "summary" | "full") {
    setReasoningView(value);
    localStorage.setItem("colearni.reasoningView", value);
  }

  return (
    <div className="w-full space-y-8 px-4 py-8">
      <header className="space-y-1 border-b border-slate-200 pb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Settings</h1>
        <p className="text-sm leading-6 text-slate-500">
          Manage your workspace and appearance preferences.
        </p>
      </header>

      {/* Workspace section */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-slate-700">Workspace</h2>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          {loading ? (
            <p className="text-sm text-slate-500">Loading workspace…</p>
          ) : error ? (
            <p className="text-sm text-red-600">{error}</p>
          ) : workspace ? (
            <div className="space-y-1">
              <p className="text-xs font-medium text-slate-500">Name</p>
              <p className="text-sm text-slate-900">{workspace.name}</p>
            </div>
          ) : null}
        </div>
      </section>

      {/* Appearance section */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-slate-700">Appearance</h2>
        <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div>
            <p className="text-sm font-medium text-slate-900">Theme</p>
            <p className="text-xs text-slate-500">
              Currently using the <strong>{theme}</strong> theme.
            </p>
          </div>
          <button
            onClick={toggleTheme}
            className="rounded-md border border-slate-300 bg-slate-50 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 transition-colors"
          >
            {theme === "light" ? "Switch to Dark" : "Switch to Light"}
          </button>
        </div>
      </section>

      {/* Tutor section */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-slate-700">Tutor</h2>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-900">Reasoning display</p>
              <p className="text-xs text-slate-500">How AI reasoning traces appear in the tutor panel</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handleReasoningViewChange("summary")}
                className={`rounded-md border px-3 py-1.5 text-sm font-medium transition-colors ${
                  reasoningView === "summary"
                    ? "border-slate-900 bg-slate-900 text-white"
                    : "border-slate-300 bg-slate-50 text-slate-700 hover:bg-slate-100"
                }`}
              >
                Compact
              </button>
              <button
                onClick={() => handleReasoningViewChange("full")}
                className={`rounded-md border px-3 py-1.5 text-sm font-medium transition-colors ${
                  reasoningView === "full"
                    ? "border-slate-900 bg-slate-900 text-white"
                    : "border-slate-300 bg-slate-50 text-slate-700 hover:bg-slate-100"
                }`}
              >
                Full
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* AI Model section */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-slate-700">AI Model</h2>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm space-y-2">
          {health ? (
            <>
              <div className="flex justify-between text-sm">
                <span className="text-slate-500">Provider</span>
                <span className="font-mono text-slate-900">{health.llm_provider}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-slate-500">Model</span>
                <span className="font-mono text-slate-900">{health.llm_model}</span>
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-500">Loading…</p>
          )}
          <p className="text-xs text-slate-400 pt-2">Configured server-side via environment variables.</p>
        </div>
      </section>

      {/* About section */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-slate-700">About</h2>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm space-y-1">
          <p className="text-sm font-medium text-slate-900">CoLearni</p>
          <p className="text-xs text-slate-500">
            A local-ready, graph-first learning workspace. Build Trails,
            learn Socratically, and track your mastery.
          </p>
        </div>
      </section>
    </div>
  );
}

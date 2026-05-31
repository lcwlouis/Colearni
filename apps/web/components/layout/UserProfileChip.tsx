"use client";

import { useEffect, useState } from "react";

const LEVEL_TITLES: [number, string][] = [
  [0, "Curious Beginner"],
  [100, "Active Learner"],
  [300, "Trail Blazer"],
  [600, "Concept Explorer"],
  [1000, "Knowledge Seeker"],
  [1500, "Graph Navigator"],
  [2200, "Mastery Builder"],
  [3000, "Socratic Scholar"],
  [4500, "Deep Thinker"],
  [6500, "Trail Architect"],
];

function computeLevel(xp: number): number {
  let level = 1;
  for (const [threshold] of LEVEL_TITLES) {
    if (xp >= threshold) level++;
    else break;
  }
  return Math.min(level, LEVEL_TITLES.length + 1);
}

function getLevelTitle(xp: number): string {
  let title = LEVEL_TITLES[0][1];
  for (const [threshold, t] of LEVEL_TITLES) {
    if (xp >= threshold) title = t;
    else break;
  }
  return title;
}

function todayString() {
  return new Date().toISOString().slice(0, 10);
}

export default function UserProfileChip() {
  const [xp, setXp] = useState(0);
  const [streak, setStreak] = useState(0);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    // Read or initialise gamification placeholder values from localStorage.
    // These are purely cosmetic and have no effect on mastery, quiz, or any
    // backend state.
    const storedXp = parseInt(localStorage.getItem("colearni.xp") ?? "0", 10);
    let storedStreak = parseInt(
      localStorage.getItem("colearni.streak") ?? "0",
      10,
    );
    const lastVisit = localStorage.getItem("colearni.lastVisit") ?? "";
    const today = todayString();

    if (lastVisit !== today) {
      // New calendar day — increment streak and record today's visit.
      storedStreak = lastVisit ? storedStreak + 1 : 1;
      localStorage.setItem("colearni.streak", String(storedStreak));
      localStorage.setItem("colearni.lastVisit", today);
    }

    setXp(storedXp);
    setStreak(storedStreak);
    setMounted(true);
  }, []);

  // Avoid hydration mismatch — render a placeholder until mounted.
  if (!mounted) {
    return (
      <div className="flex items-center gap-3 px-3 py-3">
        <div className="h-8 w-8 animate-pulse rounded-full bg-slate-200" />
        <div className="flex-1 space-y-1">
          <div className="h-3 w-20 animate-pulse rounded bg-slate-200" />
          <div className="h-2.5 w-14 animate-pulse rounded bg-slate-100" />
        </div>
      </div>
    );
  }

  const level = computeLevel(xp);
  const title = getLevelTitle(xp);

  return (
    <div className="flex flex-col gap-2 px-3 py-3">
      <div className="flex items-center gap-3">
        {/* Avatar */}
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-600 text-xs font-semibold text-white">
          L
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-slate-900">Louis</p>
          <p className="truncate text-xs text-slate-500">
            Level {level} · {title}
          </p>
        </div>
      </div>
      {/* Gamification stats row */}
      <div className="flex items-center gap-3 pl-0.5 text-xs text-slate-500">
        <span className="flex items-center gap-1">
          <span>🔥</span>
          <span className="font-medium text-slate-700">{streak}</span>
        </span>
        <span className="flex items-center gap-1">
          <span>⚡</span>
          <span className="font-medium text-slate-700">
            {xp.toLocaleString()}
          </span>
          <span className="text-slate-400">XP</span>
        </span>
      </div>
    </div>
  );
}

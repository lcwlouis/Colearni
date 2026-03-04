"use client";

import Link from "next/link";
import { GraduationCap, Network, BookOpen } from "lucide-react";

interface NavRailProps {
  pathname: string;
}

export function NavRail({ pathname }: NavRailProps) {
  return (
    <nav className="nav" aria-label="Primary">
      <div className="nav-items-group" style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
        <Link href="/tutor" className={`nav-link ${pathname === "/tutor" ? "active" : ""}`} title="Tutor">
          <GraduationCap className="nav-icon" />
          <span>Tutor</span>
        </Link>
        <Link href="/graph" className={`nav-link ${pathname === "/graph" ? "active" : ""}`} title="Graph">
          <Network className="nav-icon" />
          <span>Graph</span>
        </Link>
        <Link href="/kb" className={`nav-link ${pathname === "/kb" ? "active" : ""}`} title="Sources">
          <BookOpen className="nav-icon" />
          <span>Sources</span>
        </Link>
      </div>
    </nav>
  );
}

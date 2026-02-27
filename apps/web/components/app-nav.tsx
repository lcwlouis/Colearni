"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  ["/tutor", "Tutor"],
  ["/graph", "Graph"],
  ["/practice", "Practice"],
  ["/kb", "KB"],
] as const;

export function AppNav() {
  const pathname = usePathname();
  return (
    <nav className="nav" aria-label="Primary">
      {links.map(([href, label]) => <Link key={href} href={href} className="nav-link" aria-current={pathname === href ? "page" : undefined}>{label}</Link>)}
    </nav>
  );
}

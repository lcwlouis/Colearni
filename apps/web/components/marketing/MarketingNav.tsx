import Link from "next/link";

import { NAV_LINKS } from "@/components/marketing/marketing-content";
import { EnterAppButton } from "@/components/marketing/EnterAppButton";

export function MarketingNav() {
  return (
    <header className="sticky top-0 z-30 border-b border-[var(--mk-border)] bg-[var(--mk-bg)]/80 backdrop-blur">
      <nav className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-5 sm:px-8">
        <Link
          href="/"
          className="font-display text-xl font-semibold tracking-tight text-[var(--mk-fg)]"
        >
          Colearni
        </Link>
        <div className="hidden items-center gap-7 md:flex">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-sm font-medium text-[var(--mk-muted)] transition-colors hover:text-[var(--mk-fg)]"
            >
              {link.label}
            </Link>
          ))}
        </div>
        <EnterAppButton className="inline-flex h-9 items-center justify-center rounded-full bg-[var(--mk-accent)] px-4 text-sm font-semibold text-white transition-transform hover:scale-[1.03] disabled:opacity-60">
          Log in
        </EnterAppButton>
      </nav>
    </header>
  );
}

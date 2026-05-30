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
        <div className="flex items-center gap-2">
          <EnterAppButton className="inline-flex h-9 items-center justify-center rounded-full bg-[var(--mk-accent)] px-4 text-sm font-semibold text-white transition-transform hover:scale-[1.03] disabled:opacity-60">
            Log in
          </EnterAppButton>
          <details className="group relative md:hidden">
            <summary
              aria-label="Open menu"
              className="flex h-9 w-9 cursor-pointer list-none items-center justify-center rounded-full border border-[var(--mk-border)] text-[var(--mk-fg)] [&::-webkit-details-marker]:hidden"
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                aria-hidden="true"
              >
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </summary>
            <div className="absolute right-0 mt-2 w-52 rounded-xl border border-[var(--mk-border)] bg-[var(--mk-card)] p-2 shadow-xl">
              {NAV_LINKS.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="block rounded-lg px-3 py-2 text-sm font-medium text-[var(--mk-muted)] transition-colors hover:bg-[var(--mk-bg-soft)] hover:text-[var(--mk-fg)]"
                >
                  {link.label}
                </Link>
              ))}
            </div>
          </details>
        </div>
      </nav>
    </header>
  );
}

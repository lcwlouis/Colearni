import Link from "next/link";

import {
  CONTACT_EMAIL,
  GITHUB_URL,
  LEGAL_LINKS,
  NAV_LINKS,
} from "@/components/marketing/marketing-content";

export function MarketingFooter() {
  return (
    <footer className="border-t border-[var(--mk-border)] bg-[var(--mk-bg-soft)]">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-5 py-12 sm:px-8 md:flex-row md:items-start md:justify-between">
        <div className="max-w-sm">
          <p className="font-display text-lg font-semibold text-[var(--mk-fg)]">
            Colearni
          </p>
          <p className="mt-2 text-sm leading-6 text-[var(--mk-muted)]">
            A personal learning workspace: a concept graph, a Socratic tutor, and
            mastery you can see.
          </p>
        </div>
        <div className="flex flex-wrap gap-x-10 gap-y-3">
          <nav aria-label="Site pages" className="flex flex-col gap-2">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="text-sm text-[var(--mk-muted)] hover:text-[var(--mk-fg)]"
              >
                {link.label}
              </Link>
            ))}
          </nav>
          <nav aria-label="Contact" className="flex flex-col gap-2">
            <a
              href={`mailto:${CONTACT_EMAIL}`}
              className="text-sm text-[var(--mk-muted)] hover:text-[var(--mk-fg)]"
            >
              {CONTACT_EMAIL}
            </a>
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-[var(--mk-muted)] hover:text-[var(--mk-fg)]"
            >
              GitHub
            </a>
          </nav>
          <nav aria-label="Legal" className="flex flex-col gap-2">
            {LEGAL_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="text-sm text-[var(--mk-muted)] hover:text-[var(--mk-fg)]"
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
      </div>
      <div className="border-t border-[var(--mk-border)] px-5 py-5 text-center text-xs text-[var(--mk-muted)] sm:px-8">
        © {new Date().getFullYear()} Colearni · Source-available, license to be
        announced
      </div>
    </footer>
  );
}

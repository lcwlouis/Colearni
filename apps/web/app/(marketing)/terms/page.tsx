import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Terms & Conditions · Colearni",
  description: "Terms & Conditions for Colearni (draft placeholder).",
};

export default function TermsPage() {
  return (
    <div className="mx-auto w-full max-w-2xl px-5 py-16 sm:px-8 md:py-28">
      <header>
        <p className="font-[family-name:var(--font-geist-mono)] text-xs font-medium uppercase tracking-[0.2em] text-[var(--mk-accent)]">
          Legal
        </p>
        <h1 className="mt-4 font-display text-4xl font-semibold leading-tight tracking-tight text-[var(--mk-fg)] sm:text-5xl">
          Terms &amp; Conditions
        </h1>
      </header>

      <div className="mt-8 rounded-xl border border-[var(--mk-border)] bg-[var(--mk-bg-soft)] p-6">
        <p className="text-sm font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-300">
          Placeholder — not yet finalised
        </p>
        <p className="mt-3 text-base leading-7 text-[var(--mk-muted)]">
          Colearni is still in active development, and our Terms &amp; Conditions
          have not been finalised. This page is a placeholder so the rest of the
          site can link to it. Real terms will appear here before any public
          launch.
        </p>
        <p className="mt-3 text-base leading-7 text-[var(--mk-muted)]">
          Questions in the meantime? See the{" "}
          <Link
            href="/contact"
            className="font-medium text-[var(--mk-accent)] hover:underline"
          >
            contact page
          </Link>
          .
        </p>
      </div>
    </div>
  );
}

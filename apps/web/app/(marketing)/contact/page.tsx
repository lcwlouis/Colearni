import type { Metadata } from "next";
import { Mail, Code2 } from "lucide-react";

import { SectionReveal } from "@/components/marketing/SectionReveal";
import {
  CONTACT_EMAIL,
  GITHUB_URL,
} from "@/components/marketing/marketing-content";

export const metadata: Metadata = {
  title: "Contact · Colearni",
  description: "Get in touch with the Colearni team.",
};

export default function ContactPage() {
  return (
    <div className="mx-auto w-full max-w-2xl px-5 py-16 sm:px-8 md:py-28">
      <header>
        <p className="font-[family-name:var(--font-geist-mono)] text-xs font-medium uppercase tracking-[0.2em] text-[var(--mk-accent)]">
          Contact
        </p>
        <h1 className="mt-4 font-display text-4xl font-semibold leading-tight tracking-tight text-[var(--mk-fg)] sm:text-5xl">
          We&apos;d love to hear from you.
        </h1>
        <p className="mt-4 text-lg leading-7 text-[var(--mk-muted)]">
          Questions, ideas, or feedback about Colearni? Reach out directly —
          a real person reads every message.
        </p>
      </header>

      <SectionReveal className="mt-10">
        <div className="flex flex-col gap-4">
          <a
            href={`mailto:${CONTACT_EMAIL}`}
            className="flex items-center gap-4 rounded-xl border border-[var(--mk-border)] bg-[var(--mk-card)] p-5 transition-colors hover:bg-[var(--mk-bg-soft)]"
          >
            <Mail className="h-5 w-5 text-[var(--mk-accent)]" aria-hidden="true" />
            <div>
              <p className="text-sm font-semibold text-[var(--mk-fg)]">Email</p>
              <p className="text-sm text-[var(--mk-muted)]">{CONTACT_EMAIL}</p>
            </div>
          </a>
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-4 rounded-xl border border-[var(--mk-border)] bg-[var(--mk-card)] p-5 transition-colors hover:bg-[var(--mk-bg-soft)]"
          >
            <Code2
              className="h-5 w-5 text-[var(--mk-accent)]"
              aria-hidden="true"
            />
            <div>
              <p className="text-sm font-semibold text-[var(--mk-fg)]">GitHub</p>
              <p className="text-sm text-[var(--mk-muted)]">
                Follow development and open issues
              </p>
            </div>
          </a>
        </div>
      </SectionReveal>
    </div>
  );
}

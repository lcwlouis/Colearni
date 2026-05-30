import type { Metadata } from "next";

import { SectionReveal } from "@/components/marketing/SectionReveal";
import { PEDAGOGY_SECTIONS } from "@/components/marketing/marketing-content";

export const metadata: Metadata = {
  title: "Pedagogy · Colearni",
  description:
    "Bloom's Taxonomy, Socratic questioning, mastery learning, retrieval practice, and prerequisite scaffolding.",
};

export default function PedagogyPage() {
  return (
    <div className="mx-auto w-full max-w-4xl px-5 py-16 sm:px-8 md:py-24">
      <header className="max-w-2xl">
        <p className="font-[family-name:var(--font-geist-mono)] text-xs font-medium uppercase tracking-[0.2em] text-[var(--mk-accent)]">
          Pedagogy
        </p>
        <h1 className="mt-4 font-display text-4xl font-semibold leading-tight tracking-tight text-[var(--mk-fg)] sm:text-5xl">
          A coach, not a search engine.
        </h1>
        <p className="mt-4 text-lg leading-7 text-[var(--mk-muted)]">
          Colearni is built on established learning science. Here is what is
          actually happening while you learn.
        </p>
      </header>

      <div className="mt-14 flex flex-col gap-12">
        {PEDAGOGY_SECTIONS.map((section, i) => (
          <SectionReveal key={section.title} delayMs={i * 60}>
            <section className="border-l-2 border-[var(--mk-accent)] pl-6">
              <p className="font-[family-name:var(--font-geist-mono)] text-xs font-medium uppercase tracking-[0.18em] text-[var(--mk-accent)]">
                {section.eyebrow}
              </p>
              <h2 className="mt-2 font-display text-2xl font-semibold tracking-tight text-[var(--mk-fg)]">
                {section.title}
              </h2>
              <p className="mt-3 text-base leading-7 text-[var(--mk-muted)]">
                {section.body}
              </p>
            </section>
          </SectionReveal>
        ))}
      </div>
    </div>
  );
}

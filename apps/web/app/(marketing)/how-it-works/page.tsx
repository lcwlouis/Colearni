import type { Metadata } from "next";
import Link from "next/link";

import { SectionReveal } from "@/components/marketing/SectionReveal";
import { ProductPreview } from "@/components/marketing/ProductPreview";
import { HOW_IT_WORKS_STEPS } from "@/components/marketing/marketing-content";

export const metadata: Metadata = {
  title: "How it works · Colearni",
  description: "From a goal to mastery: how Colearni teaches.",
};

export default function HowItWorksPage() {
  return (
    <div className="mx-auto w-full max-w-5xl px-5 py-16 sm:px-8 md:py-24">
      <header className="max-w-2xl">
        <p className="font-[family-name:var(--font-geist-mono)] text-xs font-medium uppercase tracking-[0.2em] text-[var(--mk-accent)]">
          How it works
        </p>
        <h1 className="mt-4 font-display text-4xl font-semibold leading-tight tracking-tight text-[var(--mk-fg)] sm:text-5xl">
          One loop, repeated until it sticks.
        </h1>
        <p className="mt-4 text-lg leading-7 text-[var(--mk-muted)]">
          Colearni runs the same tight loop for every concept in your Trail. Each
          pass moves you from recognising an idea to genuinely using it.
        </p>
      </header>

      <SectionReveal className="mt-12">
        <ProductPreview />
      </SectionReveal>

      <ol className="mt-16 flex flex-col gap-5">
        {HOW_IT_WORKS_STEPS.map((step, i) => (
          <SectionReveal key={step.n} delayMs={i * 60}>
            <li className="flex gap-5 rounded-xl border border-[var(--mk-border)] bg-[var(--mk-card)] p-6">
              <span className="font-display text-3xl font-semibold text-[var(--mk-accent)]">
                {step.n}
              </span>
              <div>
                <h2 className="font-display text-xl font-semibold text-[var(--mk-fg)]">
                  {step.title}
                </h2>
                <p className="mt-2 text-base leading-7 text-[var(--mk-muted)]">
                  {step.body}
                </p>
              </div>
            </li>
          </SectionReveal>
        ))}
      </ol>

      <div className="mt-16 flex justify-center">
        <Link
          href="/pedagogy"
          className="inline-flex h-11 items-center justify-center rounded-full border border-[var(--mk-border)] px-6 text-base font-medium text-[var(--mk-fg)] transition-colors hover:bg-[var(--mk-bg-soft)]"
        >
          Why this works →
        </Link>
      </div>
    </div>
  );
}

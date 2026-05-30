"use client";

import Link from "next/link";

import { RedirectGate } from "@/components/marketing/RedirectGate";
import { EnterAppButton } from "@/components/marketing/EnterAppButton";
import { GraphHero } from "@/components/marketing/GraphHero";
import { ProductPreview } from "@/components/marketing/ProductPreview";
import { SectionReveal } from "@/components/marketing/SectionReveal";
import { HOW_IT_WORKS_STEPS } from "@/components/marketing/marketing-content";

export default function MarketingHome() {
  return (
    <>
      <RedirectGate />

      {/* Hero */}
      <section className="relative mk-grain overflow-hidden">
        <div
          className="pointer-events-none absolute -top-24 left-1/2 h-[420px] w-[820px] -translate-x-1/2 rounded-full opacity-30 blur-3xl"
          style={{
            background:
              "radial-gradient(closest-side, var(--mk-accent), transparent)",
          }}
          aria-hidden="true"
        />
        <div className="mx-auto grid w-full max-w-6xl items-center gap-12 px-5 py-20 sm:px-8 md:grid-cols-2 md:py-28">
          <div>
            <p className="font-[family-name:var(--font-geist-mono)] text-xs font-medium uppercase tracking-[0.2em] text-[var(--mk-accent)]">
              Graph-first Socratic learning
            </p>
            <h1 className="mt-4 font-display text-4xl font-semibold leading-[1.05] tracking-tight text-[var(--mk-fg)] sm:text-6xl">
              Learn anything as a graph, with a tutor that meets you where you
              are.
            </h1>
            <p className="mt-5 max-w-md text-lg leading-7 text-[var(--mk-muted)]">
              CoLearni turns a goal into a concept graph, then coaches you
              through it one idea at a time — Socratic questions, real
              mastery, no busywork.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <EnterAppButton className="inline-flex h-12 items-center justify-center rounded-full bg-[var(--mk-accent)] px-7 text-base font-semibold text-white shadow-lg shadow-blue-500/20 transition-transform hover:scale-[1.03] disabled:opacity-60">
                Start learning free
              </EnterAppButton>
              <Link
                href="/how-it-works"
                className="inline-flex h-12 items-center justify-center rounded-full border border-[var(--mk-border)] px-6 text-base font-medium text-[var(--mk-fg)] transition-colors hover:bg-[var(--mk-bg-soft)]"
              >
                See how it works
              </Link>
            </div>
          </div>
          <div className="text-[var(--mk-accent)]">
            <GraphHero className="h-72 w-full" />
          </div>
        </div>
      </section>

      {/* Product preview */}
      <section className="mx-auto w-full max-w-5xl px-5 pb-8 sm:px-8">
        <SectionReveal>
          <ProductPreview />
        </SectionReveal>
      </section>

      {/* How it works strip */}
      <section className="mx-auto w-full max-w-6xl px-5 py-20 sm:px-8">
        <SectionReveal>
          <h2 className="font-display text-3xl font-semibold tracking-tight text-[var(--mk-fg)]">
            From a goal to mastery, in five moves
          </h2>
        </SectionReveal>
        <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-5">
          {HOW_IT_WORKS_STEPS.map((step, i) => (
            <SectionReveal key={step.n} delayMs={i * 80}>
              <div className="h-full rounded-xl border border-[var(--mk-border)] bg-[var(--mk-card)] p-5">
                <p className="font-[family-name:var(--font-geist-mono)] text-sm text-[var(--mk-accent)]">
                  {step.n}
                </p>
                <h3 className="mt-3 font-display text-lg font-semibold text-[var(--mk-fg)]">
                  {step.title}
                </h3>
                <p className="mt-2 text-sm leading-6 text-[var(--mk-muted)]">
                  {step.body}
                </p>
              </div>
            </SectionReveal>
          ))}
        </div>
      </section>

      {/* Pedagogy teaser */}
      <section className="bg-[var(--mk-bg-soft)]">
        <div className="mx-auto flex w-full max-w-6xl flex-col items-start gap-6 px-5 py-20 sm:px-8 md:flex-row md:items-center md:justify-between">
          <SectionReveal>
            <div className="max-w-xl">
              <h2 className="font-display text-3xl font-semibold tracking-tight text-[var(--mk-fg)]">
                Built on how people actually learn
              </h2>
              <p className="mt-3 text-base leading-7 text-[var(--mk-muted)]">
                Bloom&apos;s Taxonomy sets your target depth. Socratic
                questioning, mastery gating, retrieval practice, and prerequisite
                scaffolding do the rest.
              </p>
            </div>
          </SectionReveal>
          <Link
            href="/pedagogy"
            className="inline-flex h-11 shrink-0 items-center justify-center rounded-full border border-[var(--mk-border)] bg-[var(--mk-card)] px-6 text-base font-medium text-[var(--mk-fg)] transition-colors hover:bg-[var(--mk-bg)]"
          >
            Read the pedagogy
          </Link>
        </div>
      </section>

      {/* Footer CTA */}
      <section className="mx-auto w-full max-w-4xl px-5 py-24 text-center sm:px-8">
        <SectionReveal>
          <h2 className="font-display text-4xl font-semibold tracking-tight text-[var(--mk-fg)]">
            Pick something you&apos;ve always wanted to understand.
          </h2>
          <p className="mt-4 text-lg text-[var(--mk-muted)]">
            Start a Trail in under a minute. No account required to try it.
          </p>
          <div className="mt-8 flex justify-center">
            <EnterAppButton className="inline-flex h-12 items-center justify-center rounded-full bg-[var(--mk-accent)] px-8 text-base font-semibold text-white shadow-lg shadow-blue-500/20 transition-transform hover:scale-[1.03] disabled:opacity-60">
              Start learning free
            </EnterAppButton>
          </div>
        </SectionReveal>
      </section>
    </>
  );
}

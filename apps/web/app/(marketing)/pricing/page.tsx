import type { Metadata } from "next";
import { Check } from "lucide-react";

import { SectionReveal } from "@/components/marketing/SectionReveal";
import { PRICING_TIERS } from "@/components/marketing/marketing-content";

export const metadata: Metadata = {
  title: "Pricing · Colearni",
  description: "Anticipated tiers. Pricing is still to be confirmed.",
};

export default function PricingPage() {
  return (
    <div className="mx-auto w-full max-w-5xl px-5 py-16 sm:px-8 md:py-24">
      <header className="max-w-2xl">
        <p className="font-[family-name:var(--font-geist-mono)] text-xs font-medium uppercase tracking-[0.2em] text-[var(--mk-accent)]">
          Pricing
        </p>
        <h1 className="mt-4 font-display text-4xl font-semibold leading-tight tracking-tight text-[var(--mk-fg)] sm:text-5xl">
          Pricing is still being worked out.
        </h1>
        <p className="mt-4 text-lg leading-7 text-[var(--mk-muted)]">
          Here is the shape we are planning. Nothing below is final — every
          tier is marked TBC, and the line between free and self-host is not
          settled yet.
        </p>
      </header>

      <div className="mt-12 grid gap-5 md:grid-cols-3">
        {PRICING_TIERS.map((tier, i) => (
          <SectionReveal key={tier.name} delayMs={i * 80}>
            <div className="flex h-full flex-col rounded-2xl border border-[var(--mk-border)] bg-[var(--mk-card)] p-6">
              <div className="flex items-center justify-between">
                <h2 className="font-display text-xl font-semibold text-[var(--mk-fg)]">
                  {tier.name}
                </h2>
                <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide text-amber-700">
                  TBC
                </span>
              </div>
              <p className="mt-3 text-sm leading-6 text-[var(--mk-muted)]">
                {tier.pitch}
              </p>
              <ul className="mt-5 flex flex-col gap-2">
                {tier.points.map((point) => (
                  <li
                    key={point}
                    className="flex items-center gap-2 text-sm text-[var(--mk-fg)]"
                  >
                    <Check
                      className="h-4 w-4 shrink-0 text-[var(--mk-accent)]"
                      aria-hidden="true"
                    />
                    {point}
                  </li>
                ))}
              </ul>
            </div>
          </SectionReveal>
        ))}
      </div>

      <SectionReveal className="mt-12">
        <div className="rounded-xl border border-[var(--mk-border)] bg-[var(--mk-bg-soft)] p-6">
          <h2 className="font-display text-lg font-semibold text-[var(--mk-fg)]">
            On licensing
          </h2>
          <p className="mt-2 text-sm leading-6 text-[var(--mk-muted)]">
            Colearni is intended to be source-available, with a commercial head
            start for the hosted service. It is deliberately not MIT-licensed.
            The exact license has not been chosen yet, so we are not committing
            to specific terms here.
          </p>
        </div>
      </SectionReveal>
    </div>
  );
}

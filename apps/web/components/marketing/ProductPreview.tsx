import { GraphHero } from "@/components/marketing/GraphHero";

export function ProductPreview({ className = "" }: { className?: string }) {
  return (
    <div
      className={`overflow-hidden rounded-2xl border border-[var(--mk-border)] bg-[var(--mk-card)] shadow-xl ${className}`}
      aria-hidden="true"
    >
      <div className="flex items-center gap-1.5 border-b border-[var(--mk-border)] px-4 py-3">
        <span className="h-3 w-3 rounded-full bg-red-400" />
        <span className="h-3 w-3 rounded-full bg-amber-400" />
        <span className="h-3 w-3 rounded-full bg-emerald-400" />
        <span className="ml-3 text-xs font-medium text-[var(--mk-muted)]">
          Trail · Linear Algebra
        </span>
      </div>
      <div className="grid gap-0 md:grid-cols-2">
        <div className="border-b border-[var(--mk-border)] p-5 text-[var(--mk-accent)] md:border-b-0 md:border-r">
          <GraphHero className="h-44 w-full" />
        </div>
        <div className="flex flex-col gap-3 p-5">
          <div className="self-start rounded-2xl rounded-tl-sm bg-[var(--mk-bg-soft)] px-3 py-2 text-sm text-[var(--mk-fg)]">
            What happens to a vector when you multiply it by this matrix?
          </div>
          <div className="self-end rounded-2xl rounded-tr-sm bg-[var(--mk-accent)] px-3 py-2 text-sm text-white">
            It gets scaled and rotated?
          </div>
          <div className="self-start rounded-2xl rounded-tl-sm bg-[var(--mk-bg-soft)] px-3 py-2 text-sm text-[var(--mk-fg)]">
            Close. Which part of the matrix controls the rotation — can you
            point to it?
          </div>
          <div className="mt-1 flex items-center gap-2">
            <span className="inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
              Learning → Mastered
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

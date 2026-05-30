"use client";

import { BrainIcon, ChevronDownIcon } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { useScrollLock } from "@assistant-ui/react";

const ANIMATION_DURATION = 200;

export function ReasoningRoot({
  children,
  defaultOpen = false,
}: {
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const ref = useRef<HTMLDivElement>(null);
  const lockScroll = useScrollLock(ref, ANIMATION_DURATION);

  useEffect(() => {
    if (!defaultOpen) {
      return;
    }

    const handle = window.setTimeout(() => setOpen(true), 0);
    return () => window.clearTimeout(handle);
  }, [defaultOpen]);

  const onOpenChange = useCallback(
    (nextOpen: boolean) => {
      if (!nextOpen) {
        lockScroll();
      }
      setOpen(nextOpen);
    },
    [lockScroll],
  );

  return (
    <div
      ref={ref}
      data-open={open ? "true" : "false"}
      className="mb-3 border-l-2 border-slate-200 pl-3 dark:border-slate-700"
      style={{
        ["--reasoning-animation-duration" as string]: `${ANIMATION_DURATION}ms`,
      }}
    >
      <ReasoningContext.Provider value={{ open, onOpenChange }}>
        {children}
      </ReasoningContext.Provider>
    </div>
  );
}

export function ReasoningTrigger({
  active = false,
  label,
}: {
  active?: boolean;
  label?: { open: string; closed: string };
}) {
  const context = useReasoningContext();
  const triggerLabel = context.open
    ? (label?.open ?? "Hide reasoning")
    : (label?.closed ?? "Show reasoning");

  return (
    <button
      type="button"
      onClick={() => context.onOpenChange(!context.open)}
      className="flex w-full items-center gap-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500 transition-colors hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
    >
      <BrainIcon className="size-3.5 shrink-0" />
      <span className="inline-flex items-center gap-1.5">
        <span>{triggerLabel}</span>
        {active ? (
          <span className="inline-flex items-center gap-1 text-slate-400 dark:text-slate-500">
            <span className="size-1.5 animate-pulse rounded-full bg-blue-500" />
            streaming
          </span>
        ) : null}
      </span>
      <ChevronDownIcon
        className={`ml-auto size-3.5 shrink-0 transition-transform duration-200 ${
          context.open ? "rotate-0" : "-rotate-90"
        }`}
      />
    </button>
  );
}

export function ReasoningContent({
  children,
  busy = false,
}: {
  children: ReactNode;
  busy?: boolean;
}) {
  const context = useReasoningContext();

  if (!context.open) {
    return null;
  }

  return (
    <div aria-busy={busy} className="pb-1 pt-2">
      {children}
    </div>
  );
}

export function ReasoningText({ children }: { children: ReactNode }) {
  return (
    <div className="max-h-64 overflow-y-auto text-sm text-slate-600 dark:text-slate-300">
      {children}
    </div>
  );
}

type ReasoningContextValue = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

const ReasoningContext = createContext<ReasoningContextValue | null>(null);

function useReasoningContext() {
  const context = useContext(ReasoningContext);
  if (!context) {
    throw new Error("Reasoning components must be used inside ReasoningRoot");
  }
  return context;
}

"use client";

import { BrainIcon, ChevronDownIcon } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
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
      className="mb-2 rounded-lg border border-amber-200 bg-amber-50/70"
      style={{ ["--reasoning-animation-duration" as string]: `${ANIMATION_DURATION}ms` }}
    >
      <ReasoningContext.Provider value={{ open, onOpenChange }}>{children}</ReasoningContext.Provider>
    </div>
  );
}

export function ReasoningTrigger({ active = false }: { active?: boolean }) {
  const context = useReasoningContext();

  return (
    <button
      type="button"
      onClick={() => context.onOpenChange(!context.open)}
      className="flex w-full items-center gap-2 px-3 py-2 text-sm text-amber-900 transition-colors hover:bg-amber-100/70"
    >
      <BrainIcon className="size-4 shrink-0" />
      <span className="relative inline-flex items-center gap-2 font-medium">
        <span>{context.open ? "Hide reasoning" : "Show reasoning"}</span>
        {active ? <span className="text-xs text-amber-700">streaming</span> : null}
      </span>
      <ChevronDownIcon
        className={`ml-auto size-4 shrink-0 transition-transform duration-200 ${
          context.open ? "rotate-0" : "-rotate-90"
        }`}
      />
    </button>
  );
}

export function ReasoningContent({ children, busy = false }: { children: ReactNode; busy?: boolean }) {
  const context = useReasoningContext();

  if (!context.open) {
    return null;
  }

  return (
    <div aria-busy={busy} className="border-t border-amber-200 px-3 pb-3 pt-2">
      {children}
    </div>
  );
}

export function ReasoningText({ children }: { children: ReactNode }) {
  return <div className="max-h-64 overflow-y-auto pl-5 text-sm text-amber-950">{children}</div>;
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

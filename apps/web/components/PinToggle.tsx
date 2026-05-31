"use client";

import { Bookmark } from "lucide-react";
import { useState } from "react";

import { pinItem, unpinItem, type PinItemType } from "@/lib/api";

interface PinToggleProps {
  workspaceId: string;
  trailId: string;
  itemType: PinItemType;
  itemId: string;
  initialPinned?: boolean;
  // Notified after a successful pin/unpin so parents (e.g. the Saved surface)
  // can drop the item from their list.
  onChange?: (pinned: boolean) => void;
}

/**
 * A small Save/Saved toggle that pins or unpins an item to its Trail.
 *
 * Idempotent on the backend, so a double-click never creates duplicates. The
 * UI updates optimistically and reverts on failure.
 */
export function PinToggle({
  workspaceId,
  trailId,
  itemType,
  itemId,
  initialPinned = false,
  onChange,
}: PinToggleProps) {
  const [pinned, setPinned] = useState(initialPinned);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  async function toggle(event: React.MouseEvent) {
    // Pin toggles can live inside a <summary>; keep clicks from expanding it.
    event.preventDefault();
    event.stopPropagation();
    if (busy) {
      return;
    }
    const next = !pinned;
    setBusy(true);
    setFailed(false);
    setPinned(next);
    try {
      if (next) {
        await pinItem(workspaceId, trailId, itemType, itemId);
      } else {
        await unpinItem(workspaceId, trailId, itemType, itemId);
      }
      onChange?.(next);
    } catch {
      setPinned(!next);
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={busy}
      aria-pressed={pinned}
      aria-label={pinned ? "Remove from saved" : "Save"}
      title={
        failed
          ? "Could not update saved state"
          : pinned
            ? "Saved"
            : "Save to Bookmarks"
      }
      className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-medium transition disabled:opacity-60 ${
        pinned
          ? "border-blue-300 bg-blue-50 text-blue-700"
          : "border-slate-200 text-slate-600 hover:bg-slate-50"
      }`}
    >
      <Bookmark className={`h-3.5 w-3.5 ${pinned ? "fill-current" : ""}`} />
      <span>{pinned ? "Saved" : "Save"}</span>
    </button>
  );
}

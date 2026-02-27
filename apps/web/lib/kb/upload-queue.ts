export type UploadQueuePhase = "queued" | "uploading" | "uploaded" | "failed";

export interface UploadQueueSeed {
  localId: string;
  fileName: string;
}

export interface UploadQueueItem {
  localId: string;
  fileName: string;
  phase: UploadQueuePhase;
  chunkCount: number | null;
  error: string | null;
}

export type UploadQueueAction =
  | { type: "enqueue"; items: UploadQueueSeed[] }
  | { type: "mark_uploading"; localId: string }
  | { type: "mark_uploaded"; localId: string; chunkCount: number }
  | { type: "mark_failed"; localId: string; error: string };

export function uploadQueueReducer(
  state: UploadQueueItem[],
  action: UploadQueueAction,
): UploadQueueItem[] {
  if (action.type === "enqueue") {
    const next = action.items.map((item) => ({
      localId: item.localId,
      fileName: item.fileName,
      phase: "queued" as const,
      chunkCount: null,
      error: null,
    }));
    return [...state, ...next];
  }
  if (action.type === "mark_uploading") {
    return state.map((item) =>
      item.localId === action.localId
        ? { ...item, phase: "uploading", error: null }
        : item,
    );
  }
  if (action.type === "mark_uploaded") {
    return state.map((item) =>
      item.localId === action.localId
        ? { ...item, phase: "uploaded", chunkCount: action.chunkCount, error: null }
        : item,
    );
  }
  if (action.type === "mark_failed") {
    return state.map((item) =>
      item.localId === action.localId
        ? { ...item, phase: "failed", error: action.error }
        : item,
    );
  }
  return state;
}

export function buildUploadQueueSeeds(
  files: ReadonlyArray<{ name: string; size: number; lastModified: number }>,
  batchId: string,
): UploadQueueSeed[] {
  return files.map((file, index) => ({
    localId: `${batchId}-${index}-${file.name}-${file.size}-${file.lastModified}`,
    fileName: file.name,
  }));
}


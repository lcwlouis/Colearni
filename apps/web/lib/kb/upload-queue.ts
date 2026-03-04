export type UploadQueuePhase = "queued" | "uploading" | "uploaded" | "processing" | "done" | "failed";

export interface UploadQueueSeed {
  localId: string;
  fileName: string;
}

export interface UploadQueueItem {
  localId: string;
  fileName: string;
  phase: UploadQueuePhase;
  chunkCount: number | null;
  documentId: number | null;
  error: string | null;
}

export type UploadQueueAction =
  | { type: "enqueue"; items: UploadQueueSeed[] }
  | { type: "mark_uploading"; localId: string }
  | { type: "mark_uploaded"; localId: string; chunkCount: number; documentId: number }
  | { type: "mark_processing"; localId: string }
  | { type: "mark_done"; localId: string }
  | { type: "mark_failed"; localId: string; error: string }
  | { type: "dismiss"; localId: string }
  | { type: "dismiss_done" };

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
      documentId: null,
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
        ? { ...item, phase: "uploaded", chunkCount: action.chunkCount, documentId: action.documentId, error: null }
        : item,
    );
  }
  if (action.type === "mark_processing") {
    return state.map((item) =>
      item.localId === action.localId
        ? { ...item, phase: "processing", error: null }
        : item,
    );
  }
  if (action.type === "mark_done") {
    return state.map((item) =>
      item.localId === action.localId
        ? { ...item, phase: "done", error: null }
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
  if (action.type === "dismiss") {
    return state.filter((item) => item.localId !== action.localId);
  }
  if (action.type === "dismiss_done") {
    return state.filter((item) => item.phase !== "done");
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


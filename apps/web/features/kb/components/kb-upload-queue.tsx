import type { UploadQueueItem, UploadQueueAction } from "@/lib/kb/upload-queue";

interface KBUploadQueueProps {
  uploadQueue: UploadQueueItem[];
  dispatchUploadQueue: React.Dispatch<UploadQueueAction>;
}

export function KBUploadQueue({ uploadQueue, dispatchUploadQueue }: KBUploadQueueProps) {
  if (uploadQueue.length === 0) return null;

  return (
    <div className="kb-upload-queue">
      <h2>Upload queue</h2>
      <ul>
        {uploadQueue.map((item) => (
          <li key={item.localId}>
            <span className="kb-upload-file">{item.fileName}</span>
            <span
              className={`kb-badge ${item.phase === "uploaded" || item.phase === "done" ? "ok" : item.phase === "failed" ? "failed" : "pending"}`}
            >
              {item.phase === "processing" ? "processing" : item.phase === "done" ? "done" : item.phase}
            </span>
            <span className="kb-meta">
              {item.phase === "uploading"
                ? "Uploading..."
                : item.phase === "uploaded"
                  ? `Saved ${item.chunkCount ?? 0} chunk${item.chunkCount === 1 ? "" : "s"}. Background processing will continue.`
                  : item.phase === "processing"
                    ? `${item.chunkCount ?? 0} chunk${item.chunkCount === 1 ? "" : "s"} saved. Embeddings & graph building…`
                    : item.phase === "done"
                      ? `Complete — ${item.chunkCount ?? 0} chunk${item.chunkCount === 1 ? "" : "s"} ingested.`
                      : item.phase === "failed"
                        ? item.error ?? "Upload failed."
                        : "Waiting to upload..."}
            </span>
            {item.phase === "failed" && (
              <button
                type="button"
                className="secondary"
                style={{ fontSize: "0.78rem", padding: "0.15rem 0.5rem" }}
                onClick={() => dispatchUploadQueue({ type: "dismiss", localId: item.localId })}
              >
                Dismiss
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

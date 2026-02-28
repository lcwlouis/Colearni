"use client";

import { useState, useEffect, useCallback, useRef, useReducer } from "react";
import { apiClient } from "@/lib/api/client";
import { useRequireAuth } from "@/lib/auth";
import type { KBDocumentSummary } from "@/lib/api/types";
import {
  buildUploadQueueSeeds,
  uploadQueueReducer,
} from "@/lib/kb/upload-queue";

type PendingAction = { type: "delete" | "reprocess"; documentId: number } | null;

/** Polling interval (ms) for background-ingestion status checks. */
const POLL_INTERVAL_MS = 4000;
/** Auto-dismiss completed queue items after this delay (ms). */
const AUTO_CLEAR_DELAY_MS = 5000;

export default function KBPage() {
  const auth = useRequireAuth();
  const wsId = auth.activeWorkspaceId ?? "";
  const [documents, setDocuments] = useState<KBDocumentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadQueue, dispatchUploadQueue] = useReducer(uploadQueueReducer, []);
  const [pendingAction, setPendingAction] = useState<PendingAction>(null);
  const [processingDocId, setProcessingDocId] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const autoClearTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchDocuments = useCallback(async () => {
    if (!wsId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.listKBDocuments(wsId);
      setDocuments(res.documents);
      return res.documents;
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load documents.");
      return null;
    } finally {
      setLoading(false);
    }
  }, [wsId]);

  /** Stop any active background polling. */
  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  /** Start polling for background-ingestion completion. */
  const startPolling = useCallback(() => {
    stopPolling();
    pollTimerRef.current = setInterval(async () => {
      if (!wsId) return;
      try {
        const res = await apiClient.listKBDocuments(wsId);
        setDocuments(res.documents);
      } catch {
        // swallow polling errors — next tick will retry
      }
    }, POLL_INTERVAL_MS);
  }, [wsId, stopPolling]);

  // Clean up polling on unmount
  useEffect(() => {
    return () => {
      stopPolling();
      if (autoClearTimerRef.current) clearTimeout(autoClearTimerRef.current);
    };
  }, [stopPolling]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0) return;
    setSelectedFiles(files);
    setInfo(`Selected ${files.length} file${files.length === 1 ? "" : "s"}.`);
    setError(null);
  }, []);

  const handleUpload = useCallback(async () => {
    if (selectedFiles.length === 0 || !wsId) return;
    const filesToUpload = [...selectedFiles];
    const uploadSeeds = buildUploadQueueSeeds(
      filesToUpload.map((file) => ({
        name: file.name,
        size: file.size,
        lastModified: file.lastModified,
      })),
      `batch-${Date.now().toString(36)}`,
    );
    dispatchUploadQueue({ type: "enqueue", items: uploadSeeds });
    setSelectedFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = "";

    setUploading(true);
    setError(null);
    setInfo(`Uploading ${filesToUpload.length} file${filesToUpload.length === 1 ? "" : "s"}...`);

    let uploadedCount = 0;
    const errors: string[] = [];

    for (let index = 0; index < filesToUpload.length; index += 1) {
      const file = filesToUpload[index];
      const uploadSeed = uploadSeeds[index];
      if (!file || !uploadSeed) continue;
      dispatchUploadQueue({ type: "mark_uploading", localId: uploadSeed.localId });
      try {
        const result = await apiClient.uploadKBDocument(wsId, {
          file,
          title: file.name,
        });
        uploadedCount += 1;
        dispatchUploadQueue({
          type: "mark_uploaded",
          localId: uploadSeed.localId,
          chunkCount: result.chunk_count,
          documentId: result.document_id,
        });
        // Transition to processing — background tasks are running
        dispatchUploadQueue({ type: "mark_processing", localId: uploadSeed.localId });
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Failed to upload document.";
        errors.push(`${file.name}: ${message}`);
        dispatchUploadQueue({
          type: "mark_failed",
          localId: uploadSeed.localId,
          error: message,
        });
      }
    }

    // Refresh document list immediately to show newly-inserted docs
    await fetchDocuments();
    setUploading(false);

    if (uploadedCount > 0) {
      // Start polling for background ingestion status updates
      startPolling();
    }

    if (uploadedCount === filesToUpload.length) {
      setInfo(`Uploaded ${uploadedCount} document${uploadedCount === 1 ? "" : "s"}. Background processing in progress…`);
      return;
    }
    if (uploadedCount > 0) {
      setInfo(`Uploaded ${uploadedCount} of ${filesToUpload.length} documents. Background processing in progress…`);
      setError(errors.join(" | "));
      return;
    }
    setError(errors.join(" | ") || "Failed to upload documents.");
  }, [selectedFiles, wsId, fetchDocuments, startPolling]);

  /** Whether any document is in a non-terminal processing state that needs polling. */
  const anyDocProcessing = useCallback((docs: KBDocumentSummary[]) => {
    return docs.some((d) => d.graph_status === "extracting");
  }, []);

  // ── B2: Auto-clear queue when background processing completes ──────
  useEffect(() => {
    const processingItems = uploadQueue.filter((q) => q.phase === "processing");
    if (processingItems.length === 0) {
      // No items processing — stop polling if no docs are actively extracting
      if (!anyDocProcessing(documents)) {
        stopPolling();
      }
      return;
    }
    // Check each processing item against the documents list
    let allDone = true;
    for (const qItem of processingItems) {
      if (!qItem.documentId) continue;
      const doc = documents.find((d) => d.document_id === qItem.documentId);
      if (doc && doc.ingestion_status === "ingested") {
        // Background ingestion is complete for this doc
        dispatchUploadQueue({ type: "mark_done", localId: qItem.localId });
      } else {
        allDone = false;
      }
    }
    if (allDone) {
      // Keep polling only if any documents are still actively extracting
      if (!anyDocProcessing(documents)) {
        stopPolling();
      }
      // Schedule auto-dismiss of completed items
      if (autoClearTimerRef.current) clearTimeout(autoClearTimerRef.current);
      autoClearTimerRef.current = setTimeout(() => {
        dispatchUploadQueue({ type: "dismiss_done" });
        autoClearTimerRef.current = null;
      }, AUTO_CLEAR_DELAY_MS);
    }
  }, [uploadQueue, documents, stopPolling, anyDocProcessing]);

  // B4: Auto-poll when documents are actively extracting (not failed/pending)
  useEffect(() => {
    if (anyDocProcessing(documents) && !pollTimerRef.current) {
      startPolling();
    }
  }, [documents, startPolling, anyDocProcessing]);

  const handleConfirmAction = useCallback(async () => {
    if (!pendingAction || !wsId) return;
    setProcessingDocId(pendingAction.documentId);
    setError(null);
    setInfo(null);
    try {
      if (pendingAction.type === "delete") {
        await apiClient.deleteKBDocument(wsId, pendingAction.documentId);
        setDocuments((prev) => prev.filter((d) => d.document_id !== pendingAction.documentId));
        setInfo("Document deleted.");
      } else {
        await apiClient.reprocessKBDocument(wsId, pendingAction.documentId);
        setInfo("Reprocess request queued. Use Refresh to check current status.");
      }
      setPendingAction(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Action failed.");
    } finally {
      setProcessingDocId(null);
    }
  }, [pendingAction, wsId]);

  if (auth.isLoading) return <p>Loading…</p>;

  return (
    <div className="kb-page">
      <div className="kb-header">
        <div>
          <h1 className="kb-title">Sources</h1>
          <p className="kb-subtitle">Upload documents, confirm ingestion, and verify graph extraction.</p>
        </div>
        <div className="kb-upload-controls">
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.md,.pdf"
            multiple
            onChange={handleFileSelect}
            className="hidden"
            style={{ display: "none" }}
            id="kb-upload"
            aria-label="Choose source file"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading || loading}
            className="secondary"
          >
            Choose file
          </button>
          <button
            onClick={() => void handleUpload()}
            disabled={uploading || selectedFiles.length === 0}
          >
            {uploading ? "Uploading…" : "Upload document"}
          </button>
          <button
            onClick={() => void fetchDocuments()}
            className="secondary"
          >
            Refresh
          </button>
        </div>
      </div>

      {selectedFiles.length > 0 ? (
        <p className="status loading">
          Selected {selectedFiles.length} file{selectedFiles.length === 1 ? "" : "s"}:{" "}
          {selectedFiles.slice(0, 3).map((file) => file.name).join(", ")}
          {selectedFiles.length > 3 ? "..." : ""}
        </p>
      ) : null}

      {loading && (
        <p className="status loading">Loading documents…</p>
      )}

      {error && (
        <p className="status error">{error}</p>
      )}

      {info && <p className="status ok">{info}</p>}

      {uploadQueue.length > 0 ? (
        <div className="kb-upload-queue">
          <h2>Upload queue</h2>
          <ul>
            {uploadQueue.map((item) => (
              <li key={item.localId}>
                <span className="kb-upload-file">{item.fileName}</span>
                <span className={`kb-badge ${item.phase === "uploaded" || item.phase === "done" ? "ok" : item.phase === "failed" ? "failed" : "pending"}`}>
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
      ) : null}

      {!loading && documents.length === 0 && (
        <div className="kb-empty-state">
          <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="kb-empty-icon">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="12" y1="18" x2="12" y2="12" />
            <line x1="9" y1="15" x2="15" y2="15" />
          </svg>
          <h3 className="kb-empty-title">No sources yet</h3>
          <p className="kb-empty-desc">
            Upload a document (.txt, .md, or .pdf) to start building your knowledge base.
            The system will chunk, embed, and extract concepts automatically.
          </p>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading || loading}
          >
            Upload your first document
          </button>
        </div>
      )}

      {documents.length > 0 && (
        <div className="kb-table-wrap">
          <table className="kb-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Description</th>
                <th>Ingestion</th>
                <th>Graph</th>
                <th>Chunks</th>
                <th>Uploaded</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.document_id}>
                  <td>
                    {doc.title || doc.source_uri || `Document #${doc.document_id}`}
                  </td>
                  <td>
                    {doc.summary ? (
                      <p className="kb-doc-summary" title={doc.summary}>
                        {doc.summary.length > 80 ? doc.summary.slice(0, 80) + '…' : doc.summary}
                      </p>
                    ) : doc.graph_status === "extracting" ? (
                      <span className="kb-meta kb-extracting">Extracting…</span>
                    ) : (
                      <span className="kb-meta">—</span>
                    )}
                  </td>
                  <td>
                    <span className={`kb-badge ${doc.ingestion_status === "ingested" ? "ok" : "pending"}`}>
                      {doc.ingestion_status}
                    </span>
                  </td>
                  <td>
                    <span className={`kb-badge ${doc.graph_status === "extracted" ? "ok" : doc.graph_status === "failed" ? "failed" : doc.graph_status === "extracting" ? "extracting" : doc.graph_status === "disabled" ? "disabled" : "pending"}`}
                      title={doc.graph_status === "failed" && doc.error_message ? doc.error_message : undefined}
                    >
                      {doc.graph_status === "extracting" ? "Extracting…" : doc.graph_status}
                    </span>
                    <span className="kb-meta">{doc.graph_concept_count} concepts</span>
                  </td>
                  <td>{doc.chunk_count}</td>
                  <td>
                    {new Date(doc.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    {pendingAction?.documentId === doc.document_id ? (
                      <div className="kb-inline-confirm">
                        <span>
                          {pendingAction.type === "delete" ? "Delete this document?" : "Queue reprocess?"}
                        </span>
                        <div className="button-row">
                          <button
                            type="button"
                            onClick={() => void handleConfirmAction()}
                            disabled={processingDocId === doc.document_id}
                          >
                            Confirm
                          </button>
                          <button
                            type="button"
                            className="secondary"
                            onClick={() => setPendingAction(null)}
                            disabled={processingDocId === doc.document_id}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="button-row">
                        <button
                          type="button"
                          className="secondary"
                          onClick={() => setPendingAction({ type: "reprocess", documentId: doc.document_id })}
                        >
                          Reprocess
                        </button>
                        <button
                          type="button"
                          onClick={() => setPendingAction({ type: "delete", documentId: doc.document_id })}
                          className="kb-danger-btn"
                        >
                          Delete
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

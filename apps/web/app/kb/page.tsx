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

  const fetchDocuments = useCallback(async () => {
    if (!wsId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.listKBDocuments(wsId);
      setDocuments(res.documents);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load documents.");
    } finally {
      setLoading(false);
    }
  }, [wsId]);

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
        });
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

    await fetchDocuments();
    setUploading(false);

    if (uploadedCount === filesToUpload.length) {
      setInfo(`Uploaded ${uploadedCount} document${uploadedCount === 1 ? "" : "s"}.`);
      return;
    }
    if (uploadedCount > 0) {
      setInfo(`Uploaded ${uploadedCount} of ${filesToUpload.length} documents.`);
      setError(errors.join(" | "));
      return;
    }
    setError(errors.join(" | ") || "Failed to upload documents.");
  }, [selectedFiles, wsId, fetchDocuments]);

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
          <h1 className="kb-title">Knowledge Base</h1>
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
            id="kb-upload"
            aria-label="Choose knowledge base file"
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
                <span className={`kb-badge ${item.phase === "uploaded" ? "ok" : item.phase === "failed" ? "failed" : "pending"}`}>
                  {item.phase}
                </span>
                <span className="kb-meta">
                  {item.phase === "uploading"
                    ? "Ingesting document and graph..."
                    : item.phase === "uploaded"
                    ? `Ingested ${item.chunkCount ?? 0} chunk${item.chunkCount === 1 ? "" : "s"}.`
                    : item.phase === "failed"
                    ? item.error ?? "Upload failed."
                    : "Waiting to upload..."}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {!loading && documents.length === 0 && (
        <p className="status empty">
          No documents yet. Choose a file and upload it here to start ingestion.
        </p>
      )}

      {documents.length > 0 && (
        <div className="kb-table-wrap">
          <table className="kb-table">
            <thead>
              <tr>
                <th className="px-4 py-3">Title</th>
                <th className="px-4 py-3">Ingestion</th>
                <th className="px-4 py-3">Graph</th>
                <th className="px-4 py-3">Chunks</th>
                <th className="px-4 py-3">Uploaded</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.document_id}>
                  <td className="px-4 py-3">
                    {doc.title || doc.source_uri || `Document #${doc.document_id}`}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`kb-badge ${doc.ingestion_status === "ingested" ? "ok" : "pending"}`}>
                      {doc.ingestion_status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`kb-badge ${doc.graph_status === "extracted" ? "ok" : doc.graph_status === "disabled" ? "disabled" : "pending"}`}>
                      {doc.graph_status}
                    </span>
                    <span className="kb-meta">{doc.graph_concept_count} concepts</span>
                  </td>
                  <td className="px-4 py-3">{doc.chunk_count}</td>
                  <td className="px-4 py-3">
                    {new Date(doc.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
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

import { useState, useEffect, useCallback, useRef, useReducer } from "react";
import { apiClient } from "@/lib/api/client";
import { useRequireAuth } from "@/lib/auth";
import type { KBDocumentSummary } from "@/lib/api/types";
import { buildUploadQueueSeeds, uploadQueueReducer } from "@/lib/kb/upload-queue";

type PendingAction = { type: "delete" | "reprocess"; documentId: number } | null;

const POLL_INTERVAL_MS = 4000;
const AUTO_CLEAR_DELAY_MS = 5000;

export function useKBPage() {
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

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const startPolling = useCallback(() => {
    stopPolling();
    pollTimerRef.current = setInterval(async () => {
      if (!wsId) return;
      try {
        const res = await apiClient.listKBDocuments(wsId);
        setDocuments(res.documents);
      } catch {
        // swallow polling errors
      }
    }, POLL_INTERVAL_MS);
  }, [wsId, stopPolling]);

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
        const result = await apiClient.uploadKBDocument(wsId, { file, title: file.name });
        uploadedCount += 1;
        dispatchUploadQueue({
          type: "mark_uploaded",
          localId: uploadSeed.localId,
          chunkCount: result.chunk_count,
          documentId: result.document_id,
        });
        dispatchUploadQueue({ type: "mark_processing", localId: uploadSeed.localId });
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Failed to upload document.";
        errors.push(`${file.name}: ${message}`);
        dispatchUploadQueue({ type: "mark_failed", localId: uploadSeed.localId, error: message });
      }
    }

    await fetchDocuments();
    setUploading(false);

    if (uploadedCount > 0) startPolling();

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

  const anyDocProcessing = useCallback((docs: KBDocumentSummary[]) => {
    return docs.some((d) => d.graph_status === "extracting");
  }, []);

  // Auto-clear queue when background processing completes
  useEffect(() => {
    const processingItems = uploadQueue.filter((q) => q.phase === "processing");
    if (processingItems.length === 0) {
      if (!anyDocProcessing(documents)) stopPolling();
      return;
    }
    let allDone = true;
    for (const qItem of processingItems) {
      if (!qItem.documentId) continue;
      const doc = documents.find((d) => d.document_id === qItem.documentId);
      if (doc && doc.ingestion_status === "ingested") {
        dispatchUploadQueue({ type: "mark_done", localId: qItem.localId });
      } else {
        allDone = false;
      }
    }
    if (allDone) {
      if (!anyDocProcessing(documents)) stopPolling();
      if (autoClearTimerRef.current) clearTimeout(autoClearTimerRef.current);
      autoClearTimerRef.current = setTimeout(() => {
        dispatchUploadQueue({ type: "dismiss_done" });
        autoClearTimerRef.current = null;
      }, AUTO_CLEAR_DELAY_MS);
    }
  }, [uploadQueue, documents, stopPolling, anyDocProcessing]);

  // Auto-poll when documents are actively extracting
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
        setDocuments((prev) =>
          prev.map((d) =>
            d.document_id === pendingAction.documentId
              ? { ...d, graph_status: "extracting" as const, error_message: null }
              : d,
          ),
        );
        setInfo("Reprocess started. Status will update automatically.");
        startPolling();
      }
      setPendingAction(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Action failed.");
    } finally {
      setProcessingDocId(null);
    }
  }, [pendingAction, wsId, startPolling]);

  return {
    auth,
    documents,
    loading,
    error,
    info,
    uploading,
    selectedFiles,
    uploadQueue,
    dispatchUploadQueue,
    pendingAction,
    setPendingAction,
    processingDocId,
    fileInputRef,
    fetchDocuments,
    handleFileSelect,
    handleUpload,
    handleConfirmAction,
  };
}

"use client";

import { useKBPage } from "@/features/kb/hooks/use-kb-page";
import { KBDocumentTable } from "@/features/kb/components/kb-document-table";
import { KBUploadQueue } from "@/features/kb/components/kb-upload-queue";

export default function KBPage() {
  const k = useKBPage();

  if (k.auth.isLoading) return <p>Loading…</p>;

  return (
    <div className="kb-page">
      <div className="kb-header">
        <div>
          <h1 className="kb-title">Sources</h1>
          <p className="kb-subtitle">Upload documents, confirm ingestion, and verify graph extraction.</p>
        </div>
        <div className="kb-upload-controls">
          <input
            ref={k.fileInputRef}
            type="file"
            accept=".txt,.md,.pdf"
            multiple
            onChange={k.handleFileSelect}
            className="hidden"
            style={{ display: "none" }}
            id="kb-upload"
            aria-label="Choose source file"
          />
          <button
            onClick={() => k.fileInputRef.current?.click()}
            disabled={k.uploading || k.loading}
            className="secondary"
          >
            Choose file
          </button>
          <button
            onClick={() => void k.handleUpload()}
            disabled={k.uploading || k.selectedFiles.length === 0}
          >
            {k.uploading ? "Uploading…" : "Upload document"}
          </button>
          <button onClick={() => void k.fetchDocuments()} className="secondary">
            Refresh
          </button>
        </div>
      </div>

      {k.selectedFiles.length > 0 ? (
        <p className="status loading">
          Selected {k.selectedFiles.length} file{k.selectedFiles.length === 1 ? "" : "s"}:{" "}
          {k.selectedFiles.slice(0, 3).map((file) => file.name).join(", ")}
          {k.selectedFiles.length > 3 ? "..." : ""}
        </p>
      ) : null}

      {k.loading && <p className="status loading">Loading documents…</p>}
      {k.error && <p className="status error">{k.error}</p>}
      {k.info && <p className="status ok">{k.info}</p>}

      <KBUploadQueue uploadQueue={k.uploadQueue} dispatchUploadQueue={k.dispatchUploadQueue} />

      {!k.loading && k.documents.length === 0 && (
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
            onClick={() => k.fileInputRef.current?.click()}
            disabled={k.uploading || k.loading}
          >
            Upload your first document
          </button>
        </div>
      )}

      {k.documents.length > 0 && (
        <KBDocumentTable
          documents={k.documents}
          pendingAction={k.pendingAction}
          processingDocId={k.processingDocId}
          setPendingAction={k.setPendingAction}
          handleConfirmAction={() => void k.handleConfirmAction()}
        />
      )}
    </div>
  );
}

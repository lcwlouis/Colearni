import type { KBDocumentSummary } from "@/lib/api/types";

interface KBDocumentTableProps {
  documents: KBDocumentSummary[];
  pendingAction: { type: "delete" | "reprocess"; documentId: number } | null;
  processingDocId: number | null;
  setPendingAction: (action: { type: "delete" | "reprocess"; documentId: number } | null) => void;
  handleConfirmAction: () => void;
}

export function KBDocumentTable({
  documents,
  pendingAction,
  processingDocId,
  setPendingAction,
  handleConfirmAction,
}: KBDocumentTableProps) {
  return (
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
              <td>{doc.title || doc.source_uri || `Document #${doc.document_id}`}</td>
              <td>
                {doc.summary ? (
                  <p className="kb-doc-summary" title={doc.summary}>
                    {doc.summary.length > 80 ? doc.summary.slice(0, 80) + "…" : doc.summary}
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
                <span
                  className={`kb-badge ${doc.graph_status === "extracted" ? "ok" : doc.graph_status === "failed" ? "failed" : doc.graph_status === "extracting" ? "extracting" : doc.graph_status === "disabled" ? "disabled" : "pending"}`}
                  title={doc.graph_status === "failed" && doc.error_message ? doc.error_message : undefined}
                >
                  {doc.graph_status === "extracting" ? "Extracting…" : doc.graph_status}
                </span>
                {doc.graph_concept_count > 0 && (doc.tier_umbrella_count > 0 || doc.tier_topic_count > 0 || doc.tier_subtopic_count > 0 || doc.tier_granular_count > 0) ? (
                  <span className="kb-meta">
                    {[
                      doc.tier_umbrella_count > 0 && `${doc.tier_umbrella_count} umbrella`,
                      doc.tier_topic_count > 0 && `${doc.tier_topic_count} topic`,
                      doc.tier_subtopic_count > 0 && `${doc.tier_subtopic_count} subtopic`,
                      doc.tier_granular_count > 0 && `${doc.tier_granular_count} granular`,
                    ].filter(Boolean).join(" · ")}
                  </span>
                ) : (
                  <span className="kb-meta">{doc.graph_concept_count} concepts</span>
                )}
              </td>
              <td>{doc.chunk_count}</td>
              <td>{new Date(doc.created_at).toLocaleDateString()}</td>
              <td>
                {pendingAction?.documentId === doc.document_id ? (
                  <div className="kb-inline-confirm">
                    <span>
                      {pendingAction.type === "delete"
                        ? "Delete this document?"
                        : "Queue reprocess?"}
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
                      onClick={() =>
                        setPendingAction({
                          type: "reprocess",
                          documentId: doc.document_id,
                        })
                      }
                    >
                      Reprocess
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        setPendingAction({
                          type: "delete",
                          documentId: doc.document_id,
                        })
                      }
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
  );
}

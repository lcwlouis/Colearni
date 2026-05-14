"use client";

import type { ConceptDetail, ConceptNode } from "@/lib/types";

interface ConceptPanelProps {
  detail: ConceptDetail;
  onClose: () => void;
  onSelectConcept?: (conceptId: string) => void;
}

export function ConceptPanel({ detail, onClose, onSelectConcept }: ConceptPanelProps) {
  const concept = detail.concept;

  return (
    <aside className="absolute right-0 top-0 z-20 flex h-full w-full max-w-md flex-col border-l border-slate-200 bg-white shadow-xl">
      <div className="flex items-start justify-between gap-4 border-b border-slate-200 p-5">
        <div>
          <h2 className="text-xl font-semibold text-slate-950">{concept.title}</h2>
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            <Badge>{concept.concept_level}</Badge>
            <Badge>{concept.bloom_level}</Badge>
            <Badge>{concept.difficulty}</Badge>
            <Badge>{concept.node_type}</Badge>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-md border border-slate-200 px-2 py-1 text-sm text-slate-600 hover:bg-slate-50"
        >
          Close
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-5">
        <Section title="Prerequisites" nodes={detail.prerequisites} onSelect={onSelectConcept} />
        <Section title="Contained by" nodes={detail.containing_nodes} onSelect={onSelectConcept} />
        <Section title="Contains" nodes={detail.contained_nodes} onSelect={onSelectConcept} />
        <Section title="Related" nodes={detail.related} onSelect={onSelectConcept} />

        <section className="mt-6">
          <h3 className="text-sm font-semibold text-slate-900">Mastery checks</h3>
          <div className="mt-3 flex flex-wrap gap-2">
            {concept.mastery_check_labels.length === 0 ? (
              <p className="text-sm text-slate-500">No checks yet.</p>
            ) : (
              concept.mastery_check_labels.map((label) => <Badge key={label}>{label}</Badge>)
            )}
          </div>
        </section>

        <section className="mt-6">
          <h3 className="text-sm font-semibold text-slate-900">Sources</h3>
          <p className="mt-2 text-sm text-slate-500">No sources linked yet.</p>
        </section>
      </div>
      <div className="border-t border-slate-200 p-5">
        <button
          type="button"
          disabled
          className="h-10 w-full rounded-md bg-slate-200 text-sm font-medium text-slate-500"
        >
          Start Learning: Coming in Phase 4
        </button>
      </div>
    </aside>
  );
}

function Section({
  title,
  nodes,
  onSelect,
}: {
  title: string;
  nodes: ConceptNode[];
  onSelect?: (conceptId: string) => void;
}) {
  return (
    <section className="mt-6 first:mt-0">
      <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      {nodes.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">None</p>
      ) : (
        <ul className="mt-2 grid gap-2">
          {nodes.map((node) => (
            <li key={node.id}>
              <button
                type="button"
                onClick={() => onSelect?.(node.id)}
                className="w-full rounded-md border border-slate-200 px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
              >
                {node.title}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded border border-slate-200 bg-slate-50 px-2 py-1 font-medium text-slate-700">
      {children}
    </span>
  );
}

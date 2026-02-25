"use client";

import { useState } from "react";
import { AsyncState } from "@/components/async-state";
import { ApiError, apiClient } from "@/lib/api/client";
import type { LuckyMode } from "@/lib/api/types";

export default function GraphPage() {
  const [workspace_id, setWorkspace] = useState("1"), [concept_id, setConcept] = useState("1"), [max_hops, setMaxHops] = useState("1"), [mode, setMode] = useState<LuckyMode>("adjacent");
  const [loading, setLoading] = useState(false), [error, setError] = useState<string | null>(null), [data, setData] = useState<unknown | null>(null);

  async function run(action: "detail" | "subgraph" | "lucky") {
    setLoading(true); setError(null); setData(null);
    try {
      const base = { workspace_id: Number(workspace_id), concept_id: Number(concept_id) };
      setData(action === "detail" ? await apiClient.getConceptDetail(base) : action === "subgraph" ? await apiClient.getConceptSubgraph({ ...base, max_hops: Number(max_hops) }) : await apiClient.getLuckyPick({ ...base, mode, k_hops: Number(max_hops) }));
    } catch (err: unknown) { setError(err instanceof ApiError ? err.message : "Graph request failed"); }
    finally { setLoading(false); }
  }

  return (
    <section className="panel stack">
      <h1>Graph exploration placeholder</h1>
      <div className="grid two">
        <label className="field">
          <span className="field-label">Workspace ID</span>
          <input type="number" min={1} value={workspace_id} onChange={(e) => setWorkspace(e.target.value)} />
        </label>
        <label className="field">
          <span className="field-label">Concept ID</span>
          <input type="number" min={1} value={concept_id} onChange={(e) => setConcept(e.target.value)} />
        </label>
      </div>
      <div className="grid two">
        <label className="field">
          <span className="field-label">Max hops (subgraph and lucky)</span>
          <input type="number" min={1} value={max_hops} onChange={(e) => setMaxHops(e.target.value)} />
        </label>
        <label className="field">
          <span className="field-label">Lucky mode</span>
          <select value={mode} onChange={(e) => setMode(e.target.value as LuckyMode)}>
            <option value="adjacent">adjacent</option>
            <option value="wildcard">wildcard</option>
          </select>
        </label>
      </div>
      <div className="button-row"><button type="button" disabled={loading} onClick={() => run("detail")}>Concept detail</button><button type="button" className="secondary" disabled={loading} onClick={() => run("subgraph")}>Bounded subgraph</button><button type="button" className="secondary" disabled={loading} onClick={() => run("lucky")}>Lucky pick</button></div>
      <AsyncState loading={loading} error={error} empty={!data} emptyLabel="Choose a graph action." />
      {data ? <pre>{JSON.stringify(data, null, 2)}</pre> : null}
    </section>
  );
}

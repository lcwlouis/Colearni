"use client";

import { FormEvent, useState } from "react";
import { AsyncState } from "@/components/async-state";
import { ApiError, apiClient } from "@/lib/api/client";
import type { AssistantResponseEnvelope, ChatRespondRequest } from "@/lib/api/types";

const asInt = (v: string) => (Number.isInteger(Number(v)) && Number(v) > 0 ? Number(v) : undefined);

export default function TutorPage() {
  const [workspace_id, setWorkspace] = useState("1"), [query, setQuery] = useState(""), [user_id, setUser] = useState(""), [concept_id, setConcept] = useState("");
  const [loading, setLoading] = useState(false), [error, setError] = useState<string | null>(null), [data, setData] = useState<AssistantResponseEnvelope | null>(null);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); setLoading(true); setError(null);
    try {
      const payload: ChatRespondRequest = { workspace_id: Number(workspace_id), query };
      const u = asInt(user_id), c = asInt(concept_id);
      if (u) payload.user_id = u; if (c) payload.concept_id = c;
      setData(await apiClient.respondChat(payload));
    } catch (err: unknown) { setData(null); setError(err instanceof ApiError ? err.message : "Tutor request failed"); }
    finally { setLoading(false); }
  }

  return (
    <section className="panel stack">
      <h1>Tutor chat placeholder</h1>
      <form className="stack" onSubmit={onSubmit}>
        <label className="field">
          <span className="field-label">Workspace ID</span>
          <input
            type="number"
            min={1}
            value={workspace_id}
            onChange={(e) => setWorkspace(e.target.value)}
            required
          />
        </label>
        <label className="field">
          <span className="field-label">Question</span>
          <textarea
            rows={4}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask a question"
            required
          />
        </label>
        <div className="grid two">
          <label className="field">
            <span className="field-label">User ID (optional)</span>
            <input
              type="number"
              min={1}
              value={user_id}
              onChange={(e) => setUser(e.target.value)}
            />
          </label>
          <label className="field">
            <span className="field-label">Concept ID (optional)</span>
            <input
              type="number"
              min={1}
              value={concept_id}
              onChange={(e) => setConcept(e.target.value)}
            />
          </label>
        </div>
        <div className="button-row"><button type="submit" disabled={loading}>Send</button></div>
      </form>
      <AsyncState loading={loading} error={error} empty={!data} emptyLabel="Submit a tutor prompt." />
      {data ? <pre>{JSON.stringify(data, null, 2)}</pre> : null}
    </section>
  );
}

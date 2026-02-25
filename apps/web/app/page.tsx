"use client";

import { useEffect, useState } from "react";

import { AsyncState } from "@/components/async-state";
import { ApiError, DEFAULT_API_BASE_URL, apiClient } from "@/lib/api/client";
import type { HealthzResponse } from "@/lib/api/types";

export default function HomePage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<HealthzResponse | null>(null);

  async function loadHealth() {
    setLoading(true);
    setError(null);
    try {
      const payload = await apiClient.healthz();
      setData(payload);
    } catch (e: unknown) {
      if (e instanceof ApiError) {
        setError(e.message);
      } else if (e instanceof Error) {
        setError(e.message);
      } else {
        setError("Health check failed");
      }
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadHealth();
  }, []);

  return (
    <section className="panel stack">
      <h1>Frontend scaffold</h1>
      <p>Backend controls mastery gating and evidence policy. UI renders contract outputs only.</p>
      <p className="field-label">API base URL: {DEFAULT_API_BASE_URL}</p>
      <div className="button-row">
        <button type="button" className="secondary" onClick={() => void loadHealth()} disabled={loading}>
          Retry health check
        </button>
      </div>
      <AsyncState loading={loading} error={error} empty={!data} emptyLabel="No health payload." />
      {data ? <pre>{JSON.stringify(data, null, 2)}</pre> : null}
    </section>
  );
}

"use client";

import { useEffect, useState } from "react";

import { AsyncState } from "@/components/async-state";
import { ApiError, apiClient } from "@/lib/api/client";
import type { HealthzResponse } from "@/lib/api/types";

export default function HomePage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<HealthzResponse | null>(null);

  useEffect(() => {
    apiClient.healthz().then(setData).catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Health check failed")).finally(() => setLoading(false));
  }, []);

  return (
    <section className="panel stack">
      <h1>Frontend scaffold</h1>
      <p>Backend controls mastery gating and evidence policy. UI renders contract outputs only.</p>
      <AsyncState loading={loading} error={error} empty={!data} emptyLabel="No health payload." />
      {data ? <pre>{JSON.stringify(data, null, 2)}</pre> : null}
    </section>
  );
}

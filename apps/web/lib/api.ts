import type {
  ConceptDetail,
  TrailDetail,
  TrailGenerateRequest,
  TrailGenerateResponse,
  Workspace,
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

interface WorkspaceListResponse {
  workspaces: Workspace[];
}

interface TrailListResponse {
  trails: TrailDetail["trail"][];
}

interface ErrorEnvelope {
  error?: { message?: string };
  detail?: unknown;
}

export async function createWorkspace(name: string): Promise<Workspace> {
  return request<Workspace>("/api/workspaces", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function getWorkspace(workspaceId: string): Promise<Workspace> {
  return request<Workspace>(`/api/workspaces/${workspaceId}`, { method: "GET" });
}

export async function listWorkspaces(): Promise<WorkspaceListResponse> {
  return request<WorkspaceListResponse>("/api/workspaces", { method: "GET" });
}

export async function listTrails(workspaceId: string): Promise<TrailListResponse> {
  return request<TrailListResponse>(`/api/workspaces/${workspaceId}/trails`, {
    method: "GET",
  });
}

export async function generateTrail(
  workspaceId: string,
  body: TrailGenerateRequest,
): Promise<TrailGenerateResponse> {
  return request<TrailGenerateResponse>(`/api/workspaces/${workspaceId}/trails/generate`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getTrail(workspaceId: string, trailId: string): Promise<TrailDetail> {
  return request<TrailDetail>(`/api/workspaces/${workspaceId}/trails/${trailId}`, {
    method: "GET",
  });
}

export async function deleteTrail(workspaceId: string, trailId: string): Promise<void> {
  await request<void>(`/api/workspaces/${workspaceId}/trails/${trailId}`, {
    method: "DELETE",
  });
}

export async function getConcept(
  workspaceId: string,
  trailId: string,
  conceptId: string,
): Promise<ConceptDetail> {
  return request<ConceptDetail>(
    `/api/workspaces/${workspaceId}/trails/${trailId}/concepts/${conceptId}`,
    { method: "GET" },
  );
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
    ...init,
  });
  if (response.status === 204) {
    return undefined as T;
  }
  const payload = (await response.json().catch(() => ({}))) as ErrorEnvelope;
  if (!response.ok) {
    throw new Error(errorMessage(payload));
  }
  return payload as T;
}

function errorMessage(payload: ErrorEnvelope): string {
  if (payload.error?.message) {
    return payload.error.message;
  }
  if (typeof payload.detail === "string") {
    return payload.detail;
  }
  if (Array.isArray(payload.detail)) {
    return payload.detail
      .map((item) =>
        typeof item === "object" && item !== null && "msg" in item
          ? String(item.msg)
          : String(item),
      )
      .join(", ");
  }
  return "Request failed";
}

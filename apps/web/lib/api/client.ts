import type {
  AssistantResponseEnvelope,
  ChatRespondRequest,
  ChatMessagesResponse,
  ChatSessionListResponse,
  ChatSessionSummary,
  CreateChatSessionRequest,
  DeleteChatSessionRequest,
  CreateLevelUpQuizRequest,
  CreateQuizRequest,
  FlashcardRateResponse,
  FlashcardsRequest,
  GraphConceptListResponse,
  GraphConceptDetailResponse,
  GraphLuckyResponse,
  GraphSubgraphResponse,
  HealthzResponse,
  KBDocumentListResponse,
  LevelUpQuizSubmitResponse,
  LuckyMode,
  MagicLinkResponse,
  PracticeFlashcardsResponse,
  PracticeQuizSubmitResponse,
  QuizCreateResponse,
  ReadinessSnapshotResponse,
  OnboardingStatusResponse,
  ResearchCandidateSummary,
  ResearchRunSummary,
  ResearchSourceSummary,
  StatefulFlashcardsResponse,
  SubmitLevelUpQuizRequest,
  SubmitQuizRequest,
  UserPublic,
  VerifyTokenResponse,
  WorkspaceDetail,
  WorkspaceListResponse,
  WorkspaceSummary,
} from "@/lib/api/types";

export const DEFAULT_API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";
type QueryValue = string | number | boolean | null | undefined;
type Query = Record<string, QueryValue>;
type FetchLike = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
const defaultFetch: FetchLike = (input, init) => globalThis.fetch(input, init);

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: unknown,
    readonly body: unknown,
  ) {
    super(typeof detail === "string" && detail ? detail : `Request failed with status ${status}`);
    this.name = "ApiError";
  }
}

const query = (params?: Query) => {
  if (!params) return "";
  const s = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => v !== undefined && v !== null && s.set(k, String(v)));
  const q = s.toString();
  return q ? `?${q}` : "";
};

async function parse(res: Response) {
  const text = await res.text();
  if (!text) return null;
  try { return JSON.parse(text) as unknown; } catch { return text; }
}

const SESSION_TOKEN_KEY = "colearni_session_token";

export class ApiClient {
  private baseUrl: string;
  private fetchImpl: FetchLike;

  constructor(opts?: { baseUrl?: string; fetchImpl?: FetchLike }) {
    this.baseUrl = (opts?.baseUrl ?? DEFAULT_API_BASE_URL).replace(/\/$/, "");
    this.fetchImpl = opts?.fetchImpl ?? defaultFetch;
  }

  private getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(SESSION_TOKEN_KEY);
  }

  private async request<T>(path: string, init: RequestInit, params?: Query): Promise<T> {
    const headers = new Headers(init.headers);
    if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    const token = this.getToken();
    if (token && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    const res = await this.fetchImpl(`${this.baseUrl}${path}${query(params)}`, { ...init, headers });
    const body = await parse(res);
    if (!res.ok) {
      const detail = body && typeof body === "object" && "detail" in body ? (body as { detail: unknown }).detail : body;
      throw new ApiError(res.status, detail, body);
    }
    return body as T;
  }

  async uploadFile<T>(path: string, formData: FormData, params?: Query): Promise<T> {
    const headers = new Headers();
    const token = this.getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const res = await this.fetchImpl(`${this.baseUrl}${path}${query(params)}`, { method: "POST", headers, body: formData });
    const body = await parse(res);
    if (!res.ok) {
      const detail = body && typeof body === "object" && "detail" in body ? (body as { detail: unknown }).detail : body;
      throw new ApiError(res.status, detail, body);
    }
    return body as T;
  }

  healthz() { return this.request<HealthzResponse>("/healthz", { method: "GET" }); }

  // ── Chat (workspace-scoped) ─────────────────────────────────────
  createChatSession(wsId: string, p: CreateChatSessionRequest) { return this.request<ChatSessionSummary>(`/workspaces/${wsId}/chat/sessions`, { method: "POST", body: JSON.stringify(p) }); }
  listChatSessions(wsId: string, p?: { limit?: number }) { return this.request<ChatSessionListResponse>(`/workspaces/${wsId}/chat/sessions`, { method: "GET" }, { limit: p?.limit }); }
  getChatMessages(wsId: string, sessionId: string, p?: { limit?: number }) { return this.request<ChatMessagesResponse>(`/workspaces/${wsId}/chat/sessions/${sessionId}/messages`, { method: "GET" }, { limit: p?.limit }); }
  deleteChatSession(wsId: string, sessionId: string) { return this.request<null>(`/workspaces/${wsId}/chat/sessions/${sessionId}`, { method: "DELETE" }); }
  renameChatSession(wsId: string, sessionId: string, title: string) { return this.request<ChatSessionSummary>(`/workspaces/${wsId}/chat/sessions/${sessionId}`, { method: "PATCH", body: JSON.stringify({ title }) }); }
  respondChat(wsId: string, p: ChatRespondRequest) { return this.request<AssistantResponseEnvelope>(`/workspaces/${wsId}/chat/respond`, { method: "POST", body: JSON.stringify(p) }); }

  // ── Graph (workspace-scoped) ────────────────────────────────────
  listConcepts(wsId: string, p?: { q?: string; limit?: number }) { return this.request<GraphConceptListResponse>(`/workspaces/${wsId}/graph/concepts`, { method: "GET" }, { q: p?.q, limit: p?.limit }); }
  getConceptDetail(wsId: string, conceptId: number) { return this.request<GraphConceptDetailResponse>(`/workspaces/${wsId}/graph/concepts/${conceptId}`, { method: "GET" }); }
  getConceptSubgraph(wsId: string, conceptId: number, p?: { max_hops?: number; max_nodes?: number; max_edges?: number }) { return this.request<GraphSubgraphResponse>(`/workspaces/${wsId}/graph/concepts/${conceptId}/subgraph`, { method: "GET" }, { max_hops: p?.max_hops, max_nodes: p?.max_nodes, max_edges: p?.max_edges }); }
  getFullGraph(wsId: string, p?: { max_nodes?: number; max_edges?: number }) { return this.request<GraphSubgraphResponse>(`/workspaces/${wsId}/graph/full`, { method: "GET" }, { max_nodes: p?.max_nodes, max_edges: p?.max_edges }); }
  getLuckyPick(wsId: string, p: { concept_id: number; mode: LuckyMode; k_hops?: number }) { return this.request<GraphLuckyResponse>(`/workspaces/${wsId}/graph/lucky`, { method: "GET" }, { concept_id: p.concept_id, mode: p.mode, k_hops: p.k_hops }); }

  // ── Quizzes (workspace-scoped) ──────────────────────────────────
  createLevelUpQuiz(wsId: string, p: CreateLevelUpQuizRequest) { return this.request<QuizCreateResponse>(`/workspaces/${wsId}/quizzes/level-up`, { method: "POST", body: JSON.stringify(p) }); }
  submitLevelUpQuiz(wsId: string, quizId: number, p: SubmitLevelUpQuizRequest) { return this.request<LevelUpQuizSubmitResponse>(`/workspaces/${wsId}/quizzes/${quizId}/submit`, { method: "POST", body: JSON.stringify(p) }); }

  // ── Practice (workspace-scoped) ─────────────────────────────────
  generatePracticeFlashcards(wsId: string, p: FlashcardsRequest) { return this.request<PracticeFlashcardsResponse>(`/workspaces/${wsId}/practice/flashcards`, { method: "POST", body: JSON.stringify(p) }); }
  createPracticeQuiz(wsId: string, p: CreateQuizRequest) { return this.request<QuizCreateResponse>(`/workspaces/${wsId}/practice/quizzes`, { method: "POST", body: JSON.stringify(p) }); }
  submitPracticeQuiz(wsId: string, quizId: number, p: SubmitQuizRequest) { return this.request<PracticeQuizSubmitResponse>(`/workspaces/${wsId}/practice/quizzes/${quizId}/submit`, { method: "POST", body: JSON.stringify(p) }); }
  generateStatefulFlashcards(wsId: string, p: { concept_id: number; card_count?: number }) { return this.request<StatefulFlashcardsResponse>(`/workspaces/${wsId}/practice/flashcards/stateful`, { method: "POST", body: JSON.stringify(p) }); }
  rateFlashcard(wsId: string, p: { flashcard_id: string; self_rating: string }) { return this.request<FlashcardRateResponse>(`/workspaces/${wsId}/practice/flashcards/rate`, { method: "POST", body: JSON.stringify(p) }); }

  // ── Auth ─────────────────────────────────────────────────────────
  requestMagicLink(email: string) { return this.request<MagicLinkResponse>("/auth/magic-link", { method: "POST", body: JSON.stringify({ email }) }); }
  verifyMagicLink(token: string) { return this.request<VerifyTokenResponse>("/auth/verify", { method: "POST", body: JSON.stringify({ token }) }); }
  logout() { return this.request<null>("/auth/logout", { method: "POST" }); }
  getMe() { return this.request<UserPublic>("/auth/me", { method: "GET" }); }

  // ── Workspaces ──────────────────────────────────────────────────
  listWorkspaces() { return this.request<WorkspaceListResponse>("/workspaces", { method: "GET" }); }
  createWorkspace(p: { name: string; description?: string }) { return this.request<WorkspaceSummary>("/workspaces", { method: "POST", body: JSON.stringify(p) }); }
  getWorkspace(wsId: string) { return this.request<WorkspaceDetail>(`/workspaces/${wsId}`, { method: "GET" }); }
  updateWorkspace(wsId: string, p: { name: string; description?: string }) { return this.request<WorkspaceDetail>(`/workspaces/${wsId}`, { method: "PATCH", body: JSON.stringify(p) }); }
  updateWorkspaceSettings(wsId: string, settings: Record<string, unknown>) { return this.request<WorkspaceDetail>(`/workspaces/${wsId}/settings`, { method: "PATCH", body: JSON.stringify({ settings }) }); }

  // ── Knowledge Base (workspace-scoped) ───────────────────────────
  listKBDocuments(wsId: string) { return this.request<KBDocumentListResponse>(`/workspaces/${wsId}/knowledge-base/documents`, { method: "GET" }); }
  deleteKBDocument(wsId: string, documentId: number) { return this.request<null>(`/workspaces/${wsId}/knowledge-base/documents/${documentId}`, { method: "DELETE" }); }
  reprocessKBDocument(wsId: string, documentId: number) { return this.request<Record<string, unknown>>(`/workspaces/${wsId}/knowledge-base/documents/${documentId}/reprocess`, { method: "POST" }); }
  uploadKBDocument(wsId: string, p: { file: File; title?: string }) {
    const form = new FormData();
    form.append("file", p.file);
    if (p.title) form.append("title", p.title);
    return this.uploadFile<{ document_id: number; workspace_id: number; title: string; chunk_count: number; created: boolean }>(`/workspaces/${wsId}/knowledge-base/documents/upload`, form);
  }

  // ── Readiness (workspace-scoped) ────────────────────────────────
  getReadinessSnapshot(wsId: string) { return this.request<ReadinessSnapshotResponse>(`/workspaces/${wsId}/readiness/snapshot`, { method: "GET" }); }

  // ── Research (workspace-scoped) ─────────────────────────────────
  listResearchSources(wsId: string) { return this.request<ResearchSourceSummary[]>(`/workspaces/${wsId}/research/sources`, { method: "GET" }); }
  addResearchSource(wsId: string, p: { url: string; label?: string }) { return this.request<ResearchSourceSummary>(`/workspaces/${wsId}/research/sources`, { method: "POST", body: JSON.stringify({ url: p.url, label: p.label }) }); }
  triggerResearchRun(wsId: string) { return this.request<ResearchRunSummary>(`/workspaces/${wsId}/research/runs`, { method: "POST" }); }
  listResearchCandidates(wsId: string, p?: { run_id?: number; status?: string }) { return this.request<ResearchCandidateSummary[]>(`/workspaces/${wsId}/research/candidates`, { method: "GET" }, { run_id: p?.run_id, status: p?.status }); }
  reviewResearchCandidate(wsId: string, candidateId: number, p: { status: "approved" | "rejected" }) { return this.request<ResearchCandidateSummary>(`/workspaces/${wsId}/research/candidates/${candidateId}`, { method: "PATCH", body: JSON.stringify({ status: p.status }) }); }

  // ── Onboarding (workspace-scoped) ───────────────────────────────
  getOnboardingStatus(wsId: string) { return this.request<OnboardingStatusResponse>(`/workspaces/${wsId}/onboarding/status`, { method: "GET" }); }
}

export const apiClient = new ApiClient();

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
  FlashcardsRequest,
  GraphConceptListResponse,
  GraphConceptDetailResponse,
  GraphLuckyResponse,
  GraphSubgraphResponse,
  HealthzResponse,
  LevelUpQuizSubmitResponse,
  LuckyMode,
  PracticeFlashcardsResponse,
  PracticeQuizSubmitResponse,
  QuizCreateResponse,
  SubmitLevelUpQuizRequest,
  SubmitQuizRequest,
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

export class ApiClient {
  private baseUrl: string;
  private fetchImpl: FetchLike;

  constructor(opts?: { baseUrl?: string; fetchImpl?: FetchLike }) {
    this.baseUrl = (opts?.baseUrl ?? DEFAULT_API_BASE_URL).replace(/\/$/, "");
    this.fetchImpl = opts?.fetchImpl ?? defaultFetch;
  }

  private async request<T>(path: string, init: RequestInit, params?: Query): Promise<T> {
    const headers = new Headers(init.headers);
    if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    const res = await this.fetchImpl(`${this.baseUrl}${path}${query(params)}`, { ...init, headers });
    const body = await parse(res);
    if (!res.ok) {
      const detail = body && typeof body === "object" && "detail" in body ? (body as { detail: unknown }).detail : body;
      throw new ApiError(res.status, detail, body);
    }
    return body as T;
  }

  healthz() { return this.request<HealthzResponse>("/healthz", { method: "GET" }); }
  createChatSession(p: CreateChatSessionRequest) { return this.request<ChatSessionSummary>("/chat/sessions", { method: "POST", body: JSON.stringify(p) }); }
  listChatSessions(p: { workspace_id: number; user_id: number; limit?: number }) { return this.request<ChatSessionListResponse>("/chat/sessions", { method: "GET" }, { workspace_id: p.workspace_id, user_id: p.user_id, limit: p.limit }); }
  getChatMessages(p: { workspace_id: number; user_id: number; session_id: number; limit?: number }) { return this.request<ChatMessagesResponse>(`/chat/sessions/${p.session_id}/messages`, { method: "GET" }, { workspace_id: p.workspace_id, user_id: p.user_id, limit: p.limit }); }
  deleteChatSession(p: DeleteChatSessionRequest) { return this.request<null>(`/chat/sessions/${p.session_id}`, { method: "DELETE" }, { workspace_id: p.workspace_id, user_id: p.user_id }); }
  respondChat(p: ChatRespondRequest) { return this.request<AssistantResponseEnvelope>("/chat/respond", { method: "POST", body: JSON.stringify(p) }); }
  listConcepts(p: { workspace_id: number; user_id?: number; q?: string; limit?: number }) { return this.request<GraphConceptListResponse>("/graph/concepts", { method: "GET" }, { workspace_id: p.workspace_id, user_id: p.user_id, q: p.q, limit: p.limit }); }
  getConceptDetail(p: { workspace_id: number; concept_id: number }) { return this.request<GraphConceptDetailResponse>(`/graph/concepts/${p.concept_id}`, { method: "GET" }, { workspace_id: p.workspace_id }); }
  getConceptSubgraph(p: { workspace_id: number; concept_id: number; user_id?: number; max_hops?: number; max_nodes?: number; max_edges?: number }) { return this.request<GraphSubgraphResponse>(`/graph/concepts/${p.concept_id}/subgraph`, { method: "GET" }, { workspace_id: p.workspace_id, user_id: p.user_id, max_hops: p.max_hops, max_nodes: p.max_nodes, max_edges: p.max_edges }); }
  getLuckyPick(p: { workspace_id: number; concept_id: number; mode: LuckyMode; k_hops?: number }) { return this.request<GraphLuckyResponse>("/graph/lucky", { method: "GET" }, { workspace_id: p.workspace_id, concept_id: p.concept_id, mode: p.mode, k_hops: p.k_hops }); }
  createLevelUpQuiz(p: CreateLevelUpQuizRequest) { return this.request<QuizCreateResponse>("/quizzes/level-up", { method: "POST", body: JSON.stringify(p) }); }
  submitLevelUpQuiz(quizId: number, p: SubmitLevelUpQuizRequest) { return this.request<LevelUpQuizSubmitResponse>(`/quizzes/${quizId}/submit`, { method: "POST", body: JSON.stringify(p) }); }
  generatePracticeFlashcards(p: FlashcardsRequest) { return this.request<PracticeFlashcardsResponse>("/practice/flashcards", { method: "POST", body: JSON.stringify(p) }); }
  createPracticeQuiz(p: CreateQuizRequest) { return this.request<QuizCreateResponse>("/practice/quizzes", { method: "POST", body: JSON.stringify(p) }); }
  submitPracticeQuiz(quizId: number, p: SubmitQuizRequest) { return this.request<PracticeQuizSubmitResponse>(`/practice/quizzes/${quizId}/submit`, { method: "POST", body: JSON.stringify(p) }); }
}

export const apiClient = new ApiClient();

import type {
  ConceptDetail,
  ConversationHistoryResponse,
  ConversationMessage,
  GradeResult,
  LevelUpCard,
  QuizAnswer,
  QuizQuestion,
  TrailDetail,
  TrailGenerateRequest,
  TrailGenerateResponse,
  TutorChatRequest,
  TutorMode,
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

interface TutorStreamEvent {
  type?: "mode" | "thinking" | "token" | "done" | "error";
  mode?: TutorMode;
  content?: string;
  conversation_id?: string;
  message?: ConversationMessage | string;
  code?: string;
  error?: { message?: string };
  detail?: unknown;
}

export interface StreamTutorChatOptions {
  workspaceId: string;
  trailId: string;
  conceptId: string;
  message: string;
  conversationId: string | null;
  signal?: AbortSignal;
  onMode: (mode: TutorMode) => void;
  onThinking?: (content: string) => void;
  onToken: (content: string) => void;
  onDone: (conversationId: string, message: ConversationMessage) => void;
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
  onProgress?: (message: string) => void,
  onDelta?: (chunk: string) => void,
  onThinking?: (chunk: string) => void,
): Promise<TrailGenerateResponse> {
  if (onProgress || onDelta || onThinking) {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/workspaces/${workspaceId}/trails/generate/stream`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      );
      if (response.ok && response.body) {
        return await readTrailGenerationStream(response, onProgress, onDelta, onThinking);
      }
      onProgress?.("Streaming progress unavailable; waiting for final response...");
    } catch {
      onProgress?.("Streaming progress unavailable; waiting for final response...");
    }
  }
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

export async function generateLevelUpQuiz(
  workspaceId: string,
  trailId: string,
  conceptId: string,
): Promise<LevelUpCard> {
  return request<LevelUpCard>(
    `/api/workspaces/${workspaceId}/trails/${trailId}/concepts/${conceptId}/level-up`,
    { method: "POST" },
  );
}

export async function generatePracticeQuiz(
  workspaceId: string,
  trailId: string,
  conceptId: string,
): Promise<LevelUpCard> {
  return request<LevelUpCard>(
    `/api/workspaces/${workspaceId}/trails/${trailId}/concepts/${conceptId}/practice`,
    { method: "POST" },
  );
}

export async function gradeLevelUpQuiz(
  workspaceId: string,
  trailId: string,
  conceptId: string,
  questions: QuizQuestion[],
  answers: QuizAnswer[],
): Promise<GradeResult> {
  return request<GradeResult>(
    `/api/workspaces/${workspaceId}/trails/${trailId}/concepts/${conceptId}/grade`,
    {
      method: "POST",
      body: JSON.stringify({ questions, answers }),
    },
  );
}

export async function gradePracticeQuiz(
  workspaceId: string,
  trailId: string,
  conceptId: string,
  questions: QuizQuestion[],
  answers: QuizAnswer[],
): Promise<GradeResult> {
  return request<GradeResult>(
    `/api/workspaces/${workspaceId}/trails/${trailId}/concepts/${conceptId}/practice/grade`,
    {
      method: "POST",
      body: JSON.stringify({ questions, answers }),
    },
  );
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

export async function getConversation(
  workspaceId: string,
  trailId: string,
  conceptId: string,
  limit?: number,
): Promise<ConversationHistoryResponse> {
  const query = limit ? `?limit=${encodeURIComponent(String(limit))}` : "";
  return request<ConversationHistoryResponse>(
    `/api/workspaces/${workspaceId}/trails/${trailId}/concepts/${conceptId}/conversation${query}`,
    { method: "GET" },
  );
}

export async function streamTutorChat({
  workspaceId,
  trailId,
  conceptId,
  message,
  conversationId,
  signal,
  onMode,
  onThinking,
  onToken,
  onDone,
}: StreamTutorChatOptions): Promise<void> {
  const body: TutorChatRequest = {
    message,
    conversation_id: conversationId,
  };
  const response = await fetch(
    `${API_BASE_URL}/api/workspaces/${workspaceId}/trails/${trailId}/concepts/${conceptId}/chat`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    },
  );

  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  if (!response.body) {
    throw new Error("Tutor stream is unavailable");
  }

  const sawDone = await readTutorStream(response.body, { onMode, onThinking, onToken, onDone });
  if (!sawDone) {
    throw new Error("Tutor stream ended before completion");
  }
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

async function responseErrorMessage(response: Response): Promise<string> {
  const text = await response.text().catch(() => "");
  if (!text) {
    return response.statusText || "Request failed";
  }
  try {
    return errorMessage(JSON.parse(text) as ErrorEnvelope);
  } catch {
    return text;
  }
}

async function readTutorStream(
  body: ReadableStream<Uint8Array>,
  callbacks: Pick<StreamTutorChatOptions, "onMode" | "onThinking" | "onToken" | "onDone">,
): Promise<boolean> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let sawDone = false;

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      sawDone = handleTutorStreamEvent(chunk, callbacks) || sawDone;
    }
  }

  buffer += decoder.decode();
  if (buffer.trim()) {
    sawDone = handleTutorStreamEvent(buffer, callbacks) || sawDone;
  }
  return sawDone;
}

function handleTutorStreamEvent(
  chunk: string,
  callbacks: Pick<StreamTutorChatOptions, "onMode" | "onThinking" | "onToken" | "onDone">,
): boolean {
  const dataLines = chunk
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trim());
  const rawData = dataLines.join("\n");
  if (!rawData) {
    return false;
  }

  const payload = JSON.parse(rawData) as TutorStreamEvent;
  if (payload.type === "mode") {
    if (payload.mode) {
      callbacks.onMode(payload.mode);
    }
    return false;
  }
  if (payload.type === "token") {
    if (typeof payload.content === "string") {
      callbacks.onToken(payload.content);
    }
    return false;
  }
  if (payload.type === "thinking") {
    if (typeof payload.content === "string") {
      callbacks.onThinking?.(payload.content);
    }
    return false;
  }
  if (payload.type === "done") {
    if (typeof payload.conversation_id === "string" && isConversationMessage(payload.message)) {
      callbacks.onDone(payload.conversation_id, payload.message);
      return true;
    }
    throw new Error("Tutor stream returned a malformed completion event");
  }
  if (payload.type === "error") {
    throw new Error(streamErrorMessage(payload));
  }
  return false;
}

function isConversationMessage(value: TutorStreamEvent["message"]): value is ConversationMessage {
  return (
    typeof value === "object" &&
    value !== null &&
    "id" in value &&
    "role" in value &&
    "content" in value &&
    "reasoning" in value &&
    "created_at" in value
  );
}

function streamErrorMessage(payload: TutorStreamEvent): string {
  if (typeof payload.message === "string") {
    return payload.message;
  }
  if (payload.error?.message) {
    return payload.error.message;
  }
  return errorMessage(payload as ErrorEnvelope);
}

async function readTrailGenerationStream(
  response: Response,
  onProgress: ((message: string) => void) | undefined,
  onDelta: ((chunk: string) => void) | undefined,
  onThinking: ((chunk: string) => void) | undefined,
): Promise<TrailGenerateResponse> {
  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("Generation stream is unavailable");
  }
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      const result = handleStreamEvent(chunk, onProgress, onDelta, onThinking);
      if (result) {
        return result;
      }
    }
  }

  if (buffer.trim()) {
    const result = handleStreamEvent(buffer, onProgress, onDelta, onThinking);
    if (result) {
      return result;
    }
  }
  throw new Error("Generation stream ended before returning a Trail");
}

function handleStreamEvent(
  chunk: string,
  onProgress: ((message: string) => void) | undefined,
  onDelta: ((chunk: string) => void) | undefined,
  onThinking: ((chunk: string) => void) | undefined,
): TrailGenerateResponse | null {
  const event = /^event:\s*(.+)$/m.exec(chunk)?.[1]?.trim() ?? "message";
  const dataLines = chunk
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trim());
  const rawData = dataLines.join("\n");
  const payload = rawData ? JSON.parse(rawData) : {};

  if (event === "progress") {
    if (typeof payload.message === "string") {
      onProgress?.(payload.message);
    }
    return null;
  }
  if (event === "delta") {
    if (typeof payload.text === "string") {
      onDelta?.(payload.text);
    }
    return null;
  }
  if (event === "thinking") {
    if (typeof payload.text === "string") {
      onThinking?.(payload.text);
    }
    return null;
  }
  if (event === "error") {
    throw new Error(errorMessage(payload as ErrorEnvelope));
  }
  if (event === "done") {
    return payload as TrailGenerateResponse;
  }
  return null;
}

import type { AssistantResponseEnvelope, ChatRespondRequest } from "@/lib/api/types";

export type ChatMessage =
  | { id: number; role: "user"; text: string }
  | { id: number; role: "assistant"; response: AssistantResponseEnvelope };

export type ChatStatus = "idle" | "loading" | "error";

export interface ChatState {
  status: ChatStatus;
  error: string | null;
  messages: ChatMessage[];
  pending_request: ChatRespondRequest | null;
  retry_request: ChatRespondRequest | null;
  next_id: number;
}

export type ChatAction =
  | { type: "send"; request: ChatRespondRequest; user_text: string }
  | { type: "receive"; response: AssistantResponseEnvelope }
  | { type: "fail"; error: string }
  | { type: "retry" }
  | { type: "clear_error" };

export const initialChatState: ChatState = {
  status: "idle",
  error: null,
  messages: [],
  pending_request: null,
  retry_request: null,
  next_id: 1,
};

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  if (action.type === "send") {
    return {
      ...state,
      status: "loading",
      error: null,
      messages: [...state.messages, { id: state.next_id, role: "user", text: action.user_text }],
      pending_request: action.request,
      retry_request: null,
      next_id: state.next_id + 1,
    };
  }

  if (action.type === "receive") {
    if (!state.pending_request) {
      return state;
    }
    return {
      ...state,
      status: "idle",
      error: null,
      messages: [
        ...state.messages,
        { id: state.next_id, role: "assistant", response: action.response },
      ],
      pending_request: null,
      retry_request: null,
      next_id: state.next_id + 1,
    };
  }

  if (action.type === "fail") {
    return {
      ...state,
      status: "error",
      error: action.error,
      retry_request: state.pending_request,
      pending_request: null,
    };
  }

  if (action.type === "retry") {
    if (!state.retry_request) {
      return state;
    }
    return {
      ...state,
      status: "loading",
      error: null,
      pending_request: state.retry_request,
      retry_request: null,
    };
  }

  if (action.type === "clear_error") {
    return {
      ...state,
      status: state.pending_request ? "loading" : "idle",
      error: null,
    };
  }

  return state;
}

export function canRetryChat(state: ChatState): boolean {
  return state.status === "error" && !!state.retry_request;
}

import { describe, expect, it } from "vitest";

import type { AssistantResponseEnvelope, ChatRespondRequest } from "@/lib/api/types";
import { canRetryChat, chatReducer, initialChatState } from "@/lib/tutor/chat-state";

const request: ChatRespondRequest = {
  workspace_id: 1,
  query: "What is a linear map?",
  user_id: 2,
  concept_id: 3,
  grounding_mode: "strict",
};

function answerEnvelope(): AssistantResponseEnvelope {
  return {
    kind: "answer",
    text: "SOCRATIC: What property must hold first?",
    grounding_mode: "strict",
    evidence: [
      {
        evidence_id: "e1",
        source_type: "workspace",
        content: "Linear maps preserve vector addition.",
        document_id: 7,
        chunk_id: 11,
        chunk_index: 0,
        document_title: "Notes",
        source_uri: "file://notes.md",
        score: 0.9,
      },
    ],
    citations: [
      {
        citation_id: "c1",
        evidence_id: "e1",
        label: "From your notes",
        quote: "Linear maps preserve vector addition.",
      },
    ],
    refusal_reason: null,
  };
}

function refusalEnvelope(): AssistantResponseEnvelope {
  return {
    kind: "refusal",
    text: "I do not have enough cited material.",
    grounding_mode: "strict",
    evidence: [],
    citations: [],
    refusal_reason: "insufficient_evidence",
  };
}

describe("chatReducer", () => {
  it("handles send and answer receive", () => {
    const sent = chatReducer(initialChatState, {
      type: "send",
      request,
      user_text: request.query,
    });

    expect(sent.status).toBe("loading");
    expect(sent.messages).toHaveLength(1);
    expect(sent.messages[0]).toMatchObject({ role: "user", text: request.query });

    const received = chatReducer(sent, { type: "receive", response: answerEnvelope() });
    expect(received.status).toBe("idle");
    expect(received.messages).toHaveLength(2);
    expect(received.messages[1]).toMatchObject({ role: "assistant" });
    if (received.messages[1].role === "assistant") {
      expect(received.messages[1].response.kind).toBe("answer");
    }
  });

  it("records refusal responses as assistant messages", () => {
    const sent = chatReducer(initialChatState, {
      type: "send",
      request,
      user_text: request.query,
    });
    const received = chatReducer(sent, { type: "receive", response: refusalEnvelope() });

    expect(received.messages).toHaveLength(2);
    if (received.messages[1].role === "assistant") {
      expect(received.messages[1].response.kind).toBe("refusal");
      expect(received.messages[1].response.refusal_reason).toBe("insufficient_evidence");
    }
  });

  it("captures failure and supports retry", () => {
    const sent = chatReducer(initialChatState, {
      type: "send",
      request,
      user_text: request.query,
    });
    const failed = chatReducer(sent, { type: "fail", error: "timeout" });

    expect(failed.status).toBe("error");
    expect(failed.error).toBe("timeout");
    expect(canRetryChat(failed)).toBe(true);

    const retried = chatReducer(failed, { type: "retry" });
    expect(retried.status).toBe("loading");
    expect(retried.pending_request).toEqual(request);
    expect(retried.messages).toHaveLength(1);
  });
});

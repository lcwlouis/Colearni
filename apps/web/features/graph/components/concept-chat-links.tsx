"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import type { ChatSessionSummary } from "@/lib/api/types";
import { apiClient } from "@/lib/api/client";

type Props = {
  conceptName: string;
  conceptId: number;
  workspaceId?: string;
};

export function ConceptChatLinks({
  conceptName,
  conceptId,
  workspaceId,
}: Props) {
  const router = useRouter();
  const [relatedChats, setRelatedChats] = useState<ChatSessionSummary[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!workspaceId) return;
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const res = await apiClient.listChatSessions(workspaceId!, {
          limit: 50,
        });
        const needle = conceptName.toLowerCase();
        const matches = res.sessions.filter(
          (s) => s.title && s.title.toLowerCase().includes(needle),
        );
        if (!cancelled) setRelatedChats(matches);
      } catch (err) {
        console.error("Failed to load chat sessions:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [workspaceId, conceptName]);

  const handleStartChat = () => {
    const encodedTopic = encodeURIComponent(conceptName);
    router.push(`/tutor?topic=${encodedTopic}&concept_id=${conceptId}`);
  };

  return (
    <div className="concept-chat-links">
      {workspaceId && loading && (
        <p style={{ color: "var(--muted)", padding: "0.5rem 0" }}>
          Loading chats…
        </p>
      )}

      {relatedChats.length > 0 && (
        <ul className="concept-chat-links__list" style={{ listStyle: "none", padding: 0, margin: "0 0 0.75rem" }}>
          {relatedChats.map((chat) => (
            <li
              key={chat.public_id}
              className="concept-chat-links__item"
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "0.4rem 0",
                borderBottom: "1px solid var(--border, #eee)",
              }}
            >
              <button
                type="button"
                className="concept-chat-links__resume"
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  textAlign: "left",
                  flex: 1,
                  padding: "0.25rem 0",
                  color: "inherit",
                }}
                onClick={() =>
                  router.push(`/tutor?session=${chat.public_id}`)
                }
              >
                <span style={{ fontWeight: 500 }}>
                  {chat.title ?? "Untitled chat"}
                </span>
                <span
                  style={{
                    color: "var(--muted)",
                    fontSize: "0.8em",
                    marginLeft: "0.5rem",
                  }}
                >
                  {new Date(chat.last_activity_at).toLocaleDateString()}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {!loading && workspaceId && relatedChats.length === 0 && (
        <p
          style={{
            color: "var(--muted)",
            fontSize: "0.85em",
            margin: "0 0 0.5rem",
          }}
        >
          No existing chats about this topic
        </p>
      )}

      <button
        type="button"
        className="concept-chat-links__start"
        onClick={handleStartChat}
      >
        Start a new chat about {conceptName}
      </button>
    </div>
  );
}

"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { apiClient } from "@/lib/api/client";
import type { ChatSessionSummary } from "@/lib/api/types";
import { useRequireAuth } from "@/lib/auth";
import { usePathname, useRouter } from "next/navigation";

interface ChatSessionContextType {
    sessions: ChatSessionSummary[];
    activeSessionId: string | null;
    sessionsLoading: boolean;
    sessionsError: string | null;
    setActiveSessionId: (id: string | null) => void;
    refreshSessions: () => Promise<void>;
    startNewSession: (conceptId?: number) => Promise<string | null>;
    deleteSession: (sessionId: string) => Promise<void>;
    renameSession: (sessionId: string, title: string) => void; // Optimistic rename
    syncUrl: (sessionId: string) => void;
}

const ChatSessionContext = createContext<ChatSessionContextType | null>(null);

function errorText(error: unknown, fallback: string): string {
    if (error instanceof Error) return error.message;
    return fallback;
}

export function ChatSessionProvider({ children }: { children: ReactNode }) {
    const { activeWorkspaceId } = useRequireAuth();
    const wsId = activeWorkspaceId ?? undefined;
    const router = useRouter();
    const pathname = usePathname();

    const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
    const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
    const [sessionsLoading, setSessionsLoading] = useState(false);
    const [sessionsError, setSessionsError] = useState<string | null>(null);

    const syncUrl = (sessionId: string) => {
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get("chat") !== sessionId) {
            router.replace(`${pathname}?chat=${sessionId}`);
        }
    };

    const refreshSessions = async (preferredId?: string | null) => {
        if (!wsId) {
            setSessions([]);
            setActiveSessionId(null);
            return;
        }
        setSessionsLoading(true);
        setSessionsError(null);
        try {
            const payload = await apiClient.listChatSessions(wsId, { limit: 50 });
            let nextSessions = payload.sessions;
            if (!nextSessions.length) {
                const created = await apiClient.createChatSession(wsId, {});
                nextSessions = [created];
            }
            setSessions(nextSessions);
            let resolvedId: string | null = null;
            setActiveSessionId((prev) => {
                const target = preferredId ?? prev;
                if (target && nextSessions.some((item) => item.public_id === target)) {
                    resolvedId = target;
                    return target;
                }
                resolvedId = nextSessions[0]?.public_id ?? null;
                return resolvedId;
            });
            if (resolvedId && pathname === "/tutor") {
                syncUrl(resolvedId);
            }
        } catch (error: unknown) {
            setSessionsError(errorText(error, "Failed to load chat sessions"));
            setSessions([]);
            setActiveSessionId(null);
        } finally {
            setSessionsLoading(false);
        }
    };

    const startNewSession = async (conceptId?: number): Promise<string | null> => {
        if (!wsId) return null;
        // Guard: if the active session looks empty (no title), just re-select it
        if (activeSessionId) {
            const active = sessions.find((s) => s.public_id === activeSessionId);
            if (active && !active.title) {
                // Already on an empty chat — just navigate there
                if (pathname !== "/tutor") {
                    router.push(`/tutor?chat=${activeSessionId}`);
                }
                return activeSessionId;
            }
        }
        setSessionsError(null);
        try {
            const created = await apiClient.createChatSession(wsId, {
                ...(conceptId ? { concept_id: conceptId } : {}),
            });
            setSessions((prev) => [created, ...prev]);
            setActiveSessionId(created.public_id);
            if (pathname !== "/tutor") {
                router.push(`/tutor?chat=${created.public_id}`);
            } else {
                syncUrl(created.public_id);
            }
            return created.public_id;
        } catch (error: unknown) {
            setSessionsError(errorText(error, "Could not create chat session"));
            return null;
        }
    };

    const deleteSession = async (sessionId: string) => {
        if (!wsId) return;
        setSessionsError(null);
        try {
            await apiClient.deleteChatSession(wsId, sessionId);
            await refreshSessions();
        } catch (error: unknown) {
            setSessionsError(errorText(error, "Could not delete chat session"));
        }
    };

    const renameSession = (sessionId: string, title: string) => {
        // Optimistic update
        setSessions((prev) =>
            prev.map((s) => (s.public_id === sessionId ? { ...s, title } : s))
        );
        // Persist to backend
        if (wsId) {
            apiClient.renameChatSession(wsId, sessionId, title).catch(() => {
                // Revert on failure by re-fetching
                void refreshSessions();
            });
        }
    };

    useEffect(() => {
        const urlParams = new URLSearchParams(window.location.search);
        const chatParam = urlParams.get("chat") || urlParams.get("session");
        if (chatParam) {
            setActiveSessionId(chatParam);
        }
        void refreshSessions(chatParam ?? null);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [wsId]);

    return (
        <ChatSessionContext.Provider
            value={{
                sessions,
                activeSessionId,
                sessionsLoading,
                sessionsError,
                setActiveSessionId,
                refreshSessions,
                startNewSession,
                deleteSession,
                renameSession,
                syncUrl,
            }}
        >
            {children}
        </ChatSessionContext.Provider>
    );
}

export function useChatSession() {
    const ctx = useContext(ChatSessionContext);
    if (!ctx) throw new Error("useChatSession must be used within ChatSessionProvider");
    return ctx;
}

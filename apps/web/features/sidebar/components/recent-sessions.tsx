"use client";

import Link from "next/link";
import { useState, useEffect } from "react";

function toTitleCase(str: string): string {
  return str.replace(/\w\S*/g, (txt) => txt.charAt(0).toUpperCase() + txt.substring(1).toLowerCase());
}

interface ChatSession {
  public_id: string;
  session_id: number;
  title: string | null;
}

interface RecentSessionsProps {
  collapsed: boolean;
  pathname: string;
  sessions: ChatSession[];
  activeSessionId: string | null;
  sessionsLoading: boolean;
  sessionsError: string | null;
  startNewSession: () => Promise<string | null>;
  setActiveSessionId: (id: string) => void;
  deleteSession: (id: string) => Promise<void>;
  renameSession: (id: string, title: string) => void;
  syncUrl: (id: string) => void;
}

export function RecentSessions({
  collapsed,
  pathname,
  sessions,
  activeSessionId,
  sessionsLoading,
  sessionsError,
  startNewSession,
  setActiveSessionId,
  deleteSession,
  renameSession,
  syncUrl,
}: RecentSessionsProps) {
  const [contextMenuId, setContextMenuId] = useState<string | null>(null);
  const [contextMenuPos, setContextMenuPos] = useState<{ x: number; y: number; top?: boolean } | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  useEffect(() => {
    const handleGlobalClick = () => {
      if (contextMenuId) {
        setContextMenuId(null);
        setContextMenuPos(null);
      }
    };
    document.addEventListener("click", handleGlobalClick);
    return () => document.removeEventListener("click", handleGlobalClick);
  }, [contextMenuId]);

  return (
    <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", marginTop: "0.5rem" }}>
      {collapsed && (
        <div className="collapsed-new-chat">
          <button type="button" className="icon-btn" onClick={() => void startNewSession()} title="New chat" aria-label="New chat" style={{ padding: "0.55rem", borderRadius: "0.5rem", width: "100%", display: "grid", placeItems: "center" }}>
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>
          </button>
        </div>
      )}

      {!collapsed && (
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
          <h2 style={{ margin: 0, fontSize: "0.9rem", color: "var(--muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>Recent Chats</h2>
          <button type="button" className="icon-btn" onClick={() => void startNewSession()} style={{ padding: "0.2rem" }} aria-label="New chat" title="New chat">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>
          </button>
        </div>
      )}

      {!collapsed && (
        <div className="session-list">
          {sessionsLoading && sessions.length === 0 ? <p className="status loading" style={{ padding: "0.5rem", fontSize: "0.85rem" }}>Loading...</p> : null}
          {sessionsError ? <p className="status error" style={{ padding: "0.5rem", fontSize: "0.85rem" }}>{sessionsError}</p> : null}

          {sessions.map((chat) => (
            <div key={chat.public_id} className={`session-item ${chat.public_id === activeSessionId && pathname === "/tutor" ? "active" : ""} ${contextMenuId === chat.public_id ? "menu-open" : ""}`}>
              {renamingId === chat.public_id ? (
                <form
                  className="session-rename-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const trimmed = renameValue.trim();
                    if (trimmed) {
                      renameSession(chat.public_id, trimmed);
                    }
                    setRenamingId(null);
                  }}
                >
                  <input
                    type="text"
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onBlur={() => setRenamingId(null)}
                    onKeyDown={(e) => { if (e.key === "Escape") setRenamingId(null); }}
                    autoFocus
                    style={{ fontSize: "0.85rem", padding: "0.3rem 0.5rem" }}
                  />
                </form>
              ) : (
                <Link
                  href={`/tutor?chat=${chat.public_id}`}
                  className="session-item-btn"
                  onClick={() => {
                    setActiveSessionId(chat.public_id);
                    if (pathname === "/tutor") syncUrl(chat.public_id);
                    setContextMenuId(null);
                  }}
                  style={{ textDecoration: "none" }}
                >
                  <strong style={{ fontWeight: chat.public_id === activeSessionId && pathname === "/tutor" ? 600 : 400, fontSize: "0.85rem" }}>
                    {toTitleCase(chat.title || `Chat ${chat.session_id}`)}
                  </strong>
                </Link>
              )}

              <div className="session-actions">
                <button
                  type="button"
                  className="secondary icon-btn session-more-btn"
                  title="More options"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    if (contextMenuId === chat.public_id) {
                      setContextMenuId(null);
                      setContextMenuPos(null);
                    } else {
                      const rect = e.currentTarget.getBoundingClientRect();
                      const isNearBottom = rect.bottom > window.innerHeight - 120;
                      setContextMenuPos({ x: rect.right, y: isNearBottom ? rect.top : rect.bottom, top: isNearBottom });
                      setContextMenuId(chat.public_id);
                    }
                  }}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="1.5" /><circle cx="19" cy="12" r="1.5" /><circle cx="5" cy="12" r="1.5" />
                  </svg>
                </button>
                {contextMenuId === chat.public_id && contextMenuPos && (
                  <div
                    className="session-context-menu"
                    style={{
                      left: `${contextMenuPos.x + 4}px`,
                      ...(contextMenuPos.top
                        ? { bottom: `${window.innerHeight - contextMenuPos.y}px` }
                        : { top: `${contextMenuPos.y + 4}px` }),
                    }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setRenameValue(chat.title || `Chat ${chat.session_id}`);
                        setRenamingId(chat.public_id);
                        setContextMenuId(null);
                        setContextMenuPos(null);
                      }}
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
                      Rename
                    </button>
                    <button
                      type="button"
                      className="danger-text"
                      onClick={(e) => {
                        e.stopPropagation();
                        setContextMenuId(null);
                        setContextMenuPos(null);
                        setDeleteConfirmId(chat.public_id);
                      }}
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg>
                      Delete
                    </button>
                  </div>
                )}
              </div>
              {deleteConfirmId === chat.public_id && (
                <div className="delete-confirm-bar" style={{ gridColumn: "1 / -1", display: "flex", alignItems: "center", gap: "0.35rem", padding: "0.3rem 0.5rem", background: "var(--surface)", borderRadius: "0.35rem", fontSize: "0.8rem" }}>
                  <span style={{ flex: 1, color: "var(--muted)" }}>Delete?</span>
                  <button type="button" className="danger-text" style={{ padding: "0.15rem 0.5rem", fontSize: "0.78rem" }} onClick={() => { void deleteSession(chat.public_id); setDeleteConfirmId(null); }}>Yes</button>
                  <button type="button" className="secondary" style={{ padding: "0.15rem 0.5rem", fontSize: "0.78rem" }} onClick={() => setDeleteConfirmId(null)}>No</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

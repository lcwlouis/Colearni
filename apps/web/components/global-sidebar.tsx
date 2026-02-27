"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut, Sun, Moon, Check, Edit2, Pencil, Search, Clock, GraduationCap, Network, BookOpen, Target } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { HealthDot } from "@/components/health-dot";
import { useRequireAuth } from "@/lib/auth";
import { useChatSession } from "@/lib/tutor/chat-session-context";
import { apiClient } from "@/lib/api/client";
import { useState, useEffect } from "react";

const navLinks = [
    ["/tutor", "Tutor", "🎓"],
    ["/graph", "Graph", "🕸️"],
    ["/practice", "Practice", "🎯"],
    ["/kb", "Knowledge Base", "📚"],
] as const;

function toTitleCase(str: string): string {
    return str.replace(/\w\S*/g, (txt) => txt.charAt(0).toUpperCase() + txt.substring(1).toLowerCase());
}

export function GlobalSidebar() {
    const pathname = usePathname();
    const { user, workspaces, activeWorkspaceId, setActiveWorkspaceId, logout, refreshWorkspaces } = useRequireAuth();
    const {
        sessions,
        activeSessionId,
        setActiveSessionId,
        sessionsLoading,
        sessionsError,
        startNewSession,
        deleteSession,
        renameSession,
        syncUrl
    } = useChatSession();

    const [contextMenuId, setContextMenuId] = useState<string | null>(null);
    const [contextMenuPos, setContextMenuPos] = useState<{ x: number; y: number; top?: boolean } | null>(null);
    const [renamingId, setRenamingId] = useState<string | null>(null);
    const [renameValue, setRenameValue] = useState("");
    const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

    const [isCreatingWorkspace, setIsCreatingWorkspace] = useState(false);
    const [newWorkspaceName, setNewWorkspaceName] = useState("");
    const [renamingWorkspaceId, setRenamingWorkspaceId] = useState<string | null>(null);
    const [renameWorkspaceName, setRenameWorkspaceName] = useState("");

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

    if (!user) {
        return null; // Don't render sidebar on login page
    }

    return (
        <aside className="global-sidebar">
            <div className="sidebar-header">
                <h1 className="brand" style={{ fontSize: "1.25rem", margin: 0 }}>CoLearni</h1>
                <HealthDot />
            </div>

            <nav className="nav" aria-label="Primary">
                <div className="nav-items-group" style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <Link href="/tutor" className={`nav-link ${pathname === "/tutor" ? "active" : ""}`}>
                        <GraduationCap className="nav-icon" />
                        <span>Tutor</span>
                    </Link>
                    <Link href="/graph" className={`nav-link ${pathname === "/graph" ? "active" : ""}`}>
                        <Network className="nav-icon" />
                        <span>Graph</span>
                    </Link>
                    <Link href="/kb" className={`nav-link ${pathname === "/kb" ? "active" : ""}`}>
                        <BookOpen className="nav-icon" />
                        <span>Knowledge Base</span>
                    </Link>
                </div>
            </nav>

            <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", marginTop: "0.5rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                    <h2 style={{ margin: 0, fontSize: "0.9rem", color: "var(--muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>Recent Chats</h2>
                    <button type="button" className="icon-btn" onClick={() => void startNewSession()} style={{ padding: "0.2rem" }} aria-label="New chat" title="New chat">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                    </button>
                </div>

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
                                            // TODO: emit network request to persist rename
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
                                        <circle cx="12" cy="12" r="1.5"></circle>
                                        <circle cx="19" cy="12" r="1.5"></circle>
                                        <circle cx="5" cy="12" r="1.5"></circle>
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
                                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                                            Rename
                                        </button>
                                        <button
                                            type="button"
                                            className="danger-text"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                setContextMenuId(null);
                                                setContextMenuPos(null);
                                                void deleteSession(chat.public_id);
                                            }}
                                        >
                                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                                            Delete
                                        </button>
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            <div className="sidebar-footer" style={{ borderTop: "none", paddingTop: 0 }}>
                {isCreatingWorkspace ? (
                    <form onSubmit={async (e) => {
                        e.preventDefault();
                        if (newWorkspaceName.trim()) {
                            try {
                                const ws = await apiClient.createWorkspace({ name: newWorkspaceName.trim() });
                                await refreshWorkspaces();
                                setActiveWorkspaceId(ws.public_id);
                            } catch (err) {
                                console.error(err);
                            }
                        }
                        setIsCreatingWorkspace(false);
                        setNewWorkspaceName("");
                    }} style={{ padding: "0.5rem" }}>
                        <input autoFocus value={newWorkspaceName} onChange={e => setNewWorkspaceName(e.target.value)} placeholder="Workspace name" style={{ width: "100%", padding: "0.25rem 0.5rem", fontSize: "0.85rem", borderRadius: "0.3rem", border: "1px solid var(--line)", background: "var(--surface)" }} />
                        <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
                            <button type="submit" style={{ flex: 1, padding: "0.25rem", fontSize: "0.8rem", height: "auto" }}>Create</button>
                            <button type="button" className="secondary" onClick={() => setIsCreatingWorkspace(false)} style={{ flex: 1, padding: "0.25rem", fontSize: "0.8rem", height: "auto" }}>Cancel</button>
                        </div>
                    </form>
                ) : renamingWorkspaceId ? (
                    <form onSubmit={async (e) => {
                        e.preventDefault();
                        if (renameWorkspaceName.trim()) {
                            try {
                                await apiClient.updateWorkspace(renamingWorkspaceId, { name: renameWorkspaceName.trim() });
                                await refreshWorkspaces();
                            } catch (err) {
                                console.error(err);
                            }
                        }
                        setRenamingWorkspaceId(null);
                    }} style={{ padding: "0.5rem" }}>
                        <input autoFocus value={renameWorkspaceName} onChange={e => setRenameWorkspaceName(e.target.value)} placeholder="New name" style={{ width: "100%", padding: "0.25rem 0.5rem", fontSize: "0.85rem", borderRadius: "0.3rem", border: "1px solid var(--line)", background: "var(--surface)" }} />
                        <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
                            <button type="submit" style={{ flex: 1, padding: "0.25rem", fontSize: "0.8rem", height: "auto" }}>Save</button>
                            <button type="button" className="secondary" onClick={() => setRenamingWorkspaceId(null)} style={{ flex: 1, padding: "0.25rem", fontSize: "0.8rem", height: "auto" }}>Cancel</button>
                        </div>
                    </form>
                ) : (
                    <div className="sidebar-workspace-block" style={{ padding: "0.5rem", display: "flex", alignItems: "center", gap: "0.25rem" }}>
                        <select
                            value={activeWorkspaceId ?? ""}
                            onChange={(event) => {
                                if (event.target.value === "NEW_WORKSPACE") {
                                    setNewWorkspaceName("");
                                    setIsCreatingWorkspace(true);
                                } else {
                                    setActiveWorkspaceId(event.target.value);
                                }
                            }}
                            aria-label="Select workspace"
                            style={{ flex: 1, fontSize: "0.85rem", padding: "0.4rem" }}
                        >
                            {workspaces.map((workspace) => (
                                <option key={workspace.public_id} value={workspace.public_id}>
                                    {workspace.name}
                                </option>
                            ))}
                            <option disabled>──────────</option>
                            <option value="NEW_WORKSPACE">+ Add workspace</option>
                        </select>
                        <button
                            type="button"
                            className="icon-btn secondary"
                            title="Rename workspace"
                            style={{ padding: "0.4rem" }}
                            onClick={() => {
                                if (activeWorkspaceId) {
                                    const ws = workspaces.find(w => w.public_id === activeWorkspaceId);
                                    if (ws) {
                                        setRenameWorkspaceName(ws.name);
                                        setRenamingWorkspaceId(ws.public_id);
                                    }
                                }
                            }}
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                        </button>
                    </div>
                )}
                <div className="sidebar-profile-block" style={{ display: "flex", flexDirection: "row", alignItems: "center", gap: "0.5rem", padding: "0.5rem 0.6rem" }}>
                    <div style={{ flex: 1, minWidth: 0, overflow: "hidden" }}>
                        <p className="sidebar-user-name" style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", fontSize: "0.82rem" }}>{user.display_name || user.email}</p>
                    </div>
                    <div className="sidebar-profile-actions">
                        <ThemeToggle />
                        <button type="button" className="secondary icon-btn" onClick={logout} title="Logout">
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
                        </button>
                    </div>
                </div>
            </div>
        </aside>
    );
}

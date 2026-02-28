"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { LogOut, Sun, Moon, Check, Search, Clock, GraduationCap, Network, BookOpen, Target } from "lucide-react";
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
    ["/kb", "Sources", "📚"],
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
    const [collapsed, setCollapsed] = useState(() => {
        if (typeof window !== 'undefined') {
            return localStorage.getItem('sidebar-collapsed') === 'true';
        }
        return false;
    });
    const [wsMenuOpen, setWsMenuOpen] = useState(false);

    // D3: Persist collapsed state
    useEffect(() => {
        localStorage.setItem('sidebar-collapsed', String(collapsed));
    }, [collapsed]);

    useEffect(() => {
        const handleGlobalClick = () => {
            if (contextMenuId) {
                setContextMenuId(null);
                setContextMenuPos(null);
            }
            if (wsMenuOpen) setWsMenuOpen(false);
        };
        document.addEventListener("click", handleGlobalClick);
        return () => document.removeEventListener("click", handleGlobalClick);
    }, [contextMenuId]);

    if (!user) {
        return null; // Don't render sidebar on login page
    }

    return (
        <aside className={`global-sidebar${collapsed ? ' collapsed' : ''}`}>
            <div className="sidebar-header">
                <Image src="/colearniTreeLogo.png" alt="CoLearni" width={28} height={28} className="sidebar-logo" />
                <h1 className="brand" style={{ fontSize: "1.25rem", margin: 0 }}>CoLearni</h1>
                <HealthDot />
                <button
                    type="button"
                    className="sidebar-collapse-btn"
                    onClick={() => setCollapsed(!collapsed)}
                    title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                    aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                >
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        {collapsed
                            ? <polyline points="9 18 15 12 9 6" />
                            : <polyline points="15 18 9 12 15 6" />
                        }
                    </svg>
                </button>
            </div>

            <nav className="nav" aria-label="Primary">
                <div className="nav-items-group" style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <Link href="/tutor" className={`nav-link ${pathname === "/tutor" ? "active" : ""}`} title="Tutor">
                        <GraduationCap className="nav-icon" />
                        <span>Tutor</span>
                    </Link>
                    <Link href="/graph" className={`nav-link ${pathname === "/graph" ? "active" : ""}`} title="Graph">
                        <Network className="nav-icon" />
                        <span>Graph</span>
                    </Link>
                    <Link href="/kb" className={`nav-link ${pathname === "/kb" ? "active" : ""}`} title="Sources">
                        <BookOpen className="nav-icon" />
                        <span>Sources</span>
                    </Link>
                </div>
            </nav>

            {/* Collapsed: show just a new-chat icon */}
            {collapsed && (
                <div className="collapsed-new-chat">
                    <button type="button" className="icon-btn" onClick={() => void startNewSession()} title="New chat" aria-label="New chat" style={{ padding: '0.55rem', borderRadius: '0.5rem', width: '100%', display: 'grid', placeItems: 'center' }}>
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                    </button>
                </div>
            )}

            <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", marginTop: "0.5rem" }}>
                {!collapsed && (
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                    <h2 style={{ margin: 0, fontSize: "0.9rem", color: "var(--muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>Recent Chats</h2>
                    <button type="button" className="icon-btn" onClick={() => void startNewSession()} style={{ padding: "0.2rem" }} aria-label="New chat" title="New chat">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
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
                                                setDeleteConfirmId(chat.public_id);
                                            }}
                                        >
                                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                                            Delete
                                        </button>
                                    </div>
                                )}
                            </div>
                            {deleteConfirmId === chat.public_id && (
                                <div className="delete-confirm-bar" style={{ gridColumn: '1 / -1', display: 'flex', alignItems: 'center', gap: '0.35rem', padding: '0.3rem 0.5rem', background: 'var(--surface)', borderRadius: '0.35rem', fontSize: '0.8rem' }}>
                                    <span style={{ flex: 1, color: 'var(--muted)' }}>Delete?</span>
                                    <button
                                        type="button"
                                        className="danger-text"
                                        style={{ padding: '0.15rem 0.5rem', fontSize: '0.78rem' }}
                                        onClick={() => {
                                            void deleteSession(chat.public_id);
                                            setDeleteConfirmId(null);
                                        }}
                                    >
                                        Yes
                                    </button>
                                    <button
                                        type="button"
                                        className="secondary"
                                        style={{ padding: '0.15rem 0.5rem', fontSize: '0.78rem' }}
                                        onClick={() => setDeleteConfirmId(null)}
                                    >
                                        No
                                    </button>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
                )}
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
                    <div className="sidebar-workspace-block" style={{ padding: "0.5rem", display: "flex", alignItems: "center", gap: "0.25rem", position: "relative" }}>
                        <select
                            value={activeWorkspaceId ?? ""}
                            onChange={(event) => {
                                setActiveWorkspaceId(event.target.value);
                            }}
                            aria-label="Select workspace"
                            style={{ flex: 1, fontSize: "0.85rem" }}
                        >
                            {workspaces.map((workspace) => (
                                <option key={workspace.public_id} value={workspace.public_id}>
                                    {workspace.name}
                                </option>
                            ))}
                        </select>
                        <button
                            type="button"
                            className="icon-btn secondary"
                            title="Workspace options"
                            style={{ padding: "0.4rem" }}
                            onClick={(e) => {
                                e.stopPropagation();
                                setWsMenuOpen((prev) => !prev);
                            }}
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <circle cx="12" cy="12" r="1.5"></circle>
                                <circle cx="19" cy="12" r="1.5"></circle>
                                <circle cx="5" cy="12" r="1.5"></circle>
                            </svg>
                        </button>
                        {wsMenuOpen && (
                            <div className="session-context-menu" style={{ position: "absolute", right: 0, bottom: "100%", marginBottom: "4px", zIndex: 100 }} onClick={(e) => e.stopPropagation()}>
                                <button type="button" onClick={() => {
                                    setWsMenuOpen(false);
                                    setNewWorkspaceName("");
                                    setIsCreatingWorkspace(true);
                                }}>
                                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                                    New workspace
                                </button>
                                <button type="button" onClick={() => {
                                    setWsMenuOpen(false);
                                    if (activeWorkspaceId) {
                                        const ws = workspaces.find(w => w.public_id === activeWorkspaceId);
                                        if (ws) {
                                            setRenameWorkspaceName(ws.name);
                                            setRenamingWorkspaceId(ws.public_id);
                                        }
                                    }
                                }}>
                                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                                    Rename
                                </button>
                            </div>
                        )}
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

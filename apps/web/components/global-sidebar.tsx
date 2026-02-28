"use client";

import Image from "next/image";
import { usePathname } from "next/navigation";
import { HealthDot } from "@/components/health-dot";
import { useRequireAuth } from "@/lib/auth";
import { useChatSession } from "@/lib/tutor/chat-session-context";
import { getSidebarFooterMode } from "@/lib/sidebar/footer-state";
import { useState, useEffect } from "react";

import { NavRail } from "@/features/sidebar/components/nav-rail";
import { RecentSessions } from "@/features/sidebar/components/recent-sessions";
import { WorkspaceActions } from "@/features/sidebar/components/workspace-actions";
import { CollapsedFooter } from "@/features/sidebar/components/collapsed-footer";

export function GlobalSidebar() {
    const pathname = usePathname();
    const { user, workspaces, activeWorkspaceId, setActiveWorkspaceId, logout, refreshWorkspaces } = useRequireAuth();
    const chatSession = useChatSession();

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

    useEffect(() => {
        localStorage.setItem('sidebar-collapsed', String(collapsed));
    }, [collapsed]);

    if (!user) return null;

    const activeWs = workspaces.find(w => w.public_id === activeWorkspaceId);
    const wsInitial = activeWs?.name?.charAt(0)?.toUpperCase() || 'W';
    const footerMode = getSidebarFooterMode({ collapsed, isCreatingWorkspace, renamingWorkspaceId });

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

            <NavRail pathname={pathname} />

            <RecentSessions
                collapsed={collapsed}
                pathname={pathname}
                sessions={chatSession.sessions}
                activeSessionId={chatSession.activeSessionId}
                sessionsLoading={chatSession.sessionsLoading}
                sessionsError={chatSession.sessionsError}
                startNewSession={chatSession.startNewSession}
                setActiveSessionId={chatSession.setActiveSessionId}
                deleteSession={chatSession.deleteSession}
                renameSession={chatSession.renameSession}
                syncUrl={chatSession.syncUrl}
            />

            <div className="sidebar-footer" style={{ borderTop: "none", paddingTop: 0 }}>
                {footerMode !== "collapsed" && (
                    <WorkspaceActions
                        workspaces={workspaces}
                        activeWorkspaceId={activeWorkspaceId}
                        setActiveWorkspaceId={setActiveWorkspaceId}
                        refreshWorkspaces={refreshWorkspaces}
                        user={user}
                        logout={logout}
                        footerMode={footerMode}
                        isCreatingWorkspace={isCreatingWorkspace}
                        setIsCreatingWorkspace={setIsCreatingWorkspace}
                        newWorkspaceName={newWorkspaceName}
                        setNewWorkspaceName={setNewWorkspaceName}
                        renamingWorkspaceId={renamingWorkspaceId}
                        setRenamingWorkspaceId={setRenamingWorkspaceId}
                        renameWorkspaceName={renameWorkspaceName}
                        setRenameWorkspaceName={setRenameWorkspaceName}
                    />
                )}
                {footerMode === "collapsed" && (
                    <CollapsedFooter
                        workspaces={workspaces}
                        activeWorkspaceId={activeWorkspaceId}
                        activeWsInitial={wsInitial}
                        activeWsName={activeWs?.name || "Workspace"}
                        setActiveWorkspaceId={setActiveWorkspaceId}
                        setCollapsed={setCollapsed}
                        setIsCreatingWorkspace={setIsCreatingWorkspace}
                        setNewWorkspaceName={setNewWorkspaceName}
                        setRenamingWorkspaceId={setRenamingWorkspaceId}
                        setRenameWorkspaceName={setRenameWorkspaceName}
                        logout={logout}
                    />
                )}
            </div>
        </aside>
    );
}

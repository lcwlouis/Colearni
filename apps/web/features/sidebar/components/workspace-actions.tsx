"use client";

import { useState, useEffect } from "react";
import { Check, ChevronDown } from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { ThemeToggle } from "@/components/theme-toggle";

interface Workspace {
  public_id: string;
  name: string;
}

interface WorkspaceActionsProps {
  workspaces: Workspace[];
  activeWorkspaceId: string | null;
  setActiveWorkspaceId: (id: string) => void;
  refreshWorkspaces: () => Promise<void>;
  user: { display_name?: string | null; email: string };
  logout: () => void;
  footerMode: "expanded" | "create-workspace" | "rename-workspace";
  isCreatingWorkspace: boolean;
  setIsCreatingWorkspace: (v: boolean) => void;
  newWorkspaceName: string;
  setNewWorkspaceName: (v: string) => void;
  renamingWorkspaceId: string | null;
  setRenamingWorkspaceId: (v: string | null) => void;
  renameWorkspaceName: string;
  setRenameWorkspaceName: (v: string) => void;
}

export function WorkspaceActions({
  workspaces,
  activeWorkspaceId,
  setActiveWorkspaceId,
  refreshWorkspaces,
  user,
  logout,
  footerMode,
  isCreatingWorkspace,
  setIsCreatingWorkspace,
  newWorkspaceName,
  setNewWorkspaceName,
  renamingWorkspaceId,
  setRenamingWorkspaceId,
  renameWorkspaceName,
  setRenameWorkspaceName,
}: WorkspaceActionsProps) {
  const [wsMenuOpen, setWsMenuOpen] = useState(false);

  useEffect(() => {
    const handleGlobalClick = () => {
      if (wsMenuOpen) setWsMenuOpen(false);
    };
    document.addEventListener("click", handleGlobalClick);
    return () => document.removeEventListener("click", handleGlobalClick);
  }, [wsMenuOpen]);

  return (
    <>
      {footerMode === "create-workspace" && (
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
      )}

      {footerMode === "rename-workspace" && (
        <form onSubmit={async (e) => {
          e.preventDefault();
          const workspaceId = renamingWorkspaceId;
          if (workspaceId && renameWorkspaceName.trim()) {
            try {
              await apiClient.updateWorkspace(workspaceId, { name: renameWorkspaceName.trim() });
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
      )}

      {footerMode === "expanded" && (
        <>
          <div className="sidebar-workspace-block" style={{ padding: "0.5rem", alignItems: "center", gap: "0.25rem", position: "relative" }}>
            <button
              type="button"
              className="ws-selector-btn"
              onClick={(e) => {
                e.stopPropagation();
                setWsMenuOpen((prev) => !prev);
              }}
            >
              <span className="collapsed-ws-initial-small">
                {workspaces.find(w => w.public_id === activeWorkspaceId)?.name.charAt(0).toUpperCase() || "W"}
              </span>
              <span className="ws-selector-name">
                {workspaces.find(w => w.public_id === activeWorkspaceId)?.name || "Workspace"}
              </span>
              <ChevronDown size={14} style={{ flexShrink: 0, color: "var(--muted)" }} />
            </button>
            {wsMenuOpen && (
              <div className="collapsed-ws-popover" onClick={(e) => e.stopPropagation()}>
                <div className="collapsed-ws-popover-header">Workspaces</div>
                {workspaces.map((ws) => (
                  <button
                    key={ws.public_id}
                    type="button"
                    className={`collapsed-ws-item${ws.public_id === activeWorkspaceId ? " active" : ""}`}
                    onClick={() => {
                      setActiveWorkspaceId(ws.public_id);
                      setWsMenuOpen(false);
                    }}
                  >
                    <span className="collapsed-ws-initial-small">{ws.name.charAt(0).toUpperCase()}</span>
                    <span>{ws.name}</span>
                    {ws.public_id === activeWorkspaceId && <Check size={14} />}
                  </button>
                ))}
                <div className="collapsed-ws-divider" />
                <button
                  type="button"
                  className="collapsed-ws-action"
                  onClick={() => {
                    setWsMenuOpen(false);
                    setNewWorkspaceName("");
                    setIsCreatingWorkspace(true);
                  }}
                >
                  New workspace
                </button>
                <button
                  type="button"
                  className="collapsed-ws-action"
                  onClick={() => {
                    setWsMenuOpen(false);
                    if (activeWorkspaceId) {
                      const ws = workspaces.find(w => w.public_id === activeWorkspaceId);
                      if (ws) {
                        setRenameWorkspaceName(ws.name);
                        setRenamingWorkspaceId(ws.public_id);
                      }
                    }
                  }}
                >
                  Rename
                </button>
                <button
                  type="button"
                  className="collapsed-ws-action"
                  style={{ color: "var(--error, #e53e3e)" }}
                  onClick={async () => {
                    setWsMenuOpen(false);
                    if (!activeWorkspaceId) return;
                    const ws = workspaces.find(w => w.public_id === activeWorkspaceId);
                    if (!ws) return;
                    if (!window.confirm(`Delete workspace "${ws.name}"? This cannot be undone.`)) return;
                    try {
                      await apiClient.deleteWorkspace(activeWorkspaceId);
                      await refreshWorkspaces();
                      const remaining = workspaces.filter(w => w.public_id !== activeWorkspaceId);
                      if (remaining.length > 0) {
                        setActiveWorkspaceId(remaining[0].public_id);
                      }
                    } catch (err) {
                      console.error(err);
                    }
                  }}
                >
                  Delete workspace
                </button>
              </div>
            )}
          </div>
          <div className="sidebar-profile-block" style={{ flexDirection: "row", alignItems: "center", gap: "0.5rem", padding: "0.5rem 0.6rem" }}>
            <div style={{ flex: 1, minWidth: 0, overflow: "hidden" }}>
              <p className="sidebar-user-name" style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", fontSize: "0.82rem" }}>{user.display_name || user.email}</p>
            </div>
            <div className="sidebar-profile-actions">
              <ThemeToggle />
              <button type="button" className="secondary icon-btn" onClick={logout} title="Logout">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></svg>
              </button>
            </div>
          </div>
        </>
      )}
    </>
  );
}

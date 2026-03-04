"use client";

import { useState, useEffect } from "react";
import { Check, LogOut } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";

interface Workspace {
  public_id: string;
  name: string;
}

interface CollapsedFooterProps {
  workspaces: Workspace[];
  activeWorkspaceId: string | null;
  activeWsInitial: string;
  activeWsName: string;
  setActiveWorkspaceId: (id: string) => void;
  setCollapsed: (v: boolean) => void;
  setIsCreatingWorkspace: (v: boolean) => void;
  setNewWorkspaceName: (v: string) => void;
  setRenamingWorkspaceId: (v: string | null) => void;
  setRenameWorkspaceName: (v: string) => void;
  logout: () => void;
}

export function CollapsedFooter({
  workspaces,
  activeWorkspaceId,
  activeWsInitial,
  activeWsName,
  setActiveWorkspaceId,
  setCollapsed,
  setIsCreatingWorkspace,
  setNewWorkspaceName,
  setRenamingWorkspaceId,
  setRenameWorkspaceName,
  logout,
}: CollapsedFooterProps) {
  const [collapsedWsOpen, setCollapsedWsOpen] = useState(false);

  useEffect(() => {
    const handleGlobalClick = () => {
      if (collapsedWsOpen) setCollapsedWsOpen(false);
    };
    document.addEventListener("click", handleGlobalClick);
    return () => document.removeEventListener("click", handleGlobalClick);
  }, [collapsedWsOpen]);

  return (
    <div className="collapsed-bottom-controls">
      <div style={{ position: "relative" }}>
        <button
          type="button"
          className="collapsed-icon-btn"
          title={activeWsName || "Workspace"}
          aria-label="Switch workspace"
          onClick={(e) => {
            e.stopPropagation();
            setCollapsedWsOpen((prev) => !prev);
          }}
        >
          <span className="collapsed-ws-initial">{activeWsInitial}</span>
        </button>
        {collapsedWsOpen && (
          <div className="collapsed-ws-popover" onClick={(e) => e.stopPropagation()}>
            <div className="collapsed-ws-popover-header">Workspaces</div>
            {workspaces.map((ws) => (
              <button
                key={ws.public_id}
                type="button"
                className={`collapsed-ws-item${ws.public_id === activeWorkspaceId ? " active" : ""}`}
                onClick={() => {
                  setActiveWorkspaceId(ws.public_id);
                  setCollapsedWsOpen(false);
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
                setCollapsedWsOpen(false);
                setCollapsed(false);
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
                setCollapsedWsOpen(false);
                setCollapsed(false);
                if (activeWorkspaceId) {
                  const ws = workspaces.find((w) => w.public_id === activeWorkspaceId);
                  if (ws) {
                    setRenameWorkspaceName(ws.name);
                    setRenamingWorkspaceId(ws.public_id);
                  }
                }
              }}
            >
              Rename
            </button>
          </div>
        )}
      </div>
      <ThemeToggle />
      <button type="button" className="collapsed-icon-btn" onClick={logout} title="Logout" aria-label="Logout">
        <LogOut size={18} />
      </button>
    </div>
  );
}

export type SidebarFooterMode =
  | "create-workspace"
  | "rename-workspace"
  | "collapsed"
  | "expanded";

export function getSidebarFooterMode(params: {
  collapsed: boolean;
  isCreatingWorkspace: boolean;
  renamingWorkspaceId: string | null;
}): SidebarFooterMode {
  const { collapsed, isCreatingWorkspace, renamingWorkspaceId } = params;

  if (isCreatingWorkspace) {
    return "create-workspace";
  }

  if (renamingWorkspaceId) {
    return "rename-workspace";
  }

  return collapsed ? "collapsed" : "expanded";
}

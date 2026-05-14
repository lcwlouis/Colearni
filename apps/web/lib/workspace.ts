import { createWorkspace } from "@/lib/api";

export const WORKSPACE_STORAGE_KEY = "colearni_workspace_id";

export async function ensureWorkspaceId(): Promise<string> {
  const existing = window.localStorage.getItem(WORKSPACE_STORAGE_KEY);
  if (existing) {
    return existing;
  }
  const workspace = await createWorkspace("My Workspace");
  window.localStorage.setItem(WORKSPACE_STORAGE_KEY, workspace.id);
  return workspace.id;
}

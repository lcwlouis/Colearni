"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import type { UserPublic, WorkspaceSummary } from "@/lib/api/types";
import { apiClient } from "@/lib/api/client";

const SESSION_TOKEN_KEY = "colearni_session_token";
const WORKSPACE_KEY = "colearni_active_workspace";

interface AuthContextValue {
  user: UserPublic | null;
  sessionToken: string | null;
  workspaces: WorkspaceSummary[];
  activeWorkspaceId: string | null;
  isLoading: boolean;
  login: (token: string, user: UserPublic) => void;
  logout: () => void;
  setActiveWorkspaceId: (id: string) => void;
  refreshWorkspaces: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  sessionToken: null,
  workspaces: [],
  activeWorkspaceId: null,
  isLoading: true,
  login: () => {},
  logout: () => {},
  setActiveWorkspaceId: () => {},
  refreshWorkspaces: async () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserPublic | null>(null);
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [activeWorkspaceId, setActiveWorkspaceIdRaw] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const setActiveWorkspaceId = useCallback((id: string) => {
    setActiveWorkspaceIdRaw(id);
    try { localStorage.setItem(WORKSPACE_KEY, id); } catch { /* quota */ }
  }, []);

  const refreshWorkspaces = useCallback(async () => {
    try {
      const res = await apiClient.listWorkspaces();
      let list = res.workspaces;
      if (list.length === 0) {
        // Auto-create a default workspace for new users
        const created = await apiClient.createWorkspace({ name: "My Workspace" });
        list = [created];
      }
      setWorkspaces(list);
      if (list.length > 0 && activeWorkspaceId === null) {
        const stored = localStorage.getItem(WORKSPACE_KEY);
        const match = stored && list.find((w) => w.public_id === stored);
        setActiveWorkspaceId(match ? stored : list[0].public_id);
      }
    } catch {
      setWorkspaces([]);
    }
  }, [activeWorkspaceId, setActiveWorkspaceId]);

  // Restore session on mount
  useEffect(() => {
    const stored = localStorage.getItem(SESSION_TOKEN_KEY);
    if (stored) {
      setSessionToken(stored);
      apiClient
        .getMe()
        .then((u) => {
          setUser(u);
          return apiClient.listWorkspaces();
        })
        .then(async (res) => {
          let list = res.workspaces;
          if (list.length === 0) {
            const created = await apiClient.createWorkspace({ name: "My Workspace" });
            list = [created];
          }
          setWorkspaces(list);
          if (list.length > 0) {
            const storedWs = localStorage.getItem(WORKSPACE_KEY);
            const match = storedWs && list.find((w) => w.public_id === storedWs);
            setActiveWorkspaceId(match ? storedWs : list[0].public_id);
          }
        })
        .catch(() => {
          localStorage.removeItem(SESSION_TOKEN_KEY);
          setSessionToken(null);
          setUser(null);
        })
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = useCallback(
    (token: string, userRecord: UserPublic) => {
      localStorage.setItem(SESSION_TOKEN_KEY, token);
      setSessionToken(token);
      setUser(userRecord);
      refreshWorkspaces();
    },
    [refreshWorkspaces],
  );

  const logout = useCallback(() => {
    localStorage.removeItem(SESSION_TOKEN_KEY);
    localStorage.removeItem(WORKSPACE_KEY);
    setSessionToken(null);
    setUser(null);
    setWorkspaces([]);
    setActiveWorkspaceIdRaw(null);
    apiClient.logout().catch(() => {});
    // Redirect to login page
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        sessionToken,
        workspaces,
        activeWorkspaceId,
        isLoading,
        login,
        logout,
        setActiveWorkspaceId,
        refreshWorkspaces,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

"use client";

import {
  createContext,
  useContext,
  useReducer,
  useEffect,
  useCallback,
  type Dispatch,
  type ReactNode,
} from "react";
import { createElement } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface GraphSettings {
  showLabels: boolean;
  labelDensity: number;
  showEdgeLabels: boolean;
  edgeCurvature: number;
  defaultLayout: string;
  animationDuration: number;
  highlightNeighbors: boolean;
  showLegend: boolean;
  showStatusBar: boolean;
}

type Action =
  | { type: "set"; payload: Partial<GraphSettings> }
  | { type: "reset" };

// ---------------------------------------------------------------------------
// Defaults
// ---------------------------------------------------------------------------

export const DEFAULT_GRAPH_SETTINGS: GraphSettings = {
  showLabels: true,
  labelDensity: 1,
  showEdgeLabels: false,
  edgeCurvature: 0.25,
  defaultLayout: "forceatlas2",
  animationDuration: 400,
  highlightNeighbors: true,
  showLegend: true,
  showStatusBar: true,
};

const STORAGE_KEY = "colearni-graph-settings";

// ---------------------------------------------------------------------------
// Persistence helpers
// ---------------------------------------------------------------------------

function loadSettings(): GraphSettings {
  if (typeof window === "undefined") return DEFAULT_GRAPH_SETTINGS;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_GRAPH_SETTINGS;
    return { ...DEFAULT_GRAPH_SETTINGS, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_GRAPH_SETTINGS;
  }
}

function saveSettings(s: GraphSettings) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  } catch {
    // quota exceeded — silently ignore
  }
}

// ---------------------------------------------------------------------------
// Reducer
// ---------------------------------------------------------------------------

function reducer(state: GraphSettings, action: Action): GraphSettings {
  switch (action.type) {
    case "set": {
      const next = { ...state, ...action.payload };
      saveSettings(next);
      return next;
    }
    case "reset": {
      saveSettings(DEFAULT_GRAPH_SETTINGS);
      return { ...DEFAULT_GRAPH_SETTINGS };
    }
    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const SettingsCtx = createContext<GraphSettings>(DEFAULT_GRAPH_SETTINGS);
const DispatchCtx = createContext<Dispatch<Action>>(() => {});

export function GraphSettingsProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, DEFAULT_GRAPH_SETTINGS, loadSettings);

  // Sync across tabs
  useEffect(() => {
    const handler = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY && e.newValue) {
        try {
          dispatch({ type: "set", payload: JSON.parse(e.newValue) });
        } catch { /* ignore */ }
      }
    };
    window.addEventListener("storage", handler);
    return () => window.removeEventListener("storage", handler);
  }, []);

  return createElement(
    SettingsCtx.Provider,
    { value: state },
    createElement(DispatchCtx.Provider, { value: dispatch }, children),
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useGraphSettings() {
  const settings = useContext(SettingsCtx);
  const dispatch = useContext(DispatchCtx);
  const set = useCallback(
    (partial: Partial<GraphSettings>) => dispatch({ type: "set", payload: partial }),
    [dispatch],
  );
  const reset = useCallback(() => dispatch({ type: "reset" }), [dispatch]);
  return { ...settings, set, reset };
}

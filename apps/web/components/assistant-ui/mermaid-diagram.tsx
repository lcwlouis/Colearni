"use client";

import { useAuiState } from "@assistant-ui/react";
import type { SyntaxHighlighterProps } from "@assistant-ui/react-markdown";
import mermaid from "mermaid";
import { useEffect, useRef, type FC } from "react";

mermaid.initialize({
  startOnLoad: false,
  securityLevel: "strict",
  theme: "neutral",
});

export const MermaidDiagram: FC<SyntaxHighlighterProps> = ({ code }) => {
  const ref = useRef<HTMLPreElement>(null);
  const isComplete = useAuiState((state) => {
    if (state.part.type !== "text") {
      return true;
    }

    const codeIndex = state.part.text.indexOf(code);
    if (codeIndex === -1) {
      return false;
    }

    const afterCode = state.part.text.slice(codeIndex + code.length);
    return /^```|^\n```/.test(afterCode);
  });

  useEffect(() => {
    if (!isComplete || !ref.current) {
      return;
    }

    let active = true;

    void mermaid
      .render(`tutor-mermaid-${Math.random().toString(36).slice(2)}`, code)
      .then((result) => {
        if (!active || !ref.current) {
          return;
        }
        ref.current.innerHTML = result.svg;
        result.bindFunctions?.(ref.current);
      })
      .catch(() => {
        if (!active || !ref.current) {
          return;
        }
        ref.current.textContent = code;
      });

    return () => {
      active = false;
    };
  }, [code, isComplete]);

  return (
    <pre
      ref={ref}
      aria-label="Mermaid diagram"
      className="tutor-mermaid overflow-x-auto rounded-b-lg border border-t-0 border-slate-200 bg-white p-3 text-center text-sm text-slate-500 [&_svg]:mx-auto [&_svg]:h-auto [&_svg]:max-w-full"
    >
      Drawing diagram...
    </pre>
  );
};

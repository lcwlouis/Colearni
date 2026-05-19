import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createContext, useContext, type ReactNode } from "react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { TutorPanel } from "@/app/trails/[id]/components/TutorPanel";
import type { ConceptNode, ConversationHistoryResponse, SourceRecord } from "@/lib/types";

let runtimeOptions: {
  onMode: (mode: "socratic" | "direct" | "repair" | "quiz_prompt" | "explore") => void;
  onError?: (message: string) => void;
} | null = null;
const sendMock = vi.fn();
const MockPartContext = createContext<MockPart | null>(null);

vi.mock("@/lib/api", () => ({
  getConversation: vi.fn(),
}));

vi.mock("@/lib/tutor-runtime", () => ({
  useTutorRuntime: vi.fn((options) => {
    runtimeOptions = options;
    return {};
  }),
}));

vi.mock("@/components/assistant-ui/markdown-text", async () => {
  const { default: ReactMarkdown } = await import("react-markdown");
  const { default: rehypeKatex } = await import("rehype-katex");
  const { default: remarkGfm } = await import("remark-gfm");
  const { default: remarkMath } = await import("remark-math");

  return {
    MarkdownText: () => {
      const part = useContext(MockPartContext);
      if (!part || (part.type !== "text" && part.type !== "reasoning")) {
        return null;
      }

      return (
        <div>
          <ReactMarkdown
            rehypePlugins={[rehypeKatex]}
            remarkPlugins={[remarkGfm, remarkMath]}
            components={{
              pre: ({ children }) => {
                const text = readNodeText(children);
                if (text.includes("flowchart") || text.includes("graph ")) {
                  return <div aria-label="Mermaid diagram">{text}</div>;
                }
                return <pre>{children}</pre>;
              },
            }}
          >
            {part.text}
          </ReactMarkdown>
        </div>
      );
    },
  };
});

vi.mock("mermaid", () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn(async (_id: string, chart: string) => ({
      svg: `<svg xmlns="http://www.w3.org/2000/svg"><text>${chart.trim()}</text></svg>`,
    })),
  },
}));

vi.mock("@assistant-ui/react", () => ({
  AssistantRuntimeProvider: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  ThreadPrimitive: {
    Root: ({ children, className }: { children: ReactNode; className?: string }) => (
      <div className={className}>{children}</div>
    ),
    Viewport: ({ children, className }: { children: ReactNode; className?: string }) => (
      <div className={className}>{children}</div>
    ),
    Messages: ({ children }: { children: (value: { message: MockMessage }) => ReactNode }) => (
      <div>
        {mockMessages.map((message) => (
          <div key={message.id}>{children({ message })}</div>
        ))}
      </div>
    ),
  },
  MessagePrimitive: {
    Root: ({ children, className }: { children: ReactNode; className?: string }) => (
      <div className={className}>{children}</div>
    ),
    GroupedParts: ({ children }: { children: (value: { part: MockPart; children: ReactNode }) => ReactNode }) => (
      <>
        {mockGroupedParts().map((entry, index) => (
          <PartScope key={index} part={entry.part}>
            {children(entry)}
          </PartScope>
        ))}
      </>
    ),
  },
  ComposerPrimitive: {
    Root: ({ children, className }: { children: ReactNode; className?: string }) => (
      <form className={className}>{children}</form>
    ),
    Input: ({ submitMode: _submitMode, ...props }: Record<string, unknown>) => (
      <textarea {...props} />
    ),
    Send: ({ children, className }: { children: ReactNode; className?: string }) => (
      <button type="button" className={className} onClick={sendMock}>
        {children}
      </button>
    ),
  },
  useThread: vi.fn((selector) =>
    selector({ messages: mockMessages, isRunning: mockRunning }),
  ),
  useScrollLock: vi.fn(() => vi.fn()),
}));

const getConversationMock = vi.mocked(await import("@/lib/api")).getConversation;

interface MockMessage {
  id: string;
  role: "user" | "assistant";
  content: Array<{ type: "text" | "reasoning"; text: string }>;
  status?: { type: "running" | "complete" };
}

type MockPart = { type: "group-reasoning"; indices: number[]; status: { type: "running" | "complete" } } | MockMessage["content"][number];

let mockMessages: MockMessage[] = [];
let mockRunning = false;

describe("TutorPanel", () => {
  beforeEach(() => {
    runtimeOptions = null;
    mockMessages = [];
    mockRunning = false;
    sendMock.mockClear();
    getConversationMock.mockResolvedValue(emptyHistory);
  });

  test("renders concept title and context", async () => {
    renderPanel();

    await screen.findByText("Mode: waiting");
    expect(screen.getByText("Vectors")).toBeInTheDocument();
    expect(screen.getByText("Level: topic")).toBeInTheDocument();
    expect(screen.getByText("Bloom: understand")).toBeInTheDocument();
  });

  test("mode badge updates when runtime reports mode", async () => {
    renderPanel();
    await screen.findByText("Mode: waiting");

    act(() => {
      runtimeOptions?.onMode("direct");
    });

    expect(await screen.findByText("Mode: direct")).toBeInTheDocument();
  });

  test("token chunks appear in chat UI", async () => {
    mockMessages = [assistantMessage("Think about vectors.")];

    renderPanel();

    expect(await screen.findByText("Think about vectors.")).toBeInTheDocument();
  });

  test("reasoning traces can be expanded when assistant reasoning exists", async () => {
    mockMessages = [assistantMessage("Final answer.", "Private reasoning trace.")];

    renderPanel();

    await userEvent.click(await screen.findByRole("button", { name: "Show reasoning" }));

    expect(await screen.findByText("Private reasoning trace.")).toBeInTheDocument();
    expect(screen.getByText("Final answer.")).toBeInTheDocument();
  });

  test("renders LaTeX math in assistant messages", async () => {
    mockMessages = [assistantMessage("Use $a \\cdot b$ for the dot product.")];

    const { container } = renderPanel();

    await waitFor(() => {
      expect(container.querySelector(".katex")).not.toBeNull();
    });
  });

  test("renders Mermaid diagrams from fenced code blocks", async () => {
    mockMessages = [assistantMessage("```mermaid\nflowchart LR\nA-->B\n```")];

    renderPanel();

    expect(await screen.findByLabelText("Mermaid diagram")).toBeInTheDocument();
  });

  test("error state renders when chat stream fails", async () => {
    renderPanel();
    await screen.findByText("Mode: waiting");

    act(() => {
      runtimeOptions?.onError?.("Generation failed");
    });

    expect(await screen.findByText("Generation failed")).toBeInTheDocument();
  });

  test("quiz prompt placeholder appears in quiz_prompt mode", async () => {
    renderPanel();
    await screen.findByText("Mode: waiting");

    act(() => {
      runtimeOptions?.onMode("quiz_prompt");
    });

    expect(
      await screen.findByText("Ready to level up? Quiz cards arrive in Phase 5."),
    ).toBeInTheDocument();
  });

  test("source chips render only when source metadata exists", async () => {
    const { rerender } = renderPanel();

    await screen.findByText("Vectors");
    expect(screen.queryByText("Sources available")).not.toBeInTheDocument();

    rerender(
      <TutorPanel
        workspaceId="workspace-1"
        trailId="trail-1"
        concept={concept}
        sources={[source]}
      />,
    );

    expect(await screen.findByText("Sources available")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Linear Algebra Notes" })).toHaveAttribute(
      "href",
      "https://example.com/linear-algebra",
    );
  });

  test("loads conversation history before showing chat", async () => {
    getConversationMock.mockResolvedValue({
      conversation_id: "conversation-1",
      messages: [
        {
          id: "assistant-1",
          role: "assistant",
          content: "Previously explained.",
          reasoning: "Why this answer was chosen.",
          mode: "repair",
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
    });

    renderPanel();

    expect(screen.getByText("Loading conversation...")).toBeInTheDocument();
    await waitFor(() => {
      expect(getConversationMock).toHaveBeenCalledWith("workspace-1", "trail-1", "concept-1");
    });
    expect(await screen.findByText("Mode: repair")).toBeInTheDocument();
  });

  test("send button is present and wired through assistant-ui composer mock", async () => {
    renderPanel();

    await userEvent.click(await screen.findByRole("button", { name: "Send" }));

    expect(sendMock).toHaveBeenCalledTimes(1);
  });
});

function renderPanel(sources: SourceRecord[] = []) {
  return render(
    <TutorPanel
      workspaceId="workspace-1"
      trailId="trail-1"
      concept={concept}
      sources={sources}
    />,
  );
}

function assistantMessage(text: string, reasoning?: string): MockMessage {
  return {
    id: `assistant-${text}`,
    role: "assistant",
    content: [
      ...(reasoning ? [{ type: "reasoning" as const, text: reasoning }] : []),
      { type: "text", text },
    ],
    status: { type: "complete" },
  };
}

function mockGroupedParts() {
  const message = mockMessages[0];
  if (!message) {
    return [];
  }
  const reasoningParts = message.content.filter((part) => part.type === "reasoning");
  const textParts = message.content.filter((part) => part.type === "text");
  const entries: Array<{ part: MockPart; children: ReactNode }> = [];

  if (reasoningParts.length > 0) {
    entries.push({
      part: {
        type: "group-reasoning",
        indices: reasoningParts.map((_, index) => index),
        status: message.status ?? { type: "complete" },
      },
      children: <>{reasoningParts.map((part, index) => <div key={index}>{part.text}</div>)}</>,
    });
  }

  for (const part of textParts) {
    entries.push({ part, children: null });
  }

  return entries;
}

function PartScope({ part, children }: { part: MockPart; children: ReactNode }) {
  return <MockPartContext.Provider value={part}>{children}</MockPartContext.Provider>;
}

function readNodeText(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") {
    return String(node);
  }

  if (Array.isArray(node)) {
    return node.map(readNodeText).join("");
  }

  if (node && typeof node === "object" && "props" in node) {
    return readNodeText((node as { props?: { children?: ReactNode } }).props?.children ?? null);
  }

  return "";
}

const emptyHistory: ConversationHistoryResponse = {
  conversation_id: null,
  messages: [],
};

const concept: ConceptNode = {
  id: "concept-1",
  trail_id: "trail-1",
  slug: "vectors",
  title: "Vectors",
  node_type: "concept",
  concept_level: "topic",
  difficulty: "beginner",
  bloom_level: "understand",
  mastery_check_labels: ["explain vectors"],
  metadata_json: {},
};

const source: SourceRecord = {
  id: "source-1",
  workspace_id: "workspace-1",
  title: "Linear Algebra Notes",
  url: "https://example.com/linear-algebra",
  origin: "research_agent",
  access: "public",
  license: null,
  include_on_public_export: true,
  metadata_json: {},
};

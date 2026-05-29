import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  createContext,
  useContext,
  type MouseEventHandler,
  type ReactNode,
} from "react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { TutorPanel } from "@/app/trails/[id]/components/TutorPanel";
import type {
  ConceptNode,
  ConversationHistoryResponse,
  SourceRecord,
} from "@/lib/types";

let runtimeOptions: {
  onMode: (
    mode:
      | "socratic"
      | "direct"
      | "repair"
      | "quiz_prompt"
      | "explore"
      | "free_explore",
  ) => void;
  onStatus?: (status: string | null) => void;
  onError?: (message: string) => void;
} | null = null;
const sendMock = vi.fn();
const reloadMock = vi.fn();
const editBeginMock = vi.fn();
const editSetTextMock = vi.fn();
const editSetRunConfigMock = vi.fn();
const editSendMock = vi.fn();
const MockPartContext = createContext<MockPart | null>(null);
const MockMessageContext = createContext<MockMessage | null>(null);

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
  AssistantRuntimeProvider: ({ children }: { children: ReactNode }) => (
    <div>{children}</div>
  ),
  ThreadPrimitive: {
    Root: ({
      children,
      className,
    }: {
      children: ReactNode;
      className?: string;
    }) => <div className={className}>{children}</div>,
    Viewport: ({
      children,
      className,
    }: {
      children: ReactNode;
      className?: string;
    }) => <div className={className}>{children}</div>,
    Messages: ({
      children,
    }: {
      children: (value: { message: MockMessage }) => ReactNode;
    }) => (
      <div>
        {mockMessages.map((message, index) => {
          const messageWithPosition = {
            ...message,
            index,
            isLast: index === mockMessages.length - 1,
          };
          return (
            <MockMessageContext.Provider
              key={message.id}
              value={messageWithPosition}
            >
              <div>{children({ message: messageWithPosition })}</div>
            </MockMessageContext.Provider>
          );
        })}
      </div>
    ),
    ScrollToBottom: ({
      children,
      className,
    }: {
      children: ReactNode;
      className?: string;
    }) => (
      <button type="button" className={className}>
        {children}
      </button>
    ),
    ViewportFooter: ({
      children,
      className,
    }: {
      children: ReactNode;
      className?: string;
    }) => <div className={className}>{children}</div>,
    Suggestion: ({
      children,
      className,
    }: {
      children: ReactNode;
      className?: string;
    }) => (
      <button type="button" className={className}>
        {children}
      </button>
    ),
  },
  MessagePrimitive: {
    Root: ({
      children,
      className,
    }: {
      children: ReactNode;
      className?: string;
    }) => <div className={className}>{children}</div>,
    GroupedParts: ({
      children,
    }: {
      children: (value: { part: MockPart; children: ReactNode }) => ReactNode;
    }) => {
      const message = useContext(MockMessageContext) ?? mockMessages[0];
      if (!message) {
        return null;
      }
      const reasoningParts = message.content.filter(
        (part) =>
          part.type === "reasoning" ||
          (part.type === "data" &&
            [
              "tutor-status",
              "tutor-thinking",
              "tutor-tool-call",
              "tutor-tool-result",
            ].includes(part.name)),
      );
      const textParts = message.content.filter((part) => part.type === "text");
      const rendered: ReactNode[] = [];

      if (reasoningParts.length > 0) {
        const groupPart: MockPart = {
          type: "group-chain-of-thought",
          status: message.status ?? { type: "complete" },
        };
        const groupChildren = (
          <>
            {reasoningParts.map((part, index) => (
              <PartScope key={`reasoning-${index}`} part={part}>
                {children({ part, children: null })}
              </PartScope>
            ))}
          </>
        );
        rendered.push(
          <PartScope key="reasoning-group" part={groupPart}>
            {children({ part: groupPart, children: groupChildren })}
          </PartScope>,
        );
      }

      textParts.forEach((part, index) => {
        rendered.push(
          <PartScope key={`text-${index}`} part={part}>
            {children({ part, children: null })}
          </PartScope>,
        );
      });

      return <>{rendered}</>;
    },
  },
  ComposerPrimitive: {
    Root: ({
      children,
      className,
    }: {
      children: ReactNode;
      className?: string;
    }) => <form className={className}>{children}</form>,
    Input: ({ submitMode: _submitMode, ...props }: Record<string, unknown>) => (
      <textarea {...props} />
    ),
    Send: ({
      children,
      className,
      ...props
    }: {
      children: ReactNode;
      className?: string;
      [key: string]: unknown;
    }) => (
      <button type="button" className={className} onClick={sendMock} {...props}>
        {children}
      </button>
    ),
    Cancel: ({
      children,
      className,
    }: {
      children: ReactNode;
      className?: string;
    }) => (
      <button type="button" className={className}>
        {children}
      </button>
    ),
  },
  ActionBarPrimitive: {
    Root: ({
      children,
      className,
    }: {
      children: ReactNode;
      className?: string;
    }) => <div className={className}>{children}</div>,
    Copy: ({ children, className, ...props }: ActionButtonMockProps) => (
      <button type="button" className={className} {...props}>
        {children}
      </button>
    ),
    Reload: ({ children, className, ...props }: ActionButtonMockProps) => (
      <button type="button" className={className} {...props}>
        {children}
      </button>
    ),
    Edit: ({ children, className, ...props }: ActionButtonMockProps) => (
      <button type="button" className={className} {...props}>
        {children}
      </button>
    ),
  },
  useMessageRuntime: vi.fn(() => ({
    reload: reloadMock,
    composer: {
      beginEdit: editBeginMock,
      setText: editSetTextMock,
      setRunConfig: editSetRunConfigMock,
      send: editSendMock,
    },
  })),
  useThreadRuntime: vi.fn(() => ({
    getState: () => ({
      messages: mockMessages.map((message, index) => ({
        ...message,
        index,
        isLast: index === mockMessages.length - 1,
      })),
    }),
  })),
  useThread: vi.fn((selector) =>
    selector({
      messages: mockMessages.map((message, index) => ({
        ...message,
        index,
        isLast: index === mockMessages.length - 1,
      })),
      isRunning: mockRunning,
    }),
  ),
  useScrollLock: vi.fn(() => vi.fn()),
}));

const getConversationMock = vi.mocked(
  await import("@/lib/api"),
).getConversation;

interface MockMessage {
  id: string;
  role: "user" | "assistant";
  content: Array<
    | { type: "text" | "reasoning"; text: string }
    | { type: "data"; name: string; data: Record<string, unknown> }
  >;
  status?: { type: "running" | "complete" };
  index?: number;
  isLast?: boolean;
}

interface ActionButtonMockProps {
  children: ReactNode;
  className?: string;
  onClick?: MouseEventHandler<HTMLButtonElement>;
  "aria-label"?: string;
  title?: string;
}

type MockPart =
  | { type: "group-chain-of-thought"; status: { type: "running" | "complete" } }
  | { type: "group-steps"; status: { type: "running" | "complete" } }
  | { type: "group-reasoning"; status: { type: "running" | "complete" } }
  | MockMessage["content"][number];

let mockMessages: MockMessage[] = [];
let mockRunning = false;

describe("TutorPanel", () => {
  beforeEach(() => {
    window.localStorage.clear();
    runtimeOptions = null;
    mockMessages = [];
    mockRunning = false;
    sendMock.mockClear();
    reloadMock.mockClear();
    editBeginMock.mockClear();
    editSetTextMock.mockClear();
    editSetRunConfigMock.mockClear();
    editSendMock.mockClear();
    getConversationMock.mockResolvedValue(emptyHistory);
  });

  test("renders concept title and context", async () => {
    renderPanel();

    await screen.findByText("waiting");
    expect(screen.getByText("Vectors")).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Thread options" }),
    );
    expect(screen.getByText("Level: topic")).toBeInTheDocument();
    expect(screen.getByText("Bloom: understand")).toBeInTheDocument();
  });

  test("mode badge updates when runtime reports mode", async () => {
    renderPanel();
    await screen.findByText("waiting");

    act(() => {
      runtimeOptions?.onMode("direct");
    });

    expect(await screen.findByText("direct")).toBeInTheDocument();
  });

  test("header status updates when runtime reports status", async () => {
    renderPanel();
    await screen.findByText("waiting");

    act(() => {
      runtimeOptions?.onStatus?.("calling_tool");
    });

    expect(await screen.findByText("Calling tool")).toBeInTheDocument();
  });

  test("token chunks appear in chat UI", async () => {
    mockMessages = [assistantMessage("Think about vectors.")];

    renderPanel();

    expect(await screen.findByText("Think about vectors.")).toBeInTheDocument();
  });

  test("only latest assistant message exposes regenerate", async () => {
    mockMessages = [
      assistantMessage("Older answer."),
      { ...assistantMessage("Learner reply."), role: "user" },
      assistantMessage("Latest answer."),
    ];

    renderPanel();

    await screen.findByText("Latest answer.");
    expect(
      screen.getAllByRole("button", { name: "Copy message" }),
    ).toHaveLength(2);
    expect(
      screen.getAllByRole("button", { name: "Regenerate response" }),
    ).toHaveLength(1);

    await userEvent.click(
      screen.getByRole("button", { name: "Regenerate response" }),
    );
    expect(reloadMock).toHaveBeenCalledWith({
      runConfig: { custom: { regenerate: true } },
    });
  });

  test("latest user message exposes edit even when an assistant response follows it", async () => {
    mockMessages = [
      { ...assistantMessage("First learner reply."), role: "user" },
      assistantMessage("First assistant answer."),
      { ...assistantMessage("Latest learner reply."), role: "user" },
      assistantMessage("Assistant answer."),
    ];

    renderPanel();

    await screen.findByText("Latest learner reply.");
    expect(
      screen.getAllByRole("button", { name: "Edit message" }),
    ).toHaveLength(1);

    await userEvent.click(screen.getByRole("button", { name: "Edit message" }));
    const editor = screen.getByRole("textbox", { name: "Edit message text" });
    expect(editor).toHaveValue("Latest learner reply.");

    await userEvent.clear(editor);
    await userEvent.type(editor, "Edited learner reply.");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    // Editing branches through the message's native edit composer and tags the
    // run as a backend latest-user replacement.
    expect(editSetTextMock).toHaveBeenCalledWith("Edited learner reply.");
    expect(editSetRunConfigMock).toHaveBeenCalledWith({
      custom: { replaceLatestUser: true },
    });
    expect(editSendMock).toHaveBeenCalled();
  });

  test("latest user edit can be cancelled", async () => {
    mockMessages = [
      { ...assistantMessage("Latest learner reply."), role: "user" },
      assistantMessage("Assistant answer."),
    ];

    renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: "Edit message" }),
    );
    expect(
      screen.getByRole("textbox", { name: "Edit message text" }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(
      screen.queryByRole("textbox", { name: "Edit message text" }),
    ).not.toBeInTheDocument();
    expect(editSendMock).not.toHaveBeenCalled();
  });

  test("latest user edit sends on Enter and inserts a newline on Shift+Enter", async () => {
    mockMessages = [
      { ...assistantMessage("Latest learner reply."), role: "user" },
      assistantMessage("Assistant answer."),
    ];

    renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: "Edit message" }),
    );
    const editor = screen.getByRole("textbox", { name: "Edit message text" });
    await userEvent.clear(editor);
    await userEvent.type(editor, "Line one");

    // Shift+Enter must not submit; it adds a newline like the main composer.
    await userEvent.type(editor, "{Shift>}{Enter}{/Shift}Line two");
    expect(editSendMock).not.toHaveBeenCalled();

    // Plain Enter submits the edit.
    await userEvent.type(editor, "{Enter}");
    expect(editSendMock).toHaveBeenCalled();
  });

  test("reasoning traces can be expanded when assistant reasoning exists", async () => {
    window.localStorage.setItem("colearni.reasoningView", "full");
    mockMessages = [
      assistantMessage("Final answer.", "Private reasoning trace."),
    ];

    renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: "Show reasoning" }),
    );

    expect(
      (await screen.findAllByText("Private reasoning trace.")).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("Final answer.")).toBeInTheDocument();
  });

  test("renders tutor stream status inside the reasoning group", async () => {
    window.localStorage.setItem("colearni.reasoningView", "full");
    mockMessages = [
      assistantMessage(
        "Final answer.",
        "Private reasoning trace.",
        "calling_tool",
      ),
    ];

    renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: "Show reasoning" }),
    );

    expect(await screen.findByText("Calling tool")).toBeInTheDocument();
  });

  test("renders ordered thinking and tool events inside the reasoning group", async () => {
    window.localStorage.setItem("colearni.reasoningView", "full");
    mockMessages = [
      {
        id: "assistant-tool-flow",
        role: "assistant",
        content: [
          {
            type: "data",
            name: "tutor-thinking",
            data: { text: "I should call the tool first." },
          },
          {
            type: "data",
            name: "tutor-tool-call",
            data: { name: "get_tutor_instructions", mode: "direct" },
          },
          {
            type: "data",
            name: "tutor-tool-result",
            data: {
              name: "get_tutor_instructions",
              mode: "direct",
              result: "Use direct mode.",
            },
          },
          {
            type: "data",
            name: "tutor-thinking",
            data: { text: "Now I can answer." },
          },
          { type: "text", text: "Final answer." },
        ],
        status: { type: "complete" },
      },
    ];

    renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: "Show reasoning" }),
    );

    expect(
      await screen.findByText("I should call the tool first."),
    ).toBeInTheDocument();
    expect(screen.getByText("Choosing response style")).toBeInTheDocument();
    expect(screen.getByText("Use direct mode.")).toBeInTheDocument();
    expect(screen.getByText("Now I can answer.")).toBeInTheDocument();
  });

  test("defaults to learner-safe reasoning summary", async () => {
    mockMessages = [
      assistantMessage(
        "Final answer.",
        "This is the first safe sentence. Hidden details follow.",
      ),
    ];

    renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: "Show reasoning summary" }),
    );

    expect(await screen.findByText("Reasoning summary")).toBeInTheDocument();
    expect(screen.getByText("Thinking")).toBeInTheDocument();
    expect(
      screen.getByText("This is the first safe sentence."),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Hidden details follow."),
    ).not.toBeInTheDocument();
  });

  test("summary reasoning shows streamed tool steps", async () => {
    mockMessages = [
      {
        id: "assistant-summary-tool-flow",
        role: "assistant",
        content: [
          {
            type: "data",
            name: "tutor-thinking",
            data: { text: "I should inspect the source first." },
          },
          {
            type: "data",
            name: "tutor-tool-call",
            data: { name: "search_sources", mode: null, query: "lead singles" },
          },
          {
            type: "data",
            name: "tutor-tool-result",
            data: {
              name: "search_sources",
              mode: null,
              result: "Found the overview section.",
            },
          },
          { type: "text", text: "Final answer." },
        ],
        status: { type: "complete" },
      },
    ];

    renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: "Show reasoning summary" }),
    );

    expect(
      (await screen.findAllByText("Searching sources")).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText('"lead singles"')).toBeInTheDocument();
    expect(screen.queryByText("Tool result")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Found the overview section."),
    ).not.toBeInTheDocument();
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
    await screen.findByText("waiting");

    act(() => {
      runtimeOptions?.onError?.("Generation failed");
    });

    expect(await screen.findByText("Generation failed")).toBeInTheDocument();
  });

  test("quiz prompt placeholder appears in quiz_prompt mode", async () => {
    renderPanel();
    await screen.findByText("waiting");

    act(() => {
      runtimeOptions?.onMode("quiz_prompt");
    });

    expect(
      await screen.findByText(
        "Ready to level up? Go back to the concept details and use the Level Up button.",
      ),
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

    await userEvent.click(
      await screen.findByRole("button", { name: "Thread options" }),
    );
    expect(await screen.findByText("Sources available")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Linear Algebra Notes" }),
    ).toHaveAttribute("href", "https://example.com/linear-algebra");
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
      expect(getConversationMock).toHaveBeenCalledWith(
        "workspace-1",
        "trail-1",
        "concept-1",
      );
    });
    expect(await screen.findByText("repair")).toBeInTheDocument();
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

function assistantMessage(
  text: string,
  reasoning?: string,
  status?: string,
): MockMessage {
  return {
    id: `assistant-${text}`,
    role: "assistant",
    content: [
      ...(status
        ? [{ type: "data" as const, name: "tutor-status", data: { status } }]
        : []),
      ...(reasoning ? [{ type: "reasoning" as const, text: reasoning }] : []),
      { type: "text", text },
    ],
    status: { type: "complete" },
  };
}

function PartScope({
  part,
  children,
}: {
  part: MockPart;
  children: ReactNode;
}) {
  return (
    <MockPartContext.Provider value={part}>{children}</MockPartContext.Provider>
  );
}

function readNodeText(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") {
    return String(node);
  }

  if (Array.isArray(node)) {
    return node.map(readNodeText).join("");
  }

  if (node && typeof node === "object" && "props" in node) {
    return readNodeText(
      (node as { props?: { children?: ReactNode } }).props?.children ?? null,
    );
  }

  return "";
}

function formatMockStatus(status: string): string {
  switch (status) {
    case "thinking":
      return "Thinking";
    case "calling_tool":
      return "Calling tool";
    case "tool_called":
      return "Tool requested";
    case "tool_complete":
      return "Tool result ready";
    case "responding":
      return "Responding";
    default:
      return status;
  }
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

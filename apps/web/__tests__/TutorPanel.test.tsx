import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  createContext,
  useContext,
  type MouseEventHandler,
  type ReactNode,
} from "react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { TutorPanel } from "@/app/(app)/trails/[id]/components/TutorPanel";
import type {
  ConceptNode,
  ConversationHistoryResponse,
  Note,
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
  listConversationThreads: vi.fn(),
  createConversationThread: vi.fn(),
  updateConversationThread: vi.fn(),
  deleteConversationThread: vi.fn(),
  listNotes: vi.fn(),
  createNote: vi.fn(),
  updateNote: vi.fn(),
  deleteNote: vi.fn(),
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
      const ungroupedDataParts = message.content.filter(
        (part) =>
          part.type === "data" &&
          (part.name === "tutor-suggest-quiz" ||
            part.name === "tutor-suggest-flashcards" ||
            part.name === "tutor-suggest-artifact"),
      );
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

      ungroupedDataParts.forEach((part, index) => {
        rendered.push(
          <PartScope key={`data-${index}`} part={part}>
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
    Input: ({ submitMode, ...props }: Record<string, unknown>) => {
      void submitMode;
      return <textarea {...props} />;
    },
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

const apiMocks = vi.mocked(await import("@/lib/api"));
const getConversationMock = apiMocks.getConversation;
const listConversationThreadsMock = apiMocks.listConversationThreads;
const createConversationThreadMock = apiMocks.createConversationThread;
const updateConversationThreadMock = apiMocks.updateConversationThread;
const deleteConversationThreadMock = apiMocks.deleteConversationThread;
const listNotesMock = apiMocks.listNotes;
const createNoteMock = apiMocks.createNote;
const updateNoteMock = apiMocks.updateNote;
const deleteNoteMock = apiMocks.deleteNote;

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
    listConversationThreadsMock.mockResolvedValue({ conversations: [] });
    createConversationThreadMock.mockResolvedValue({
      id: "conversation-new",
      title: "New thread",
      preview: null,
      message_count: 0,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });
    updateConversationThreadMock.mockImplementation(
      async (_workspaceId, _trailId, _conceptId, conversationId, title) => ({
        id: conversationId,
        title,
        preview: null,
        message_count: 2,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      }),
    );
    deleteConversationThreadMock.mockResolvedValue(undefined);
    listNotesMock.mockResolvedValue([]);
    createNoteMock.mockResolvedValue({
      ...note,
      id: "note-new",
      title: "New note",
      body: "Remember bases.",
      created_at: "2026-01-03T00:00:00Z",
      updated_at: "2026-01-03T00:00:00Z",
    });
    updateNoteMock.mockImplementation(
      async (_workspaceId, _trailId, noteId, body) => ({
        ...note,
        id: noteId,
        title: body.title ?? null,
        body: body.body ?? note.body,
        updated_at: "2026-01-04T00:00:00Z",
      }),
    );
    deleteNoteMock.mockResolvedValue(undefined);
  });

  test("renders a compact tutor header and context menu metadata", async () => {
    renderPanel();

    await screen.findByText("waiting");
    expect(screen.queryByText("Learning thread")).not.toBeInTheDocument();
    expect(screen.getByText("Tutor workspace")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Tutor workspace" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Start a conversation for this concept."),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Conversation settings" }),
    );
    expect(screen.getByText("Level: Topic")).toBeInTheDocument();
    expect(screen.getByText("Bloom: Understand")).toBeInTheDocument();
  });

  test("uses mobile-safe shell and full-width tutor tabs", async () => {
    renderPanel();

    const heading = await screen.findByRole("heading", { name: "Tutor workspace" });
    const shell = heading.closest("section");
    expect(shell).toHaveClass("min-h-0");
    expect(shell).not.toHaveClass("min-h-130");

    const tablist = screen.getByRole("tablist", { name: "Tutor panel sections" });
    expect(tablist).toHaveClass("w-full");
    expect(screen.getByRole("tab", { name: "Tutor" })).toHaveClass("flex-1");
    expect(screen.getByRole("tab", { name: "Notes" })).toHaveClass("flex-1");
    const viewport = document.querySelector("div.touch-pan-y");
    expect(viewport).not.toBeNull();
    expect(viewport).toHaveClass(
      "overflow-y-auto",
      "touch-pan-y",
      "overscroll-y-contain",
    );
    const footer = viewport?.querySelector(".sticky.bottom-0");
    expect(footer).toHaveClass("z-20", "border-t", "bg-white");
    expect(screen.getByLabelText("Message tutor").closest("form")).toHaveClass(
      "rounded-2xl",
      "shadow-sm",
    );
  });

  test("conversation settings menu closes on outside click", async () => {
    renderPanel();

    await screen.findByText("waiting");
    await userEvent.click(
      screen.getByRole("button", { name: "Conversation settings" }),
    );
    expect(screen.getByText("Level: Topic")).toBeInTheDocument();

    await userEvent.click(document.body);

    await waitFor(() => {
      expect(screen.queryByText("Level: Topic")).not.toBeInTheDocument();
    });
  });

  test("mode badge updates when runtime reports mode", async () => {
    renderPanel();
    await screen.findByText("waiting");

    act(() => {
      runtimeOptions?.onMode("direct");
    });

    expect(await screen.findByText("Direct")).toBeInTheDocument();
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

    expect(await screen.findByText("Thinking")).toBeInTheDocument();
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

  test("reasoning indicator pulses while reasoning before any answer text", async () => {
    window.localStorage.setItem("colearni.reasoningView", "full");
    mockMessages = [
      {
        id: "assistant-reasoning-running",
        role: "assistant",
        content: [
          {
            type: "data",
            name: "tutor-thinking",
            data: { text: "Still working it out." },
          },
        ],
        // Run is in progress and no visible answer has started yet.
        status: { type: "running" },
      },
    ];

    renderPanel();

    expect(await screen.findByText("streaming")).toBeInTheDocument();
  });

  test("reasoning indicator stops once the answer has started or the run is done", async () => {
    window.localStorage.setItem("colearni.reasoningView", "full");
    mockMessages = [
      {
        id: "assistant-running-with-answer",
        role: "assistant",
        content: [
          {
            type: "data",
            name: "tutor-thinking",
            data: { text: "Done reasoning." },
          },
          { type: "text", text: "Here is the answer." },
        ],
        // Even while the run is still marked running, a visible answer means the
        // chain-of-thought is finished and the indicator must not keep pulsing.
        status: { type: "running" },
      },
    ];

    renderPanel();

    expect(await screen.findByText("Here is the answer.")).toBeInTheDocument();
    expect(screen.queryByText("streaming")).not.toBeInTheDocument();
  });

  test("completed full-view status steps render a static (non-pulsing) dot", async () => {
    window.localStorage.setItem("colearni.reasoningView", "full");
    mockMessages = [
      {
        id: "assistant-completed-status",
        role: "assistant",
        content: [
          {
            type: "data",
            name: "tutor-status",
            data: { status: "selecting_mode" },
          },
          {
            type: "data",
            name: "tutor-status",
            data: { status: "calling_tool" },
          },
          { type: "text", text: "Here is the final answer." },
        ],
        // The whole run has finished.
        status: { type: "complete" },
      },
    ];

    renderPanel();

    await userEvent.click(
      await screen.findByRole("button", { name: "Show reasoning" }),
    );

    // Each status step still renders its label...
    const firstStep = await screen.findByText("Choosing answering mode");
    const secondStep = await screen.findByText("Calling tool");

    // ...but its indicator dot must be static once the run is complete (Bug 1).
    for (const step of [firstStep, secondStep]) {
      const dot = step.querySelector("span");
      expect(dot?.className).toContain("bg-blue-500");
      expect(dot?.className).not.toContain("animate-pulse");
    }

    // No group-level streaming/active pulse remains either.
    expect(screen.queryByText("streaming")).not.toBeInTheDocument();
  });

  test("summary view surfaces live status progress during reasoning", async () => {
    mockMessages = [
      {
        id: "assistant-status-progress",
        role: "assistant",
        content: [
          {
            type: "data",
            name: "tutor-status",
            data: { status: "calling_tool" },
          },
        ],
        status: { type: "running" },
      },
    ];

    renderPanel();

    // A running reasoning group auto-expands, so the live status is visible
    // without toggling the trigger.
    expect(await screen.findByText("Calling tool")).toBeInTheDocument();
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

  test("quiz prompt banner offers a direct level-up CTA in quiz_prompt mode", async () => {
    const onSuggestQuiz = vi.fn();
    render(
      <TutorPanel
        workspaceId="workspace-1"
        trailId="trail-1"
        concept={concept}
        onSuggestQuiz={onSuggestQuiz}
      />,
    );
    await screen.findByText("waiting");

    act(() => {
      runtimeOptions?.onMode("quiz_prompt");
    });

    const cta = await screen.findByRole("button", {
      name: "Start level-up quiz",
    });
    await userEvent.click(cta);
    expect(onSuggestQuiz).toHaveBeenCalledWith("level_up");
  });

  test("renders the suggested quiz CTA and opens the quiz on click", async () => {
    const onSuggestQuiz = vi.fn();
    mockMessages = [
      {
        id: "assistant-cta",
        role: "assistant",
        content: [
          {
            type: "data",
            name: "tutor-suggest-quiz",
            data: {
              quizType: "level_up",
              reason: "You're close to mastering this.",
            },
          },
          { type: "text", text: "Great progress so far." },
        ],
        status: { type: "complete" },
      },
    ];

    render(
      <TutorPanel
        workspaceId="workspace-1"
        trailId="trail-1"
        concept={concept}
        onSuggestQuiz={onSuggestQuiz}
      />,
    );

    const cta = await screen.findByRole("button", {
      name: "Take level-up quiz",
    });
    expect(
      screen.getByText("You're close to mastering this."),
    ).toBeInTheDocument();

    await userEvent.click(cta);
    expect(onSuggestQuiz).toHaveBeenCalledWith("level_up");
  });

  test("renders the suggested flashcards CTA and opens flashcards on click", async () => {
    const onSuggestFlashcards = vi.fn();
    mockMessages = [
      {
        id: "assistant-flashcards-cta",
        role: "assistant",
        content: [
          {
            type: "data",
            name: "tutor-suggest-flashcards",
            data: {
              reason: "A quick recall deck would help cement this.",
            },
          },
          {
            type: "text",
            text: "Let's turn the key ideas into recall prompts.",
          },
        ],
        status: { type: "complete" },
      },
    ];

    render(
      <TutorPanel
        workspaceId="workspace-1"
        trailId="trail-1"
        concept={concept}
        onSuggestFlashcards={onSuggestFlashcards}
      />,
    );

    const cta = await screen.findByRole("button", {
      name: "Generate flashcards",
    });
    expect(
      screen.getByText("A quick recall deck would help cement this."),
    ).toBeInTheDocument();

    await userEvent.click(cta);
    expect(onSuggestFlashcards).toHaveBeenCalledTimes(1);
  });

  test("renders the suggested artifact CTA and opens the build on click", async () => {
    const onSuggestArtifact = vi.fn();
    mockMessages = [
      {
        id: "assistant-artifact-cta",
        role: "assistant",
        content: [
          {
            type: "data",
            name: "tutor-suggest-artifact",
            data: {
              artifactKind: "timeline",
              reason: "A timeline would tie these steps together.",
            },
          },
          { type: "text", text: "Here is the sequence so far." },
        ],
        status: { type: "complete" },
      },
    ];

    render(
      <TutorPanel
        workspaceId="workspace-1"
        trailId="trail-1"
        concept={concept}
        onSuggestArtifact={onSuggestArtifact}
      />,
    );

    const cta = await screen.findByRole("button", {
      name: "Build timeline",
    });
    expect(
      screen.getByText("A timeline would tie these steps together."),
    ).toBeInTheDocument();

    await userEvent.click(cta);
    expect(onSuggestArtifact).toHaveBeenCalledWith("timeline");
  });

  test("loads and switches between saved conversation threads", async () => {
    listConversationThreadsMock.mockResolvedValue({
      conversations: [
        {
          id: "conversation-2",
          title: "Second thread",
          preview: "Recent answer",
          message_count: 2,
          created_at: "2026-01-02T00:00:00Z",
          updated_at: "2026-01-02T00:00:00Z",
        },
        {
          id: "conversation-1",
          title: "First thread",
          preview: "Older answer",
          message_count: 2,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
      ],
    });

    renderPanel();

    await waitFor(() => {
      expect(getConversationMock).toHaveBeenCalledWith(
        "workspace-1",
        "trail-1",
        "concept-1",
        { conversationId: "conversation-2" },
      );
    });

    await userEvent.click(
      screen.getAllByRole("button", { name: /First thread/ })[0],
    );

    await waitFor(() => {
      expect(getConversationMock).toHaveBeenCalledWith(
        "workspace-1",
        "trail-1",
        "concept-1",
        { conversationId: "conversation-1" },
      );
    });
  });

  test("creates a fresh conversation thread from the thread switcher", async () => {
    renderPanel();
    await screen.findByText("waiting");

    await userEvent.click(screen.getByRole("button", { name: "New thread" }));

    expect(createConversationThreadMock).toHaveBeenCalledWith(
      "workspace-1",
      "trail-1",
      "concept-1",
    );
    await waitFor(() => {
      expect(getConversationMock).toHaveBeenCalledWith(
        "workspace-1",
        "trail-1",
        "concept-1",
        { conversationId: "conversation-new" },
      );
    });
  });

  test("renames a thread from the thread chip actions", async () => {
    vi.spyOn(window, "prompt").mockReturnValue("Renamed thread");
    listConversationThreadsMock.mockResolvedValue({
      conversations: [
        {
          id: "conversation-2",
          title: "Second thread",
          preview: "Recent answer",
          message_count: 2,
          created_at: "2026-01-02T00:00:00Z",
          updated_at: "2026-01-02T00:00:00Z",
        },
      ],
    });

    renderPanel();

    await screen.findByRole("button", {
      name: /Thread actions for Second thread/,
    });
    await userEvent.click(
      screen.getByRole("button", { name: /Thread actions for Second thread/ }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Rename" }));

    await waitFor(() => {
      expect(updateConversationThreadMock).toHaveBeenCalledWith(
        "workspace-1",
        "trail-1",
        "concept-1",
        "conversation-2",
        "Renamed thread",
      );
    });
    expect(
      (await screen.findAllByRole("button", { name: /Renamed thread/ }))[0],
    ).toBeInTheDocument();
  });

  test("thread actions menu closes on outside click", async () => {
    listConversationThreadsMock.mockResolvedValue({
      conversations: [
        {
          id: "conversation-2",
          title: "Second thread",
          preview: "Recent answer",
          message_count: 2,
          created_at: "2026-01-02T00:00:00Z",
          updated_at: "2026-01-02T00:00:00Z",
        },
      ],
    });

    renderPanel();

    await screen.findByRole("button", {
      name: /Thread actions for Second thread/,
    });
    await userEvent.click(
      screen.getByRole("button", { name: /Thread actions for Second thread/ }),
    );
    expect(screen.getByRole("button", { name: "Rename" })).toBeInTheDocument();

    await userEvent.click(document.body);

    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: "Rename" }),
      ).not.toBeInTheDocument();
    });
  });

  test("deletes the selected thread from the thread chip actions", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    listConversationThreadsMock.mockResolvedValue({
      conversations: [
        {
          id: "conversation-2",
          title: "Second thread",
          preview: "Recent answer",
          message_count: 2,
          created_at: "2026-01-02T00:00:00Z",
          updated_at: "2026-01-02T00:00:00Z",
        },
        {
          id: "conversation-1",
          title: "First thread",
          preview: "Older answer",
          message_count: 2,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
      ],
    });

    renderPanel();

    await waitFor(() => {
      expect(getConversationMock).toHaveBeenCalledWith(
        "workspace-1",
        "trail-1",
        "concept-1",
        { conversationId: "conversation-2" },
      );
    });

    await userEvent.click(
      screen.getByRole("button", { name: /Thread actions for Second thread/ }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      expect(deleteConversationThreadMock).toHaveBeenCalledWith(
        "workspace-1",
        "trail-1",
        "concept-1",
        "conversation-2",
      );
    });
    await waitFor(() => {
      expect(getConversationMock).toHaveBeenCalledWith(
        "workspace-1",
        "trail-1",
        "concept-1",
        { conversationId: "conversation-1" },
      );
    });
    expect(
      screen.queryByRole("button", { name: /Second thread/ }),
    ).not.toBeInTheDocument();
  });

  test("notes tab loads, creates, edits, and deletes concept notes", async () => {
    listNotesMock.mockResolvedValue([note]);

    renderPanel();

    await userEvent.click(await screen.findByRole("tab", { name: "Notes" }));

    await waitFor(() => {
      expect(listNotesMock).toHaveBeenCalledWith(
        "workspace-1",
        "trail-1",
        "concept-1",
      );
    });
    expect(await screen.findByText("Existing note")).toBeInTheDocument();
    expect(
      screen.getByText("Vectors have magnitude and direction."),
    ).toBeInTheDocument();

    await userEvent.type(
      screen.getByPlaceholderText("Optional title"),
      "New note",
    );
    await userEvent.type(
      screen.getByPlaceholderText(
        "Write a note, summary, question, or next step...",
      ),
      "Remember bases.",
    );
    await userEvent.click(screen.getByRole("button", { name: "Save note" }));

    await waitFor(() => {
      expect(createNoteMock).toHaveBeenCalledWith("workspace-1", "trail-1", {
        title: "New note",
        body: "Remember bases.",
        concept_id: "concept-1",
      });
    });
    expect(await screen.findByText("New note")).toBeInTheDocument();

    await userEvent.click(screen.getAllByRole("button", { name: "Edit" })[0]);
    const editTitle = screen.getByDisplayValue("New note");
    const editBody = screen.getByDisplayValue("Remember bases.");
    await userEvent.clear(editTitle);
    await userEvent.type(editTitle, "Updated note");
    await userEvent.clear(editBody);
    await userEvent.type(editBody, "Updated body");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(updateNoteMock).toHaveBeenCalledWith(
        "workspace-1",
        "trail-1",
        "note-new",
        { title: "Updated note", body: "Updated body" },
      );
    });
    expect(await screen.findByText("Updated note")).toBeInTheDocument();

    await userEvent.click(screen.getAllByRole("button", { name: "Delete" })[0]);

    await waitFor(() => {
      expect(deleteNoteMock).toHaveBeenCalledWith(
        "workspace-1",
        "trail-1",
        "note-new",
      );
    });
    await waitFor(() => {
      expect(screen.queryByText("Updated body")).not.toBeInTheDocument();
    });
  });

  test("source chips render only when source metadata exists", async () => {
    const { rerender } = renderPanel();

    await screen.findByText("waiting");
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
      await screen.findByRole("button", { name: "Conversation settings" }),
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
        { conversationId: null },
      );
    });
    expect(await screen.findByText("Repair")).toBeInTheDocument();
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

const note: Note = {
  id: "note-1",
  workspace_id: "workspace-1",
  trail_id: "trail-1",
  concept_id: "concept-1",
  title: "Existing note",
  body: "Vectors have magnitude and direction.",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
};

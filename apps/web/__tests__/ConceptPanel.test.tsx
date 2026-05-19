import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

import { ConceptPanel } from "@/app/trails/[id]/components/ConceptPanel";
import type { ConceptDetail } from "@/lib/types";

vi.mock("@/app/trails/[id]/components/TutorPanel", () => ({
  TutorPanel: ({ concept }: { concept: { title: string } }) => (
    <div data-testid="tutor-panel">Tutor for {concept.title}</div>
  ),
}));

const detail: ConceptDetail = {
  concept: {
    id: "concept-1",
    trail_id: "trail-1",
    slug: "vectors",
    title: "Vectors",
    node_type: "concept",
    concept_level: "topic",
    difficulty: "beginner",
    bloom_level: "understand",
    mastery_check_labels: ["explain vectors", "compute a dot product"],
    metadata_json: {},
  },
  prerequisites: [],
  contained_nodes: [],
  containing_nodes: [],
  related: [],
  mastery: null,
  sources: [],
};

describe("ConceptPanel", () => {
  test("renders concept title and level", () => {
    render(
      <ConceptPanel
        workspaceId="workspace-1"
        trailId="trail-1"
        detail={detail}
        onClose={() => undefined}
      />,
    );

    expect(screen.getByRole("heading", { name: "Vectors" })).toBeInTheDocument();
    expect(screen.getByText("topic")).toBeInTheDocument();
  });

  test("mobile sheet starts collapsed and expands from the handle", async () => {
    render(
      <ConceptPanel
        workspaceId="workspace-1"
        trailId="trail-1"
        detail={detail}
        onClose={() => undefined}
      />,
    );

    expect(screen.getByTestId("concept-sheet-body")).toHaveClass("hidden");

    await userEvent.click(screen.getByRole("button", { name: "Expand concept details" }));

    expect(screen.getByTestId("concept-sheet-body")).toHaveClass("block");
    expect(screen.getByRole("button", { name: "Collapse concept details" })).toBeInTheDocument();
  });

  test("close button calls onClose from inside draggable header", async () => {
    const onClose = vi.fn();

    render(
      <ConceptPanel
        workspaceId="workspace-1"
        trailId="trail-1"
        detail={detail}
        onClose={onClose}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Close" }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("Start Learning button is enabled and opens tutor panel", async () => {
    render(
      <ConceptPanel
        workspaceId="workspace-1"
        trailId="trail-1"
        detail={detail}
        onClose={() => undefined}
      />,
    );

    const start = screen.getByRole("button", { name: "Start Learning" });
    expect(start).toBeEnabled();

    await userEvent.click(start);

    expect(screen.getByTestId("tutor-panel")).toHaveTextContent("Tutor for Vectors");
  });
});

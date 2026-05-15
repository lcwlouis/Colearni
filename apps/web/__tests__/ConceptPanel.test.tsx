import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test } from "vitest";

import { ConceptPanel } from "@/app/trails/[id]/components/ConceptPanel";
import type { ConceptDetail } from "@/lib/types";

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
    render(<ConceptPanel detail={detail} onClose={() => undefined} />);

    expect(screen.getByRole("heading", { name: "Vectors" })).toBeInTheDocument();
    expect(screen.getByText("topic")).toBeInTheDocument();
  });

  test("mobile sheet starts collapsed and expands from the handle", async () => {
    render(<ConceptPanel detail={detail} onClose={() => undefined} />);

    expect(screen.getByTestId("concept-sheet-body")).toHaveClass("hidden");

    await userEvent.click(screen.getByRole("button", { name: "Expand concept details" }));

    expect(screen.getByTestId("concept-sheet-body")).toHaveClass("block");
    expect(screen.getByRole("button", { name: "Collapse concept details" })).toBeInTheDocument();
  });
});

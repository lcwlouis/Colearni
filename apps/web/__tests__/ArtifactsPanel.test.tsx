import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { ArtifactsPanel } from "@/app/(app)/trails/[id]/components/ArtifactsPanel";
import type {
  ArtifactRead,
  ComparisonCardEnvelope,
  WorkedExampleEnvelope,
} from "@/lib/artifacts";

vi.mock("@/lib/api", () => ({
  listArtifacts: vi.fn(),
  streamBuildArtifact: vi.fn(),
}));

import * as api from "@/lib/api";

function workedExampleEnvelope(): WorkedExampleEnvelope {
  return {
    artifact_version: 1,
    kind: "worked_example",
    title: "Solving 2x + 3 = 11",
    caption: "A linear equation worked end to end.",
    text_fallback: "Step 1: subtract 3. Step 2: divide by 2. Answer: x = 4.",
    provenance: { source_ids: [], visibility: "local_only", citations: [] },
    data: {
      steps: [
        { label: "Isolate the term", detail: "Subtract 3 from both sides." },
        { label: "Solve for x", detail: "Divide both sides by 2." },
      ],
      final_answer: "x = 4",
    },
  };
}

function comparisonCardEnvelope(): ComparisonCardEnvelope {
  return {
    artifact_version: 1,
    kind: "comparison_card",
    title: "TCP vs UDP",
    caption: null,
    text_fallback:
      "TCP is reliable and ordered; UDP is fast and connectionless.",
    provenance: { source_ids: [], visibility: "local_only", citations: [] },
    data: {
      items: ["TCP", "UDP"],
      criteria: [{ label: "Reliability", values: ["Reliable", "Best-effort"] }],
    },
  };
}

function artifactRow(
  id: string,
  payload: WorkedExampleEnvelope | ComparisonCardEnvelope,
): ArtifactRead {
  return {
    id,
    workspace_id: "workspace-1",
    trail_id: "trail-1",
    concept_id: "concept-1",
    artifact_type: payload.kind,
    title: payload.title,
    visibility: payload.provenance.visibility,
    payload,
    created_at: "2026-05-30T10:00:00Z",
  };
}

function renderPanel(onBack = vi.fn()) {
  return render(
    <ArtifactsPanel
      workspaceId="workspace-1"
      trailId="trail-1"
      conceptId="concept-1"
      onBack={onBack}
    />,
  );
}

describe("ArtifactsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listArtifacts).mockResolvedValue({ artifacts: [] });
  });

  test("lists existing artifacts and renders them through ArtifactRenderer", async () => {
    vi.mocked(api.listArtifacts).mockResolvedValue({
      artifacts: [
        artifactRow("artifact-1", workedExampleEnvelope()),
        artifactRow("artifact-2", comparisonCardEnvelope()),
      ],
    });

    renderPanel();

    await waitFor(() => {
      expect(screen.getByTestId("artifact-worked-example")).toBeInTheDocument();
    });

    expect(api.listArtifacts).toHaveBeenCalledWith(
      "workspace-1",
      "trail-1",
      "concept-1",
    );
    // Rendered through the registry: worked-example steps + comparison table.
    expect(screen.getByText("Isolate the term")).toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: "TCP" }),
    ).toBeInTheDocument();
  });

  test("shows an empty state when there are no artifacts", async () => {
    renderPanel();

    await waitFor(() => {
      expect(screen.getByText(/No artifacts yet/)).toBeInTheDocument();
    });
  });

  test("Generate worked example calls the build stream and renders the result on done", async () => {
    const fresh = artifactRow("artifact-new", workedExampleEnvelope());
    vi.mocked(api.streamBuildArtifact).mockImplementation(
      async (_workspaceId, _trailId, _body, callbacks) => {
        callbacks.onStatus?.("retrieving");
        callbacks.onStatus?.("generating");
        callbacks.onDone(fresh);
      },
    );

    renderPanel();

    await waitFor(() => {
      expect(screen.getByText(/No artifacts yet/)).toBeInTheDocument();
    });

    await userEvent.click(
      screen.getByRole("button", { name: "Generate worked example" }),
    );

    expect(api.streamBuildArtifact).toHaveBeenCalledWith(
      "workspace-1",
      "trail-1",
      { kind: "worked_example", conceptId: "concept-1" },
      expect.anything(),
    );

    await waitFor(() => {
      expect(screen.getByTestId("artifact-worked-example")).toBeInTheDocument();
    });
    expect(screen.getByText("Solving 2x + 3 = 11")).toBeInTheDocument();
    expect(screen.queryByText(/No artifacts yet/)).not.toBeInTheDocument();
  });

  test("surfaces the live generating status while the build streams", async () => {
    let release = (): void => undefined;
    vi.mocked(api.streamBuildArtifact).mockImplementation(
      async (_workspaceId, _trailId, _body, callbacks) => {
        callbacks.onStatus?.("retrieving");
        callbacks.onStatus?.("generating");
        await new Promise<void>((resolve) => {
          release = resolve;
        });
        callbacks.onDone(artifactRow("artifact-new", workedExampleEnvelope()));
      },
    );

    renderPanel();
    await waitFor(() => {
      expect(screen.getByText(/No artifacts yet/)).toBeInTheDocument();
    });

    await userEvent.click(
      screen.getByRole("button", { name: "Generate comparison" }),
    );

    await waitFor(() => {
      expect(screen.getByRole("status")).toHaveTextContent(
        /Generating the artifact/,
      );
    });

    release();
  });

  test("shows an error state when the build stream emits an error event", async () => {
    vi.mocked(api.streamBuildArtifact).mockImplementation(
      async (_workspaceId, _trailId, _body, callbacks) => {
        callbacks.onError?.("The model could not build this artifact.");
      },
    );

    renderPanel();
    await waitFor(() => {
      expect(screen.getByText(/No artifacts yet/)).toBeInTheDocument();
    });

    await userEvent.click(
      screen.getByRole("button", { name: "Generate worked example" }),
    );

    await waitFor(() => {
      expect(
        screen.getByText("The model could not build this artifact."),
      ).toBeInTheDocument();
    });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  test("shows a load error when listing artifacts fails", async () => {
    vi.mocked(api.listArtifacts).mockRejectedValue(new Error("boom"));

    renderPanel();

    await waitFor(() => {
      expect(screen.getByText("boom")).toBeInTheDocument();
    });
  });

  test("back button calls onBack", async () => {
    const onBack = vi.fn();
    renderPanel(onBack);

    await userEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });
});

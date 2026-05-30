import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test, vi } from "vitest";

import type { Trail, TrailGenerateRequest } from "@/lib/types";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/lib/workspace", () => ({
  ensureWorkspaceId: vi.fn().mockResolvedValue("workspace-1"),
}));

const listTrailsMock = vi.fn();
const generateTrailMock = vi.fn();

vi.mock("@/lib/api", () => ({
  listTrails: (...args: unknown[]) => listTrailsMock(...args),
  generateTrail: (...args: unknown[]) => generateTrailMock(...args),
  deleteTrail: vi.fn(),
}));

function fixtureTrail(): Trail {
  return {
    id: "trail-1",
    workspace_id: "workspace-1",
    title: "Math",
    topic: "Math",
    goal: "Learn",
    target_depth: "apply",
    created_at: "2026-01-01T00:00:00Z",
    node_count: 3,
    edge_count: 1,
  };
}

async function loadPage() {
  const mod = await import("@/app/trails/page");
  return mod.default;
}

describe("Trails page prior-knowledge field", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });
  test("renders the optional prior-knowledge input", async () => {
    listTrailsMock.mockResolvedValueOnce({ trails: [] });
    const TrailsPage = await loadPage();
    render(<TrailsPage />);

    await waitFor(() => {
      expect(
        screen.getByLabelText(/What do you already know about this/i),
      ).toBeInTheDocument();
    });
  });

  test("includes prior_knowledge in the generate request when filled", async () => {
    listTrailsMock.mockResolvedValueOnce({ trails: [] });
    generateTrailMock.mockResolvedValueOnce({ trail: fixtureTrail() });

    const TrailsPage = await loadPage();
    render(<TrailsPage />);

    const user = userEvent.setup();
    await waitFor(() => {
      expect(screen.getByLabelText(/^Topic$/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/^Topic$/i), "Linear Algebra");
    await user.type(screen.getByLabelText(/^Goal$/i), "ML readiness");
    await user.type(
      screen.getByLabelText(/What do you already know about this/i),
      "Comfortable with basic algebra.",
    );
    await user.click(screen.getByRole("button", { name: /Generate Trail/i }));

    await waitFor(() => {
      expect(generateTrailMock).toHaveBeenCalled();
    });
    const body = generateTrailMock.mock.calls[0][1] as TrailGenerateRequest;
    expect(body.prior_knowledge).toBe("Comfortable with basic algebra.");
  });

  test("sends null prior_knowledge when left blank", async () => {
    listTrailsMock.mockResolvedValueOnce({ trails: [] });
    generateTrailMock.mockResolvedValueOnce({ trail: fixtureTrail() });

    const TrailsPage = await loadPage();
    render(<TrailsPage />);

    const user = userEvent.setup();
    await waitFor(() => {
      expect(screen.getByLabelText(/^Topic$/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/^Topic$/i), "Linear Algebra");
    await user.type(screen.getByLabelText(/^Goal$/i), "ML readiness");
    await user.click(screen.getByRole("button", { name: /Generate Trail/i }));

    await waitFor(() => {
      expect(generateTrailMock).toHaveBeenCalled();
    });
    const body = generateTrailMock.mock.calls[0][1] as TrailGenerateRequest;
    expect(body.prior_knowledge).toBeNull();
  });
});

describe("Trails page target-depth selector", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  test("renders title-cased depth options without changing the API value", async () => {
    listTrailsMock.mockResolvedValueOnce({ trails: [] });
    generateTrailMock.mockResolvedValueOnce({ trail: fixtureTrail() });

    const TrailsPage = await loadPage();
    render(<TrailsPage />);

    const user = userEvent.setup();
    await waitFor(() => {
      expect(screen.getByLabelText(/^Topic$/i)).toBeInTheDocument();
    });

    // Title-cased labels are shown to the user.
    const understand = screen.getByRole("radio", { name: "Understand" });
    expect(understand).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Apply" })).toBeInTheDocument();

    await user.type(screen.getByLabelText(/^Topic$/i), "Linear Algebra");
    await user.type(screen.getByLabelText(/^Goal$/i), "ML readiness");
    await user.click(understand);
    await user.click(screen.getByRole("button", { name: /Generate Trail/i }));

    await waitFor(() => {
      expect(generateTrailMock).toHaveBeenCalled();
    });
    const body = generateTrailMock.mock.calls[0][1] as TrailGenerateRequest;
    // Underlying enum value stays lowercase.
    expect(body.target_depth).toBe("understand");
  });
});

describe("Trails page delete action", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  test("exposes an accessible icon delete button and confirms", async () => {
    listTrailsMock.mockResolvedValueOnce({ trails: [fixtureTrail()] });

    const TrailsPage = await loadPage();
    render(<TrailsPage />);

    const user = userEvent.setup();
    const deleteButton = await screen.findByRole("button", {
      name: /Delete Math/i,
    });
    expect(deleteButton).toHaveAttribute("title", "Delete Trail");

    await user.click(deleteButton);
    expect(
      screen.getByRole("button", { name: /^Confirm$/i }),
    ).toBeInTheDocument();
  });
});

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi, beforeEach } from "vitest";

const pushMock = vi.fn();
const replaceMock = vi.fn();
const ensureWorkspaceIdMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
}));

vi.mock("@/lib/workspace", () => ({
  WORKSPACE_STORAGE_KEY: "colearni_workspace_id",
  ensureWorkspaceId: (...args: unknown[]) => ensureWorkspaceIdMock(...args),
}));

import MarketingHome from "@/app/(marketing)/page";

beforeEach(() => {
  pushMock.mockReset();
  replaceMock.mockReset();
  ensureWorkspaceIdMock.mockReset();
  ensureWorkspaceIdMock.mockResolvedValue("ws-1");
  window.localStorage.clear();
});

describe("marketing Home", () => {
  test("redirects returning users with a workspace to /dashboard", async () => {
    window.localStorage.setItem("colearni_workspace_id", "ws-existing");
    render(<MarketingHome />);
    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/dashboard");
    });
  });

  test("first-time visitor sees the hero, no redirect", () => {
    render(<MarketingHome />);
    expect(
      screen.getByRole("heading", { name: /learn anything as a graph/i }),
    ).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  test("Start learning free ensures workspace and enters the app", async () => {
    const user = userEvent.setup();
    render(<MarketingHome />);
    const [cta] = screen.getAllByRole("button", {
      name: /start learning free/i,
    });
    await user.click(cta);
    await waitFor(() => {
      expect(ensureWorkspaceIdMock).toHaveBeenCalledTimes(1);
      expect(pushMock).toHaveBeenCalledWith("/dashboard");
    });
  });
});

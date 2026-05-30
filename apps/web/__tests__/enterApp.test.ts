import { describe, expect, test, vi, beforeEach } from "vitest";

const ensureWorkspaceIdMock = vi.fn();

vi.mock("@/lib/workspace", () => ({
  ensureWorkspaceId: (...args: unknown[]) => ensureWorkspaceIdMock(...args),
}));

import { enterApp } from "@/lib/enter-app";

beforeEach(() => {
  ensureWorkspaceIdMock.mockReset();
});

describe("enterApp", () => {
  test("ensures a workspace then pushes to /dashboard", async () => {
    ensureWorkspaceIdMock.mockResolvedValue("ws-123");
    const push = vi.fn();

    await enterApp({ push });

    expect(ensureWorkspaceIdMock).toHaveBeenCalledTimes(1);
    expect(push).toHaveBeenCalledWith("/dashboard");
  });

  test("does not navigate if workspace creation fails", async () => {
    ensureWorkspaceIdMock.mockRejectedValue(new Error("offline"));
    const push = vi.fn();

    await expect(enterApp({ push })).rejects.toThrow("offline");
    expect(push).not.toHaveBeenCalled();
  });
});

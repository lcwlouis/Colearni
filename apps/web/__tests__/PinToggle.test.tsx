import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { PinToggle } from "@/components/PinToggle";

vi.mock("@/lib/api", () => ({
  pinItem: vi.fn().mockResolvedValue(undefined),
  unpinItem: vi.fn().mockResolvedValue(undefined),
}));

import * as api from "@/lib/api";

describe("PinToggle", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("pins an unpinned item via pinItem", async () => {
    render(
      <PinToggle
        workspaceId="ws-1"
        trailId="trail-1"
        itemType="artifact"
        itemId="artifact-1"
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(api.pinItem).toHaveBeenCalledWith(
      "ws-1",
      "trail-1",
      "artifact",
      "artifact-1",
    );
    expect(api.unpinItem).not.toHaveBeenCalled();
    expect(
      await screen.findByRole("button", { name: "Remove from saved" }),
    ).toBeInTheDocument();
  });

  test("unpins a pinned item and notifies onChange", async () => {
    const onChange = vi.fn();
    render(
      <PinToggle
        workspaceId="ws-1"
        trailId="trail-1"
        itemType="quiz_attempt"
        itemId="attempt-1"
        initialPinned
        onChange={onChange}
      />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Remove from saved" }),
    );

    expect(api.unpinItem).toHaveBeenCalledWith(
      "ws-1",
      "trail-1",
      "quiz_attempt",
      "attempt-1",
    );
    expect(onChange).toHaveBeenCalledWith(false);
  });

  test("reverts to the prior state when the request fails", async () => {
    vi.mocked(api.pinItem).mockRejectedValueOnce(new Error("offline"));

    render(
      <PinToggle
        workspaceId="ws-1"
        trailId="trail-1"
        itemType="artifact"
        itemId="artifact-1"
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(
      await screen.findByRole("button", { name: "Save" }),
    ).toBeInTheDocument();
  });
});

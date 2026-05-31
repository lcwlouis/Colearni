import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: () => "/trails",
}));

vi.mock("@/components/layout/UserProfileChip", () => ({
  default: () => <div>User profile</div>,
}));

import Sidebar from "@/components/layout/Sidebar";

describe("Sidebar", () => {
  test("collapse control is accessible from the brand row and toggles the sidebar", async () => {
    render(<Sidebar />);

    expect(screen.getByText("CoLearni")).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "Collapse sidebar" }),
    );

    expect(
      screen.getByRole("button", { name: "Expand sidebar" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "CoLearni" })).toBeInTheDocument();
    expect(screen.queryByText("User profile")).not.toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "Expand sidebar" }),
    );
    expect(screen.getByText("CoLearni")).toBeInTheDocument();
  });
});

import { describe, expect, it } from "vitest";

import { getSidebarFooterMode } from "@/lib/sidebar/footer-state";

describe("getSidebarFooterMode", () => {
  it("uses collapsed mode only when no workspace form is active", () => {
    expect(
      getSidebarFooterMode({
        collapsed: true,
        isCreatingWorkspace: false,
        renamingWorkspaceId: null,
      }),
    ).toBe("collapsed");
  });

  it("prioritizes the create workspace form over collapsed mode", () => {
    expect(
      getSidebarFooterMode({
        collapsed: true,
        isCreatingWorkspace: true,
        renamingWorkspaceId: null,
      }),
    ).toBe("create-workspace");
  });

  it("prioritizes the rename workspace form over collapsed mode", () => {
    expect(
      getSidebarFooterMode({
        collapsed: true,
        isCreatingWorkspace: false,
        renamingWorkspaceId: "ws_123",
      }),
    ).toBe("rename-workspace");
  });

  it("shows expanded controls when the sidebar is open", () => {
    expect(
      getSidebarFooterMode({
        collapsed: false,
        isCreatingWorkspace: false,
        renamingWorkspaceId: null,
      }),
    ).toBe("expanded");
  });
});

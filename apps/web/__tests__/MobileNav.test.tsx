import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

let pathname = "/dashboard";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
}));

import MobileNav from "@/components/layout/MobileNav";

describe("MobileNav", () => {
  test("uses unique IA destinations and does not render a duplicate chat entry", () => {
    pathname = "/dashboard";
    render(<MobileNav />);

    expect(screen.getByRole("link", { name: "Trails" })).toHaveAttribute(
      "href",
      "/trails",
    );
    expect(screen.getByRole("link", { name: "Quizzes" })).toHaveAttribute(
      "href",
      "/quizzes",
    );
    expect(screen.queryByRole("link", { name: "Chat" })).not.toBeInTheDocument();
  });

  test("highlights only Trails on trail routes, including trail detail pages", () => {
    pathname = "/trails/trail-1";
    render(<MobileNav />);

    const links = screen.getAllByRole("link");
    const activeLinks = links.filter((link) =>
      link.className.includes("text-blue-600"),
    );

    expect(activeLinks).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Trails" })).toHaveClass(
      "text-blue-600",
    );
  });
});

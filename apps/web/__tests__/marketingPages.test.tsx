import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi, beforeEach } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("@/lib/workspace", () => ({
  WORKSPACE_STORAGE_KEY: "colearni_workspace_id",
  ensureWorkspaceId: vi.fn().mockResolvedValue("ws-1"),
}));

import MarketingLayout from "@/app/(marketing)/layout";
import HowItWorksPage from "@/app/(marketing)/how-it-works/page";
import PedagogyPage from "@/app/(marketing)/pedagogy/page";
import PricingPage from "@/app/(marketing)/pricing/page";
import ContactPage from "@/app/(marketing)/contact/page";
import TermsPage from "@/app/(marketing)/terms/page";
import PrivacyPage from "@/app/(marketing)/privacy/page";

beforeEach(() => {
  window.localStorage.clear();
});

describe("marketing pages render without a workspace", () => {
  test("How it works", () => {
    render(<HowItWorksPage />);
    expect(
      screen.getByRole("heading", { name: /one loop, repeated/i }),
    ).toBeInTheDocument();
  });

  test("Pedagogy mentions Bloom's Taxonomy", () => {
    render(<PedagogyPage />);
    expect(screen.getByText(/Bloom's Taxonomy/i)).toBeInTheDocument();
  });

  test("Pricing marks every tier TBC and avoids committing a license", () => {
    render(<PricingPage />);
    expect(screen.getAllByText(/TBC/).length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText(/not MIT-licensed/i)).toBeInTheDocument();
  });

  test("Contact shows an email and no form", () => {
    const { container } = render(<ContactPage />);
    expect(screen.getByText(/hello@colearni\.app/i)).toBeInTheDocument();
    expect(container.querySelector("form")).toBeNull();
  });

  test("Terms is a clearly-marked placeholder", () => {
    render(<TermsPage />);
    expect(
      screen.getByRole("heading", { name: /terms & conditions/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/placeholder/i)).toBeInTheDocument();
  });

  test("Privacy is a clearly-marked placeholder", () => {
    render(<PrivacyPage />);
    expect(
      screen.getByRole("heading", { name: /privacy policy/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/placeholder/i)).toBeInTheDocument();
  });
});

describe("marketing layout + theming", () => {
  test("wraps children in the themed marketing surface", () => {
    const { container } = render(
      <MarketingLayout>
        <p>hello</p>
      </MarketingLayout>,
    );
    expect(container.querySelector(".marketing-surface")).not.toBeNull();
  });

  test("footer links to Terms and Privacy", () => {
    render(
      <MarketingLayout>
        <p>hello</p>
      </MarketingLayout>,
    );
    expect(
      screen.getByRole("link", { name: /terms & conditions/i }),
    ).toHaveAttribute("href", "/terms");
    expect(
      screen.getByRole("link", { name: /privacy policy/i }),
    ).toHaveAttribute("href", "/privacy");
  });

  test("uses the Colearni brand name (not CoLearni)", () => {
    const { container } = render(
      <MarketingLayout>
        <p>hello</p>
      </MarketingLayout>,
    );
    expect(container.textContent).toContain("Colearni");
    expect(container.textContent).not.toContain("CoLearni");
  });

  test("pages render under a dark prefers-color-scheme", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockImplementation((query: string) => ({
        matches: query.includes("dark"),
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    );
    expect(() => render(<PedagogyPage />)).not.toThrow();
    vi.unstubAllGlobals();
  });
});

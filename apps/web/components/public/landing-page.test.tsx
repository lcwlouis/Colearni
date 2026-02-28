import { describe, it, expect } from "vitest";
import { renderToString } from "react-dom/server";
import { LandingPage } from "./landing-page";

describe("LandingPage", () => {
  it("renders the brand title", () => {
    const html = renderToString(<LandingPage />);
    expect(html).toContain("CoLearni");
  });

  it("renders a Sign up CTA linking to /login", () => {
    const html = renderToString(<LandingPage />);
    expect(html).toContain('href="/login"');
    expect(html).toContain("Sign up");
  });

  it("renders a Log in CTA linking to /login", () => {
    const html = renderToString(<LandingPage />);
    expect(html).toContain("Log in");
    // Both CTAs point to /login
    const loginLinks = html.match(/href="\/login"/g);
    expect(loginLinks).not.toBeNull();
    expect(loginLinks!.length).toBeGreaterThanOrEqual(2);
  });

  it("renders feature cards", () => {
    const html = renderToString(<LandingPage />);
    expect(html).toContain("AI Tutor");
    expect(html).toContain("Knowledge Graph");
    expect(html).toContain("Adaptive Quizzes");
  });

  it("wraps content in .public-entry", () => {
    const html = renderToString(<LandingPage />);
    expect(html).toContain('class="public-entry"');
  });
});

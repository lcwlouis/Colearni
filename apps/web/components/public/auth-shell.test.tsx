import { describe, it, expect } from "vitest";
import { renderToString } from "react-dom/server";
import { AuthShell } from "./auth-shell";

describe("AuthShell", () => {
  it("wraps children in .public-entry and .auth-shell", () => {
    const html = renderToString(<AuthShell><p>child</p></AuthShell>);
    expect(html).toContain('class="public-entry"');
    expect(html).toContain('class="auth-shell"');
    expect(html).toContain("child");
  });

  it("renders a link back to home", () => {
    const html = renderToString(<AuthShell><p>x</p></AuthShell>);
    expect(html).toContain('href="/"');
  });

  it("renders the CoLearni brand name", () => {
    const html = renderToString(<AuthShell><p>x</p></AuthShell>);
    expect(html).toContain("CoLearni");
  });
});

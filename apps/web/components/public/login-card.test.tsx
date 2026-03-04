import { describe, it, expect } from "vitest";
import { renderToString } from "react-dom/server";
import { LoginCard, type LoginCardProps } from "./login-card";

function defaults(overrides: Partial<LoginCardProps> = {}): LoginCardProps {
  return {
    step: "email",
    email: "",
    token: "",
    debugToken: null,
    error: null,
    busy: false,
    onEmailChange: () => {},
    onTokenChange: () => {},
    onRequestLink: () => {},
    onVerify: () => {},
    onBackToEmail: () => {},
    ...overrides,
  };
}

describe("LoginCard", () => {
  it("renders the email step by default", () => {
    const html = renderToString(<LoginCard {...defaults()} />);
    expect(html).toContain("Email address");
    expect(html).toContain("Send magic link");
  });

  it("shows the verify step with sent-to message", () => {
    const html = renderToString(
      <LoginCard {...defaults({ step: "verify", email: "test@co.ai" })} />
    );
    expect(html).toContain("test@co.ai");
    expect(html).toContain("Verification token");
    expect(html).toContain("Sign in");
  });

  it("shows dev-token notice when debugToken is set", () => {
    const html = renderToString(
      <LoginCard {...defaults({ step: "verify", debugToken: "tok123" })} />
    );
    expect(html).toContain("Dev mode");
    expect(html).toContain('data-testid="dev-token-notice"');
  });

  it("hides dev-token notice when debugToken is null", () => {
    const html = renderToString(
      <LoginCard {...defaults({ step: "verify", debugToken: null })} />
    );
    expect(html).not.toContain("Dev mode");
  });

  it("renders error message with alert role", () => {
    const html = renderToString(
      <LoginCard {...defaults({ error: "bad token" })} />
    );
    expect(html).toContain("bad token");
    expect(html).toContain('role="alert"');
  });

  it("shows busy state on email step", () => {
    const html = renderToString(
      <LoginCard {...defaults({ busy: true })} />
    );
    expect(html).toContain("Sending…");
    expect(html).toContain("disabled");
  });

  it("shows busy state on verify step", () => {
    const html = renderToString(
      <LoginCard {...defaults({ step: "verify", busy: true })} />
    );
    expect(html).toContain("Verifying…");
    expect(html).toContain("disabled");
  });

  it("renders back button on verify step", () => {
    const html = renderToString(
      <LoginCard {...defaults({ step: "verify" })} />
    );
    expect(html).toContain("Use a different email");
  });
});

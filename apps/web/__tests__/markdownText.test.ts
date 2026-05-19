import { describe, expect, test } from "vitest";

import { preprocessTutorMarkdown } from "@/components/assistant-ui/markdown-text";

describe("preprocessTutorMarkdown", () => {
  test("converts TeX inline and display delimiters for remark-math", () => {
    expect(
      preprocessTutorMarkdown("Use \\(2 \\times x\\) and \\[x^2 + y^2\\]."),
    ).toBe("Use $2 \\times x$ and $$x^2 + y^2$$.");
  });

  test("does not rewrite delimiters inside fenced code blocks", () => {
    const markdown = "```python\nprint('\\\\(x\\\\)')\n```\nThen \\(x\\).";

    expect(preprocessTutorMarkdown(markdown)).toBe(
      "```python\nprint('\\\\(x\\\\)')\n```\nThen $x$.",
    );
  });

  test("does not rewrite delimiters inside inline code spans", () => {
    expect(preprocessTutorMarkdown("Use `\\(x\\)` as text, then \\(x\\)."))
      .toBe("Use `\\(x\\)` as text, then $x$.");
  });
});

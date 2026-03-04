import { describe, it, expect } from "vitest";
import { renderToString } from "react-dom/server";
import { MarkdownContent } from "./markdown-content";

describe("MarkdownContent render contract", () => {
  it("renders fenced code inside pre > code", () => {
    const md = "```js\nconsole.log('hi');\n```";
    const html = renderToString(<MarkdownContent content={md} />);
    expect(html).toContain("<pre>");
    expect(html).toContain("<code");
    // pre must wrap code for fenced blocks
    const preIdx = html.indexOf("<pre>");
    const codeIdx = html.indexOf("<code", preIdx);
    expect(codeIdx).toBeGreaterThan(preIdx);
  });

  it("renders inline code without pre wrapper", () => {
    const md = "Use `console.log` here.";
    const html = renderToString(<MarkdownContent content={md} />);
    expect(html).toContain("<code>");
    expect(html).not.toContain("<pre>");
  });

  it("wraps output in .markdown-content", () => {
    const html = renderToString(<MarkdownContent content="hello" />);
    expect(html).toContain('class="markdown-content');
  });

  it("renders a markdown table as <table>", () => {
    const md = "| A | B |\n|---|---|\n| 1 | 2 |";
    const html = renderToString(<MarkdownContent content={md} />);
    expect(html).toContain("<table>");
    expect(html).toContain("<th>");
    expect(html).toContain("<td>");
  });

  it("renders strikethrough as <del>", () => {
    const md = "~~removed~~";
    const html = renderToString(<MarkdownContent content={md} />);
    expect(html).toContain("<del>");
  });

  it("renders task list checkboxes", () => {
    const md = "- [x] done\n- [ ] todo";
    const html = renderToString(<MarkdownContent content={md} />);
    expect(html).toContain('type="checkbox"');
  });
});

"use client";

import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

import { preprocessTutorMarkdown } from "@/lib/markdown";

const REMARK_PLUGINS = [remarkGfm, remarkMath];
const REHYPE_PLUGINS = [rehypeKatex];

/**
 * Lightweight Markdown + math renderer for quiz prompts and feedback.
 *
 * Reuses the tutor delimiter preprocessing so `$...$`, `\(...\)`, fenced code
 * blocks, and inline code render consistently with the tutor chat. Kept separate
 * from the assistant-ui `MarkdownText` primitive, which requires a message-part
 * context and cannot render arbitrary strings.
 */
export function QuizMarkdown({
  text,
  className,
}: {
  text: string;
  className?: string;
}) {
  return (
    <div className={`quiz-markdown ${className ?? ""}`}>
      <ReactMarkdown
        remarkPlugins={REMARK_PLUGINS}
        rehypePlugins={REHYPE_PLUGINS}
        components={{
          p: ({ className: c, ...props }) => (
            <p className={`mb-2 last:mb-0 ${c ?? ""}`} {...props} />
          ),
          code: ({ className: c, ...props }) => (
            <code
              className={`rounded bg-slate-100 px-1 py-0.5 font-mono text-[0.85em] ${c ?? ""}`}
              {...props}
            />
          ),
          pre: ({ className: c, ...props }) => (
            <pre
              className={`my-2 overflow-x-auto rounded-md bg-slate-900 p-3 text-xs text-slate-100 ${c ?? ""}`}
              {...props}
            />
          ),
        }}
      >
        {preprocessTutorMarkdown(text)}
      </ReactMarkdown>
    </div>
  );
}

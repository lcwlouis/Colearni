"use client";

import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import remarkGfm from "remark-gfm";
import rehypeKatex from "rehype-katex";
import rehypeHighlight from "rehype-highlight";
import "katex/dist/katex.min.css";
import "highlight.js/styles/github-dark.css";

type Props = { content: string; className?: string };

export function MarkdownContent({ content, className }: Props) {
    return (
        <div className={`markdown-content ${className ?? ""}`}>
            <ReactMarkdown remarkPlugins={[remarkMath, remarkGfm]} rehypePlugins={[rehypeKatex, rehypeHighlight]}>
                {content}
            </ReactMarkdown>
        </div>
    );
}

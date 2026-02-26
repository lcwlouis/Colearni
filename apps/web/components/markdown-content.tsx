"use client";

import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

type Props = { content: string; className?: string };

export function MarkdownContent({ content, className }: Props) {
    return (
        <div className={`markdown-content ${className ?? ""}`}>
            <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                {content}
            </ReactMarkdown>
        </div>
    );
}

"use client";

import "@assistant-ui/react-markdown/styles/dot.css";

import {
  type CodeHeaderProps,
  MarkdownTextPrimitive,
  type SyntaxHighlighterProps,
} from "@assistant-ui/react-markdown";
import { CheckIcon, CopyIcon } from "lucide-react";
import { useMemo, useState, type FC } from "react";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

import { MermaidDiagram } from "@/components/assistant-ui/mermaid-diagram";
import { preprocessTutorMarkdown } from "@/lib/markdown";

export { preprocessTutorMarkdown };

const MARKDOWN_REHYPE_PLUGINS = [rehypeKatex];
const MARKDOWN_REMARK_PLUGINS = [remarkGfm, remarkMath];

export function MarkdownText() {
  const components = useMemo(
    () => ({
      h1: ({ className, ...props }: React.ComponentProps<"h1">) => (
        <h1
          className={join("mb-2 text-base font-semibold first:mt-0", className)}
          {...props}
        />
      ),
      h2: ({ className, ...props }: React.ComponentProps<"h2">) => (
        <h2
          className={join(
            "mb-1.5 mt-3 text-sm font-semibold first:mt-0",
            className,
          )}
          {...props}
        />
      ),
      h3: ({ className, ...props }: React.ComponentProps<"h3">) => (
        <h3
          className={join(
            "mb-1 mt-2.5 text-sm font-semibold first:mt-0",
            className,
          )}
          {...props}
        />
      ),
      p: ({ className, ...props }: React.ComponentProps<"p">) => (
        <p
          className={join("my-2 leading-6 first:mt-0 last:mb-0", className)}
          {...props}
        />
      ),
      a: ({ className, ...props }: React.ComponentProps<"a">) => (
        <a
          className={join(
            "text-blue-700 underline underline-offset-2 hover:text-blue-800",
            className,
          )}
          target="_blank"
          rel="noreferrer"
          {...props}
        />
      ),
      blockquote: ({
        className,
        ...props
      }: React.ComponentProps<"blockquote">) => (
        <blockquote
          className={join(
            "my-2 border-l-2 border-slate-300 pl-3 italic text-slate-600",
            className,
          )}
          {...props}
        />
      ),
      ul: ({ className, ...props }: React.ComponentProps<"ul">) => (
        <ul
          className={join("my-2 ml-5 list-disc [&>li]:mt-1", className)}
          {...props}
        />
      ),
      ol: ({ className, ...props }: React.ComponentProps<"ol">) => (
        <ol
          className={join("my-2 ml-5 list-decimal [&>li]:mt-1", className)}
          {...props}
        />
      ),
      li: ({ className, ...props }: React.ComponentProps<"li">) => (
        <li className={join("leading-6", className)} {...props} />
      ),
      table: ({ className, ...props }: React.ComponentProps<"table">) => (
        <div className="my-2 overflow-x-auto">
          <table
            className={join(
              "w-full border-separate border-spacing-0 text-sm",
              className,
            )}
            {...props}
          />
        </div>
      ),
      th: ({ className, ...props }: React.ComponentProps<"th">) => (
        <th
          className={join(
            "bg-slate-100 px-2 py-1 text-left font-medium",
            className,
          )}
          {...props}
        />
      ),
      td: ({ className, ...props }: React.ComponentProps<"td">) => (
        <td
          className={join(
            "border border-slate-200 px-2 py-1 align-top",
            className,
          )}
          {...props}
        />
      ),
      pre: ({ className, ...props }: React.ComponentProps<"pre">) => (
        <pre
          className={join(
            "overflow-x-auto rounded-b-lg border border-t-0 border-slate-200 bg-slate-950 p-4 text-xs leading-6 text-slate-100",
            className,
          )}
          {...props}
        />
      ),
      code: ({ className, ...props }: React.ComponentProps<"code">) => {
        const codeClass = String(className ?? "");
        const block = codeClass.includes("language-");

        return (
          <code
            className={join(
              block
                ? "block whitespace-pre font-mono text-[0.95em] text-inherit"
                : "rounded bg-slate-100 px-1 py-0.5 font-mono text-[0.9em] text-slate-800",
              className,
            )}
            {...props}
          />
        );
      },
      SyntaxHighlighter: CodeBlockContent,
      CodeHeader,
    }),
    [],
  );

  return (
    <MarkdownTextPrimitive
      className="aui-md max-w-none text-sm text-inherit"
      components={components}
      componentsByLanguage={{
        mermaid: {
          SyntaxHighlighter: MermaidDiagram,
        },
      }}
      preprocess={preprocessTutorMarkdown}
      rehypePlugins={MARKDOWN_REHYPE_PLUGINS}
      remarkPlugins={MARKDOWN_REMARK_PLUGINS}
    />
  );
}

const CodeBlockContent: FC<SyntaxHighlighterProps> = ({
  code,
  components: { Pre },
}) => (
  <Pre>
    <code className="block whitespace-pre font-mono text-[0.95em] text-slate-100">
      {code.replace(/\n$/, "")}
    </code>
  </Pre>
);

const CodeHeader: FC<CodeHeaderProps> = ({ language, code }) => {
  const { isCopied, copyToClipboard } = useCopyToClipboard();

  return (
    <div className="mt-2.5 flex items-center justify-between rounded-t-lg border border-b-0 border-slate-200 bg-slate-100 px-3 py-1.5 text-xs">
      <span className="font-medium lowercase text-slate-500">
        {language ?? "text"}
      </span>
      <button
        type="button"
        aria-label="Copy code"
        onClick={() => copyToClipboard(code)}
        className="rounded p-1 text-slate-500 transition-colors hover:bg-slate-200 hover:text-slate-900"
      >
        {isCopied ? (
          <CheckIcon className="size-3.5" />
        ) : (
          <CopyIcon className="size-3.5" />
        )}
      </button>
    </div>
  );
};

function useCopyToClipboard(copiedDuration = 3000) {
  const [isCopied, setIsCopied] = useState(false);

  return {
    isCopied,
    copyToClipboard(value: string) {
      if (
        !value ||
        typeof navigator === "undefined" ||
        !navigator.clipboard ||
        isCopied
      ) {
        return;
      }

      void navigator.clipboard.writeText(value).then(() => {
        setIsCopied(true);
        window.setTimeout(() => setIsCopied(false), copiedDuration);
      });
    },
  };
}

function join(...parts: Array<string | undefined>) {
  return parts.filter(Boolean).join(" ");
}

"use client";

import { FileTextIcon } from "lucide-react";
import { useState } from "react";

function extractDomain(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function defaultFaviconUrl(domain: string) {
  return `https://icons.duckduckgo.com/ip3/${domain}.ico`;
}

export function SourceChip({
  href,
  title,
  className,
}: {
  href: string;
  title: string;
  className?: string;
}) {
  const domain = extractDomain(href);
  const favicon = defaultFaviconUrl(domain);
  const [failed, setFailed] = useState(false);

  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className={join(
        "inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 transition-colors hover:border-blue-300 hover:text-blue-700",
        className,
      )}
    >
      {failed ? (
        <span className="flex size-3 shrink-0 items-center justify-center rounded-sm bg-slate-200 text-[10px] font-semibold text-slate-700">
          {domain.charAt(0).toUpperCase() || <FileTextIcon className="size-3" />}
        </span>
      ) : (
        <img
          src={favicon}
          alt=""
          className="size-3 shrink-0 rounded-sm"
          onError={() => setFailed(true)}
        />
      )}
      <span className="max-w-40 truncate">{title}</span>
    </a>
  );
}

export function join(...parts: Array<string | undefined>) {
  return parts.filter(Boolean).join(" ");
}

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { enterApp } from "@/lib/enter-app";

export function EnterAppButton({
  children = "Log in",
  className = "",
}: {
  children?: React.ReactNode;
  className?: string;
}) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);

  async function handleClick() {
    setPending(true);
    setError(false);
    try {
      await enterApp(router);
    } catch {
      setError(true);
      setPending(false);
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={pending}
      className={className}
    >
      {pending ? "Opening…" : error ? "Try again" : children}
    </button>
  );
}

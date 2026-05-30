"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { WORKSPACE_STORAGE_KEY } from "@/lib/workspace";

export function RedirectGate() {
  const router = useRouter();

  useEffect(() => {
    if (typeof window === "undefined") return;
    const existing = window.localStorage.getItem(WORKSPACE_STORAGE_KEY);
    if (existing) {
      router.replace("/dashboard");
    }
  }, [router]);

  return null;
}

"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { LandingPage } from "@/components/public/landing-page";

export default function HomePage() {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && user) {
      router.replace("/tutor");
    }
  }, [user, isLoading, router]);

  if (isLoading) {
    return (
      <div className="public-entry" style={{ justifyContent: "center", minHeight: "100vh" }}>
        <p style={{ color: "var(--muted)" }}>Loading…</p>
      </div>
    );
  }

  if (user) return null;

  return <LandingPage />;
}

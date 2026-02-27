"use client";

import { AuthProvider } from "@/lib/auth";
import { ChatSessionProvider } from "@/lib/tutor/chat-session-context";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <ChatSessionProvider>{children}</ChatSessionProvider>
    </AuthProvider>
  );
}

"use client";

import { GlobalSidebar } from "@/components/global-sidebar";
import { ChatSessionProvider } from "@/lib/tutor/chat-session-context";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <ChatSessionProvider>
      <div className="shell">
        <GlobalSidebar />
        <main className="content">{children}</main>
      </div>
    </ChatSessionProvider>
  );
}

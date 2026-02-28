import { GlobalSidebar } from "@/components/global-sidebar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="shell">
      <GlobalSidebar />
      <main className="content">{children}</main>
    </div>
  );
}

import MobileNav from "@/components/layout/MobileNav";
import Sidebar from "@/components/layout/Sidebar";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-[100svh] overflow-hidden md:h-screen">
      <Sidebar />
      <main className="flex flex-1 flex-col overflow-auto pb-[calc(4rem+env(safe-area-inset-bottom))] md:pb-0">
        {children}
      </main>
      <MobileNav />
    </div>
  );
}

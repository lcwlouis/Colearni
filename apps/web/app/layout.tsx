import type { Metadata } from "next";
import { GlobalSidebar } from "@/components/global-sidebar";
import { Providers } from "@/components/providers";
import "./globals.css";

export const metadata: Metadata = { title: "CoLearni", description: "Learning-first tutor workspace" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <div className="shell">
            <GlobalSidebar />
            <main className="content">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import { AppNav } from "@/components/app-nav";
import { ThemeToggle } from "@/components/theme-toggle";
import { HealthDot } from "@/components/health-dot";
import "./globals.css";

export const metadata: Metadata = { title: "CoLearni", description: "Learning-first tutor workspace" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <header className="topbar">
            <div className="topbar-left">
              <p className="brand">CoLearni</p>
              <HealthDot />
            </div>
            <div className="topbar-right">
              <AppNav />
              <ThemeToggle />
            </div>
          </header>
          <main className="content">{children}</main>
        </div>
      </body>
    </html>
  );
}

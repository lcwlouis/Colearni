import type { Metadata } from "next";
import { AppNav } from "@/components/app-nav";
import "./globals.css";

export const metadata: Metadata = { title: "Colearni", description: "Learning-first tutor workspace" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <header className="topbar"><p className="brand">Colearni</p><AppNav /></header>
          <main className="content">{children}</main>
        </div>
      </body>
    </html>
  );
}

"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bookmark,
  ChartNoAxesColumn,
  Compass,
  Home,
  LayoutDashboard,
  LibraryBig,
  Map,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
} from "lucide-react";

import UserProfileChip from "./UserProfileChip";

type NavItem = {
  label: string;
  href: string;
  icon: React.ElementType;
  matchPrefix?: string;
};

const NAV_ITEMS: NavItem[] = [
  {
    label: "Home",
    href: "/dashboard",
    icon: Home,
  },
  {
    label: "Trails",
    href: "/trails",
    icon: Map,
    matchPrefix: "/trails",
  },
  {
    label: "Explore",
    href: "/explore",
    icon: Compass,
  },
  {
    label: "Quizzes",
    href: "/quizzes",
    icon: LibraryBig,
  },
  {
    label: "Progress",
    href: "/progress",
    icon: ChartNoAxesColumn,
  },
  {
    label: "Sources",
    href: "/sources",
    icon: LayoutDashboard,
  },
  {
    label: "Bookmarks",
    href: "/bookmarks",
    icon: Bookmark,
  },
];

function NavLink({
  item,
  pathname,
  collapsed,
}: {
  item: NavItem;
  pathname: string;
  collapsed: boolean;
}) {
  const isActive = item.matchPrefix
    ? pathname.startsWith(item.matchPrefix)
    : pathname === item.href;

  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      title={collapsed ? item.label : undefined}
      className={`flex rounded-xl text-sm font-medium transition-colors ${
        collapsed
          ? "mx-auto h-10 w-10 items-center justify-center px-0 py-0"
          : "items-center gap-3 px-3 py-2"
      } ${
        isActive
          ? "bg-blue-50 text-blue-700"
          : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
      }`}
    >
      <Icon
        className={`h-4 w-4 shrink-0 ${isActive ? "text-blue-600" : "text-slate-400"}`}
      />
      {collapsed ? (
        <span className="sr-only">{item.label}</span>
      ) : (
        <span className="truncate">{item.label}</span>
      )}
    </Link>
  );
}

export default function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  // Determine the active trail so Home and Trails both get correct states.
  const isHome = pathname === "/dashboard";
  const isTrail = pathname.startsWith("/trails");

  // Override: if on a specific trail page, keep the Trails section active.
  const resolvedPathname = isHome
    ? "/dashboard"
    : isTrail
      ? "/trails"
      : pathname;

  return (
    <aside
      className={`hidden h-full shrink-0 flex-col border-r border-slate-200 bg-white transition-[width] duration-200 md:flex ${collapsed ? "w-16" : "w-56"}`}
    >
      {/* Logo / collapse affordance */}
      <div
        className={`group shrink-0 border-b border-slate-100 ${collapsed ? "px-2 py-3" : "h-14 px-3"}`}
      >
        {collapsed ? (
          <div className="flex flex-col items-center gap-2">
            <Link
              href="/dashboard"
              title="Home"
              aria-label="CoLearni"
              className="flex h-9 w-9 items-center justify-center rounded-xl font-semibold text-slate-900 transition-colors hover:bg-slate-100"
            >
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-blue-600 text-xs font-bold text-white">
                C
              </span>
              <span className="sr-only">CoLearni</span>
            </Link>
            <button
              type="button"
              onClick={() => setCollapsed((value) => !value)}
              className="grid size-7 place-items-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-200"
              aria-label="Expand sidebar"
              title="Expand sidebar"
            >
              <PanelLeftOpen className="h-4 w-4" />
            </button>
          </div>
        ) : (
          <div className="flex h-full items-center justify-between gap-2">
            <Link
              href="/dashboard"
              className="flex min-w-0 items-center gap-2 font-semibold text-slate-900"
            >
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-blue-600 text-xs font-bold text-white">
                C
              </span>
              <span>CoLearni</span>
            </Link>
            <button
              type="button"
              onClick={() => setCollapsed((value) => !value)}
              className="grid size-8 shrink-0 place-items-center rounded-md text-slate-500 opacity-0 transition hover:bg-slate-100 hover:text-slate-900 group-hover:opacity-100 group-focus-within:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-200"
              aria-label="Collapse sidebar"
              title="Collapse sidebar"
            >
              <PanelLeftClose className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav
        // Collapsed: use `no-scrollbar` (no reserved gutter) so the icon hit
        // areas stay centered on the same rail axis as the logo, expand, and
        // settings buttons. `app-scrollbar` reserves a stable gutter that would
        // pull the centered items off-axis. Expanded labels are left-aligned,
        // so the stable gutter there only prevents layout shift.
        className={`flex-1 overflow-y-auto ${collapsed ? "px-2 py-3 no-scrollbar" : "px-2 py-2 app-scrollbar"}`}
      >
        <div className={`flex flex-col ${collapsed ? "gap-1.5" : "gap-0.5"}`}>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={`${item.label}-${item.href}`}
              item={item}
              pathname={resolvedPathname}
              collapsed={collapsed}
            />
          ))}
        </div>
      </nav>

      {/* Bottom: Settings + User */}
      <div className="shrink-0 border-t border-slate-100">
        <div className={collapsed ? "px-2 py-3" : "px-2 py-2"}>
          <Link
            href="/settings"
            title={collapsed ? "Settings" : undefined}
            className={`flex rounded-xl text-sm font-medium transition-colors ${
              collapsed
                ? "mx-auto h-10 w-10 items-center justify-center px-0 py-0"
                : "items-center gap-3 px-3 py-2"
            } ${
              pathname === "/settings"
                ? "bg-blue-50 text-blue-700"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            }`}
          >
            <Settings
              className={`h-4 w-4 shrink-0 ${pathname === "/settings" ? "text-blue-600" : "text-slate-400"}`}
            />
            {collapsed ? <span className="sr-only">Settings</span> : "Settings"}
          </Link>
        </div>
        {collapsed ? null : (
          <div className="border-t border-slate-100">
            <UserProfileChip />
          </div>
        )}
      </div>
    </aside>
  );
}
